# ARCHITECTURE NOTE:
# Portfolio models handle the vulnerability heatmap data contracts.
# Each holding gets 5 risk dimensions scored as LOW/MEDIUM/HIGH,
# plus an overall 0-10 numeric score for the heatmap display.

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class HoldingInput(BaseModel):
    ticker: str
    quantity: int = Field(gt=0)
    avg_cost: float = Field(gt=0)


class PortfolioInput(BaseModel):
    user_id: str
    holdings: List[HoldingInput]


class MacroSensitivity(BaseModel):
    usd_inr_corr: float = 0.0
    crude_corr: float = 0.0
    gsec_10y_corr: float = 0.0
    cpi_surprise_corr: float = 0.0
    label: RiskLevel = RiskLevel.LOW


class EarningsRisk(BaseModel):
    days_to_result: Optional[int] = None
    historical_move_pct: Optional[float] = None
    implied_move_pct: Optional[float] = None
    label: RiskLevel = RiskLevel.LOW


class HoldingVulnerability(BaseModel):
    overall_vulnerability_score: float = Field(ge=0.0, le=10.0)
    overall_label: RiskLevel
    macro_sensitivity: MacroSensitivity
    supply_chain_risk: RiskLevel = RiskLevel.LOW
    fii_flight_risk: RiskLevel = RiskLevel.LOW
    earnings_risk: EarningsRisk
    technical_risk: RiskLevel = RiskLevel.LOW
    active_alerts: List[str] = []


class PortfolioAnalysisResponse(BaseModel):
    holdings_analysis: Dict[str, HoldingVulnerability]


class StressScenarioResult(BaseModel):
    scenario_name: str
    description: str
    portfolio_pnl_inr: float
    portfolio_pnl_pct: float
    most_affected_ticker: str
    most_affected_pnl_pct: float


class StressTestResponse(BaseModel):
    scenarios: List[StressScenarioResult]
    total_portfolio_value: float


class PortfolioHolding(BaseModel):
    ticker: str
    quantity: int
    avg_cost: float
    vulnerability_score: Optional[float] = None
    vulnerability_breakdown: Optional[Dict] = None
    last_updated: Optional[datetime] = None
