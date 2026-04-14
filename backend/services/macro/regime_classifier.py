# ARCHITECTURE NOTE:
# The regime classifier combines rule-based heuristics (40% weight)
# with LLM analysis of MPC minutes (60% weight). A noise filter
# requires 2 consecutive identical classifications before committing
# a regime change. This prevents spurious regime flips from transient data.

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import structlog

from backend.config import MacroRegime, settings
from backend.db.timescale_client import db
from backend.models.signal_models import RegimeScore

logger = structlog.get_logger(__name__)

# Noise filter state
_last_classification: Optional[str] = None
_consecutive_count: int = 0


def classify_rule_based(macro_data: Dict[str, Any]) -> MacroRegime:
    """Rule-based regime classification from macro indicators."""
    cfg = settings.regime

    repo_delta_3m = macro_data.get("repo_rate_delta_3m", 0.0)
    cpi_yoy = macro_data.get("cpi_yoy", 4.0)
    yield_slope = macro_data.get("yield_curve_slope", 0.5)
    nifty_vix = macro_data.get("nifty_vix", 15.0)

    # Crisis check first
    if nifty_vix > cfg.vix_crisis_threshold:
        return MacroRegime.CRISIS_LIQUIDITY

    # Hiking cycle
    if repo_delta_3m > 0:
        return MacroRegime.HAWKISH_TIGHTENING

    # Cutting cycle
    if repo_delta_3m < 0:
        if cpi_yoy < cfg.cpi_target:
            return MacroRegime.DOVISH_EASING
        return MacroRegime.DOVISH_PAUSE

    # Paused — determine bias from CPI
    if cpi_yoy > cfg.cpi_upper_band:
        return MacroRegime.HAWKISH_TIGHTENING
    elif cpi_yoy > cfg.cpi_target + 0.5:
        return MacroRegime.HAWKISH_PAUSE
    elif cpi_yoy < cfg.cpi_target - 0.5:
        return MacroRegime.DOVISH_PAUSE
    else:
        return MacroRegime.NEUTRAL_WATCHFUL


def blend_regimes(
    rule_regime: MacroRegime,
    llm_regime: Optional[MacroRegime],
    llm_confidence: float = 0.5,
) -> MacroRegime:
    """Blend rule-based and LLM regime with configurable weights."""
    if llm_regime is None:
        return rule_regime

    cfg = settings.regime

    # If both agree, high confidence
    if rule_regime == llm_regime:
        return rule_regime

    # Use LLM if its confidence is high enough
    if llm_confidence > 0.75:
        return llm_regime

    # Default: weight-based — if LLM weight is dominant, prefer LLM
    if cfg.llm_weight > cfg.rule_weight:
        return llm_regime

    return rule_regime


def apply_noise_filter(regime: MacroRegime) -> Optional[MacroRegime]:
    """Require 2 consecutive identical classifications before committing."""
    global _last_classification, _consecutive_count

    regime_str = regime.value

    if regime_str == _last_classification:
        _consecutive_count += 1
    else:
        _last_classification = regime_str
        _consecutive_count = 1

    if _consecutive_count >= settings.regime.noise_filter_confirmations:
        return regime

    logger.info(
        "regime_noise_filter",
        candidate=regime_str,
        count=_consecutive_count,
        needed=settings.regime.noise_filter_confirmations,
    )
    return None


async def run_regime_classification(
    macro_data: Dict[str, Any],
    llm_score: Optional[RegimeScore] = None,
) -> Optional[str]:
    """
    Full classification pipeline:
    1. Rule-based classification
    2. Blend with LLM score
    3. Apply noise filter
    4. Store in DB if confirmed
    """
    # Step 1: Rule-based
    rule_regime = classify_rule_based(macro_data)
    logger.info("regime_rule_based", regime=rule_regime.value)

    # Step 2: Blend
    llm_regime = None
    llm_confidence = 0.5
    if llm_score:
        try:
            llm_regime = MacroRegime(llm_score.regime)
            llm_confidence = llm_score.confidence
        except ValueError:
            logger.warning("regime_llm_invalid", value=llm_score.regime)

    final_regime = blend_regimes(rule_regime, llm_regime, llm_confidence)
    logger.info(
        "regime_blended",
        rule=rule_regime.value,
        llm=llm_regime.value if llm_regime else None,
        final=final_regime.value,
    )

    # Step 3: Noise filter
    confirmed = apply_noise_filter(final_regime)

    if confirmed is None:
        return None  # Not yet confirmed

    # Step 4: Store
    try:
        await db.insert_regime({
            "time": datetime.now(timezone.utc),
            "regime": confirmed.value,
            "confidence": llm_confidence if llm_score else 0.5,
            "repo_rate": macro_data.get("repo_rate"),
            "cpi_yoy": macro_data.get("cpi_yoy"),
            "wpi_yoy": macro_data.get("wpi_yoy"),
            "gsec_10y": macro_data.get("gsec_10y"),
            "gsec_2y": macro_data.get("gsec_2y"),
            "yield_curve_slope": macro_data.get("yield_curve_slope"),
            "usd_inr": macro_data.get("usd_inr"),
            "nifty_vix": macro_data.get("nifty_vix"),
            "llm_regime_score": llm_score.model_dump() if llm_score else None,
            "rule_based_regime": rule_regime.value,
            "llm_regime": llm_regime.value if llm_regime else None,
            "final_regime": confirmed.value,
        })
        logger.info("regime_committed", regime=confirmed.value)
    except Exception as e:
        logger.error("regime_store_error", error=str(e))

    return confirmed.value
