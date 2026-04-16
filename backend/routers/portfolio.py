from __future__ import annotations

import json
from datetime import datetime
from typing import List

from fastapi import APIRouter

from backend.db.timescale_client import db
from backend.models.portfolio_models import PortfolioInput
from backend.services.risk.stress_tester import stress_tester
from backend.services.risk.vulnerability_mapper import vulnerability_mapper

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.post("/analyze", response_model=dict)
async def analyze_portfolio(portfolio: PortfolioInput):
    """Analyse portfolio vulnerability across 5 risk dimensions."""
    # Load watchlist metadata
    watchlist_meta = {}
    try:
        with open("watchlist.json", "r") as f:
            wl = json.load(f)
            for stock in wl.get("stocks", []):
                watchlist_meta[stock["ticker"]] = stock
    except Exception:
        pass

    # Save holdings to DB
    for h in portfolio.holdings:
        await db.upsert_holding(
            user_id=portfolio.user_id,
            ticker=h.ticker,
            quantity=h.quantity,
            avg_cost=h.avg_cost,
        )

    # Run vulnerability analysis
    holdings_dicts = [h.model_dump() for h in portfolio.holdings]
    analysis = await vulnerability_mapper.analyze_portfolio(
        holdings_dicts, watchlist_meta
    )

    # Update DB with vulnerability scores
    for ticker, vuln in analysis.items():
        await db.update_vulnerability(
            user_id=portfolio.user_id,
            ticker=ticker,
            score=vuln.overall_vulnerability_score,
            breakdown=vuln.model_dump(),
        )

    return {
        "data": {
            "holdings_analysis": {
                ticker: vuln.model_dump() for ticker, vuln in analysis.items()
            }
        },
        "meta": {"timestamp": datetime.utcnow().isoformat(), "version": "1.0"},
    }


@router.get("/{user_id}", response_model=dict)
async def get_portfolio(user_id: str):
    """Get saved portfolio holdings for a user."""
    rows = await db.get_portfolio(user_id)

    holdings = []
    for r in rows:
        breakdown = r.get("vulnerability_breakdown")
        if isinstance(breakdown, str):
            try:
                breakdown = json.loads(breakdown)
            except Exception:
                breakdown = None

        holdings.append({
            "ticker": r["ticker"],
            "quantity": r["quantity"],
            "avg_cost": r["avg_cost"],
            "vulnerability_score": r.get("vulnerability_score"),
            "vulnerability_breakdown": breakdown,
            "last_updated": str(r["last_updated"]) if r.get("last_updated") else None,
        })

    return {
        "data": holdings,
        "meta": {"timestamp": datetime.utcnow().isoformat(), "version": "1.0"},
    }


@router.post("/stress-test", response_model=dict)
async def run_stress_test(portfolio: PortfolioInput):
    """Run stress scenarios against portfolio."""
    watchlist_meta = {}
    try:
        with open("watchlist.json", "r") as f:
            wl = json.load(f)
            for stock in wl.get("stocks", []):
                watchlist_meta[stock["ticker"]] = stock
    except Exception:
        pass

    holdings_dicts = [h.model_dump() for h in portfolio.holdings]
    result = stress_tester.run_stress_test(holdings_dicts, watchlist_meta)

    return {
        "data": result.model_dump(),
        "meta": {"timestamp": datetime.utcnow().isoformat(), "version": "1.0"},
    }


@router.post("/current-prices", response_model=dict)
async def get_current_prices(tickers: List[str]):
    """Fetch current prices for a list of tickers from NSE."""
    from backend.services.scrapers.nse_scraper import fetch_stock_quote

    prices = {}
    for ticker in tickers:
        quote = await fetch_stock_quote(ticker.upper().strip())
        if quote:
            prices[ticker.upper()] = {
                "lastPrice": quote.get("lastPrice", 0),
                "change": quote.get("change", 0),
                "pChange": quote.get("pChange", 0),
                "dayHigh": quote.get("dayHigh", 0),
                "dayLow": quote.get("dayLow", 0),
                "previousClose": quote.get("previousClose", 0),
            }
        else:
            prices[ticker.upper()] = None

    return {
        "data": prices,
        "meta": {"timestamp": datetime.utcnow().isoformat(), "version": "1.0"},
    }


@router.post("/optimize", response_model=dict)
async def optimize_portfolio(portfolio: PortfolioInput):
    """LLM-based portfolio optimization suggestions."""
    from backend.services.risk.portfolio_optimizer import optimize_portfolio as run_optimize
    from backend.services.scrapers.nse_scraper import fetch_stock_quote

    holdings = []
    for h in portfolio.holdings:
        hd = h.model_dump()
        # Try to get current price
        quote = await fetch_stock_quote(h.ticker)
        if quote:
            hd["current_price"] = quote.get("lastPrice", 0)
        holdings.append(hd)

    result = await run_optimize(holdings)

    return {
        "data": result,
        "meta": {"timestamp": datetime.utcnow().isoformat(), "version": "1.0"},
    }


@router.post("/risk-analysis", response_model=dict)
async def risk_analysis(portfolio: PortfolioInput):
    """LLM + FinBERT risk analysis of portfolio."""
    from backend.services.risk.portfolio_optimizer import analyze_portfolio_risk

    holdings_dicts = [h.model_dump() for h in portfolio.holdings]
    result = await analyze_portfolio_risk(holdings_dicts)

    return {
        "data": result,
        "meta": {"timestamp": datetime.utcnow().isoformat(), "version": "1.0"},
    }
