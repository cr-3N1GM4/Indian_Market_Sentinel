# Market Mood Index calculator
# Combines advance/decline ratio, VIX, FII flows, and news sentiment
# into a 0-100 Fear & Greed style gauge.

from __future__ import annotations
from typing import Any, Dict
import structlog

logger = structlog.get_logger(__name__)


def compute_market_mood(
    advances: int = 25,
    declines: int = 25,
    vix: float = 15.0,
    fii_net: float = 0.0,
    avg_news_sentiment: float = 0.0,
) -> Dict[str, Any]:
    """
    Compute a market mood index from 0 (Extreme Fear) to 100 (Extreme Greed).

    Components (equal weight 25% each):
    1. Advance/Decline ratio → 0-100
    2. VIX level (inverse) → 0-100
    3. FII net flow direction → 0-100
    4. News sentiment → 0-100
    """

    total = advances + declines
    if total > 0:
        ad_score = (advances / total) * 100
    else:
        ad_score = 50.0

    # VIX: lower = greedier. VIX 10 = 90 score, VIX 30+ = 10 score
    if vix <= 10:
        vix_score = 90.0
    elif vix >= 30:
        vix_score = 10.0
    else:
        vix_score = 90.0 - (vix - 10) * (80.0 / 20.0)

    # FII net flow: positive buying = bullish
    if fii_net > 2000:
        fii_score = 90.0
    elif fii_net < -2000:
        fii_score = 10.0
    else:
        fii_score = 50.0 + (fii_net / 2000.0) * 40.0

    # News sentiment: -1 to +1 → 0 to 100
    news_score = max(0, min(100, (avg_news_sentiment + 1) * 50))

    # Weighted average
    mood = (ad_score * 0.30 + vix_score * 0.25 + fii_score * 0.25 + news_score * 0.20)
    mood = max(0, min(100, mood))

    if mood >= 75:
        label = "Extreme Greed"
        color = "#00FF88"
    elif mood >= 60:
        label = "Greed"
        color = "#88FF00"
    elif mood >= 40:
        label = "Neutral"
        color = "#FFB800"
    elif mood >= 25:
        label = "Fear"
        color = "#FF6B35"
    else:
        label = "Extreme Fear"
        color = "#FF3B5C"

    return {
        "score": round(mood, 1),
        "label": label,
        "color": color,
        "components": {
            "advance_decline": round(ad_score, 1),
            "vix": round(vix_score, 1),
            "fii_flow": round(fii_score, 1),
            "news_sentiment": round(news_score, 1),
        },
        "raw": {
            "advances": advances,
            "declines": declines,
            "vix": vix,
            "fii_net_crores": fii_net,
            "avg_news_sentiment": avg_news_sentiment,
        },
    }
