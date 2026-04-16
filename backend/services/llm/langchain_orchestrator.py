# ARCHITECTURE NOTE:
# Central coordinator for all LLM interactions. Manages client init,
# retry logic, token tracking, and Redis caching.
# Priority cascade: Groq -> Gemini -> Anthropic -> OpenAI.

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

import structlog

from backend.config import settings

logger = structlog.get_logger(__name__)

# Token usage tracking
_daily_tokens_used = 0
_daily_cost_estimate = 0.0


class LangChainOrchestrator:
    """Central LLM orchestration layer with retry, caching, and priority routing."""

    def __init__(self) -> None:
        self._groq_client = None
        self._gemini_client = None
        self._anthropic_client = None
        self._openai_client = None
        self._redis = None

    async def init(self, redis_client=None) -> None:
        """Initialize all available LLM clients and Redis cache."""
        self._redis = redis_client

        # 1. Initialize Groq (Lightning fast, primary for high-volume sentiment)
        groq_key = os.getenv("GROQ_API_KEY", "")
        if groq_key:
            try:
                from langchain_groq import ChatGroq
                self._groq_client = ChatGroq(
                    model="llama-3.1-8b-instant",
                    api_key=groq_key,
                    temperature=settings.llm.temperature,
                )
                logger.info("llm_groq_initialized")
            except Exception as e:
                logger.warning("llm_groq_init_failed", error=str(e))

        # 2. Initialize Gemini (Fast reasoning, excellent free tier)
        gemini_key = os.getenv("GEMINI_API_KEY", "")
        if gemini_key:
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                self._gemini_client = ChatGoogleGenerativeAI(
                    model="gemini-2.5-flash",
                    google_api_key=gemini_key,
                    max_output_tokens=settings.llm.max_tokens,
                    temperature=settings.llm.temperature,
                )
                logger.info("llm_gemini_initialized")
            except Exception as e:
                logger.warning("llm_gemini_init_failed", error=str(e))

        # 3. Initialize Anthropic (High-tier reasoning)
        anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
        if anthropic_key:
            try:
                from langchain_anthropic import ChatAnthropic
                self._anthropic_client = ChatAnthropic(
                    model=settings.llm.primary_model,
                    anthropic_api_key=anthropic_key,
                    max_tokens=settings.llm.max_tokens,
                    temperature=settings.llm.temperature,
                )
                logger.info("llm_anthropic_initialized")
            except Exception as e:
                logger.warning("llm_anthropic_init_failed", error=str(e))

        # 4. Initialize OpenAI (General fallback)
        openai_key = os.getenv("OPENAI_API_KEY", "")
        if openai_key:
            try:
                from langchain_openai import ChatOpenAI
                self._openai_client = ChatOpenAI(
                    model=settings.llm.fallback_model,
                    api_key=openai_key,
                    max_tokens=settings.llm.max_tokens,
                    temperature=settings.llm.temperature,
                )
                logger.info("llm_openai_initialized")
            except Exception as e:
                logger.warning("llm_openai_init_failed", error=str(e))

    @property
    def client(self):
        """Get the active LLM client in priority order: Groq -> Gemini -> Anthropic -> OpenAI."""
        return self._groq_client or self._gemini_client or self._anthropic_client or self._openai_client

    async def invoke_with_retry(
        self,
        messages: list,
        cache_key: Optional[str] = None,
        max_retries: int = 3,
    ) -> Optional[str]:
        """Invoke LLM with retry logic and optional Redis caching."""
        global _daily_tokens_used, _daily_cost_estimate

        # Check cache first
        if cache_key and self._redis:
            try:
                cached = await self._redis.get(cache_key)
                if cached:
                    logger.info("llm_cache_hit", key=cache_key)
                    return cached.decode() if isinstance(cached, bytes) else cached
            except Exception:
                pass

        if not self.client:
            logger.error("llm_no_client_available")
            return None

        import asyncio
        for attempt in range(max_retries):
            try:
                response = await asyncio.to_thread(
                    self.client.invoke, messages
                )

                result = response.content if hasattr(response, "content") else str(response)

                # Track tokens (approximate)
                token_count = len(result) // 4 + sum(
                    len(str(m)) // 4 for m in messages
                )
                _daily_tokens_used += token_count
                
                # Cache result
                if cache_key and self._redis:
                    try:
                        await self._redis.setex(
                            cache_key,
                            settings.llm.regime_cache_ttl_seconds,
                            result,
                        )
                    except Exception:
                        pass

                return result

            except Exception as e:
                wait = settings.resilience.backoff_base_seconds * (2 ** attempt)
                logger.warning(
                    "llm_invoke_retry",
                    attempt=attempt + 1,
                    error=str(e),
                    wait_seconds=wait,
                )
                await asyncio.sleep(wait)

        logger.error("llm_invoke_failed_all_retries")
        return None

    def get_usage_stats(self) -> Dict[str, Any]:
        return {
            "daily_tokens_used": _daily_tokens_used,
            "daily_cost_estimate_usd": round(_daily_cost_estimate, 4),
            "budget_remaining": settings.llm.daily_token_budget - _daily_tokens_used,
        }


# Singleton
llm_orchestrator = LangChainOrchestrator()