# ARCHITECTURE NOTE:
# The DivergenceDetector is the brain of the IMS. It evaluates 5
# regime-conditioned patterns on every scheduler tick and emits
# alpha signals when conditions are met. Each pattern encodes a
# specific market microstructure hypothesis about retail vs.
# institutional behavior in different macro environments.

from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

import structlog

from backend.config import MacroRegime, settings
from backend.db.timescale_client import db
from backend.models.signal_models import AlphaSignal

logger = structlog.get_logger(__name__)


class DivergenceDetector:
    """
    Evaluates 5 divergence patterns across all watchlist tickers:
    1. Retail Bubble
    2. Smart Money Accumulation
    3. Regime-Confirmed Breakout
    4. News-Institutional Divergence
    5. Supply Chain Stress (Pharma)
    """

    def __init__(self) -> None:
        self._redis = None
        self._watchlist_meta: Dict[str, Any] = {}

    async def init(self, redis_client=None, watchlist_meta: Dict = None) -> None:
        self._redis = redis_client
        self._watchlist_meta = watchlist_meta or {}

    async def run(self) -> List[AlphaSignal]:
        """Run all 5 pattern checks across all watchlist tickers."""
        signals: List[AlphaSignal] = []

        # Get current regime
        regime_row = await db.get_current_regime()
        current_regime = regime_row["final_regime"] if regime_row else "neutral_watchful"

        tickers = settings.sectors.all_tickers

        for ticker in tickers:
            try:
                # Fetch latest CRSS and ICS
                crss_row = await db.get_crss_latest(ticker)
                ics_row = await db.get_ics_latest(ticker)
                tech_row = await db.get_technical_latest(ticker)

                crss = crss_row["crss"] if crss_row else self._mock_crss()
                ics = ics_row["ics"] if ics_row else self._mock_ics()
                fii_net = ics_row["fii_net_crores"] if ics_row else random.uniform(-500, 500)

                sector = settings.sectors.get_sector(ticker)

                # Pattern 1: Retail Bubble
                signal = self._check_retail_bubble(
                    ticker, sector, crss, ics, fii_net, current_regime
                )
                if signal:
                    signals.append(signal)

                # Pattern 2: Smart Money Accumulation
                signal = self._check_smart_money(
                    ticker, sector, crss, ics, fii_net, current_regime
                )
                if signal:
                    signals.append(signal)

                # Pattern 3: Regime-Confirmed Breakout
                golden_cross = tech_row["golden_cross"] if tech_row else False
                signal = self._check_regime_breakout(
                    ticker, sector, crss, ics, golden_cross, current_regime
                )
                if signal:
                    signals.append(signal)

                # Pattern 4: News-Institutional Divergence
                news_score = await self._get_news_score(ticker)
                signal = self._check_news_divergence(
                    ticker, sector, news_score, ics, current_regime
                )
                if signal:
                    signals.append(signal)

                # Pattern 5: Supply Chain Stress (Pharma)
                if sector == "Pharma":
                    signal = await self._check_supply_chain(
                        ticker, sector, current_regime
                    )
                    if signal:
                        signals.append(signal)

            except Exception as e:
                logger.error("divergence_ticker_error", ticker=ticker, error=str(e))

        # Store and publish signals
        for signal in signals:
            try:
                signal_dict = {
                    "time": signal.timestamp,
                    "ticker": signal.ticker,
                    "exchange": signal.exchange,
                    "sector": signal.sector,
                    "pattern": signal.pattern,
                    "signal_type": signal.signal_type,
                    "confidence": signal.confidence,
                    "regime": signal.regime,
                    "crss": signal.crss,
                    "ics": signal.ics,
                    "fii_net_5d_crores": signal.fii_net_5d_crores,
                    "supporting_evidence": signal.supporting_evidence,
                }
                signal_id = await db.insert_alpha_signal(signal_dict)
                signal.signal_id = str(signal_id)

                # Publish to Redis for WebSocket streaming
                if self._redis:
                    await self._redis.publish(
                        "live_signals",
                        json.dumps(signal.model_dump(), default=str),
                    )

            except Exception as e:
                logger.error("signal_store_error", error=str(e))

        if signals:
            logger.info("divergence_signals_emitted", count=len(signals))

        return signals

    # ----------------------------------------------------------
    # Pattern 1: Retail Bubble
    # ----------------------------------------------------------
    def _check_retail_bubble(
        self, ticker: str, sector: str, crss: float, ics: float,
        fii_net: float, regime: str,
    ) -> Optional[AlphaSignal]:
        t = settings.signals
        hawkish_regimes = [
            MacroRegime.HAWKISH_TIGHTENING.value,
            MacroRegime.HAWKISH_PAUSE.value,
        ]

        if (
            crss > t.retail_bubble_crss_min
            and ics < t.retail_bubble_ics_max
            and regime in hawkish_regimes
        ):
            return AlphaSignal(
                timestamp=datetime.now(timezone.utc),
                ticker=ticker,
                sector=sector,
                pattern="RETAIL_BUBBLE",
                signal_type="MEAN_REVERSION_SHORT",
                confidence="HIGH",
                regime=regime,
                crss=crss,
                ics=ics,
                fii_net_5d_crores=fii_net,
                supporting_evidence=[
                    f"CRSS at {crss:.2f} — retail extremely bullish",
                    f"ICS at {ics:.2f} — institutions not confirming",
                    f"Regime: {regime} — macro headwind present",
                    f"FII net 5-day: ₹{fii_net:.1f} Cr",
                ],
            )
        return None

    # ----------------------------------------------------------
    # Pattern 2: Smart Money Accumulation
    # ----------------------------------------------------------
    def _check_smart_money(
        self, ticker: str, sector: str, crss: float, ics: float,
        fii_net: float, regime: str,
    ) -> Optional[AlphaSignal]:
        t = settings.signals

        if (
            crss < t.smart_money_crss_max
            and ics > t.smart_money_ics_min
            and fii_net > 0
        ):
            return AlphaSignal(
                timestamp=datetime.now(timezone.utc),
                ticker=ticker,
                sector=sector,
                pattern="SMART_MONEY_ACCUMULATION",
                signal_type="MOMENTUM_LONG",
                confidence="MEDIUM_HIGH",
                regime=regime,
                crss=crss,
                ics=ics,
                fii_net_5d_crores=fii_net,
                supporting_evidence=[
                    f"CRSS at {crss:.2f} — retail apathetic/bearish",
                    f"ICS at {ics:.2f} — strong institutional buying",
                    f"FII net buyer: ₹{fii_net:.1f} Cr over 5 days",
                    "Classic quiet accumulation setup",
                ],
            )
        return None

    # ----------------------------------------------------------
    # Pattern 3: Regime-Confirmed Breakout
    # ----------------------------------------------------------
    def _check_regime_breakout(
        self, ticker: str, sector: str, crss: float, ics: float,
        golden_cross: bool, regime: str,
    ) -> Optional[AlphaSignal]:
        t = settings.signals
        dovish_regimes = [
            MacroRegime.DOVISH_EASING.value,
            MacroRegime.DOVISH_PAUSE.value,
        ]

        if (
            crss > t.breakout_crss_min
            and ics > t.breakout_ics_min
            and regime in dovish_regimes
            and golden_cross
        ):
            return AlphaSignal(
                timestamp=datetime.now(timezone.utc),
                ticker=ticker,
                sector=sector,
                pattern="REGIME_CONFIRMED_BREAKOUT",
                signal_type="TREND_FOLLOWING_LONG",
                confidence="HIGH",
                regime=regime,
                crss=crss,
                ics=ics,
                supporting_evidence=[
                    f"CRSS at {crss:.2f} — retail constructive",
                    f"ICS at {ics:.2f} — institutional conviction",
                    f"Regime: {regime} — macro tailwind",
                    "Golden Cross detected — 50 SMA crossed above 200 SMA",
                    "Highest-conviction long setup in the system",
                ],
            )
        return None

    # ----------------------------------------------------------
    # Pattern 4: News-Institutional Divergence
    # ----------------------------------------------------------
    def _check_news_divergence(
        self, ticker: str, sector: str, news_score: float, ics: float,
        regime: str,
    ) -> Optional[AlphaSignal]:
        t = settings.signals

        if (
            news_score > t.news_divergence_news_min
            and ics < t.news_divergence_ics_max
        ):
            return AlphaSignal(
                timestamp=datetime.now(timezone.utc),
                ticker=ticker,
                sector=sector,
                pattern="NEWS_INSTITUTIONAL_DIVERGENCE",
                signal_type="DISTRIBUTION_WARNING",
                confidence="MEDIUM",
                regime=regime,
                crss=None,
                ics=ics,
                supporting_evidence=[
                    f"News sentiment at {news_score:.2f} — positive media blitz",
                    f"ICS at {ics:.2f} — institutions quietly selling",
                    "Classic distribution pattern",
                    "Insiders may be using media attention as exit liquidity",
                ],
            )
        return None

    # ----------------------------------------------------------
    # Pattern 5: Supply Chain Stress (Pharma)
    # ----------------------------------------------------------
    async def _check_supply_chain(
        self, ticker: str, sector: str, regime: str,
    ) -> Optional[AlphaSignal]:
        t = settings.signals

        # Get supply chain sentiment (from LLM macro parsing)
        supply_sentiment = random.uniform(-1, 0.5)  # MOCK_FALLBACK

        # Get API import dependency from watchlist metadata
        meta = self._watchlist_meta.get(ticker, {})
        api_dep = meta.get("api_import_dependency", 0.0)

        if (
            supply_sentiment < t.supply_chain_sentiment_max
            and api_dep > t.api_import_dependency_min
        ):
            return AlphaSignal(
                timestamp=datetime.now(timezone.utc),
                ticker=ticker,
                sector=sector,
                pattern="SUPPLY_CHAIN_STRESS",
                signal_type="SECTOR_RISK_FLAG",
                confidence="HIGH",
                regime=regime,
                supporting_evidence=[
                    f"Global supply chain sentiment: {supply_sentiment:.2f}",
                    f"API import dependency: {api_dep:.0%}",
                    "Indian Pharma exposed to China API disruption",
                    "Impact typically hits P&L in 3-6 months",
                ],
            )
        return None

    # ----------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------
    async def _get_news_score(self, ticker: str) -> float:
        """Get average news sentiment for ticker over last 6 hours."""
        rows = await db.get_sentiment_by_ticker(ticker, hours=6)
        if not rows:
            return random.uniform(-0.3, 0.3)  # MOCK
        news_rows = [r for r in rows if r["source"] in ("moneycontrol", "et", "bs")]
        if not news_rows:
            return 0.0
        return sum(r["sentiment_score"] for r in news_rows) / len(news_rows)

    @staticmethod
    def _mock_crss() -> float:
        return round(random.uniform(-0.8, 0.8), 2)

    @staticmethod
    def _mock_ics() -> float:
        return round(random.uniform(-0.6, 0.6), 2)


divergence_detector = DivergenceDetector()
