# ARCHITECTURE NOTE:
# Single entry point for the FastAPI backend. Uses lifespan context
# manager for clean startup/shutdown of DB pools, Redis, and APScheduler.
# WebSocket endpoint at /ws/live-signals streams alpha signals in real-time
# via Redis pub/sub. All routers mounted under /api/v1/.

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import redis.asyncio as aioredis
import structlog
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.db.timescale_client import db
from backend.routers import calendar, institutional, macro, portfolio, sentiment, signals
from backend.routers import stock_analyzer
from backend.services.scrapers.nse_scraper import fetch_market_indices, generate_mock_market_data

logger = structlog.get_logger(__name__)

# Global Redis client
redis_client = None
scheduler = None


# ----------------------------------------------------------
# Scheduler job functions
# ----------------------------------------------------------

async def run_sentiment_pipeline():
    """Run all sentiment scrapers: Twitter, Reddit, MC, ET."""
    try:
        from backend.services.scrapers.twitter_scraper import twitter_scraper
        from backend.services.scrapers.reddit_scraper import reddit_scraper
        from backend.services.scrapers.moneycontrol_scraper import moneycontrol_scraper
        from backend.services.scrapers.economic_times_scraper import et_scraper

        results = await asyncio.gather(
            twitter_scraper.run_pipeline(),
            reddit_scraper.run_pipeline(),
            moneycontrol_scraper.run_pipeline(),
            et_scraper.run_pipeline(),
            return_exceptions=True,
        )
        logger.info("sentiment_pipeline_complete", results=[
            r if isinstance(r, int) else str(r) for r in results
        ])
    except Exception as e:
        logger.error("sentiment_pipeline_error", error=str(e))


async def run_bulk_block_scraper():
    try:
        from backend.services.institutional.nse_bulk_block_deals import nse_bulk_block
        await nse_bulk_block.run_pipeline()
    except Exception as e:
        logger.error("bulk_block_error", error=str(e))


async def run_fii_dii_scraper():
    try:
        from backend.services.institutional.dii_fii_flows import dii_fii_flows
        await dii_fii_flows.run_pipeline()
    except Exception as e:
        logger.error("fii_dii_error", error=str(e))


async def run_corporate_actions():
    try:
        from backend.services.corporate_actions.earnings_calendar import earnings_calendar
        await earnings_calendar.run_pipeline()
    except Exception as e:
        logger.error("corporate_actions_error", error=str(e))


async def run_macro_fetcher():
    try:
        from backend.services.macro.cpi_wpi_fetcher import cpi_wpi_fetcher
        await cpi_wpi_fetcher.fetch_all()
    except Exception as e:
        logger.error("macro_fetch_error", error=str(e))


async def run_regime_classifier():
    try:
        from backend.services.macro.cpi_wpi_fetcher import cpi_wpi_fetcher
        from backend.services.macro.rbi_minutes_parser import rbi_minutes_parser
        from backend.services.llm.regime_scorer import score_regime
        from backend.services.macro.regime_classifier import run_regime_classification

        macro_data = await cpi_wpi_fetcher.fetch_all()
        mpc_texts = await rbi_minutes_parser.run_pipeline()
        llm_score = await score_regime(mpc_texts, macro_data)
        await run_regime_classification(macro_data, llm_score)
    except Exception as e:
        logger.error("regime_classifier_error", error=str(e))


async def run_divergence_detector():
    try:
        from backend.services.alpha.divergence_detector import divergence_detector
        await divergence_detector.run()
    except Exception as e:
        logger.error("divergence_detector_error", error=str(e))


async def run_pre_event_alerts():
    try:
        from backend.services.corporate_actions.earnings_calendar import earnings_calendar
        alerts = await earnings_calendar.generate_pre_event_alerts()
        if alerts:
            logger.info("pre_event_alerts_generated", count=len(alerts))
    except Exception as e:
        logger.error("pre_event_alerts_error", error=str(e))


# ----------------------------------------------------------
# Lifespan
# ----------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle management."""
    global redis_client, scheduler

    # Startup
    logger.info("ims_starting")

    # Connect to database
    try:
        await db.connect()
    except Exception as e:
        logger.error("db_connect_failed", error=str(e))

    # Connect to Redis
    try:
        redis_client = aioredis.from_url(
            settings.redis_url, decode_responses=True
        )
        await redis_client.ping()
        logger.info("redis_connected")
    except Exception as e:
        logger.warning("redis_connect_failed", error=str(e))
        redis_client = None

    # Init LLM orchestrator
    try:
        from backend.services.llm.langchain_orchestrator import llm_orchestrator
        await llm_orchestrator.init(redis_client=redis_client)
    except Exception as e:
        logger.warning("llm_init_failed", error=str(e))

    # Init divergence detector
    try:
        from backend.services.alpha.divergence_detector import divergence_detector
        watchlist_meta = {}
        try:
            with open("watchlist.json", "r") as f:
                wl = json.load(f)
                for stock in wl.get("stocks", []):
                    watchlist_meta[stock["ticker"]] = stock
        except Exception:
            pass
        await divergence_detector.init(redis_client=redis_client, watchlist_meta=watchlist_meta)
    except Exception as e:
        logger.warning("divergence_init_failed", error=str(e))

    # Start APScheduler
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.interval import IntervalTrigger
        from apscheduler.triggers.cron import CronTrigger

        scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")

        cfg = settings.scheduler

        scheduler.add_job(
            run_sentiment_pipeline, IntervalTrigger(minutes=cfg.sentiment_interval_minutes),
            id="sentiment", replace_existing=True,
        )
        scheduler.add_job(
            run_bulk_block_scraper,
            CronTrigger(hour=cfg.bulk_block_hour, minute=0, timezone="Asia/Kolkata"),
            id="bulk_block", replace_existing=True,
        )
        scheduler.add_job(
            run_fii_dii_scraper,
            CronTrigger(hour=cfg.fii_dii_hour, minute=0, timezone="Asia/Kolkata"),
            id="fii_dii", replace_existing=True,
        )
        scheduler.add_job(
            run_corporate_actions,
            CronTrigger(hour=cfg.corporate_actions_hour, minute=0, timezone="Asia/Kolkata"),
            id="corporate_actions", replace_existing=True,
        )
        scheduler.add_job(
            run_divergence_detector,
            IntervalTrigger(minutes=cfg.divergence_interval_minutes),
            id="divergence", replace_existing=True,
        )
        scheduler.add_job(
            run_pre_event_alerts,
            CronTrigger(hour=cfg.pre_event_hour, minute=0, timezone="Asia/Kolkata"),
            id="pre_event", replace_existing=True,
        )
        scheduler.add_job(
            run_regime_classifier,
            CronTrigger(day_of_week=cfg.macro_day_of_week, hour=cfg.regime_hour, timezone="Asia/Kolkata"),
            id="regime", replace_existing=True,
        )

        scheduler.start()
        logger.info("scheduler_started", jobs=len(scheduler.get_jobs()))

    except Exception as e:
        logger.error("scheduler_start_failed", error=str(e))

    # Run initial data fetch
    try:
        await run_sentiment_pipeline()
    except Exception:
        pass

    logger.info("ims_ready")

    yield

    # Shutdown
    logger.info("ims_shutting_down")
    if scheduler:
        scheduler.shutdown(wait=False)
    if redis_client:
        await redis_client.close()
    await db.disconnect()
    logger.info("ims_stopped")


# ----------------------------------------------------------
# FastAPI App
# ----------------------------------------------------------

app = FastAPI(
    title="IMS API",
    description="Indian Market Sentinel — Regime-Conditioned Market Intelligence",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(sentiment.router, prefix="/api/v1")
app.include_router(institutional.router, prefix="/api/v1")
app.include_router(macro.router, prefix="/api/v1")
app.include_router(signals.router, prefix="/api/v1")
app.include_router(portfolio.router, prefix="/api/v1")
app.include_router(calendar.router, prefix="/api/v1")
app.include_router(stock_analyzer.router, prefix="/api/v1")


# ----------------------------------------------------------
# Health check
# ----------------------------------------------------------

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
    }


@app.get("/api/v1/market-data")
async def get_market_data():
    """Live market index data (Nifty, Sensex, etc.)."""
    try:
        data = await fetch_market_indices()
    except Exception:
        data = generate_mock_market_data()
    return {
        "data": data,
        "meta": {"timestamp": datetime.utcnow().isoformat(), "version": "1.0"},
    }


# ----------------------------------------------------------
# WebSocket for live signal streaming
# ----------------------------------------------------------

@app.websocket("/ws/live-signals")
async def websocket_live_signals(websocket: WebSocket):
    """Stream alpha signals in real-time via Redis pub/sub."""
    await websocket.accept()

    if not redis_client:
        # No Redis — send periodic mock signals
        try:
            while True:
                import random
                mock_signal = {
                    "signal_id": f"ws-mock-{random.randint(1000, 9999)}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "ticker": random.choice(["SUNPHARMA", "RELIANCE", "ONGC"]),
                    "pattern": random.choice(["RETAIL_BUBBLE", "SMART_MONEY_ACCUMULATION"]),
                    "confidence": random.choice(["HIGH", "MEDIUM"]),
                    "crss": round(random.uniform(-0.5, 0.8), 2),
                    "ics": round(random.uniform(-0.5, 0.6), 2),
                }
                await websocket.send_json(mock_signal)
                await asyncio.sleep(30)
        except WebSocketDisconnect:
            pass
        return

    # Subscribe to Redis channel
    pubsub = redis_client.pubsub()
    await pubsub.subscribe("live_signals")

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = message["data"]
                if isinstance(data, str):
                    await websocket.send_text(data)
                elif isinstance(data, bytes):
                    await websocket.send_text(data.decode())
    except WebSocketDisconnect:
        logger.info("websocket_disconnected")
    finally:
        await pubsub.unsubscribe("live_signals")


# ----------------------------------------------------------
# Celery app (for heavy async tasks)
# ----------------------------------------------------------
try:
    from celery import Celery

    celery_app = Celery(
        "ims",
        broker=settings.redis_url,
        backend=settings.redis_url,
    )
    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="Asia/Kolkata",
    )
except ImportError:
    celery_app = None
