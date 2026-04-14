# ARCHITECTURE NOTE:
# Computes all technical indicators for watchlist tickers using numpy.
# Runs on each market close. All parameters come from config.py.
# Uses mock price data when real OHLCV feed is unavailable.
# Alternative considered: TA-Lib — rejected to avoid C dependency;
# numpy implementations are transparent and auditable.

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import structlog

from backend.config import settings
from backend.db.timescale_client import db

logger = structlog.get_logger(__name__)


def compute_sma(prices: np.ndarray, period: int) -> Optional[float]:
    if len(prices) < period:
        return None
    return float(np.mean(prices[-period:]))


def compute_rsi(prices: np.ndarray, period: int = 14) -> Optional[float]:
    if len(prices) < period + 1:
        return None
    deltas = np.diff(prices[-(period + 1):])
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains) if np.sum(gains) > 0 else 0.001
    avg_loss = np.mean(losses) if np.sum(losses) > 0 else 0.001
    rs = avg_gain / avg_loss
    return float(100 - (100 / (1 + rs)))


def compute_bollinger_bands(
    prices: np.ndarray, period: int = 20, std_mult: float = 2.0
) -> Dict[str, Optional[float]]:
    if len(prices) < period:
        return {"upper": None, "lower": None, "squeeze": False}
    window = prices[-period:]
    sma = float(np.mean(window))
    std = float(np.std(window))
    upper = sma + std_mult * std
    lower = sma - std_mult * std
    # Band squeeze: bandwidth < 50% of 120-day avg bandwidth
    squeeze = std < np.std(prices[-min(120, len(prices)):]) * 0.5 if len(prices) >= 40 else False
    return {"upper": upper, "lower": lower, "squeeze": bool(squeeze)}


def compute_macd(
    prices: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9
) -> Dict[str, Optional[float]]:
    if len(prices) < slow + signal:
        return {"line": None, "signal": None, "histogram": None, "crossover": None}

    def ema(data, period):
        alpha = 2 / (period + 1)
        result = np.zeros_like(data, dtype=float)
        result[0] = data[0]
        for i in range(1, len(data)):
            result[i] = alpha * data[i] + (1 - alpha) * result[i - 1]
        return result

    ema_fast = ema(prices, fast)
    ema_slow = ema(prices, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)

    curr_macd = float(macd_line[-1])
    curr_signal = float(signal_line[-1])
    histogram = curr_macd - curr_signal

    # Crossover detection
    crossover = None
    if len(macd_line) >= 2:
        prev_diff = float(macd_line[-2] - signal_line[-2])
        curr_diff = curr_macd - curr_signal
        if prev_diff < 0 and curr_diff > 0:
            crossover = "BULLISH"
        elif prev_diff > 0 and curr_diff < 0:
            crossover = "BEARISH"

    return {
        "line": round(curr_macd, 4),
        "signal": round(curr_signal, 4),
        "histogram": round(histogram, 4),
        "crossover": crossover,
    }


def compute_supertrend(
    highs: np.ndarray,
    lows: np.ndarray,
    closes: np.ndarray,
    period: int = 10,
    multiplier: float = 3.0,
) -> Dict[str, Any]:
    if len(closes) < period + 1:
        return {"direction": None, "flip": False}

    # ATR calculation
    tr_list = []
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        tr_list.append(tr)

    if len(tr_list) < period:
        return {"direction": None, "flip": False}

    atr = float(np.mean(tr_list[-period:]))

    hl2 = (highs[-1] + lows[-1]) / 2
    upper_band = hl2 + multiplier * atr
    lower_band = hl2 - multiplier * atr

    # Simple direction: price above lower_band = UP
    direction = "UP" if closes[-1] > lower_band else "DOWN"

    # Flip detection
    prev_direction = "UP" if closes[-2] > (
        (highs[-2] + lows[-2]) / 2 - multiplier * atr
    ) else "DOWN"
    flip = direction != prev_direction

    return {"direction": direction, "flip": flip}


class SignalEngine:
    """Computes all technical indicators for watchlist tickers."""

    async def compute_for_ticker(self, ticker: str) -> Dict[str, Any]:
        """Compute all technical signals for a single ticker."""
        # Get historical price data (mock for now)
        prices = self._get_price_data(ticker)
        if not prices or len(prices) < 30:
            return {}

        closes = np.array([p["close"] for p in prices])
        highs = np.array([p["high"] for p in prices])
        lows = np.array([p["low"] for p in prices])
        volumes = np.array([p["volume"] for p in prices])

        cfg = settings.technical

        # SMA
        sma_50 = compute_sma(closes, cfg.sma_short)
        sma_200 = compute_sma(closes, cfg.sma_long)

        # Golden/Death Cross detection
        golden_cross = False
        death_cross = False
        if sma_50 is not None and sma_200 is not None and len(closes) > cfg.sma_long + 5:
            prev_sma50 = compute_sma(closes[:-1], cfg.sma_short)
            prev_sma200 = compute_sma(closes[:-1], cfg.sma_long)
            if prev_sma50 and prev_sma200:
                if prev_sma50 < prev_sma200 and sma_50 > sma_200:
                    golden_cross = True
                elif prev_sma50 > prev_sma200 and sma_50 < sma_200:
                    death_cross = True

        # RSI
        rsi = compute_rsi(closes, cfg.rsi_period)

        # Bollinger Bands
        bb = compute_bollinger_bands(closes, cfg.bb_period, cfg.bb_std)

        # MACD
        macd = compute_macd(closes, cfg.macd_fast, cfg.macd_slow, cfg.macd_signal)

        # Volume
        volume = int(volumes[-1])
        avg_vol_20 = float(np.mean(volumes[-20:])) if len(volumes) >= 20 else float(volumes[-1])
        vol_ratio = volume / avg_vol_20 if avg_vol_20 > 0 else 1.0

        # Supertrend
        st = compute_supertrend(highs, lows, closes, cfg.supertrend_atr_period, cfg.supertrend_multiplier)

        signal_data = {
            "time": datetime.now(timezone.utc),
            "ticker": ticker,
            "close_price": float(closes[-1]),
            "sma_50": round(sma_50, 2) if sma_50 else None,
            "sma_200": round(sma_200, 2) if sma_200 else None,
            "golden_cross": golden_cross,
            "death_cross": death_cross,
            "rsi_14": round(rsi, 2) if rsi else None,
            "rsi_overbought": rsi > cfg.rsi_overbought if rsi else False,
            "rsi_oversold": rsi < cfg.rsi_oversold if rsi else False,
            "bb_upper": round(bb["upper"], 2) if bb["upper"] else None,
            "bb_lower": round(bb["lower"], 2) if bb["lower"] else None,
            "bb_squeeze": bb.get("squeeze", False),
            "macd_line": macd["line"],
            "macd_signal": macd["signal"],
            "macd_histogram": macd["histogram"],
            "macd_crossover": macd["crossover"],
            "volume": volume,
            "volume_vs_avg20": round(vol_ratio, 2),
            "supertrend_direction": st["direction"],
            "supertrend_flip": st["flip"],
        }

        # Store in DB
        try:
            await db.insert_technical_signal(signal_data)
        except Exception as e:
            logger.error("tech_signal_store_error", ticker=ticker, error=str(e))

        return signal_data

    async def run_pipeline(self) -> int:
        """Compute technicals for all watchlist tickers."""
        tickers = settings.sectors.all_tickers
        computed = 0

        for ticker in tickers:
            try:
                result = await self.compute_for_ticker(ticker)
                if result:
                    computed += 1
            except Exception as e:
                logger.error("tech_signal_error", ticker=ticker, error=str(e))

        logger.info("signal_engine_complete", tickers_computed=computed)
        return computed

    # MOCK_FALLBACK: synthetic OHLCV data
    def _get_price_data(self, ticker: str, days: int = 252) -> List[Dict]:
        """Generate synthetic price history for development."""
        base_price = random.uniform(100, 5000)
        data = []
        price = base_price

        for i in range(days):
            change = random.gauss(0, 0.02)
            price *= (1 + change)
            high = price * (1 + abs(random.gauss(0, 0.01)))
            low = price * (1 - abs(random.gauss(0, 0.01)))
            volume = random.randint(100000, 10000000)
            data.append({
                "close": round(price, 2),
                "high": round(high, 2),
                "low": round(low, 2),
                "open": round(price * (1 + random.gauss(0, 0.005)), 2),
                "volume": volume,
            })

        return data


signal_engine = SignalEngine()
