# ARCHITECTURE NOTE:
# FRED API provides US macro data (CPI, Fed Funds Rate, DXY)
# needed for cross-market regime analysis. Free tier allows
# 120 requests/minute which is more than sufficient.

from __future__ import annotations

import os
import random
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
import structlog

logger = structlog.get_logger(__name__)


class FREDApi:
    """Fetches US macro data from the Federal Reserve Economic Data API."""

    BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

    SERIES = {
        "CPIAUCSL": "US CPI All Items",
        "FEDFUNDS": "Federal Funds Rate",
        "DTWEXBGS": "DXY Trade Weighted USD Index",
    }

    def __init__(self) -> None:
        self.api_key = os.getenv("FRED_API_KEY", "")

    async def fetch_series(
        self, series_id: str, limit: int = 12
    ) -> List[Dict[str, Any]]:
        """Fetch latest observations for a FRED series."""
        if not self.api_key:
            logger.warning("fred_no_api_key", msg="Using mock data")
            return self._generate_mock_series(series_id, limit)

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                params = {
                    "series_id": series_id,
                    "api_key": self.api_key,
                    "file_type": "json",
                    "sort_order": "desc",
                    "limit": limit,
                }
                resp = await client.get(self.BASE_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
                return data.get("observations", [])

        except Exception as e:
            logger.error("fred_fetch_error", series=series_id, error=str(e))
            return self._generate_mock_series(series_id, limit)

    async def fetch_all(self) -> Dict[str, Any]:
        """Fetch latest values for all tracked US macro series."""
        result = {}
        for series_id, name in self.SERIES.items():
            obs = await self.fetch_series(series_id, limit=1)
            if obs:
                try:
                    result[series_id] = {
                        "value": float(obs[0].get("value", 0)),
                        "date": obs[0].get("date", ""),
                        "name": name,
                    }
                except (ValueError, IndexError):
                    pass
        return result

    # MOCK_FALLBACK
    def _generate_mock_series(
        self, series_id: str, limit: int
    ) -> List[Dict[str, Any]]:
        mock_values = {
            "CPIAUCSL": lambda: round(random.uniform(300, 315), 1),
            "FEDFUNDS": lambda: round(random.uniform(5.0, 5.5), 2),
            "DTWEXBGS": lambda: round(random.uniform(103, 108), 2),
        }
        gen = mock_values.get(series_id, lambda: random.uniform(0, 100))
        return [
            {"date": "2025-01-01", "value": str(gen())}
            for _ in range(limit)
        ]


fred_api = FREDApi()
