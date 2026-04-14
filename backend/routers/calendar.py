from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query

from backend.db.timescale_client import db
from backend.services.corporate_actions.buyback_tracker import buyback_tracker
from backend.services.corporate_actions.earnings_calendar import earnings_calendar
from backend.services.corporate_actions.result_analyzer import result_analyzer

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.get("/upcoming", response_model=dict)
async def get_upcoming_actions(days: int = Query(default=7, ge=1, le=30)):
    """Get upcoming corporate actions."""
    rows = await db.get_upcoming_actions(days=days)

    actions = []
    for r in rows:
        details = r.get("details")
        if isinstance(details, str):
            import json
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
        actions = _generate_mock_calendar()

    return {
        "data": actions,
        "meta": {"timestamp": datetime.utcnow().isoformat(), "version": "1.0"},
    }


@router.get("/alerts", response_model=dict)
async def get_pre_event_alerts():
    """Get pre-event alerts for today and tomorrow."""
    alerts = await earnings_calendar.generate_pre_event_alerts()

    if not alerts:
        # Mock alerts
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
    analysis = await result_analyzer.analyze(ticker.upper())

    return {
        "data": analysis,
        "meta": {"timestamp": datetime.utcnow().isoformat(), "version": "1.0"},
    }


@router.get("/buybacks", response_model=dict)
async def get_buyback_opportunities():
    """Get active buyback opportunities."""
    opportunities = await buyback_tracker.check_buyback_opportunities()

    return {
        "data": opportunities,
        "meta": {"timestamp": datetime.utcnow().isoformat(), "version": "1.0"},
    }


def _generate_mock_calendar():
    import random
    from datetime import timedelta

    tickers = ["SUNPHARMA", "RELIANCE", "ONGC", "DRREDDY", "NTPC", "CIPLA", "PAGEIND"]
    types = ["RESULT", "DIVIDEND", "BONUS", "BUYBACK", "AGM"]
    actions = []
    for i in range(8):
        dt = datetime.utcnow().date() + timedelta(days=random.randint(0, 7))
        actions.append({
            "id": f"mock-ca-{i}",
            "ticker": random.choice(tickers),
            "exchange": "NSE",
            "action_type": random.choice(types),
            "event_date": str(dt),
            "record_date": None,
            "ex_date": None,
            "details": {},
            "momentum_label": random.choice(["BUY", "NEUTRAL", "SELL", None]),
        })
    return sorted(actions, key=lambda x: x["event_date"])
