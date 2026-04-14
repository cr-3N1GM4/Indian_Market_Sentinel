// ARCHITECTURE NOTE:
// All API response types + Zod validation schemas in one place.
// Frontend never uses `any` — every API response is validated
// through these schemas before being used in components.

import { z } from "zod";

// ----------------------------------------------------------
// Enums
// ----------------------------------------------------------

export const MacroRegime = {
  HAWKISH_TIGHTENING: "hawkish_tightening",
  HAWKISH_PAUSE: "hawkish_pause",
  NEUTRAL_WATCHFUL: "neutral_watchful",
  DOVISH_PAUSE: "dovish_pause",
  DOVISH_EASING: "dovish_easing",
  CRISIS_LIQUIDITY: "crisis_liquidity",
} as const;

export type MacroRegimeType = (typeof MacroRegime)[keyof typeof MacroRegime];

export const REGIME_COLORS: Record<string, string> = {
  hawkish_tightening: "#FF3B5C",
  hawkish_pause: "#FFB800",
  neutral_watchful: "#64748B",
  dovish_pause: "#00D4FF",
  dovish_easing: "#00FF88",
  crisis_liquidity: "#FF3B5C",
};

export const REGIME_LABELS: Record<string, string> = {
  hawkish_tightening: "Hawkish Tightening",
  hawkish_pause: "Hawkish Pause",
  neutral_watchful: "Neutral Watchful",
  dovish_pause: "Dovish Pause",
  dovish_easing: "Dovish Easing",
  crisis_liquidity: "Crisis Liquidity",
};

// ----------------------------------------------------------
// API Response Envelope
// ----------------------------------------------------------

export const ApiMetaSchema = z.object({
  timestamp: z.string(),
  version: z.string().default("1.0"),
  stale: z.boolean().optional(),
});

// ----------------------------------------------------------
// Sentiment
// ----------------------------------------------------------

export const TickerSentimentSchema = z.object({
  ticker: z.string(),
  crss: z.number(),
  twitter_score: z.number().nullable().optional(),
  reddit_score: z.number().nullable().optional(),
  news_score: z.number().nullable().optional(),
  data_points: z.number().default(0),
  trend: z.enum(["RISING", "FALLING", "STABLE"]).default("STABLE"),
  last_updated: z.string().nullable().optional(),
});

export type TickerSentiment = z.infer<typeof TickerSentimentSchema>;

export const HeatmapTickerSchema = z.object({
  crss: z.number().default(0),
  ics: z.number().default(0),
  crss_trend: z.string().default("STABLE"),
  data_points: z.number().default(0),
});

export const HeatmapSectorSchema = z.object({
  tickers: z.record(HeatmapTickerSchema),
});

export const HeatmapResponseSchema = z.object({
  sectors: z.record(HeatmapSectorSchema),
});

export type HeatmapResponse = z.infer<typeof HeatmapResponseSchema>;

// ----------------------------------------------------------
// Alpha Signals
// ----------------------------------------------------------

export const AlphaSignalSchema = z.object({
  signal_id: z.string(),
  timestamp: z.string(),
  ticker: z.string(),
  exchange: z.string().default("NSE"),
  sector: z.string().nullable().optional(),
  pattern: z.string(),
  signal_type: z.string(),
  confidence: z.string(),
  regime: z.string().nullable().optional(),
  crss: z.number().nullable().optional(),
  ics: z.number().nullable().optional(),
  fii_net_5d_crores: z.number().nullable().optional(),
  supporting_evidence: z.array(z.string()).default([]),
  is_resolved: z.boolean().default(false),
  resolved_at: z.string().nullable().optional(),
  actual_return: z.number().nullable().optional(),
});

export type AlphaSignal = z.infer<typeof AlphaSignalSchema>;

// ----------------------------------------------------------
// Regime
// ----------------------------------------------------------

export const RegimeScoreSchema = z.object({
  regime: z.string(),
  confidence: z.number(),
  hawkish_signals: z.array(z.string()).default([]),
  dovish_signals: z.array(z.string()).default([]),
  key_quote: z.string().default(""),
  rate_trajectory_6m: z.string().default("UNCERTAIN"),
  liquidity_stance: z.string().default("NEUTRAL"),
  growth_vs_inflation_priority: z.string().default("BALANCED"),
  committee_vote_breakdown: z.string().default(""),
});

export const RegimeCurrentSchema = z.object({
  regime: z.string(),
  confidence: z.number().nullable().optional(),
  repo_rate: z.number().nullable().optional(),
  cpi_yoy: z.number().nullable().optional(),
  wpi_yoy: z.number().nullable().optional(),
  gsec_10y: z.number().nullable().optional(),
  gsec_2y: z.number().nullable().optional(),
  yield_curve_slope: z.number().nullable().optional(),
  usd_inr: z.number().nullable().optional(),
  nifty_vix: z.number().nullable().optional(),
  llm_score: RegimeScoreSchema.nullable().optional(),
  last_updated: z.string().nullable().optional(),
});

export type RegimeCurrent = z.infer<typeof RegimeCurrentSchema>;

export const RegimeHistorySchema = z.object({
  time: z.string(),
  regime: z.string(),
  confidence: z.number().nullable().optional(),
  repo_rate: z.number().nullable().optional(),
  cpi_yoy: z.number().nullable().optional(),
});

export type RegimeHistory = z.infer<typeof RegimeHistorySchema>;

// ----------------------------------------------------------
// Corporate Actions
// ----------------------------------------------------------

export const CorporateActionSchema = z.object({
  id: z.string(),
  ticker: z.string(),
  exchange: z.string().default("NSE"),
  action_type: z.string(),
  event_date: z.string(),
  record_date: z.string().nullable().optional(),
  ex_date: z.string().nullable().optional(),
  details: z.any().optional(),
  momentum_label: z.string().nullable().optional(),
});

export type CorporateAction = z.infer<typeof CorporateActionSchema>;

export const PreEventAlertSchema = z.object({
  ticker: z.string(),
  event_type: z.string(),
  event_date: z.string(),
  days_until: z.number(),
  alert_severity: z.string(),
  context: z.string().nullable().optional(),
});

export type PreEventAlert = z.infer<typeof PreEventAlertSchema>;

// ----------------------------------------------------------
// Institutional
// ----------------------------------------------------------

export const FIIDIIFlowSchema = z.object({
  date: z.string(),
  fii_net_crores: z.number().default(0),
  dii_net_crores: z.number().default(0),
});

export type FIIDIIFlow = z.infer<typeof FIIDIIFlowSchema>;

// ----------------------------------------------------------
// Portfolio
// ----------------------------------------------------------

export const VulnerabilitySchema = z.object({
  overall_vulnerability_score: z.number(),
  overall_label: z.string(),
  macro_sensitivity: z.object({
    usd_inr_corr: z.number().default(0),
    crude_corr: z.number().default(0),
    gsec_10y_corr: z.number().default(0),
    cpi_surprise_corr: z.number().default(0),
    label: z.string().default("LOW"),
  }),
  supply_chain_risk: z.string().default("LOW"),
  fii_flight_risk: z.string().default("LOW"),
  earnings_risk: z.object({
    days_to_result: z.number().nullable().optional(),
    historical_move_pct: z.number().nullable().optional(),
    implied_move_pct: z.number().nullable().optional(),
    label: z.string().default("LOW"),
  }),
  technical_risk: z.string().default("LOW"),
  active_alerts: z.array(z.string()).default([]),
});

export type Vulnerability = z.infer<typeof VulnerabilitySchema>;

export const StressScenarioSchema = z.object({
  scenario_name: z.string(),
  description: z.string(),
  portfolio_pnl_inr: z.number(),
  portfolio_pnl_pct: z.number(),
  most_affected_ticker: z.string(),
  most_affected_pnl_pct: z.number(),
});

export type StressScenario = z.infer<typeof StressScenarioSchema>;

// ----------------------------------------------------------
// Market Data
// ----------------------------------------------------------

export const MarketIndexSchema = z.object({
  last: z.number(),
  change: z.number(),
  pChange: z.number(),
});

export const MarketDataSchema = z.object({
  nifty50: MarketIndexSchema,
  sensex: MarketIndexSchema,
  niftyBank: MarketIndexSchema,
  usdInr: z.number(),
  brentCrude: z.number(),
  goldMcx: z.number(),
  indiaVix: z.number(),
});

export type MarketData = z.infer<typeof MarketDataSchema>;
