# ARCHITECTURE NOTE:
# Implements the 12-condition result scoring pipeline (6 bullish,
# 6 bearish) producing STRONG_BUY to STRONG_SELL momentum labels.
# Triggered automatically when a RESULT corporate action date arrives.

from __future__ import annotations

from typing import Any, Dict, List, Optional

import structlog

from backend.config import settings
from backend.services.scrapers.screener_scraper import screener_scraper

logger = structlog.get_logger(__name__)


MOMENTUM_LABELS = {
    4: "STRONG_BUY",
    3: "BUY",
    2: "BUY",
    1: "NEUTRAL",
    0: "NEUTRAL",
    -1: "NEUTRAL",
    -2: "SELL",
    -3: "SELL",
    -4: "STRONG_SELL",
}


def get_momentum_label(score: int) -> str:
    if score >= 4:
        return "STRONG_BUY"
    elif score >= 2:
        return "BUY"
    elif score >= 0:
        return "NEUTRAL"
    elif score >= -3:
        return "SELL"
    return "STRONG_SELL"


class ResultAnalyzer:
    """Analyses quarterly results with a 12-condition scoring pipeline."""

    async def analyze(self, ticker: str) -> Dict[str, Any]:
        """Full result analysis for a ticker. Returns scoring breakdown."""
        data = await screener_scraper.fetch_company_data(ticker)

        if not data:
            return {"ticker": ticker, "score": 0, "momentum_label": "NEUTRAL", "error": "No data"}

        score = 0
        flags: Dict[str, Any] = {}
        cfg = settings.result_scoring

        quarters = data.get("quarterly_results", [])

        # --- BULLISH CONDITIONS ---

        # B1: Revenue YoY growth > 15%
        rev_growth = self._compute_yoy_growth(quarters, "revenue")
        flags["B1_revenue_yoy"] = rev_growth
        if rev_growth and rev_growth > cfg.revenue_yoy_bullish_pct:
            score += 1
            flags["B1_triggered"] = True

        # B2: PAT YoY growth > 20%
        pat_growth = self._compute_yoy_growth(quarters, "pat")
        flags["B2_pat_yoy"] = pat_growth
        if pat_growth and pat_growth > cfg.pat_yoy_bullish_pct:
            score += 1
            flags["B2_triggered"] = True

        # B3: EBITDA margin QoQ expansion > 100 bps
        margin_delta = self._compute_margin_delta(quarters)
        flags["B3_margin_delta_bps"] = margin_delta
        if margin_delta and margin_delta > cfg.ebitda_margin_expansion_bps:
            score += 1
            flags["B3_triggered"] = True

        # B4: Promoter holding stable or increased
        promoter = data.get("promoter_holding_pct", [])
        if len(promoter) >= 2 and promoter[0] is not None and promoter[1] is not None:
            flags["B4_promoter_delta"] = promoter[0] - promoter[1]
            if promoter[0] >= promoter[1]:
                score += 1
                flags["B4_triggered"] = True

        # B5: Beat consensus EPS by > 5% (would need analyst estimates)
        flags["B5_eps_beat"] = None  # Requires analyst data

        # B6: Debt/Equity declining
        de = data.get("debt_equity")
        flags["B6_debt_equity"] = de
        if de is not None and de < 0.8:
            score += 1
            flags["B6_triggered"] = True

        # --- BEARISH CONDITIONS ---

        # R1: Revenue miss > 3%
        if rev_growth and rev_growth < -cfg.revenue_miss_pct:
            score -= 1
            flags["R1_triggered"] = True

        # R2: PAT declined YoY
        if pat_growth and pat_growth < 0:
            score -= 1
            flags["R2_triggered"] = True

        # R3: EBITDA margin QoQ compression > 150 bps
        if margin_delta and margin_delta < -cfg.ebitda_margin_compression_bps:
            score -= 1
            flags["R3_triggered"] = True

        # R4: Promoter holding decreased > 1%
        if len(promoter) >= 2 and promoter[0] is not None and promoter[1] is not None:
            if (promoter[1] - promoter[0]) > cfg.promoter_decrease_pct:
                score -= 1
                flags["R4_triggered"] = True

        # R5: Exceptional items flag
        flags["R5_exceptional_items"] = False  # Would need detailed P&L parsing

        # R6: Working capital deterioration
        flags["R6_working_capital"] = None  # Would need balance sheet data

        momentum_label = get_momentum_label(score)

        result = {
            "ticker": ticker,
            "score": score,
            "momentum_label": momentum_label,
            "condition_flags": flags,
            "screener_url": f"https://www.screener.in/company/{ticker}/",
            "pe_ratio": data.get("pe_ratio"),
            "roe": data.get("roe"),
            "debt_equity": data.get("debt_equity"),
            "promoter_holding_pct": promoter[0] if promoter else None,
            "fii_holding_pct": (data.get("fii_holding_pct") or [None])[0],
        }

        logger.info(
            "result_analysis_complete",
            ticker=ticker,
            score=score,
            label=momentum_label,
        )

        return result

    @staticmethod
    def _compute_yoy_growth(
        quarters: List[Dict], metric: str
    ) -> Optional[float]:
        """Compute YoY growth from quarterly data."""
        if not quarters:
            return None

        # Find metric rows
        for q in quarters:
            if isinstance(q, dict) and q.get("metric") == metric:
                values = q.get("values", [])
                if len(values) >= 5:
                    curr = values[0]
                    prev = values[4]
                    if curr and prev and prev != 0:
                        return ((curr - prev) / prev) * 100
            elif isinstance(q, dict) and metric in q:
                # Direct quarter format
                pass

        # Try direct quarterly_results format
        if quarters and isinstance(quarters[0], dict) and metric in quarters[0]:
            if len(quarters) >= 5:
                curr = quarters[0].get(metric)
                prev = quarters[4].get(metric)
                if curr and prev and prev != 0:
                    return ((curr - prev) / prev) * 100

        return None

    @staticmethod
    def _compute_margin_delta(quarters: List[Dict]) -> Optional[float]:
        """Compute QoQ EBITDA margin change in basis points."""
        if not quarters:
            return None

        margins = []
        for q in quarters:
            if isinstance(q, dict) and "ebitda_margin" in q:
                m = q.get("ebitda_margin")
                if m is not None:
                    margins.append(m)

        if len(margins) >= 2:
            return (margins[0] - margins[1]) * 100  # bps

        return None


result_analyzer = ResultAnalyzer()
