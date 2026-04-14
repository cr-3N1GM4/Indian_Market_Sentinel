# ARCHITECTURE NOTE:
# Screener.in provides clean financial data per company. We scrape
# quarterly results, shareholding patterns, and key ratios. This feeds
# into the Result Scoring Pipeline (Module 3B) for momentum labelling.
# Mock fallback provides realistic financial data for development.

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
import structlog
from bs4 import BeautifulSoup

from backend.config import settings

logger = structlog.get_logger(__name__)


class ScreenerScraper:
    """Scrapes quarterly financial data from Screener.in."""

    BASE_URL = "https://www.screener.in/company/{ticker}/"

    def __init__(self) -> None:
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
            ),
        }

    async def fetch_company_data(self, ticker: str) -> Dict[str, Any]:
        """Fetch and parse all financial data for a ticker."""
        try:
            async with httpx.AsyncClient(
                timeout=30, headers=self.headers, follow_redirects=True
            ) as client:
                url = self.BASE_URL.format(ticker=ticker)
                resp = await client.get(url)
                resp.raise_for_status()
                return self._parse_company_page(resp.text, ticker)
        except Exception as e:
            logger.warning("screener_fetch_error", ticker=ticker, error=str(e))
            return self._generate_mock_data(ticker)

    def _parse_company_page(self, html: str, ticker: str) -> Dict[str, Any]:
        """Parse Screener.in company page for key financials."""
        soup = BeautifulSoup(html, "lxml")
        data: Dict[str, Any] = {"ticker": ticker, "source": "screener.in"}

        try:
            # Try to extract quarterly results table
            tables = soup.find_all("table", class_="data-table")

            # Extract key ratios from the top section
            ratio_list = soup.select("li.flex.flex-space-between")
            for item in ratio_list:
                name_el = item.find("span", class_="name")
                value_el = item.find("span", class_="number")
                if name_el and value_el:
                    name = name_el.get_text(strip=True).lower()
                    value = value_el.get_text(strip=True)
                    if "p/e" in name:
                        data["pe_ratio"] = self._parse_number(value)
                    elif "market cap" in name:
                        data["market_cap_cr"] = self._parse_number(value)
                    elif "debt" in name and "equity" in name:
                        data["debt_equity"] = self._parse_number(value)
                    elif "roe" in name:
                        data["roe"] = self._parse_number(value)

            # Extract shareholding pattern
            shareholding = soup.find("div", id="shareholding")
            if shareholding:
                rows = shareholding.find_all("tr")
                for row in rows:
                    cols = row.find_all("td")
                    if len(cols) >= 2:
                        label = cols[0].get_text(strip=True).lower()
                        values = [self._parse_number(c.get_text(strip=True)) for c in cols[1:]]
                        if "promoter" in label:
                            data["promoter_holding_pct"] = values
                        elif "fii" in label or "foreign" in label:
                            data["fii_holding_pct"] = values
                        elif "dii" in label or "domestic" in label:
                            data["dii_holding_pct"] = values

            # Revenue, PAT from quarterly results
            if tables:
                data["quarterly_results"] = self._parse_quarterly_table(tables[0])

        except Exception as e:
            logger.warning("screener_parse_error", ticker=ticker, error=str(e))

        # Fill with mock data if parsing returned empty
        if not data.get("quarterly_results"):
            data = self._generate_mock_data(ticker)

        return data

    def _parse_quarterly_table(self, table) -> List[Dict[str, Any]]:
        """Parse quarterly results HTML table."""
        quarters = []
        headers = [th.get_text(strip=True) for th in table.find_all("th")]

        for row in table.find_all("tr")[1:]:
            cols = row.find_all("td")
            if len(cols) < 2:
                continue
            label = cols[0].get_text(strip=True).lower()
            values = [self._parse_number(c.get_text(strip=True)) for c in cols[1:]]

            if "revenue" in label or "sales" in label:
                quarters.append({"metric": "revenue", "values": values})
            elif "net profit" in label or "pat" in label:
                quarters.append({"metric": "pat", "values": values})
            elif "ebitda" in label:
                quarters.append({"metric": "ebitda", "values": values})

        return quarters

    @staticmethod
    def _parse_number(text: str) -> Optional[float]:
        """Parse number from text, handling commas and Cr/L suffixes."""
        try:
            cleaned = text.replace(",", "").replace("%", "").strip()
            if cleaned.endswith("Cr"):
                cleaned = cleaned[:-2]
            elif cleaned.endswith("L"):
                cleaned = cleaned[:-1]
            return float(cleaned) if cleaned else None
        except (ValueError, TypeError):
            return None

    # MOCK_FALLBACK: realistic synthetic financial data
    def _generate_mock_data(self, ticker: str) -> Dict[str, Any]:
        base_rev = random.uniform(2000, 50000)
        base_pat = base_rev * random.uniform(0.05, 0.20)
        base_ebitda = base_rev * random.uniform(0.12, 0.30)

        quarters = []
        for i in range(8):
            growth = 1 + random.uniform(-0.10, 0.25)
            quarters.append({
                "quarter": f"Q{(i % 4) + 1} FY{2024 - i // 4}",
                "revenue": round(base_rev * growth, 2),
                "pat": round(base_pat * growth * random.uniform(0.8, 1.3), 2),
                "ebitda": round(base_ebitda * growth, 2),
                "ebitda_margin": round(random.uniform(12, 30), 1),
            })

        promoter = round(random.uniform(40, 75), 2)
        fii = round(random.uniform(10, 40), 2)
        dii = round(random.uniform(5, 25), 2)

        return {
            "ticker": ticker,
            "source": "screener.in (mock)",
            "pe_ratio": round(random.uniform(10, 60), 1),
            "market_cap_cr": round(random.uniform(5000, 500000), 0),
            "debt_equity": round(random.uniform(0.0, 1.5), 2),
            "roe": round(random.uniform(8, 30), 1),
            "interest_coverage": round(random.uniform(2, 20), 1),
            "promoter_holding_pct": [promoter, promoter + random.uniform(-2, 1),
                                      promoter + random.uniform(-3, 0.5),
                                      promoter + random.uniform(-4, 0)],
            "fii_holding_pct": [fii, fii + random.uniform(-3, 3),
                                 fii + random.uniform(-5, 2),
                                 fii + random.uniform(-5, 5)],
            "dii_holding_pct": [dii, dii + random.uniform(-2, 3),
                                 dii + random.uniform(-3, 4),
                                 dii + random.uniform(-4, 5)],
            "quarterly_results": quarters,
            "peg_ratio": round(random.uniform(0.5, 3.0), 2),
        }


screener_scraper = ScreenerScraper()
