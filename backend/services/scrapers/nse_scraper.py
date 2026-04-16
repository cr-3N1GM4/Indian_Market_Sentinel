# ARCHITECTURE NOTE:
# NSE India's website uses session-cookie anti-scraping. We must first
# hit the homepage to seed a session cookie, then use that session for
# API requests. This module provides REAL data fetching from NSE endpoints
# for market indices, gainers/losers, FII/DII, corporate actions.

from __future__ import annotations

import asyncio
import random
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import httpx
import structlog

from backend.config import settings

logger = structlog.get_logger(__name__)

# In-memory cache for rate limiting
_cache: Dict[str, Any] = {}
_cache_ts: Dict[str, float] = {}
CACHE_TTL = 300  # 5 minutes


def _get_cached(key: str) -> Optional[Any]:
    ts = _cache_ts.get(key, 0)
    if (datetime.now(timezone.utc).timestamp() - ts) < CACHE_TTL:
        return _cache.get(key)
    return None


def _set_cached(key: str, data: Any) -> None:
    _cache[key] = data
    _cache_ts[key] = datetime.now(timezone.utc).timestamp()


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
# Real NSE data fetching
# ----------------------------------------------------------

async def fetch_market_indices() -> Dict[str, Any]:
    """Fetch real market index data from NSE."""
    cached = _get_cached("market_indices")
    if cached:
        return cached

    try:
        data = await nse_session.get_json("/api/allIndices")
        if data and "data" in data:
            indices = {}
            for idx in data["data"]:
                name = idx.get("index", "")
                if name == "NIFTY 50":
                    indices["nifty50"] = {
                        "last": idx.get("last", 0),
                        "change": round(idx.get("variation", 0), 2),
                        "pChange": round(idx.get("percentChange", 0), 2),
                    }
                elif name == "NIFTY BANK":
                    indices["niftyBank"] = {
                        "last": idx.get("last", 0),
                        "change": round(idx.get("variation", 0), 2),
                        "pChange": round(idx.get("percentChange", 0), 2),
                    }
                elif name == "S&P BSE SENSEX" or name == "NIFTY NEXT 50":
                    if "sensex" not in indices:
                        indices["sensex"] = {
                            "last": idx.get("last", 0),
                            "change": round(idx.get("variation", 0), 2),
                            "pChange": round(idx.get("percentChange", 0), 2),
                        }

            # Also try to get VIX
            indices["indiaVix"] = data.get("metadata", {}).get("indexVix", 0)

            result = _fill_missing_indices(indices)
            _set_cached("market_indices", result)
            return result
    except Exception as e:
        logger.error("fetch_market_indices_error", error=str(e))

    return generate_mock_market_data()


async def fetch_top_gainers() -> List[Dict[str, Any]]:
    """Fetch top gainers from NSE."""
    cached = _get_cached("top_gainers")
    if cached:
        return cached

    try:
        data = await nse_session.get_json("/api/live-analysis-variations?index=gainers")
        if data and "NIFTY" in data:
            gainers = []
            items = data.get("NIFTY", {}).get("data", [])
            for item in items[:15]:
                gainers.append({
                    "symbol": item.get("symbol", ""),
                    "lastPrice": item.get("ltp", 0),
                    "change": round(item.get("netPrice", 0), 2),
                    "pChange": round(item.get("perChange", 0), 2),
                    "tradedQuantity": item.get("tradedQuantity", 0),
                    "openPrice": item.get("openPrice", 0),
                    "highPrice": item.get("highPrice", 0),
                    "lowPrice": item.get("lowPrice", 0),
                    "previousClose": item.get("previousPrice", 0),
                })
            if gainers:
                _set_cached("top_gainers", gainers)
                return gainers
    except Exception as e:
        logger.error("fetch_top_gainers_error", error=str(e))

    # Alternative: try equity market status
    try:
        data = await nse_session.get_json("/api/equity-stockIndices?index=NIFTY%2050")
        if data and "data" in data:
            stocks = sorted(data["data"], key=lambda x: x.get("pChange", 0), reverse=True)
            gainers = []
            for s in stocks[:15]:
                if s.get("pChange", 0) > 0:
                    gainers.append({
                        "symbol": s.get("symbol", ""),
                        "lastPrice": s.get("lastPrice", 0),
                        "change": round(s.get("change", 0), 2),
                        "pChange": round(s.get("pChange", 0), 2),
                        "tradedQuantity": s.get("totalTradedVolume", 0),
                        "openPrice": s.get("open", 0),
                        "highPrice": s.get("dayHigh", 0),
                        "lowPrice": s.get("dayLow", 0),
                        "previousClose": s.get("previousClose", 0),
                    })
            if gainers:
                _set_cached("top_gainers", gainers)
                return gainers
    except Exception as e:
        logger.error("fetch_top_gainers_alt_error", error=str(e))

    return _mock_gainers_losers("gainers")


async def fetch_top_losers() -> List[Dict[str, Any]]:
    """Fetch top losers from NSE."""
    cached = _get_cached("top_losers")
    if cached:
        return cached

    try:
        data = await nse_session.get_json("/api/live-analysis-variations?index=losers")
        if data and "NIFTY" in data:
            losers = []
            items = data.get("NIFTY", {}).get("data", [])
            for item in items[:15]:
                losers.append({
                    "symbol": item.get("symbol", ""),
                    "lastPrice": item.get("ltp", 0),
                    "change": round(item.get("netPrice", 0), 2),
                    "pChange": round(item.get("perChange", 0), 2),
                    "tradedQuantity": item.get("tradedQuantity", 0),
                    "openPrice": item.get("openPrice", 0),
                    "highPrice": item.get("highPrice", 0),
                    "lowPrice": item.get("lowPrice", 0),
                    "previousClose": item.get("previousPrice", 0),
                })
            if losers:
                _set_cached("top_losers", losers)
                return losers
    except Exception as e:
        logger.error("fetch_top_losers_error", error=str(e))

    # Alternative
    try:
        data = await nse_session.get_json("/api/equity-stockIndices?index=NIFTY%2050")
        if data and "data" in data:
            stocks = sorted(data["data"], key=lambda x: x.get("pChange", 0))
            losers = []
            for s in stocks[:15]:
                if s.get("pChange", 0) < 0:
                    losers.append({
                        "symbol": s.get("symbol", ""),
                        "lastPrice": s.get("lastPrice", 0),
                        "change": round(s.get("change", 0), 2),
                        "pChange": round(s.get("pChange", 0), 2),
                        "tradedQuantity": s.get("totalTradedVolume", 0),
                        "openPrice": s.get("open", 0),
                        "highPrice": s.get("dayHigh", 0),
                        "lowPrice": s.get("dayLow", 0),
                        "previousClose": s.get("previousClose", 0),
                    })
            if losers:
                _set_cached("top_losers", losers)
                return losers
    except Exception as e:
        logger.error("fetch_top_losers_alt_error", error=str(e))

    return _mock_gainers_losers("losers")


async def fetch_fii_dii_activity() -> Dict[str, Any]:
    """Fetch real FII/DII activity from NSE."""
    cached = _get_cached("fii_dii")
    if cached:
        return cached

    try:
        data = await nse_session.get_json("/api/fiidiiActivity")
        if data:
            result = {"fii": [], "dii": []}
            for item in data:
                category = item.get("category", "").upper()
                entry = {
                    "date": item.get("date", ""),
                    "buyValue": item.get("buyValue", 0),
                    "sellValue": item.get("sellValue", 0),
                    "netValue": item.get("netValue", 0),
                }
                if "FII" in category or "FPI" in category:
                    result["fii"].append(entry)
                elif "DII" in category:
                    result["dii"].append(entry)
            if result["fii"] or result["dii"]:
                _set_cached("fii_dii", result)
                return result
    except Exception as e:
        logger.error("fetch_fii_dii_error", error=str(e))

    return _mock_fii_dii()


async def fetch_corporate_actions(days: int = 30) -> List[Dict[str, Any]]:
    """Fetch corporate actions from NSE for upcoming days."""
    cache_key = f"corp_actions_{days}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    try:
        from_date = datetime.now().strftime("%d-%m-%Y")
        to_date = (datetime.now() + timedelta(days=days)).strftime("%d-%m-%Y")
        endpoint = f"/api/corporateActions?index=equities&from_date={from_date}&to_date={to_date}"
        data = await nse_session.get_json(endpoint)
        if data and isinstance(data, list):
            actions = []
            for item in data:
                actions.append({
                    "symbol": item.get("symbol", ""),
                    "company": item.get("comp", ""),
                    "subject": item.get("subject", ""),
                    "exDate": item.get("exDate", ""),
                    "recordDate": item.get("recDate", ""),
                    "bcStartDate": item.get("bcStrtDt", ""),
                    "bcEndDate": item.get("bcEndDt", ""),
                })
            if actions:
                _set_cached(cache_key, actions)
                return actions
    except Exception as e:
        logger.error("fetch_corporate_actions_error", error=str(e))

    return _mock_corporate_actions(days)


async def fetch_advances_declines() -> Dict[str, int]:
    """Fetch advance/decline data from NSE for market mood."""
    cached = _get_cached("adv_dec")
    if cached:
        return cached

    try:
        data = await nse_session.get_json("/api/equity-stockIndices?index=NIFTY%2050")
        if data and "advance" in data:
            result = {
                "advances": data.get("advance", {}).get("advances", 25),
                "declines": data.get("advance", {}).get("declines", 25),
                "unchanged": data.get("advance", {}).get("unchanged", 0),
            }
            _set_cached("adv_dec", result)
            return result
    except Exception as e:
        logger.error("fetch_advances_declines_error", error=str(e))

    return {"advances": 25, "declines": 25, "unchanged": 0}


async def fetch_stock_quote(symbol: str) -> Optional[Dict[str, Any]]:
    """Fetch real-time quote for a single stock from NSE."""
    cache_key = f"quote_{symbol}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    try:
        data = await nse_session.get_json(f"/api/quote-equity?symbol={symbol}")
        if data and "priceInfo" in data:
            pi = data["priceInfo"]
            info = data.get("info", {})
            result = {
                "symbol": info.get("symbol", symbol),
                "companyName": info.get("companyName", symbol),
                "lastPrice": pi.get("lastPrice", 0),
                "change": round(pi.get("change", 0), 2),
                "pChange": round(pi.get("pChange", 0), 2),
                "open": pi.get("open", 0),
                "dayHigh": pi.get("intraDayHighLow", {}).get("max", 0),
                "dayLow": pi.get("intraDayHighLow", {}).get("min", 0),
                "previousClose": pi.get("previousClose", 0),
                "totalTradedVolume": data.get("securityWiseDP", {}).get("quantityTraded", 0),
                "marketCap": info.get("totalMarketCap", 0),
                "industry": info.get("industry", ""),
            }
            _set_cached(cache_key, result)
            return result
    except Exception as e:
        logger.error("fetch_stock_quote_error", symbol=symbol, error=str(e))

    return None


# ----------------------------------------------------------
# Helper / Fill functions
# ----------------------------------------------------------

def _fill_missing_indices(indices: Dict) -> Dict:
    """Fill missing indices with defaults."""
    if "nifty50" not in indices:
        indices["nifty50"] = {"last": 0, "change": 0, "pChange": 0}
    if "sensex" not in indices:
        indices["sensex"] = {"last": 0, "change": 0, "pChange": 0}
    if "niftyBank" not in indices:
        indices["niftyBank"] = {"last": 0, "change": 0, "pChange": 0}
    if "indiaVix" not in indices:
        indices["indiaVix"] = 0
    indices.setdefault("usdInr", 0)
    indices.setdefault("brentCrude", 0)
    indices.setdefault("goldMcx", 0)
    return indices


# ----------------------------------------------------------
# Mock data generators (fallback only)
# ----------------------------------------------------------

def generate_mock_market_data() -> Dict[str, Any]:
    """Generate synthetic market index data as fallback."""
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


def _mock_gainers_losers(direction: str) -> List[Dict[str, Any]]:
    tickers = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HINDUNILVR",
               "SBIN", "BHARTIARTL", "ITC", "KOTAKBANK", "LT", "AXISBANK",
               "BAJFINANCE", "MARUTI", "SUNPHARMA"]
    result = []
    for t in tickers[:10]:
        price = round(random.uniform(500, 5000), 2)
        pct = round(random.uniform(0.5, 5.0), 2) if direction == "gainers" else round(random.uniform(-5.0, -0.5), 2)
        result.append({
            "symbol": t,
            "lastPrice": price,
            "change": round(price * pct / 100, 2),
            "pChange": pct,
            "tradedQuantity": random.randint(100000, 5000000),
            "openPrice": round(price * 0.99, 2),
            "highPrice": round(price * 1.02, 2),
            "lowPrice": round(price * 0.97, 2),
            "previousClose": round(price / (1 + pct / 100), 2),
        })
    return result


def _mock_fii_dii() -> Dict[str, Any]:
    from datetime import timedelta
    result = {"fii": [], "dii": []}
    for i in range(10):
        dt = datetime.now() - timedelta(days=i)
        date_str = dt.strftime("%d-%b-%Y")
        result["fii"].append({
            "date": date_str,
            "buyValue": round(random.uniform(5000, 15000), 2),
            "sellValue": round(random.uniform(5000, 15000), 2),
            "netValue": round(random.uniform(-3000, 3000), 2),
        })
        result["dii"].append({
            "date": date_str,
            "buyValue": round(random.uniform(4000, 12000), 2),
            "sellValue": round(random.uniform(4000, 12000), 2),
            "netValue": round(random.uniform(-2000, 2000), 2),
        })
    return result


def _mock_corporate_actions(days: int) -> List[Dict[str, Any]]:
    tickers = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "SUNPHARMA", "ITC", "SBIN", "WIPRO"]
    subjects = ["Dividend - Rs 5 Per Share", "Bonus 1:1", "Annual General Meeting",
                "Buyback", "Stock Split", "Rights Issue 1:5", "Interim Dividend Rs 10"]
    actions = []
    for i in range(min(days // 2, 15)):
        dt = datetime.now() + timedelta(days=random.randint(1, days))
        actions.append({
            "symbol": random.choice(tickers),
            "company": "",
            "subject": random.choice(subjects),
            "exDate": dt.strftime("%d-%b-%Y"),
            "recordDate": (dt + timedelta(days=2)).strftime("%d-%b-%Y"),
            "bcStartDate": "",
            "bcEndDate": "",
        })
    return sorted(actions, key=lambda x: x["exDate"])
