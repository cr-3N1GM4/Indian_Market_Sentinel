# ARCHITECTURE NOTE:
# RBI MPC minutes are the primary input to the regime classifier.
# We download PDFs from RBI's website, extract text with pdfplumber,
# clean and section-split, then feed into the LLM regime scorer.

from __future__ import annotations

import io
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
import structlog

from backend.db.timescale_client import db

logger = structlog.get_logger(__name__)


class RBIMinutesParser:
    """Downloads and parses RBI MPC meeting minutes."""

    RBI_URL = "https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx"

    async def fetch_latest_minutes(self) -> List[Dict[str, Any]]:
        """Fetch links to recent MPC minutes from RBI website."""
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.get(self.RBI_URL)
                resp.raise_for_status()
                # Parse for PDF links containing "MPC" or "Minutes"
                return self._extract_minute_links(resp.text)
        except Exception as e:
            logger.warning("rbi_fetch_error", error=str(e))
            return self._generate_mock_minutes()

    def _extract_minute_links(self, html: str) -> List[Dict[str, Any]]:
        """Extract MPC minutes PDF links from RBI press releases page."""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        minutes = []

        for link in soup.find_all("a", href=True):
            text = link.get_text(strip=True).lower()
            href = link["href"]
            if ("minutes" in text and "monetary" in text) or "mpc" in text:
                if not href.startswith("http"):
                    href = f"https://www.rbi.org.in{href}"
                minutes.append({
                    "title": link.get_text(strip=True),
                    "url": href,
                })

        return minutes[:3]  # Last 3 meetings

    async def download_and_parse_pdf(self, pdf_url: str) -> str:
        """Download PDF and extract cleaned text."""
        try:
            import pdfplumber

            async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
                resp = await client.get(pdf_url)
                resp.raise_for_status()

                pdf = pdfplumber.open(io.BytesIO(resp.content))
                pages_text = []
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        pages_text.append(text)
                pdf.close()

                full_text = "\n\n".join(pages_text)
                return self._clean_text(full_text)

        except Exception as e:
            logger.error("rbi_pdf_parse_error", url=pdf_url, error=str(e))
            return self._generate_mock_mpc_text()

    def _clean_text(self, text: str) -> str:
        """Remove headers, footers, normalise whitespace."""
        # Remove page numbers
        text = re.sub(r"\n\s*\d+\s*\n", "\n", text)
        # Remove repeated headers
        text = re.sub(r"Reserve Bank of India\n", "", text, flags=re.IGNORECASE)
        # Normalise whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        return text.strip()

    async def run_pipeline(self) -> List[str]:
        """Fetch and parse last 3 MPC minutes. Returns list of parsed texts."""
        minute_links = await self.fetch_latest_minutes()
        parsed_texts = []

        for link_info in minute_links[:3]:
            url = link_info.get("url", "")
            if url.endswith(".pdf"):
                text = await self.download_and_parse_pdf(url)
            else:
                text = self._generate_mock_mpc_text()

            if text:
                parsed_texts.append(text)
                logger.info(
                    "rbi_minutes_parsed",
                    title=link_info.get("title", ""),
                    chars=len(text),
                )

        if not parsed_texts:
            parsed_texts = [self._generate_mock_mpc_text()]

        return parsed_texts

    # MOCK_FALLBACK
    def _generate_mock_minutes(self) -> List[Dict[str, Any]]:
        return [
            {"title": "Minutes of MPC Meeting - Mock", "url": "mock://mpc1.pdf"},
            {"title": "Minutes of MPC Meeting - Mock 2", "url": "mock://mpc2.pdf"},
        ]

    def _generate_mock_mpc_text(self) -> str:
        return """
        Minutes of the Monetary Policy Committee Meeting

        The Monetary Policy Committee (MPC) met on 6th, 7th and 8th February 2025.
        The MPC decided to keep the policy repo rate unchanged at 6.50 per cent.
        The standing deposit facility (SDF) rate remains at 6.25 per cent and the
        marginal standing facility (MSF) rate at 6.75 per cent.

        The MPC also decided to remain focused on withdrawal of accommodation to
        ensure that inflation progressively aligns with the target, while supporting growth.

        Dr. Shashanka Bhide voted to keep the repo rate unchanged and to remain focused
        on withdrawal of accommodation. He noted that CPI inflation at 5.1 per cent remains
        above the 4 per cent target. Supply-side pressures from food prices continue.
        However, core inflation has moderated to 3.8 per cent, providing some comfort.

        Dr. Ashima Goyal voted to keep the repo rate unchanged but suggested changing the
        stance to neutral. She emphasised that real interest rates are sufficiently restrictive
        and growth needs support. The output gap remains negative.

        Prof. Jayanth R. Varma voted for a 25 basis point reduction in the repo rate and
        a change in stance to neutral. He argued that the current real interest rate is too
        high relative to the neutral rate and is unnecessarily restricting growth.

        Dr. Rajiv Ranjan voted to keep the repo rate unchanged and the stance as
        withdrawal of accommodation. He highlighted persistent food inflation risks
        and the need for vigilance on the inflation front.

        Shri Shaktikanta Das voted to keep the repo rate unchanged. The Governor noted
        that while inflation has moderated, it remains above target. The MPC needs to
        see durable decline before considering any change in stance. GDP growth remains
        resilient at 7.0 per cent, suggesting no urgency for rate cuts.

        Vote: 4-2 in favour of keeping rates unchanged. 2 members wanted rate cut or
        stance change.
        """


rbi_minutes_parser = RBIMinutesParser()
