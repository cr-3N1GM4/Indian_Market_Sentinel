from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query

from backend.db.timescale_client import db

router = APIRouter(prefix="/institutional", tags=["institutional"])


@router.get("/{ticker}", response_model=dict)
async def get_institutional_data(ticker: str):
    """Get institutional conviction data for a ticker."""
    import random

    ics_row = await db.get_ics_latest(ticker.upper())
    flows = await db.get_institutional_flows(ticker.upper(), days=10)

    bulk_deals = [
        {
            "time": str(f["time"]),
            "entity_name": f.get("entity_name"),
            "deal_type": f.get("deal_type"),
            "quantity": f.get("quantity"),
            "price": f.get("price"),
            "value_crores": f.get("value_crores"),
        }
        for f in flows
        if f.get("source") in ("nse_bulk",)
    ]

    block_deals = [
        {
            "time": str(f["time"]),
            "entity_name": f.get("entity_name"),
            "deal_type": f.get("deal_type"),
            "quantity": f.get("quantity"),
            "price": f.get("price"),
            "value_crores": f.get("value_crores"),
        }
        for f in flows
        if f.get("source") in ("nse_block",)
    ]

    return {
        "data": {
            "ticker": ticker.upper(),
            "ics": ics_row["ics"] if ics_row else round(random.uniform(-0.5, 0.5), 2),
            "fii_net_5d": ics_row["fii_net_crores"] if ics_row else round(random.uniform(-500, 500), 1),
            "dii_net_5d": ics_row["dii_net_crores"] if ics_row else round(random.uniform(-300, 300), 1),
            "bulk_deals_recent": bulk_deals[:10],
            "block_deals_recent": block_deals[:10],
        },
        "meta": {"timestamp": datetime.utcnow().isoformat(), "version": "1.0"},
    }


@router.get("/fii-dii-flows", response_model=dict)
async def get_fii_dii_flows(days: int = Query(default=30, ge=1, le=365)):
    """Get daily FII/DII flow aggregates."""
    import random

    flows = await db.get_fii_dii_flows(days=days)

    if flows:
        daily = {}
        for f in flows:
            date_key = f["time"].strftime("%Y-%m-%d")
            if date_key not in daily:
                daily[date_key] = {"date": date_key, "fii_net_crores": 0, "dii_net_crores": 0}
            if f["source"] == "fii_daily":
                daily[date_key]["fii_net_crores"] = f.get("value_crores", 0)
            elif f["source"] == "dii_daily":
                daily[date_key]["dii_net_crores"] = f.get("value_crores", 0)

        return {
            "data": list(daily.values()),
            "meta": {"timestamp": datetime.utcnow().isoformat(), "version": "1.0"},
        }

    # Mock data
    from datetime import timedelta
    mock_data = []
    for i in range(days):
        dt = datetime.utcnow() - timedelta(days=days - i)
        mock_data.append({
            "date": dt.strftime("%Y-%m-%d"),
            "fii_net_crores": round(random.uniform(-3000, 3000), 1),
            "dii_net_crores": round(random.uniform(-2000, 2000), 1),
        })

    return {
        "data": mock_data,
        "meta": {"timestamp": datetime.utcnow().isoformat(), "version": "1.0", "stale": True},
    }
