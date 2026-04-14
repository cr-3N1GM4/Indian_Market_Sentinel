# ARCHITECTURE NOTE:
# Runs 5 predefined stress scenarios against portfolio holdings.
# Each scenario applies sector-specific betas/sensitivities to
# estimate P&L impact. Uses mock betas when historical data unavailable.

from __future__ import annotations

import random
from typing import Any, Dict, List

import structlog

from backend.config import settings
from backend.models.portfolio_models import StressScenarioResult, StressTestResponse

logger = structlog.get_logger(__name__)

# Sector-specific sensitivities (mock betas)
SECTOR_BETAS = {
    "Energy": {"rate_beta": -0.8, "inr_beta": -0.5, "crude_beta": 1.2, "fii_beta": -1.0, "supply_beta": -0.3},
    "Pharma": {"rate_beta": -0.5, "inr_beta": 0.4, "crude_beta": -0.3, "fii_beta": -0.8, "supply_beta": -1.5},
    "Textile": {"rate_beta": -0.6, "inr_beta": 0.6, "crude_beta": -0.4, "fii_beta": -0.7, "supply_beta": -0.8},
    "Other": {"rate_beta": -0.5, "inr_beta": -0.2, "crude_beta": 0.0, "fii_beta": -0.6, "supply_beta": -0.2},
}


class StressTester:
    """Runs scenario stress tests against portfolio holdings."""

    def run_stress_test(
        self,
        holdings: List[Dict[str, Any]],
        watchlist_meta: Dict[str, Any] = None,
    ) -> StressTestResponse:
        """Run all 5 stress scenarios. Returns P&L impact per scenario."""
        meta = watchlist_meta or {}
        total_value = sum(
            h["quantity"] * h.get("current_price", h["avg_cost"])
            for h in holdings
        )

        scenarios = [
            self._rbi_hike(holdings, meta),
            self._inr_depreciation(holdings, meta),
            self._crude_shock(holdings, meta),
            self._fii_exodus(holdings, meta),
            self._china_supply_chain(holdings, meta),
        ]

        return StressTestResponse(
            scenarios=scenarios,
            total_portfolio_value=round(total_value, 2),
        )

    def _rbi_hike(self, holdings, meta) -> StressScenarioResult:
        shock = settings.stress.rbi_hike_bps / 100
        impacts = []
        for h in holdings:
            sector = settings.sectors.get_sector(h["ticker"])
            beta = SECTOR_BETAS.get(sector, SECTOR_BETAS["Other"])["rate_beta"]
            value = h["quantity"] * h.get("current_price", h["avg_cost"])
            pnl = value * beta * shock / 100
            impacts.append((h["ticker"], pnl, pnl / value * 100 if value else 0))

        total_pnl = sum(i[1] for i in impacts)
        total_val = sum(h["quantity"] * h.get("current_price", h["avg_cost"]) for h in holdings)
        worst = min(impacts, key=lambda x: x[1])

        return StressScenarioResult(
            scenario_name="RBI Emergency Hike +50bps",
            description="RBI raises repo rate by 50 basis points in emergency meeting",
            portfolio_pnl_inr=round(total_pnl, 2),
            portfolio_pnl_pct=round(total_pnl / total_val * 100, 2) if total_val else 0,
            most_affected_ticker=worst[0],
            most_affected_pnl_pct=round(worst[2], 2),
        )

    def _inr_depreciation(self, holdings, meta) -> StressScenarioResult:
        shock = settings.stress.inr_depreciation_pct
        impacts = []
        for h in holdings:
            sector = settings.sectors.get_sector(h["ticker"])
            beta = SECTOR_BETAS.get(sector, SECTOR_BETAS["Other"])["inr_beta"]
            value = h["quantity"] * h.get("current_price", h["avg_cost"])
            pnl = value * beta * shock / 100
            impacts.append((h["ticker"], pnl, pnl / value * 100 if value else 0))

        total_pnl = sum(i[1] for i in impacts)
        total_val = sum(h["quantity"] * h.get("current_price", h["avg_cost"]) for h in holdings)
        worst = min(impacts, key=lambda x: x[1])

        return StressScenarioResult(
            scenario_name="INR Depreciates 5% vs USD",
            description="Rupee weakens 5% against the US dollar",
            portfolio_pnl_inr=round(total_pnl, 2),
            portfolio_pnl_pct=round(total_pnl / total_val * 100, 2) if total_val else 0,
            most_affected_ticker=worst[0],
            most_affected_pnl_pct=round(worst[2], 2),
        )

    def _crude_shock(self, holdings, meta) -> StressScenarioResult:
        shock = settings.stress.crude_shock_pct
        impacts = []
        for h in holdings:
            sector = settings.sectors.get_sector(h["ticker"])
            beta = SECTOR_BETAS.get(sector, SECTOR_BETAS["Other"])["crude_beta"]
            value = h["quantity"] * h.get("current_price", h["avg_cost"])
            pnl = value * beta * shock / 100
            impacts.append((h["ticker"], pnl, pnl / value * 100 if value else 0))

        total_pnl = sum(i[1] for i in impacts)
        total_val = sum(h["quantity"] * h.get("current_price", h["avg_cost"]) for h in holdings)
        worst = min(impacts, key=lambda x: x[1])

        return StressScenarioResult(
            scenario_name="Crude Oil +20%",
            description="Brent crude rises 20% due to geopolitical shock",
            portfolio_pnl_inr=round(total_pnl, 2),
            portfolio_pnl_pct=round(total_pnl / total_val * 100, 2) if total_val else 0,
            most_affected_ticker=worst[0],
            most_affected_pnl_pct=round(worst[2], 2),
        )

    def _fii_exodus(self, holdings, meta) -> StressScenarioResult:
        shock = settings.stress.fii_exodus_free_float_pct
        impacts = []
        for h in holdings:
            sector = settings.sectors.get_sector(h["ticker"])
            beta = SECTOR_BETAS.get(sector, SECTOR_BETAS["Other"])["fii_beta"]
            value = h["quantity"] * h.get("current_price", h["avg_cost"])
            pnl = value * beta * shock / 100
            impacts.append((h["ticker"], pnl, pnl / value * 100 if value else 0))

        total_pnl = sum(i[1] for i in impacts)
        total_val = sum(h["quantity"] * h.get("current_price", h["avg_cost"]) for h in holdings)
        worst = min(impacts, key=lambda x: x[1])

        return StressScenarioResult(
            scenario_name="FII Mass Exodus",
            description="FIIs sell 2% of free-float across holdings in 5 days",
            portfolio_pnl_inr=round(total_pnl, 2),
            portfolio_pnl_pct=round(total_pnl / total_val * 100, 2) if total_val else 0,
            most_affected_ticker=worst[0],
            most_affected_pnl_pct=round(worst[2], 2),
        )

    def _china_supply_chain(self, holdings, meta) -> StressScenarioResult:
        impacts = []
        for h in holdings:
            sector = settings.sectors.get_sector(h["ticker"])
            ticker_meta = meta.get(h["ticker"], {})
            api_dep = ticker_meta.get("api_import_dependency", 0.0)
            value = h["quantity"] * h.get("current_price", h["avg_cost"])

            if sector == "Pharma" and api_dep > 0.3:
                pnl = value * -api_dep * 0.15
            else:
                beta = SECTOR_BETAS.get(sector, SECTOR_BETAS["Other"])["supply_beta"]
                pnl = value * beta * 0.05
            impacts.append((h["ticker"], pnl, pnl / value * 100 if value else 0))

        total_pnl = sum(i[1] for i in impacts)
        total_val = sum(h["quantity"] * h.get("current_price", h["avg_cost"]) for h in holdings)
        worst = min(impacts, key=lambda x: x[1])

        return StressScenarioResult(
            scenario_name="China Supply Chain Disruption",
            description="Major disruption to China API/raw material supply affecting Pharma and manufacturing",
            portfolio_pnl_inr=round(total_pnl, 2),
            portfolio_pnl_pct=round(total_pnl / total_val * 100, 2) if total_val else 0,
            most_affected_ticker=worst[0],
            most_affected_pnl_pct=round(worst[2], 2),
        )


stress_tester = StressTester()
