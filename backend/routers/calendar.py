from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Query

from backend.db.timescale_client import db
from backend.services.scrapers.nse_scraper import fetch_corporate_actions

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.get("/upcoming", response_model=dict)
async def get_upcoming_actions(days: int = Query(default=7, ge=1, le=30)):
    """Get upcoming corporate actions — tries real NSE data first."""

    # Try real NSE corporate actions first (with timeout)
    try:
        import asyncio
        nse_actions = await asyncio.wait_for(fetch_corporate_actions(days=days), timeout=10)
        if nse_actions:
            actions = []
            for i, item in enumerate(nse_actions):
                actions.append({
                    "id": f"nse-ca-{i}",
                    "ticker": item.get("symbol", ""),
                    "exchange": "NSE",
                    "action_type": _classify_action(item.get("subject", "")),
                    "event_date": item.get("exDate", ""),
                    "record_date": item.get("recordDate"),
                    "ex_date": item.get("exDate"),
                    "details": {"subject": item.get("subject", ""), "company": item.get("company", "")},
                    "momentum_label": None,
                })
            return {
                "data": actions,
                "meta": {"timestamp": datetime.utcnow().isoformat(), "version": "1.0"},
            }
    except Exception:
        pass

    # Fallback: DB
    rows = await db.get_upcoming_actions(days=days)
    actions = []
    for r in rows:
        details = r.get("details")
        if isinstance(details, str):
            try:
                details = json.loads(details)
            except Exception:
                details = {}

        actions.append({
            "id": str(r["id"]),
            "ticker": r["ticker"],
            "exchange": r.get("exchange", "NSE"),
            "action_type": r["action_type"],
            "event_date": str(r["event_date"]),
            "record_date": str(r["record_date"]) if r.get("record_date") else None,
            "ex_date": str(r["ex_date"]) if r.get("ex_date") else None,
            "details": details,
            "momentum_label": r.get("momentum_label"),
        })

    if not actions:
        actions = _generate_mock_calendar(days)

    return {
        "data": actions,
        "meta": {"timestamp": datetime.utcnow().isoformat(), "version": "1.0"},
    }


@router.get("/full", response_model=dict)
async def get_full_calendar(days: int = Query(default=30, ge=1, le=90)):
    """Get full corporate calendar for next N days from NSE."""
    try:
        import asyncio
        nse_actions = await asyncio.wait_for(fetch_corporate_actions(days=days), timeout=10)
        if nse_actions:
            actions = []
            for i, item in enumerate(nse_actions):
                actions.append({
                    "id": f"nse-ca-full-{i}",
                    "ticker": item.get("symbol", ""),
                    "company": item.get("company", ""),
                    "subject": item.get("subject", ""),
                    "action_type": _classify_action(item.get("subject", "")),
                    "ex_date": item.get("exDate", ""),
                    "record_date": item.get("recordDate", ""),
                    "bc_start_date": item.get("bcStartDate", ""),
                    "bc_end_date": item.get("bcEndDate", ""),
                })
            return {
                "data": actions,
                "meta": {"timestamp": datetime.utcnow().isoformat(), "version": "1.0"},
            }
    except Exception:
        pass

    # Fallback mock
    return {
        "data": _generate_mock_calendar(days),
        "meta": {"timestamp": datetime.utcnow().isoformat(), "version": "1.0", "stale": True},
    }


@router.get("/alerts", response_model=dict)
async def get_pre_event_alerts():
    """Get pre-event alerts for today and tomorrow."""
    from backend.services.corporate_actions.earnings_calendar import earnings_calendar
    alerts = await earnings_calendar.generate_pre_event_alerts()

    if not alerts:
        from backend.models.signal_models import PreEventAlert
        alerts = [
            PreEventAlert(
                ticker="SUNPHARMA",
                event_type="RESULT",
                event_date=str(datetime.utcnow().date()),
                days_until=1,
                alert_severity="HIGH",
                context="Q3 FY25 quarterly result tomorrow",
            ),
        ]

    return {
        "data": [a.model_dump() for a in alerts],
        "meta": {"timestamp": datetime.utcnow().isoformat(), "version": "1.0"},
    }


@router.get("/results/{ticker}", response_model=dict)
async def get_result_analysis(ticker: str):
    """Get latest result analysis for a ticker."""
    from backend.services.corporate_actions.result_analyzer import result_analyzer
    analysis = await result_analyzer.analyze(ticker.upper())

    return {
        "data": analysis,
        "meta": {"timestamp": datetime.utcnow().isoformat(), "version": "1.0"},
    }


@router.get("/buybacks", response_model=dict)
async def get_buyback_opportunities():
    """Get active buyback opportunities."""
    from backend.services.corporate_actions.buyback_tracker import buyback_tracker
    opportunities = await buyback_tracker.check_buyback_opportunities()

    return {
        "data": opportunities,
        "meta": {"timestamp": datetime.utcnow().isoformat(), "version": "1.0"},
    }


def _classify_action(subject: str) -> str:
    """Classify corporate action type from description text."""
    subject_lower = subject.lower()
    if "dividend" in subject_lower:
        return "DIVIDEND"
    elif "bonus" in subject_lower:
        return "BONUS"
    elif "split" in subject_lower:
        return "SPLIT"
    elif "buyback" in subject_lower:
        return "BUYBACK"
    elif "right" in subject_lower:
        return "RIGHTS"
    elif "agm" in subject_lower or "annual general" in subject_lower:
        return "AGM"
    elif "result" in subject_lower or "quarterly" in subject_lower:
        return "RESULT"
    return "OTHER"


def _generate_mock_calendar(days=7):
    import random
    from datetime import timedelta

    tickers = ["SUNPHARMA", "RELIANCE", "ONGC", "DRREDDY", "NTPC", "CIPLA", "PAGEIND",
               "TCS", "INFY", "HDFCBANK", "SBIN", "ITC"]
    types = ["RESULT", "DIVIDEND", "BONUS", "BUYBACK", "AGM"]
    subjects = {
        "RESULT": "Quarterly Results",
        "DIVIDEND": "Interim Dividend - Rs 5 Per Share",
        "BONUS": "Bonus Issue 1:1",
        "BUYBACK": "Buyback of Equity Shares",
        "AGM": "Annual General Meeting",
    }
    actions = []
    for i in range(min(days, 12)):
        dt = datetime.utcnow().date() + timedelta(days=random.randint(0, days))
        action_type = random.choice(types)
        actions.append({
            "id": f"mock-ca-{i}",
            "ticker": random.choice(tickers),
            "exchange": "NSE",
            "action_type": action_type,
            "event_date": str(dt),
            "record_date": None,
            "ex_date": str(dt),
            "details": {"subject": subjects.get(action_type, "")},
            "momentum_label": random.choice(["BUY", "NEUTRAL", "SELL", None]),
            "company": "",
            "subject": subjects.get(action_type, ""),
        })
    return sorted(actions, key=lambda x: x["event_date"])
