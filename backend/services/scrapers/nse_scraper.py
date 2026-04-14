# ARCHITECTURE NOTE:
# NSE India's website uses session-cookie anti-scraping. We must first
# hit the homepage to seed a session cookie, then use that session for
# API requests. This module provides the shared NSE session management
# used by bulk/block deal and FII/DII scrapers.

from __future__ import annotations

import asyncio
import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
import structlog

from backend.config import settings

logger = structlog.get_logger(__name__)


class NSESession:
    """Manages authenticated NSE session with cookie seeding."""

    BASE_URL = "https://www.nseindia.com"
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.nseindia.com/",
        "X-Requested-With": "XMLHttpRequest",
        "Connection": "keep-alive",
    }

    def __init__(self) -> None:
        self._client: Optional[httpx.AsyncClient] = None
        self._cookies_seeded = False

    async def _ensure_session(self) -> httpx.AsyncClient:
        """Create client and seed cookies by visiting homepage."""
        if self._client is None or not self._cookies_seeded:
            if self._client:
                await self._client.aclose()

            self._client = httpx.AsyncClient(
                timeout=settings.resilience.nse_session_timeout,
                headers=self.HEADERS,
                follow_redirects=True,
            )

            try:
                # Seed session cookie
                resp = await self._client.get(self.BASE_URL)
                resp.raise_for_status()
                self._cookies_seeded = True
                logger.info("nse_session_seeded")
                await asyncio.sleep(1)  # Courtesy delay
            except Exception as e:
                logger.error("nse_session_seed_failed", error=str(e))
                self._cookies_seeded = False

        return self._client

    async def get_json(self, endpoint: str) -> Optional[Dict[str, Any]]:
        """Fetch JSON from NSE API endpoint with session cookies."""
        client = await self._ensure_session()

        try:
            url = f"{self.BASE_URL}{endpoint}"
            resp = await client.get(url)

            if resp.status_code == 401 or resp.status_code == 403:
                # Cookie expired, re-seed
                self._cookies_seeded = False
                client = await self._ensure_session()
                resp = await client.get(url)

            resp.raise_for_status()
            return resp.json()

        except Exception as e:
            logger.error("nse_api_error", endpoint=endpoint, error=str(e))
            return None

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
            self._cookies_seeded = False


# Shared session instance
nse_session = NSESession()


# ----------------------------------------------------------
# Mock data generators for NSE endpoints
# ----------------------------------------------------------

def generate_mock_market_data() -> Dict[str, Any]:
    """Generate synthetic market index data."""
    nifty = 22000 + random.uniform(-500, 500)
    sensex = 72000 + random.uniform(-1500, 1500)
    return {
        "nifty50": {
            "last": round(nifty, 2),
            "change": round(random.uniform(-200, 200), 2),
            "pChange": round(random.uniform(-1.5, 1.5), 2),
        },
        "sensex": {
            "last": round(sensex, 2),
            "change": round(random.uniform(-600, 600), 2),
            "pChange": round(random.uniform(-1.5, 1.5), 2),
        },
        "niftyBank": {
            "last": round(47000 + random.uniform(-1000, 1000), 2),
            "change": round(random.uniform(-400, 400), 2),
            "pChange": round(random.uniform(-2.0, 2.0), 2),
        },
        "usdInr": round(83.0 + random.uniform(-1, 1), 4),
        "brentCrude": round(75 + random.uniform(-5, 5), 2),
        "goldMcx": round(62000 + random.uniform(-2000, 2000), 0),
        "indiaVix": round(12 + random.uniform(-3, 8), 2),
    }
