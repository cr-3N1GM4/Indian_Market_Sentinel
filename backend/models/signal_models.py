# ARCHITECTURE NOTE:
# Signal models serve three purposes: (1) internal data flow between
# divergence detector and DB, (2) API response serialisation, and
# (3) WebSocket message format for live signal streaming.

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class SignalPattern(str, Enum):
    RETAIL_BUBBLE = "RETAIL_BUBBLE"
    SMART_MONEY_ACCUMULATION = "SMART_MONEY_ACCUMULATION"
    REGIME_CONFIRMED_BREAKOUT = "REGIME_CONFIRMED_BREAKOUT"
    NEWS_INSTITUTIONAL_DIVERGENCE = "NEWS_INSTITUTIONAL_DIVERGENCE"
    SUPPLY_CHAIN_STRESS = "SUPPLY_CHAIN_STRESS"


class SignalType(str, Enum):
    MEAN_REVERSION_SHORT = "MEAN_REVERSION_SHORT"
    MOMENTUM_LONG = "MOMENTUM_LONG"
    TREND_FOLLOWING_LONG = "TREND_FOLLOWING_LONG"
    DISTRIBUTION_WARNING = "DISTRIBUTION_WARNING"
    SECTOR_RISK_FLAG = "SECTOR_RISK_FLAG"
    BUYBACK_OPPORTUNITY = "BUYBACK_OPPORTUNITY"


class SignalConfidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM_HIGH = "MEDIUM_HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class AlphaSignal(BaseModel):
    signal_id: Optional[str] = None
    timestamp: datetime
    ticker: str
    exchange: str = "NSE"
    sector: Optional[str] = None
    pattern: str
    signal_type: str
    confidence: str
    regime: Optional[str] = None
    crss: Optional[float] = None
    ics: Optional[float] = None
    fii_net_5d_crores: Optional[float] = None
    supporting_evidence: List[str] = []
    is_resolved: bool = False
    resolved_at: Optional[datetime] = None
    actual_return: Optional[float] = None


class TechnicalSignalRecord(BaseModel):
    time: datetime
    ticker: str
    close_price: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None
    golden_cross: bool = False
    death_cross: bool = False
    rsi_14: Optional[float] = None
    rsi_overbought: bool = False
    rsi_oversold: bool = False
    bb_upper: Optional[float] = None
    bb_lower: Optional[float] = None
    bb_squeeze: bool = False
    macd_line: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    macd_crossover: Optional[str] = None
    volume: Optional[int] = None
    volume_vs_avg20: Optional[float] = None
    supertrend_direction: Optional[str] = None
    supertrend_flip: bool = False


class TechnicalResponse(BaseModel):
    latest: Optional[TechnicalSignalRecord] = None
    history: List[TechnicalSignalRecord] = []


# ----------------------------------------------------------
# Regime Models
# ----------------------------------------------------------

class RegimeScore(BaseModel):
    regime: str
    confidence: float = Field(ge=0.0, le=1.0)
    hawkish_signals: List[str] = []
    dovish_signals: List[str] = []
    key_quote: str = ""
    rate_trajectory_6m: Literal["HIKE", "PAUSE", "CUT", "UNCERTAIN"] = "UNCERTAIN"
    liquidity_stance: Literal["TIGHT", "NEUTRAL", "LOOSE"] = "NEUTRAL"
    growth_vs_inflation_priority: Literal[
        "INFLATION_FIGHTER", "BALANCED", "GROWTH_SUPPORTER"
    ] = "BALANCED"
    committee_vote_breakdown: str = ""


class RegimeCurrentResponse(BaseModel):
    regime: str
    confidence: Optional[float] = None
    repo_rate: Optional[float] = None
    cpi_yoy: Optional[float] = None
    wpi_yoy: Optional[float] = None
    gsec_10y: Optional[float] = None
    gsec_2y: Optional[float] = None
    yield_curve_slope: Optional[float] = None
    usd_inr: Optional[float] = None
    nifty_vix: Optional[float] = None
    llm_score: Optional[RegimeScore] = None
    last_updated: Optional[datetime] = None


class RegimeHistoryRecord(BaseModel):
    time: datetime
    regime: str
    confidence: Optional[float] = None
    repo_rate: Optional[float] = None
    cpi_yoy: Optional[float] = None


# ----------------------------------------------------------
# Pre-Event Alert
# ----------------------------------------------------------

class PreEventAlert(BaseModel):
    ticker: str
    event_type: str
    event_date: str
    days_until: int
    alert_severity: str
    context: Optional[str] = None


# ----------------------------------------------------------
# Corporate Action
# ----------------------------------------------------------

class CorporateAction(BaseModel):
    id: Optional[str] = None
    ticker: str
    exchange: str = "NSE"
    action_type: str
    event_date: str
    record_date: Optional[str] = None
    ex_date: Optional[str] = None
    details: Optional[dict] = None
    result_analysis: Optional[dict] = None
    momentum_label: Optional[str] = None
    alert_sent: bool = False


# ----------------------------------------------------------
# Institutional
# ----------------------------------------------------------

class InstitutionalFlowRecord(BaseModel):
    time: datetime
    ticker: Optional[str] = None
    source: str
    entity_name: Optional[str] = None
    deal_type: Optional[str] = None
    quantity: Optional[int] = None
    price: Optional[float] = None
    value_crores: Optional[float] = None


class InstitutionalTickerResponse(BaseModel):
    ticker: str
    ics: float = 0.0
    fii_net_5d: float = 0.0
    dii_net_5d: float = 0.0
    bulk_deals_recent: List[InstitutionalFlowRecord] = []
    block_deals_recent: List[InstitutionalFlowRecord] = []


class FIIDIIFlowDay(BaseModel):
    date: str
    fii_net_crores: float = 0.0
    dii_net_crores: float = 0.0
