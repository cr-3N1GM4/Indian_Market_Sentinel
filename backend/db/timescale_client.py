# ARCHITECTURE NOTE:
# Uses asyncpg for high-performance async PostgreSQL access.
# Connection pool is created once at app startup and shared across
# all services. Alternative considered: SQLAlchemy async — rejected
# because we need raw SQL for TimescaleDB-specific features and
# asyncpg is significantly faster for time-series inserts.

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

import asyncpg
import structlog

from backend.config import settings

logger = structlog.get_logger(__name__)


class TimescaleClient:
    """Async PostgreSQL/TimescaleDB client with connection pooling."""

    def __init__(self) -> None:
        self._pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        """Create connection pool. Call once at app startup."""
        self._pool = await asyncpg.create_pool(
            dsn=settings.database_url,
            min_size=2,
            max_size=10,
            command_timeout=30,
        )
        logger.info("timescale_connected", dsn=settings.database_url.split("@")[-1])

    async def disconnect(self) -> None:
        """Close connection pool. Call at app shutdown."""
        if self._pool:
            await self._pool.close()
            logger.info("timescale_disconnected")

    @property
    def pool(self) -> asyncpg.Pool:
        if not self._pool:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._pool

    # ----------------------------------------------------------
    # Generic helpers
    # ----------------------------------------------------------

    async def execute(self, query: str, *args: Any) -> str:
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args: Any) -> List[asyncpg.Record]:
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args: Any) -> Optional[asyncpg.Record]:
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def fetchval(self, query: str, *args: Any) -> Any:
        async with self.pool.acquire() as conn:
            return await conn.fetchval(query, *args)

    # ----------------------------------------------------------
    # Social Sentiment
    # ----------------------------------------------------------

    async def insert_social_sentiment(
        self,
        time: datetime,
        ticker: str,
        source: str,
        raw_text: str,
        sentiment_score: float,
        sentiment_label: str,
        engagement_weight: float = 0.0,
        crss_contribution: float = 0.0,
        event_type: Optional[str] = None,
        url: Optional[str] = None,
    ) -> None:
        await self.execute(
            """
            INSERT INTO social_sentiment
                (time, ticker, source, raw_text, sentiment_score, sentiment_label,
                 engagement_weight, crss_contribution, event_type, url)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """,
            time, ticker, source, raw_text, sentiment_score, sentiment_label,
            engagement_weight, crss_contribution, event_type, url,
        )

    async def get_sentiment_by_ticker(
        self, ticker: str, hours: int = 24
    ) -> List[asyncpg.Record]:
        return await self.fetch(
            """
            SELECT * FROM social_sentiment
            WHERE ticker = $1 AND time > NOW() - INTERVAL '%s hours'
            ORDER BY time DESC
            """ % hours,
            ticker,
        )

    # ----------------------------------------------------------
    # CRSS Timeseries
    # ----------------------------------------------------------

    async def insert_crss(
        self,
        time: datetime,
        ticker: str,
        crss: float,
        twitter_score: float,
        reddit_score: float,
        news_score: float,
        data_points: int,
    ) -> None:
        await self.execute(
            """
            INSERT INTO crss_timeseries
                (time, ticker, crss, twitter_score, reddit_score, news_score, data_points)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            time, ticker, crss, twitter_score, reddit_score, news_score, data_points,
        )

    async def get_crss_latest(self, ticker: str) -> Optional[asyncpg.Record]:
        return await self.fetchrow(
            "SELECT * FROM crss_timeseries WHERE ticker = $1 ORDER BY time DESC LIMIT 1",
            ticker,
        )

    async def get_crss_history(
        self, ticker: str, hours: int = 168
    ) -> List[asyncpg.Record]:
        return await self.fetch(
            """
            SELECT * FROM crss_timeseries
            WHERE ticker = $1 AND time > NOW() - INTERVAL '%s hours'
            ORDER BY time ASC
            """ % hours,
            ticker,
        )

    # ----------------------------------------------------------
    # Institutional Flows
    # ----------------------------------------------------------

    async def insert_institutional_flow(
        self,
        time: datetime,
        source: str,
        ticker: Optional[str] = None,
        entity_name: Optional[str] = None,
        deal_type: Optional[str] = None,
        quantity: Optional[int] = None,
        price: Optional[float] = None,
        value_crores: Optional[float] = None,
        ics_contribution: Optional[float] = None,
    ) -> None:
        await self.execute(
            """
            INSERT INTO institutional_flows
                (time, ticker, source, entity_name, deal_type, quantity, price,
                 value_crores, ics_contribution)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            time, ticker, source, entity_name, deal_type, quantity, price,
            value_crores, ics_contribution,
        )

    async def get_institutional_flows(
        self, ticker: str, days: int = 30
    ) -> List[asyncpg.Record]:
        return await self.fetch(
            """
            SELECT * FROM institutional_flows
            WHERE ticker = $1 AND time > NOW() - INTERVAL '%s days'
            ORDER BY time DESC
            """ % days,
            ticker,
        )

    async def get_fii_dii_flows(self, days: int = 30) -> List[asyncpg.Record]:
        return await self.fetch(
            """
            SELECT * FROM institutional_flows
            WHERE source IN ('fii_daily', 'dii_daily')
              AND time > NOW() - INTERVAL '%s days'
            ORDER BY time DESC
            """ % days,
        )

    # ----------------------------------------------------------
    # ICS Timeseries
    # ----------------------------------------------------------

    async def insert_ics(
        self,
        time: datetime,
        ticker: str,
        ics: float,
        fii_net_crores: float = 0.0,
        dii_net_crores: float = 0.0,
    ) -> None:
        await self.execute(
            """
            INSERT INTO ics_timeseries (time, ticker, ics, fii_net_crores, dii_net_crores)
            VALUES ($1, $2, $3, $4, $5)
            """,
            time, ticker, ics, fii_net_crores, dii_net_crores,
        )

    async def get_ics_latest(self, ticker: str) -> Optional[asyncpg.Record]:
        return await self.fetchrow(
            "SELECT * FROM ics_timeseries WHERE ticker = $1 ORDER BY time DESC LIMIT 1",
            ticker,
        )

    # ----------------------------------------------------------
    # Macro Regime History
    # ----------------------------------------------------------

    async def insert_regime(self, data: Dict[str, Any]) -> None:
        await self.execute(
            """
            INSERT INTO macro_regime_history
                (time, regime, confidence, repo_rate, cpi_yoy, wpi_yoy,
                 gsec_10y, gsec_2y, yield_curve_slope, usd_inr, nifty_vix,
                 llm_regime_score, rule_based_regime, llm_regime, final_regime)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)
            """,
            data["time"], data["regime"], data.get("confidence"),
            data.get("repo_rate"), data.get("cpi_yoy"), data.get("wpi_yoy"),
            data.get("gsec_10y"), data.get("gsec_2y"), data.get("yield_curve_slope"),
            data.get("usd_inr"), data.get("nifty_vix"),
            json.dumps(data.get("llm_regime_score")) if data.get("llm_regime_score") else None,
            data.get("rule_based_regime"), data.get("llm_regime"),
            data.get("final_regime"),
        )

    async def get_current_regime(self) -> Optional[asyncpg.Record]:
        return await self.fetchrow(
            "SELECT * FROM macro_regime_history ORDER BY time DESC LIMIT 1"
        )

    async def get_regime_history(self, days: int = 180) -> List[asyncpg.Record]:
        return await self.fetch(
            """
            SELECT * FROM macro_regime_history
            WHERE time > NOW() - INTERVAL '%s days'
            ORDER BY time ASC
            """ % days,
        )

    # ----------------------------------------------------------
    # Technical Signals
    # ----------------------------------------------------------

    async def insert_technical_signal(self, data: Dict[str, Any]) -> None:
        await self.execute(
            """
            INSERT INTO technical_signals
                (time, ticker, close_price, sma_50, sma_200, golden_cross, death_cross,
                 rsi_14, rsi_overbought, rsi_oversold, bb_upper, bb_lower, bb_squeeze,
                 macd_line, macd_signal, macd_histogram, macd_crossover,
                 volume, volume_vs_avg20, supertrend_direction, supertrend_flip)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21)
            """,
            data["time"], data["ticker"], data.get("close_price"),
            data.get("sma_50"), data.get("sma_200"),
            data.get("golden_cross", False), data.get("death_cross", False),
            data.get("rsi_14"), data.get("rsi_overbought", False),
            data.get("rsi_oversold", False),
            data.get("bb_upper"), data.get("bb_lower"), data.get("bb_squeeze", False),
            data.get("macd_line"), data.get("macd_signal"), data.get("macd_histogram"),
            data.get("macd_crossover"),
            data.get("volume"), data.get("volume_vs_avg20"),
            data.get("supertrend_direction"), data.get("supertrend_flip", False),
        )

    async def get_technical_latest(self, ticker: str) -> Optional[asyncpg.Record]:
        return await self.fetchrow(
            "SELECT * FROM technical_signals WHERE ticker = $1 ORDER BY time DESC LIMIT 1",
            ticker,
        )

    async def get_technical_history(
        self, ticker: str, days: int = 30
    ) -> List[asyncpg.Record]:
        return await self.fetch(
            """
            SELECT * FROM technical_signals
            WHERE ticker = $1 AND time > NOW() - INTERVAL '%s days'
            ORDER BY time ASC
            """ % days,
            ticker,
        )

    # ----------------------------------------------------------
    # Alpha Signals
    # ----------------------------------------------------------

    async def insert_alpha_signal(self, data: Dict[str, Any]) -> UUID:
        row = await self.fetchrow(
            """
            INSERT INTO alpha_signals
                (time, ticker, exchange, sector, pattern, signal_type, confidence,
                 regime, crss, ics, fii_net_5d_crores, supporting_evidence)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
            RETURNING id
            """,
            data["time"], data["ticker"], data.get("exchange", "NSE"),
            data.get("sector"), data["pattern"], data["signal_type"],
            data["confidence"], data.get("regime"),
            data.get("crss"), data.get("ics"), data.get("fii_net_5d_crores"),
            json.dumps(data.get("supporting_evidence", [])),
        )
        return row["id"]

    async def get_active_signals(self) -> List[asyncpg.Record]:
        return await self.fetch(
            """
            SELECT * FROM alpha_signals
            WHERE is_resolved = FALSE
            ORDER BY
                CASE confidence
                    WHEN 'HIGH' THEN 1
                    WHEN 'MEDIUM_HIGH' THEN 2
                    WHEN 'MEDIUM' THEN 3
                    ELSE 4
                END,
                time DESC
            LIMIT 50
            """
        )

    async def get_signals_history(
        self,
        ticker: Optional[str] = None,
        sector: Optional[str] = None,
        confidence: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[asyncpg.Record]:
        conditions = []
        params: list = []
        idx = 1

        if ticker:
            conditions.append(f"ticker = ${idx}")
            params.append(ticker)
            idx += 1
        if sector:
            conditions.append(f"sector = ${idx}")
            params.append(sector)
            idx += 1
        if confidence:
            conditions.append(f"confidence = ${idx}")
            params.append(confidence)
            idx += 1

        where = "WHERE " + " AND ".join(conditions) if conditions else ""

        return await self.fetch(
            f"""
            SELECT * FROM alpha_signals {where}
            ORDER BY time DESC
            LIMIT ${idx} OFFSET ${idx + 1}
            """,
            *params, limit, offset,
        )

    async def get_signal_by_id(self, signal_id: str) -> Optional[asyncpg.Record]:
        return await self.fetchrow(
            "SELECT * FROM alpha_signals WHERE id = $1",
            UUID(signal_id),
        )

    # ----------------------------------------------------------
    # Corporate Actions
    # ----------------------------------------------------------

    async def upsert_corporate_action(self, data: Dict[str, Any]) -> None:
        await self.execute(
            """
            INSERT INTO corporate_actions
                (ticker, exchange, action_type, event_date, record_date, ex_date, details)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT DO NOTHING
            """,
            data["ticker"], data.get("exchange", "NSE"), data["action_type"],
            data["event_date"], data.get("record_date"), data.get("ex_date"),
            json.dumps(data.get("details", {})),
        )

    async def get_upcoming_actions(self, days: int = 7) -> List[asyncpg.Record]:
        return await self.fetch(
            """
            SELECT * FROM corporate_actions
            WHERE event_date BETWEEN CURRENT_DATE AND CURRENT_DATE + $1
            ORDER BY event_date ASC
            """,
            days,
        )

    async def get_result_analysis(self, ticker: str) -> Optional[asyncpg.Record]:
        return await self.fetchrow(
            """
            SELECT * FROM corporate_actions
            WHERE ticker = $1 AND action_type = 'RESULT'
            ORDER BY event_date DESC LIMIT 1
            """,
            ticker,
        )

    # ----------------------------------------------------------
    # Portfolio Holdings
    # ----------------------------------------------------------

    async def upsert_holding(
        self,
        user_id: str,
        ticker: str,
        quantity: int,
        avg_cost: float,
    ) -> None:
        await self.execute(
            """
            INSERT INTO portfolio_holdings (user_id, ticker, quantity, avg_cost)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id, ticker) DO UPDATE
            SET quantity = $3, avg_cost = $4, last_updated = NOW()
            """,
            user_id, ticker, quantity, avg_cost,
        )

    async def get_portfolio(self, user_id: str) -> List[asyncpg.Record]:
        return await self.fetch(
            "SELECT * FROM portfolio_holdings WHERE user_id = $1",
            user_id,
        )

    async def update_vulnerability(
        self, user_id: str, ticker: str, score: float, breakdown: Dict
    ) -> None:
        await self.execute(
            """
            UPDATE portfolio_holdings
            SET vulnerability_score = $3,
                vulnerability_breakdown = $4,
                last_updated = NOW()
            WHERE user_id = $1 AND ticker = $2
            """,
            user_id, ticker, score, json.dumps(breakdown),
        )


# Singleton instance
db = TimescaleClient()
