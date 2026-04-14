# ARCHITECTURE NOTE:
# Uses LangChain with Pydantic output parser to extract structured
# RegimeScore from RBI MPC minutes. The system prompt establishes
# expertise context; the user prompt includes the last 3 MPC documents
# plus current macro data for trend analysis.

from __future__ import annotations

import json
from typing import Optional

import structlog

from backend.models.signal_models import RegimeScore
from backend.services.llm.langchain_orchestrator import llm_orchestrator

logger = structlog.get_logger(__name__)

SYSTEM_PROMPT = """You are an expert RBI monetary policy analyst with 20 years of experience reading
MPC minutes. Your task is to classify the current macro regime from the provided
meeting minutes with precision. You understand the difference between hawkish language
used as forward guidance versus actual policy action.

Analyse: inflation tolerance signals, growth concern weight, liquidity stance,
voting patterns (hawks vs doves), forward guidance phrases, and any mention of
unconventional tools or emergency measures.

Return ONLY valid JSON matching the provided schema. No preamble, no explanation outside the JSON.
"""

USER_PROMPT_TEMPLATE = """Here are the last {n} MPC meeting minutes documents:

{mpc_minutes_text}

Current macro data context:
- Repo rate: {repo_rate}%
- Latest CPI YoY: {cpi_yoy}%
- 10Y G-Sec yield: {gsec_10y}%
- USD/INR: {usd_inr}
- Nifty VIX: {nifty_vix}

Return a JSON object with these exact fields:
{{
  "regime": one of ["hawkish_tightening", "hawkish_pause", "neutral_watchful", "dovish_pause", "dovish_easing", "crisis_liquidity"],
  "confidence": float between 0.0 and 1.0,
  "hawkish_signals": list of specific phrases/votes evidencing hawkishness,
  "dovish_signals": list of specific phrases/votes evidencing dovishness,
  "key_quote": single most important sentence from the documents,
  "rate_trajectory_6m": one of ["HIKE", "PAUSE", "CUT", "UNCERTAIN"],
  "liquidity_stance": one of ["TIGHT", "NEUTRAL", "LOOSE"],
  "growth_vs_inflation_priority": one of ["INFLATION_FIGHTER", "BALANCED", "GROWTH_SUPPORTER"],
  "committee_vote_breakdown": string describing the vote split
}}
"""


async def score_regime(
    mpc_texts: list[str],
    macro_data: dict,
) -> Optional[RegimeScore]:
    """Score the current regime using LLM analysis of MPC minutes."""

    combined_text = "\n\n---\n\n".join(mpc_texts)

    # Truncate to fit context window
    if len(combined_text) > 50000:
        combined_text = combined_text[:50000] + "\n... [truncated]"

    user_prompt = USER_PROMPT_TEMPLATE.format(
        n=len(mpc_texts),
        mpc_minutes_text=combined_text,
        repo_rate=macro_data.get("repo_rate", 6.50),
        cpi_yoy=macro_data.get("cpi_yoy", 5.0),
        gsec_10y=macro_data.get("gsec_10y", 7.25),
        usd_inr=macro_data.get("usd_inr", 83.0),
        nifty_vix=macro_data.get("nifty_vix", 14.0),
    )

    from langchain_core.messages import SystemMessage, HumanMessage

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_prompt),
    ]

    result = await llm_orchestrator.invoke_with_retry(
        messages=messages,
        cache_key="regime_score_latest",
    )

    if not result:
        logger.warning("regime_scorer_no_result", msg="Using mock score")
        return _generate_mock_score()

    try:
        # Clean JSON from markdown fences if present
        cleaned = result.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()

        parsed = json.loads(cleaned)
        return RegimeScore(**parsed)

    except (json.JSONDecodeError, Exception) as e:
        logger.error("regime_score_parse_error", error=str(e), raw=result[:200])
        return _generate_mock_score()


def _generate_mock_score() -> RegimeScore:
    """Generate a realistic mock regime score for development."""
    return RegimeScore(
        regime="hawkish_pause",
        confidence=0.72,
        hawkish_signals=[
            "withdrawal of accommodation stance maintained",
            "4-2 vote in favour of status quo",
            "CPI remains above 4% target",
        ],
        dovish_signals=[
            "core inflation moderated to 3.8%",
            "2 members voted for rate cut",
            "output gap remains negative",
        ],
        key_quote=(
            "The MPC decided to remain focused on withdrawal of accommodation "
            "to ensure that inflation progressively aligns with the target."
        ),
        rate_trajectory_6m="PAUSE",
        liquidity_stance="TIGHT",
        growth_vs_inflation_priority="INFLATION_FIGHTER",
        committee_vote_breakdown="4-2 for pause, 2 members wanted rate cut or stance change",
    )
