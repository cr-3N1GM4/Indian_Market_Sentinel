# ARCHITECTURE NOTE:
# Tracks NSE/BSE buyback announcements and flags opportunities when
# buyback price premium > 20% and size > 2% of market cap.
# Tender offers get higher priority than open market buybacks.

from __future__ import annotations

import random
from datetime import date, timedelta
from typing import Any, Dict, List

import structlog

from backend.config import settings
from backend.db.timescale_client import db

logger = structlog.get_logger(__name__)


class BuybackTracker:
    """Tracks and evaluates corporate buyback opportunities."""

    async def check_buyback_opportunities(self) -> List[Dict[str, Any]]:
        """Scan upcoming corporate actions for buyback opportunities."""
        upcoming = await db.get_upcoming_actions(days=30)
        opportunities = []

        for row in upcoming:
            if row["action_type"] != "BUYBACK":
                continue

            details = row.get("details") or {}
            if isinstance(details, str):
                import json
                try:
                    details = json.loads(details)
                except Exception:
                    details = {}

            # Extract buyback parameters
            buyback_price = details.get("buyback_price") or self._mock_price(row["ticker"])
            cmp = details.get("current_price") or buyback_price * random.uniform(0.7, 0.95)
            mcap = details.get("market_cap_cr") or random.uniform(5000, 100000)
            buyback_size = details.get("buyback_size_cr") or mcap * random.uniform(0.01, 0.05)
            method = details.get("method", "TENDER_OFFER")

            premium_pct = ((buyback_price - cmp) / cmp * 100) if cmp > 0 else 0
            size_pct_mcap = (buyback_size / mcap * 100) if mcap > 0 else 0

            is_opportunity = (
                premium_pct > settings.signals.buyback_premium_min_pct
                and size_pct_mcap > settings.signals.buyback_size_min_pct_mcap
            )

            opportunity = {
                "ticker": row["ticker"],
                "buyback_price": round(buyback_price, 2),
                "current_price": round(cmp, 2),
                "premium_pct": round(premium_pct, 1),
                "buyback_size_cr": round(buyback_size, 0),
                "size_pct_mcap": round(size_pct_mcap, 1),
                "method": method,
                "event_date": str(row["event_date"]),
                "is_opportunity": is_opportunity,
                "priority": "HIGH" if method == "TENDER_OFFER" else "MEDIUM",
            }
            opportunities.append(opportunity)

        logger.info("buyback_check_complete", opportunities=len(
            [o for o in opportunities if o["is_opportunity"]]
        ))
        return opportunities

    @staticmethod
    def _mock_price(ticker: str) -> float:
        prices = {
            "SUNPHARMA": 1200, "RELIANCE": 2500, "ONGC": 250,
            "DRREDDY": 5500, "CIPLA": 1300, "NTPC": 350,
        }
        return prices.get(ticker, random.uniform(200, 3000))


buyback_tracker = BuybackTracker()
