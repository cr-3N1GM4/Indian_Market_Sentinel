-- ============================================================
-- IMS Database Schema
-- PostgreSQL 15 + TimescaleDB
-- Run automatically on first docker-compose up via init script
-- ============================================================

CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ----------------------------------------------------------
-- 1. Social sentiment (Twitter, Reddit, News)
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS social_sentiment (
    time                TIMESTAMPTZ     NOT NULL,
    ticker              VARCHAR(20)     NOT NULL,
    source              VARCHAR(50)     NOT NULL,
    raw_text            TEXT,
    sentiment_score     FLOAT           NOT NULL,
    sentiment_label     VARCHAR(20),
    engagement_weight   FLOAT,
    crss_contribution   FLOAT,
    event_type          VARCHAR(50),
    url                 TEXT
);
SELECT create_hypertable('social_sentiment', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_social_sentiment_ticker ON social_sentiment (ticker, time DESC);
CREATE INDEX IF NOT EXISTS idx_social_sentiment_source ON social_sentiment (source, time DESC);

-- ----------------------------------------------------------
-- 2. Composite Retail Sentiment Score
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS crss_timeseries (
    time            TIMESTAMPTZ     NOT NULL,
    ticker          VARCHAR(20)     NOT NULL,
    crss            FLOAT           NOT NULL,
    twitter_score   FLOAT,
    reddit_score    FLOAT,
    news_score      FLOAT,
    data_points     INT
);
SELECT create_hypertable('crss_timeseries', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_crss_ticker ON crss_timeseries (ticker, time DESC);

-- ----------------------------------------------------------
-- 3. Institutional flows
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS institutional_flows (
    time            TIMESTAMPTZ     NOT NULL,
    ticker          VARCHAR(20),
    source          VARCHAR(50)     NOT NULL,
    entity_name     VARCHAR(200),
    deal_type       VARCHAR(20),
    quantity        BIGINT,
    price           FLOAT,
    value_crores    FLOAT,
    ics_contribution FLOAT
);
SELECT create_hypertable('institutional_flows', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_inst_flows_ticker ON institutional_flows (ticker, time DESC);

-- ----------------------------------------------------------
-- 4. ICS timeseries
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS ics_timeseries (
    time            TIMESTAMPTZ     NOT NULL,
    ticker          VARCHAR(20)     NOT NULL,
    ics             FLOAT           NOT NULL,
    fii_net_crores  FLOAT,
    dii_net_crores  FLOAT
);
SELECT create_hypertable('ics_timeseries', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_ics_ticker ON ics_timeseries (ticker, time DESC);

-- ----------------------------------------------------------
-- 5. Macro regime history
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS macro_regime_history (
    time                TIMESTAMPTZ     NOT NULL,
    regime              VARCHAR(50)     NOT NULL,
    confidence          FLOAT,
    repo_rate           FLOAT,
    cpi_yoy             FLOAT,
    wpi_yoy             FLOAT,
    gsec_10y            FLOAT,
    gsec_2y             FLOAT,
    yield_curve_slope   FLOAT,
    usd_inr             FLOAT,
    nifty_vix           FLOAT,
    llm_regime_score    JSONB,
    rule_based_regime   VARCHAR(50),
    llm_regime          VARCHAR(50),
    final_regime        VARCHAR(50)
);
SELECT create_hypertable('macro_regime_history', 'time', if_not_exists => TRUE);

-- ----------------------------------------------------------
-- 6. Technical signals
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS technical_signals (
    time                TIMESTAMPTZ     NOT NULL,
    ticker              VARCHAR(20)     NOT NULL,
    close_price         FLOAT,
    sma_50              FLOAT,
    sma_200             FLOAT,
    golden_cross        BOOLEAN,
    death_cross         BOOLEAN,
    rsi_14              FLOAT,
    rsi_overbought      BOOLEAN,
    rsi_oversold        BOOLEAN,
    bb_upper            FLOAT,
    bb_lower            FLOAT,
    bb_squeeze          BOOLEAN,
    macd_line           FLOAT,
    macd_signal         FLOAT,
    macd_histogram      FLOAT,
    macd_crossover      VARCHAR(10),
    volume              BIGINT,
    volume_vs_avg20     FLOAT,
    supertrend_direction VARCHAR(5),
    supertrend_flip     BOOLEAN
);
SELECT create_hypertable('technical_signals', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_tech_ticker ON technical_signals (ticker, time DESC);

-- ----------------------------------------------------------
-- 7. Alpha signals
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS alpha_signals (
    id                  UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    time                TIMESTAMPTZ     NOT NULL,
    ticker              VARCHAR(20)     NOT NULL,
    exchange            VARCHAR(10),
    sector              VARCHAR(30),
    pattern             VARCHAR(50)     NOT NULL,
    signal_type         VARCHAR(50)     NOT NULL,
    confidence          VARCHAR(20)     NOT NULL,
    regime              VARCHAR(50),
    crss                FLOAT,
    ics                 FLOAT,
    fii_net_5d_crores   FLOAT,
    supporting_evidence JSONB,
    is_resolved         BOOLEAN         DEFAULT FALSE,
    resolved_at         TIMESTAMPTZ,
    actual_return       FLOAT
);
SELECT create_hypertable('alpha_signals', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_alpha_ticker ON alpha_signals (ticker, time DESC);
CREATE INDEX IF NOT EXISTS idx_alpha_confidence ON alpha_signals (confidence, is_resolved);

-- ----------------------------------------------------------
-- 8. Corporate actions
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS corporate_actions (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    ticker          VARCHAR(20) NOT NULL,
    exchange        VARCHAR(10),
    action_type     VARCHAR(50) NOT NULL,
    event_date      DATE        NOT NULL,
    record_date     DATE,
    ex_date         DATE,
    details         JSONB,
    result_analysis JSONB,
    momentum_label  VARCHAR(20),
    alert_sent      BOOLEAN      DEFAULT FALSE,
    created_at      TIMESTAMPTZ  DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_corp_ticker ON corporate_actions (ticker, event_date);
CREATE INDEX IF NOT EXISTS idx_corp_event ON corporate_actions (event_date, action_type);

-- ----------------------------------------------------------
-- 9. Portfolio holdings
-- ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS portfolio_holdings (
    id                      UUID    PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id                 VARCHAR(100) NOT NULL,
    ticker                  VARCHAR(20)  NOT NULL,
    quantity                INT          NOT NULL,
    avg_cost                FLOAT        NOT NULL,
    vulnerability_score     FLOAT,
    vulnerability_breakdown JSONB,
    last_updated            TIMESTAMPTZ  DEFAULT NOW(),
    UNIQUE (user_id, ticker)
);
