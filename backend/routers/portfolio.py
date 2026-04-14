from __future__ import annotations

import json
from datetime import datetime

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
