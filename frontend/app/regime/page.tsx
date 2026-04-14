"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import RegimeBadge from "@/components/regime/RegimeBadge";
import { REGIME_COLORS, REGIME_LABELS } from "@/lib/types";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function RegimePage() {
  const [current, setCurrent] = useState<Record<string, unknown> | null>(null);
  const [history, setHistory] = useState<Record<string, unknown>[]>([]);

  useEffect(() => {
    async function load() {
      try {
        const [curRes, histRes] = await Promise.all([
          fetch(`${API}/api/v1/regime/current`).then(r => r.json()),
          fetch(`${API}/api/v1/regime/history?days=365`).then(r => r.json()),
        ]);
        setCurrent(curRes.data);
        setHistory(histRes.data || []);
      } catch (err) { console.error(err); }
    }
    load();
  }, []);

  const llmScore = current?.llm_score as Record<string, unknown> | null;

  return (
    <div className="min-h-screen bg-ims-bg">
      {/* Nav */}
      <nav className="border-b border-ims-border bg-ims-bg-panel px-4 py-2 flex items-center gap-4 text-xs">
        <Link href="/" className="text-ims-text-secondary hover:text-ims-teal">← Dashboard</Link>
        <span className="text-ims-teal font-semibold">Regime Intelligence</span>
      </nav>

      <div className="p-4 space-y-4 max-w-7xl mx-auto">
        {/* Current Regime Card */}
        <div className="terminal-panel p-6">
          <div className="flex items-start justify-between flex-wrap gap-4">
            <div>
              <h1 className="text-lg font-semibold text-ims-text-primary mb-2">Current Macro Regime</h1>
              <RegimeBadge
                regime={(current?.regime as string) || "neutral_watchful"}
                confidence={current?.confidence as number}
                size="lg"
              />
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-center">
              {[
                { label: "Repo Rate", value: current?.repo_rate, suffix: "%" },
                { label: "CPI YoY", value: current?.cpi_yoy, suffix: "%" },
                { label: "10Y G-Sec", value: current?.gsec_10y, suffix: "%" },
                { label: "VIX", value: current?.nifty_vix, suffix: "" },
              ].map(item => (
                <div key={item.label} className="terminal-panel p-3">
                  <div className="text-[10px] text-ims-text-secondary uppercase">{item.label}</div>
                  <div className="font-mono font-bold text-lg text-ims-text-primary mt-1">
                    {(item.value as number)?.toFixed(2) || "—"}{item.suffix}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* LLM Score Details */}
          {llmScore && (
            <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="terminal-panel p-3">
                <div className="text-[10px] text-ims-text-secondary uppercase mb-1">Rate Trajectory (6M)</div>
                <div className="font-mono font-semibold text-ims-teal">{llmScore.rate_trajectory_6m as string}</div>
              </div>
              <div className="terminal-panel p-3">
                <div className="text-[10px] text-ims-text-secondary uppercase mb-1">Liquidity Stance</div>
                <div className="font-mono font-semibold text-ims-warning">{llmScore.liquidity_stance as string}</div>
              </div>
              <div className="terminal-panel p-3">
                <div className="text-[10px] text-ims-text-secondary uppercase mb-1">Priority</div>
                <div className="font-mono font-semibold text-ims-text-primary">{(llmScore.growth_vs_inflation_priority as string)?.replace(/_/g, " ")}</div>
              </div>
            </div>
          )}

          {/* Key Quote */}
          {llmScore?.key_quote && (
            <div className="mt-4 p-3 bg-ims-bg-card rounded border-l-2 border-ims-teal">
              <div className="text-[10px] text-ims-text-secondary uppercase mb-1">Key Quote from MPC Minutes</div>
              <div className="text-sm text-ims-text-primary italic">&ldquo;{llmScore.key_quote as string}&rdquo;</div>
            </div>
          )}

          {/* Vote Breakdown */}
          {llmScore?.committee_vote_breakdown && (
            <div className="mt-3 text-xs text-ims-text-secondary">
              <span className="font-semibold text-ims-text-primary">Committee Vote: </span>
              {llmScore.committee_vote_breakdown as string}
            </div>
          )}
        </div>

        {/* Hawkish / Dovish Signals */}
        {llmScore && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="terminal-panel p-4">
              <h3 className="text-sm font-semibold text-ims-bearish mb-3">Hawkish Signals</h3>
              <div className="space-y-2">
                {(llmScore.hawkish_signals as string[])?.map((s, i) => (
                  <div key={i} className="text-xs text-ims-text-primary flex gap-2">
                    <span className="text-ims-bearish shrink-0">▸</span>
                    <span>{s}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="terminal-panel p-4">
              <h3 className="text-sm font-semibold text-ims-bullish mb-3">Dovish Signals</h3>
              <div className="space-y-2">
                {(llmScore.dovish_signals as string[])?.map((s, i) => (
                  <div key={i} className="text-xs text-ims-text-primary flex gap-2">
                    <span className="text-ims-bullish shrink-0">▸</span>
                    <span>{s}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Regime Timeline */}
        <div className="terminal-panel p-4">
          <h3 className="text-sm font-semibold text-ims-text-secondary mb-4 uppercase tracking-wider">
            Regime History
          </h3>
          <div className="overflow-x-auto">
            <div className="flex gap-0.5 min-w-[600px] h-10">
              {history.map((h, i) => {
                const regime = h.regime as string;
                const color = REGIME_COLORS[regime] || "#64748B";
                return (
                  <div
                    key={i}
                    className="flex-1 rounded-sm cursor-pointer hover:opacity-80 transition-opacity"
                    style={{ backgroundColor: color + "40", borderBottom: `3px solid ${color}` }}
                    title={`${REGIME_LABELS[regime] || regime} | ${(h.time as string)?.slice(0, 10)} | Repo: ${h.repo_rate}% | CPI: ${h.cpi_yoy}%`}
                  />
                );
              })}
            </div>
            <div className="flex justify-between text-[9px] text-ims-text-secondary mt-1">
              <span>{(history[0]?.time as string)?.slice(0, 10) || ""}</span>
              <span>{(history[history.length - 1]?.time as string)?.slice(0, 10) || ""}</span>
            </div>
          </div>

          {/* Legend */}
          <div className="flex flex-wrap gap-3 mt-3">
            {Object.entries(REGIME_LABELS).map(([key, label]) => (
              <div key={key} className="flex items-center gap-1 text-[10px]">
                <span className="w-3 h-2 rounded-sm" style={{ backgroundColor: REGIME_COLORS[key] }} />
                <span className="text-ims-text-secondary">{label}</span>
              </div>
            ))}
          </div>
        </div>

        {/* History Table */}
        <div className="terminal-panel p-4">
          <h3 className="text-sm font-semibold text-ims-text-secondary mb-3 uppercase tracking-wider">
            Regime History Table
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-xs font-mono">
              <thead>
                <tr className="text-ims-text-secondary border-b border-ims-border">
                  <th className="text-left py-2 px-2">Date</th>
                  <th className="text-left py-2 px-2">Regime</th>
                  <th className="text-right py-2 px-2">Confidence</th>
                  <th className="text-right py-2 px-2">Repo</th>
                  <th className="text-right py-2 px-2">CPI</th>
                </tr>
              </thead>
              <tbody>
                {history.slice(-20).reverse().map((h, i) => (
                  <tr key={i} className="border-b border-ims-border/30 hover:bg-ims-bg-card">
                    <td className="py-1.5 px-2 text-ims-text-secondary">{(h.time as string)?.slice(0, 10)}</td>
                    <td className="py-1.5 px-2">
                      <span style={{ color: REGIME_COLORS[h.regime as string] || "#64748B" }}>
                        {REGIME_LABELS[h.regime as string] || h.regime as string}
                      </span>
                    </td>
                    <td className="py-1.5 px-2 text-right">{((h.confidence as number) * 100)?.toFixed(0)}%</td>
                    <td className="py-1.5 px-2 text-right">{(h.repo_rate as number)?.toFixed(2)}%</td>
                    <td className="py-1.5 px-2 text-right">{(h.cpi_yoy as number)?.toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
