# Indian Market Sentinel (IMS)

**Regime-Conditioned Market Intelligence Terminal for Indian Equities**

---

## What Is IMS?

The Indian Market Sentinel is a live intelligence terminal that simultaneously monitors:

- **Retail sentiment** (Twitter, Reddit, financial news)
- **Institutional flows** (NSE bulk/block deals, FII/DII daily flows)
- **Macro regime** (RBI MPC minutes, CPI, repo rate, yield curve)

It detects **divergences** between these data layers and surfaces structured alpha signals when meaningful patterns emerge — conditioned on the current macro environment.

### Core Thesis

> *"Is Retail Hype a leading indicator or noise — and does the answer change depending on the current Macro Regime?"*

The system encodes 5 specific divergence patterns:

1. **Retail Bubble** — Retail bullish + institutions absent + hawkish regime → mean-reversion risk
2. **Smart Money Accumulation** — Retail bearish + institutions buying → quiet accumulation
3. **Regime-Confirmed Breakout** — Retail + institutional alignment + dovish regime + Golden Cross → highest-conviction long
4. **News-Institutional Divergence** — Positive media + institutions selling → distribution warning
5. **Supply Chain Stress** — China API disruption signal for Indian Pharma companies

---

## Quick Start

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- API keys (see `.env.example` for full list)

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/ims.git
cd ims

# 2. Create your environment file
cp .env.example .env
# Edit .env with your API keys (at minimum: ANTHROPIC_API_KEY, POSTGRES_PASSWORD)

# 3. Start everything
docker-compose up -d

# 4. Verify services are running
docker-compose ps

# 5. Open the dashboard
# Navigate to http://localhost:3000
```

First startup takes 5-15 minutes to download all dependencies.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Next.js 14 Frontend (:3000)                  │
│  Bloomberg-style terminal UI · 5 pages · WebSocket live feed    │
├─────────────────────────────────────────────────────────────────┤
│                    FastAPI Backend (:8000)                       │
│  6 routers · APScheduler · WebSocket · Celery worker            │
├──────────┬──────────┬──────────┬──────────┬─────────────────────┤
│ Scrapers │ Instit.  │  Macro   │  Alpha   │     LLM Layer       │
│ Twitter  │ NSE Bulk │ RBI MPC  │ Signal   │  Claude (primary)   │
│ Reddit   │ FII/DII  │ CPI/WPI  │ Engine   │  Regime Scorer      │
│ MC / ET  │ SEC 13F  │ FRED API │ Diverg.  │  News Pipeline      │
├──────────┴──────────┴──────────┴──────────┴─────────────────────┤
│           PostgreSQL 15 + TimescaleDB · Redis 7                  │
│           9 tables (7 hypertables) · Pub/Sub · Cache             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Dashboard Pages

| Page | Route | Purpose |
|------|-------|---------|
| **Dashboard** | `/` | Main terminal — signals, heatmap, FII/DII, calendar |
| **Regime** | `/regime` | Macro regime timeline, MPC analysis, hawkish/dovish signals |
| **Signals** | `/signals` | Full signal history with filtering and detail view |
| **Portfolio** | `/portfolio` | Vulnerability heatmap + stress testing |
| **Calendar** | `/calendar` | Corporate actions, pre-event alerts, buyback opportunities |

---

## Key Concepts

### CRSS (Composite Retail Sentiment Score)
Weighted blend of Twitter (35%), Reddit (30%), and News (35%) sentiment per ticker. Normalised to [-1, +1] via 30-day z-score.

### ICS (Institutional Conviction Score)
Net institutional volume over 5 days / average daily volume over 20 days. Measures whether institutions are actively accumulating or distributing.

### Macro Regime
One of 6 classifications derived from RBI policy, CPI, yield curve, and VIX:
- **Hawkish Tightening** — RBI hiking rates, CPI above 6%
- **Hawkish Pause** — Hikes paused, language still hawkish
- **Neutral Watchful** — Data-dependent, CPI near 4%
- **Dovish Pause** — Language softening, growth support emerging
- **Dovish Easing** — RBI actively cutting rates
- **Crisis Liquidity** — Emergency measures, VIX > 30

---

## Configuration

All tuneable parameters are in `backend/config.py`:
- Sentiment weights (VADER vs FinBERT, source weights)
- Signal thresholds (CRSS/ICS cutoffs for each pattern)
- Regime classifier weights (rule-based vs LLM)
- Technical indicator periods
- Scheduler timing
- Vulnerability scoring thresholds

The only file you regularly edit during operation: `watchlist.json`

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/regime/current` | GET | Current macro regime |
| `/api/v1/regime/history` | GET | Regime history |
| `/api/v1/sentiment/{ticker}` | GET | Ticker sentiment |
| `/api/v1/sentiment/heatmap` | GET | Sector heatmap |
| `/api/v1/signals/active` | GET | Active alpha signals |
| `/api/v1/signals/history` | GET | Signal history (filtered) |
| `/api/v1/institutional/{ticker}` | GET | ICS + deals |
| `/api/v1/institutional/fii-dii-flows` | GET | FII/DII flows |
| `/api/v1/calendar/upcoming` | GET | Corporate actions |
| `/api/v1/calendar/alerts` | GET | Pre-event alerts |
| `/api/v1/portfolio/analyze` | POST | Vulnerability analysis |
| `/api/v1/portfolio/stress-test` | POST | Stress scenarios |
| `/ws/live-signals` | WS | Live signal stream |

---

## Maintenance

```bash
# View logs
docker-compose logs -f backend

# Restart a stuck service
docker-compose restart backend

# Update after code changes
docker-compose down && docker-compose up -d --build

# Database backup
docker exec ims_postgres pg_dump -U ims ims_db > backup_$(date +%Y%m%d).sql

# Full reset (WARNING: deletes all data)
docker-compose down -v && docker-compose up -d
```

---

## License

Internal use only. Not for redistribution.
