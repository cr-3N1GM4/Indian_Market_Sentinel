from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query

from backend.db.timescale_client import db

router = APIRouter(prefix="/signals", tags=["signals"])


def _signal_to_dict(row) -> dict:
    """Convert DB row to signal response dict."""
    evidence = row.get("supporting_evidence")
    if isinstance(evidence, str):
        try:
            evidence = json.loads(evidence)
        except Exception:
            evidence = [evidence]

    return {
        "signal_id": str(row["id"]),
        "timestamp": str(row["time"]),
        "ticker": row["ticker"],
        "exchange": row.get("exchange", "NSE"),
        "sector": row.get("sector"),
        "pattern": row["pattern"],
        "signal_type": row["signal_type"],
        "confidence": row["confidence"],
        "regime": row.get("regime"),
        "crss": row.get("crss"),
        "ics": row.get("ics"),
        "fii_net_5d_crores": row.get("fii_net_5d_crores"),
        "supporting_evidence": evidence or [],
        "is_resolved": row.get("is_resolved", False),
        "resolved_at": str(row["resolved_at"]) if row.get("resolved_at") else None,
        "actual_return": row.get("actual_return"),
    }


@router.get("/active", response_model=dict)
async def get_active_signals():
    """Get all unresolved alpha signals."""
    rows = await db.get_active_signals()

    if rows:
        signals = [_signal_to_dict(r) for r in rows]
    else:
        # Mock signals
        signals = _generate_mock_signals()

    return {
        "data": signals,
        "meta": {"timestamp": datetime.utcnow().isoformat(), "version": "1.0"},
    }


@router.get("/history", response_model=dict)
async def get_signals_history(
    ticker: Optional[str] = Query(default=None),
    sector: Optional[str] = Query(default=None),
    confidence: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """Get paginated signal history with filters."""
    rows = await db.get_signals_history(
        ticker=ticker, sector=sector, confidence=confidence,
        limit=limit, offset=offset,
    )

    if rows:
        signals = [_signal_to_dict(r) for r in rows]
    else:
        signals = _generate_mock_signals()[:limit]

    return {
        "data": signals,
        "meta": {
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0",
            "limit": limit,
            "offset": offset,
        },
    }


@router.get("/{signal_id}", response_model=dict)
async def get_signal_detail(signal_id: str):
    """Get full detail for a single signal."""
    row = await db.get_signal_by_id(signal_id)

    if row:
        return {
            "data": _signal_to_dict(row),
            "meta": {"timestamp": datetime.utcnow().isoformat(), "version": "1.0"},
        }

    return {
        "data": None,
        "meta": {"timestamp": datetime.utcnow().isoformat(), "version": "1.0", "error": "not_found"},
    }


def _generate_mock_signals():
    import random
    patterns = [
        ("RETAIL_BUBBLE", "MEAN_REVERSION_SHORT", "HIGH"),
        ("SMART_MONEY_ACCUMULATION", "MOMENTUM_LONG", "MEDIUM_HIGH"),
        ("REGIME_CONFIRMED_BREAKOUT", "TREND_FOLLOWING_LONG", "HIGH"),
        ("NEWS_INSTITUTIONAL_DIVERGENCE", "DISTRIBUTION_WARNING", "MEDIUM"),
        ("SUPPLY_CHAIN_STRESS", "SECTOR_RISK_FLAG", "HIGH"),
    ]
    tickers = ["SUNPHARMA", "RELIANCE", "ONGC", "DRREDDY", "NTPC", "CIPLA", "PAGEIND"]
    sectors = {"SUNPHARMA": "Pharma", "RELIANCE": "Energy", "ONGC": "Energy",
               "DRREDDY": "Pharma", "NTPC": "Energy", "CIPLA": "Pharma", "PAGEIND": "Textile"}
    signals = []
    for i in range(8):
        ticker = random.choice(tickers)
        pattern, sig_type, conf = random.choice(patterns)
        signals.append({
            "signal_id": f"mock-{i:04d}",
            "timestamp": datetime.utcnow().isoformat(),
            "ticker": ticker,
            "exchange": "NSE",
            "sector": sectors.get(ticker, "Other"),
            "pattern": pattern,
            "signal_type": sig_type,
            "confidence": conf,
            "regime": random.choice(["hawkish_pause", "dovish_easing", "neutral_watchful"]),
            "crss": round(random.uniform(-0.8, 0.8), 2),
            "ics": round(random.uniform(-0.6, 0.6), 2),
            "fii_net_5d_crores": round(random.uniform(-500, 500), 1),
            "supporting_evidence": [
                f"CRSS indicates {random.choice(['bullish', 'bearish'])} retail sentiment",
                f"ICS shows institutional {random.choice(['buying', 'selling'])}",
                f"Regime context: {random.choice(['macro headwind', 'macro tailwind'])}",
            ],
            "is_resolved": random.choice([True, False]),
            "actual_return": round(random.uniform(-8, 12), 1) if random.random() > 0.5 else None,
        })
    return signals
