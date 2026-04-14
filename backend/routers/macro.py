from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Query

from backend.db.timescale_client import db
from backend.models.signal_models import RegimeCurrentResponse, RegimeScore

router = APIRouter(prefix="/regime", tags=["regime"])


@router.get("/current", response_model=dict)
async def get_current_regime():
    """Get current macro regime classification."""
    row = await db.get_current_regime()

    if row:
        llm_score = None
        if row.get("llm_regime_score"):
            try:
                score_data = row["llm_regime_score"]
                if isinstance(score_data, str):
                    score_data = json.loads(score_data)
                llm_score = RegimeScore(**score_data)
            except Exception:
                pass

        return {
            "data": RegimeCurrentResponse(
                regime=row["final_regime"] or row["regime"],
                confidence=row.get("confidence"),
                repo_rate=row.get("repo_rate"),
                cpi_yoy=row.get("cpi_yoy"),
                wpi_yoy=row.get("wpi_yoy"),
                gsec_10y=row.get("gsec_10y"),
                gsec_2y=row.get("gsec_2y"),
                yield_curve_slope=row.get("yield_curve_slope"),
                usd_inr=row.get("usd_inr"),
                nifty_vix=row.get("nifty_vix"),
                llm_score=llm_score,
                last_updated=row["time"],
            ).model_dump(),
            "meta": {"timestamp": datetime.utcnow().isoformat(), "version": "1.0"},
        }

    # Mock response
    from backend.services.llm.regime_scorer import _generate_mock_score
    mock_score = _generate_mock_score()

    return {
        "data": RegimeCurrentResponse(
            regime="hawkish_pause",
            confidence=0.72,
            repo_rate=6.50,
            cpi_yoy=5.1,
            gsec_10y=7.25,
            gsec_2y=7.05,
            yield_curve_slope=0.20,
            usd_inr=83.25,
            nifty_vix=14.5,
            llm_score=mock_score,
        ).model_dump(),
        "meta": {"timestamp": datetime.utcnow().isoformat(), "version": "1.0", "stale": True},
    }


@router.get("/history", response_model=dict)
async def get_regime_history(days: int = Query(default=180, ge=1, le=730)):
    """Get regime history over time."""
    rows = await db.get_regime_history(days=days)

    if rows:
        history = [
            {
                "time": str(r["time"]),
                "regime": r["final_regime"] or r["regime"],
                "confidence": r.get("confidence"),
                "repo_rate": r.get("repo_rate"),
                "cpi_yoy": r.get("cpi_yoy"),
            }
            for r in rows
        ]
    else:
        # Mock history
        from datetime import timedelta
        import random
        regimes = ["hawkish_tightening", "hawkish_pause", "neutral_watchful",
                    "dovish_pause", "dovish_easing"]
        history = []
        current_regime = random.choice(regimes)
        for i in range(0, days, 30):
            if random.random() > 0.7:
                current_regime = random.choice(regimes)
            dt = datetime.utcnow() - timedelta(days=days - i)
            history.append({
                "time": dt.isoformat(),
                "regime": current_regime,
                "confidence": round(random.uniform(0.5, 0.9), 2),
                "repo_rate": round(6.5 + random.uniform(-0.5, 0.25), 2),
                "cpi_yoy": round(random.uniform(4, 6.5), 1),
            })

    return {
        "data": history,
        "meta": {"timestamp": datetime.utcnow().isoformat(), "version": "1.0"},
    }
