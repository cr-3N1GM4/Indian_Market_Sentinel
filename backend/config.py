# ARCHITECTURE NOTE:
# All tuneable parameters live here as typed dataclasses. Service files
# import from this module instead of hardcoding magic numbers. The operator
# can adjust sensitivity without touching any business logic code.
# Alternative considered: YAML config file — rejected because dataclasses
# give us IDE autocomplete, type safety, and validation for free.

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import List


# ------------------------------------------------------------------
# Macro Regime Enum — central definition used by classifier + UI
# ------------------------------------------------------------------
class MacroRegime(str, Enum):
    HAWKISH_TIGHTENING = "hawkish_tightening"
    HAWKISH_PAUSE = "hawkish_pause"
    NEUTRAL_WATCHFUL = "neutral_watchful"
    DOVISH_PAUSE = "dovish_pause"
    DOVISH_EASING = "dovish_easing"
    CRISIS_LIQUIDITY = "crisis_liquidity"


# ------------------------------------------------------------------
# Sentiment Weights
# ------------------------------------------------------------------
@dataclass(frozen=True)
class SentimentWeights:
    """Weights for combining VADER + FinBERT and source-level CRSS."""
    vader_weight: float = 0.4
    finbert_weight: float = 0.6

    # CRSS source weights (must sum to 1.0)
    twitter_weight: float = 0.35
    reddit_weight: float = 0.30
    news_weight: float = 0.35

    # Z-score normalisation window (trading days)
    zscore_window_days: int = 30


# ------------------------------------------------------------------
# Divergence / Alpha Signal Thresholds
# ------------------------------------------------------------------
@dataclass(frozen=True)
class SignalThresholds:
    # Pattern 1 — Retail Bubble
    retail_bubble_crss_min: float = 0.70
    retail_bubble_ics_max: float = 0.20

    # Pattern 2 — Smart Money Accumulation
    smart_money_crss_max: float = 0.0
    smart_money_ics_min: float = 0.60

    # Pattern 3 — Regime-Confirmed Breakout
    breakout_crss_min: float = 0.50
    breakout_ics_min: float = 0.50
    golden_cross_lookback_days: int = 5

    # Pattern 4 — News-Institutional Divergence
    news_divergence_news_min: float = 0.60
    news_divergence_ics_max: float = -0.30

    # Pattern 5 — Supply Chain Stress (Pharma)
    supply_chain_sentiment_max: float = -0.50
    api_import_dependency_min: float = 0.40

    # Buyback opportunity thresholds
    buyback_premium_min_pct: float = 20.0
    buyback_size_min_pct_mcap: float = 2.0

    # ICS computation
    ics_net_volume_window_days: int = 5
    ics_avg_volume_window_days: int = 20
    ics_clip_min: float = -1.0
    ics_clip_max: float = 1.0

    # Free-float alert threshold
    free_float_alert_pct: float = 0.5


# ------------------------------------------------------------------
# Regime Classifier Config
# ------------------------------------------------------------------
@dataclass(frozen=True)
class RegimeConfig:
    rule_weight: float = 0.40
    llm_weight: float = 0.60
    noise_filter_confirmations: int = 2

    # Rule-based thresholds
    cpi_target: float = 4.0
    cpi_upper_band: float = 6.0
    vix_crisis_threshold: float = 30.0

    # Yield curve
    yield_curve_inversion_threshold: float = 0.0


# ------------------------------------------------------------------
# Technical Indicator Parameters
# ------------------------------------------------------------------
@dataclass(frozen=True)
class TechnicalConfig:
    sma_short: int = 50
    sma_long: int = 200
    rsi_period: int = 14
    rsi_overbought: float = 70.0
    rsi_oversold: float = 30.0
    bb_period: int = 20
    bb_std: float = 2.0
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    volume_spike_ratio: float = 2.0
    supertrend_atr_period: int = 10
    supertrend_multiplier: float = 3.0


# ------------------------------------------------------------------
# Result Analyzer Scoring
# ------------------------------------------------------------------
@dataclass(frozen=True)
class ResultScoringConfig:
    revenue_yoy_bullish_pct: float = 15.0
    pat_yoy_bullish_pct: float = 20.0
    ebitda_margin_expansion_bps: float = 100.0
    eps_beat_pct: float = 5.0
    revenue_miss_pct: float = 3.0
    ebitda_margin_compression_bps: float = 150.0
    promoter_decrease_pct: float = 1.0


# ------------------------------------------------------------------
# Vulnerability Mapper
# ------------------------------------------------------------------
@dataclass(frozen=True)
class VulnerabilityConfig:
    correlation_low: float = 0.3
    correlation_high: float = 0.5
    fii_holding_high_pct: float = 40.0
    fii_holding_medium_pct: float = 25.0
    fii_selling_lookback_days: int = 10
    earnings_risk_high_days: int = 5
    earnings_risk_medium_days: int = 15
    correlation_window_days: int = 252


# ------------------------------------------------------------------
# Stress Test Scenarios
# ------------------------------------------------------------------
@dataclass(frozen=True)
class StressScenarios:
    rbi_hike_bps: float = 50.0
    inr_depreciation_pct: float = 5.0
    crude_shock_pct: float = 20.0
    fii_exodus_free_float_pct: float = 2.0


# ------------------------------------------------------------------
# Scheduler Timing (IST)
# ------------------------------------------------------------------
@dataclass(frozen=True)
class SchedulerConfig:
    sentiment_interval_minutes: int = 15
    bulk_block_hour: int = 18
    fii_dii_hour: int = 19
    corporate_actions_hour: int = 8
    macro_day_of_week: str = "mon"
    macro_hour: int = 7
    regime_hour: int = 8
    divergence_interval_minutes: int = 15
    pre_event_hour: int = 9


# ------------------------------------------------------------------
# External API / Resilience
# ------------------------------------------------------------------
@dataclass(frozen=True)
class ResilienceConfig:
    max_retries: int = 3
    backoff_base_seconds: float = 1.0
    backoff_max_seconds: float = 60.0
    circuit_breaker_threshold: int = 5
    circuit_breaker_reset_seconds: float = 60.0
    redis_cache_ttl_seconds: int = 3600
    nse_session_timeout: int = 30


# ------------------------------------------------------------------
# Sector Definitions
# ------------------------------------------------------------------
@dataclass(frozen=True)
class SectorConfig:
    energy_tickers: List[str] = field(default_factory=lambda: [
        "RELIANCE", "ONGC", "NTPC", "BPCL", "IOC", "GAIL",
        "ADANIGREEN", "TATAPOWER", "POWERGRID", "COALINDIA"
    ])
    pharma_tickers: List[str] = field(default_factory=lambda: [
        "SUNPHARMA", "DRREDDY", "CIPLA", "AUROPHARMA", "DIVISLAB",
        "BIOCON", "LUPIN", "TORNTPHARM", "ALKEM", "IPCALAB"
    ])
    textile_tickers: List[str] = field(default_factory=lambda: [
        "PAGEIND", "WELSPUNLIV", "ARVIND", "RAYMOND", "TRIDENT",
        "VARDHMAN", "KITEX", "GOKEX", "NITIRAJ", "SIYARAM"
    ])

    def get_sector(self, ticker: str) -> str:
        if ticker in self.energy_tickers:
            return "Energy"
        elif ticker in self.pharma_tickers:
            return "Pharma"
        elif ticker in self.textile_tickers:
            return "Textile"
        return "Other"

    @property
    def all_tickers(self) -> List[str]:
        return self.energy_tickers + self.pharma_tickers + self.textile_tickers


# ------------------------------------------------------------------
# Twitter Search Keywords by Sector
# ------------------------------------------------------------------
@dataclass(frozen=True)
class TwitterKeywords:
    energy: List[str] = field(default_factory=lambda: [
        "$RELIANCE", "$ONGC", "$NTPC", "$BPCL", "$IOC", "#IndianEnergy"
    ])
    pharma: List[str] = field(default_factory=lambda: [
        "$SUNPHARMA", "$DRREDDY", "$CIPLA", "$AUROPHARMA", "#IndianPharma"
    ])
    textile: List[str] = field(default_factory=lambda: [
        "$PAGEIND", "$WELSPUN", "$ARVIND", "#IndianTextile"
    ])
    broad_market: List[str] = field(default_factory=lambda: [
        "#NSE", "#BSE", "#Nifty50", "#IndianStocks", "#DalalStreet"
    ])


# ------------------------------------------------------------------
# Reddit Config
# ------------------------------------------------------------------
@dataclass(frozen=True)
class RedditConfig:
    subreddits: List[str] = field(default_factory=lambda: [
        "IndiaInvestments", "IndianStreetBets", "DalalStreet",
        "NSEbets", "SecurityAnalysis"
    ])
    comment_depth: int = 2
    hype_velocity_multiplier: float = 3.0


# ------------------------------------------------------------------
# LLM Config
# ------------------------------------------------------------------
@dataclass(frozen=True)
class LLMConfig:
    primary_model: str = "claude-sonnet-4-20250514"
    fallback_model: str = "gpt-4o-mini"
    max_tokens: int = 4096
    temperature: float = 0.1
    news_batch_size: int = 10
    regime_cache_ttl_seconds: int = 3600
    daily_token_budget: int = 500_000


# ------------------------------------------------------------------
# Pre-Event Alert Severity
# ------------------------------------------------------------------
class AlertSeverity(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


# ------------------------------------------------------------------
# Master Settings — single import point
# ------------------------------------------------------------------
@dataclass
class IMSConfig:
    sentiment: SentimentWeights = field(default_factory=SentimentWeights)
    signals: SignalThresholds = field(default_factory=SignalThresholds)
    regime: RegimeConfig = field(default_factory=RegimeConfig)
    technical: TechnicalConfig = field(default_factory=TechnicalConfig)
    result_scoring: ResultScoringConfig = field(default_factory=ResultScoringConfig)
    vulnerability: VulnerabilityConfig = field(default_factory=VulnerabilityConfig)
    stress: StressScenarios = field(default_factory=StressScenarios)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    resilience: ResilienceConfig = field(default_factory=ResilienceConfig)
    sectors: SectorConfig = field(default_factory=SectorConfig)
    twitter_keywords: TwitterKeywords = field(default_factory=TwitterKeywords)
    reddit: RedditConfig = field(default_factory=RedditConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)

    # Environment-sourced values
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            "postgresql://ims:password@localhost:5432/ims_db"
        )
    )
    redis_url: str = field(
        default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379")
    )


# Singleton instance
settings = IMSConfig()
