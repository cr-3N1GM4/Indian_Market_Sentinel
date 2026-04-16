"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface RegimeData {
  regime: string;
  confidence: number | null;
  repo_rate: number | null;
  cpi_yoy: number | null;
  wpi_yoy: number | null;
  gsec_10y: number | null;
  gsec_2y: number | null;
  yield_curve_slope: number | null;
  usd_inr: number | null;
  nifty_vix: number | null;
  llm_score: {
    regime: string;
    confidence: number;
    hawkish_signals: string[];
    dovish_signals: string[];
    key_quote: string;
    rate_trajectory_6m: string;
    liquidity_stance: string;
    growth_vs_inflation_priority: string;
    committee_vote_breakdown: string;
  } | null;
}

interface RegimeHistoryItem {
  time: string;
  regime: string;
  confidence: number | null;
  repo_rate: number | null;
  cpi_yoy: number | null;
}

const REGIME_COLORS: Record<string, string> = {
  hawkish_tightening: "#FF3B5C",
  hawkish_pause: "#FFB800",
  neutral_watchful: "#64748B",
  dovish_pause: "#00D4FF",
  dovish_easing: "#00FF88",
  crisis_liquidity: "#FF3B5C",
};

const REGIME_LABELS: Record<string, string> = {
  hawkish_tightening: "Hawkish Tightening",
  hawkish_pause: "Hawkish Pause",
  neutral_watchful: "Neutral Watchful",
  dovish_pause: "Dovish Pause",
  dovish_easing: "Dovish Easing",
  crisis_liquidity: "Crisis Liquidity",
};

export default function RegimePage() {
  const [data, setData] = useState<RegimeData | null>(null);
  const [history, setHistory] = useState<RegimeHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [currentRes, historyRes] = await Promise.allSettled([
          fetch(`${API}/api/v1/regime/current`).then(r => r.json()),
          fetch(`${API}/api/v1/regime/history?days=180`).then(r => r.json()),
        ]);
        if (currentRes.status === "fulfilled") setData(currentRes.value.data);
        if (historyRes.status === "fulfilled") setHistory(historyRes.value.data || []);
      } catch (err) {
        console.error("Regime load error:", err);
      }
      setLoading(false);
    }
    load();
  }, []);

  const formatNum = (v: number | null | undefined, decimals = 2, suffix = "%") => {
    if (v === null || v === undefined) return "—";
    return `${v.toFixed(decimals)}${suffix}`;
  };

  const regimeColor = data ? REGIME_COLORS[data.regime] || "#64748B" : "#64748B";
  const regimeLabel = data ? REGIME_LABELS[data.regime] || data.regime.replace(/_/g, " ") : "Loading...";

  return (
    <div className="min-h-screen bg-ims-bg">
      <nav className="border-b border-ims-border bg-ims-bg-panel px-4 py-2 flex items-center gap-4 text-xs">
        <Link href="/" className="text-ims-text-secondary hover:text-ims-teal">← Dashboard</Link>
        <span className="text-ims-teal font-semibold">Regime Intelligence</span>
      </nav>

      <div className="p-4 max-w-5xl mx-auto space-y-4">
        {loading ? (
          <div className="text-center text-ims-text-secondary py-20 animate-pulse">Loading regime data...</div>
        ) : data ? (
          <>
            {/* Current Regime Card */}
            <div className="terminal-panel p-6">
              <div className="flex items-start justify-between flex-wrap gap-4">
                <div>
                  <h2 className="text-lg font-bold text-ims-text-primary mb-2">Current Macro Regime</h2>
                  <div
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border-2"
                    style={{ borderColor: regimeColor, backgroundColor: `${regimeColor}15` }}
                  >
                    <div className="w-3 h-3 rounded-full" style={{ backgroundColor: regimeColor }} />
                    <span className="font-semibold text-lg" style={{ color: regimeColor }}>{regimeLabel}</span>
                  </div>
                  {data.confidence != null && (
                    <div className="text-xs text-ims-text-secondary mt-2">
                      Confidence: <span className="font-mono font-bold text-ims-text-primary">{(data.confidence * 100).toFixed(0)}%</span>
                    </div>
                  )}
                </div>

                {/* Macro Indicators */}
                <div className="grid grid-cols-4 gap-3">
                  {[
                    { label: "REPO RATE", value: formatNum(data.repo_rate) },
                    { label: "CPI YoY", value: formatNum(data.cpi_yoy, 1) },
                    { label: "10Y G-SEC", value: formatNum(data.gsec_10y) },
                    { label: "VIX", value: data.nifty_vix != null ? data.nifty_vix.toFixed(1) : "—" },
                  ].map((ind) => (
                    <div key={ind.label} className="terminal-panel p-3 text-center min-w-[80px]">
                      <div className="text-[10px] text-ims-text-secondary uppercase font-semibold">{ind.label}</div>
                      <div className="font-mono font-bold text-lg text-ims-text-primary mt-1">{ind.value}</div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Additional Macro Data */}
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mt-4">
                {[
                  { label: "WPI YoY", value: formatNum(data.wpi_yoy, 1) },
                  { label: "2Y G-Sec", value: formatNum(data.gsec_2y) },
                  { label: "Yield Slope", value: data.yield_curve_slope != null ? data.yield_curve_slope.toFixed(2) : "—" },
                  { label: "USD/INR", value: data.usd_inr != null ? `₹${data.usd_inr.toFixed(2)}` : "—" },
                  { label: "Confidence", value: data.confidence != null ? `${(data.confidence * 100).toFixed(0)}%` : "—" },
                ].map((ind) => (
                  <div key={ind.label} className="terminal-panel p-2 text-center">
                    <div className="text-[9px] text-ims-text-secondary uppercase">{ind.label}</div>
                    <div className="font-mono font-bold text-sm text-ims-text-primary">{ind.value}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* LLM Analysis */}
            {data.llm_score && (
              <div className="terminal-panel p-4">
                <h3 className="text-sm font-semibold text-ims-teal uppercase tracking-wider mb-4">🤖 LLM Regime Analysis</h3>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
                  <div className="terminal-panel p-3 text-center">
                    <div className="text-[10px] text-ims-text-secondary">Rate Trajectory (6M)</div>
                    <div className="font-mono font-bold text-ims-text-primary mt-1">{data.llm_score.rate_trajectory_6m}</div>
                  </div>
                  <div className="terminal-panel p-3 text-center">
                    <div className="text-[10px] text-ims-text-secondary">Liquidity Stance</div>
                    <div className="font-mono font-bold text-ims-text-primary mt-1">{data.llm_score.liquidity_stance}</div>
                  </div>
                  <div className="terminal-panel p-3 text-center">
                    <div className="text-[10px] text-ims-text-secondary">Priority</div>
                    <div className="font-mono font-bold text-ims-text-primary mt-1">
                      {data.llm_score.growth_vs_inflation_priority?.replace(/_/g, " ") || "—"}
                    </div>
                  </div>
                </div>

                {/* Key Quote */}
                {data.llm_score.key_quote && (
                  <div className="terminal-panel p-3 border-l-2 border-l-ims-teal mb-4">
                    <div className="text-[10px] text-ims-text-secondary mb-1">Key Quote</div>
                    <div className="text-sm text-ims-text-primary italic">&ldquo;{data.llm_score.key_quote}&rdquo;</div>
                  </div>
                )}

                {/* Hawkish / Dovish Signals */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <h4 className="text-xs font-semibold text-ims-bearish uppercase mb-2">🔴 Hawkish Signals</h4>
                    <div className="space-y-1">
                      {(data.llm_score.hawkish_signals || []).map((s, i) => (
                        <div key={i} className="text-xs text-ims-text-secondary flex gap-1">
                          <span className="text-ims-bearish shrink-0">▸</span>
                          <span>{s}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div>
                    <h4 className="text-xs font-semibold text-ims-bullish uppercase mb-2">🟢 Dovish Signals</h4>
                    <div className="space-y-1">
                      {(data.llm_score.dovish_signals || []).map((s, i) => (
                        <div key={i} className="text-xs text-ims-text-secondary flex gap-1">
                          <span className="text-ims-bullish shrink-0">▸</span>
                          <span>{s}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {data.llm_score.committee_vote_breakdown && (
                  <div className="text-xs text-ims-text-secondary mt-3">
                    <span className="font-semibold">Committee Vote:</span> {data.llm_score.committee_vote_breakdown}
                  </div>
                )}
              </div>
            )}

            {/* Regime History */}
            {history.length > 0 && (
              <div className="terminal-panel p-4">
                <h3 className="text-sm font-semibold text-ims-text-secondary uppercase tracking-wider mb-4">Regime History</h3>

                {/* Timeline */}
                <div className="flex gap-1 mb-4 h-8 rounded overflow-hidden">
                  {history.map((h, i) => (
                    <div
                      key={i}
                      className="flex-1 cursor-pointer hover:opacity-80 transition-opacity"
                      style={{ backgroundColor: REGIME_COLORS[h.regime] || "#64748B" }}
                      title={`${new Date(h.time).toLocaleDateString()} - ${REGIME_LABELS[h.regime] || h.regime} (${h.confidence ? (h.confidence * 100).toFixed(0) : "?"}%)`}
                    />
                  ))}
                </div>

                {/* Legend */}
                <div className="flex flex-wrap gap-3 mb-4 text-[10px]">
                  {Object.entries(REGIME_LABELS).map(([key, label]) => (
                    <span key={key} className="flex items-center gap-1">
                      <span
                        className="w-3 h-3 rounded"
                        style={{ backgroundColor: REGIME_COLORS[key] }}
                      />
                      {label}
                    </span>
                  ))}
                </div>

                {/* History Table */}
                <h4 className="text-xs font-semibold text-ims-text-secondary uppercase tracking-wider mb-2">Regime History Table</h4>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs font-mono">
                    <thead>
                      <tr className="text-ims-text-secondary border-b border-ims-border">
                        <th className="text-left py-2 px-2">Date</th>
                        <th className="text-left py-2 px-2">Regime</th>
                        <th className="text-center py-2 px-2">Confidence</th>
                        <th className="text-center py-2 px-2">Repo</th>
                        <th className="text-center py-2 px-2">CPI</th>
                      </tr>
                    </thead>
                    <tbody>
                      {history.slice(-20).reverse().map((h, i) => (
                        <tr key={i} className="border-b border-ims-border/30 hover:bg-ims-bg-card">
                          <td className="py-2 px-2 text-ims-text-secondary">
                            {new Date(h.time).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" })}
                          </td>
                          <td className="py-2 px-2">
                            <span className="flex items-center gap-1.5">
                              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: REGIME_COLORS[h.regime] || "#64748B" }} />
                              <span style={{ color: REGIME_COLORS[h.regime] || "#64748B" }}>
                                {REGIME_LABELS[h.regime] || h.regime}
                              </span>
                            </span>
                          </td>
                          <td className="py-2 px-2 text-center text-ims-text-primary">
                            {h.confidence != null ? `${(h.confidence * 100).toFixed(0)}%` : "—"}
                          </td>
                          <td className="py-2 px-2 text-center text-ims-text-primary">
                            {h.repo_rate != null ? `${h.repo_rate.toFixed(2)}%` : "—"}
                          </td>
                          <td className="py-2 px-2 text-center text-ims-text-primary">
                            {h.cpi_yoy != null ? `${h.cpi_yoy.toFixed(1)}%` : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </>
        ) : (
          <div className="text-center text-ims-text-secondary py-20">No regime data available</div>
        )}
      </div>
    </div>
  );
}
