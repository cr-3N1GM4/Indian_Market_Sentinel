"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function CalendarPage() {
  const [actions, setActions] = useState<Record<string, unknown>[]>([]);
  const [alerts, setAlerts] = useState<Record<string, unknown>[]>([]);
  const [buybacks, setBuybacks] = useState<Record<string, unknown>[]>([]);
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [resultAnalysis, setResultAnalysis] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [actRes, alertRes, bbRes] = await Promise.all([
          fetch(`${API}/api/v1/calendar/upcoming?days=30`).then(r => r.json()),
          fetch(`${API}/api/v1/calendar/alerts`).then(r => r.json()),
          fetch(`${API}/api/v1/calendar/buybacks`).then(r => r.json()),
        ]);
        setActions(actRes.data || []);
        setAlerts(alertRes.data || []);
        setBuybacks(bbRes.data || []);
      } catch {}
    }
    load();
  }, []);

  const loadResult = async (ticker: string) => {
    setSelectedTicker(ticker);
    try {
      const res = await fetch(`${API}/api/v1/calendar/results/${ticker}`);
      const json = await res.json();
      setResultAnalysis(json.data);
    } catch {}
  };

  const chipColor = (type: string) => {
    const colors: Record<string, string> = {
      RESULT: "bg-ims-teal/20 text-ims-teal border-ims-teal",
      BUYBACK: "bg-ims-bullish/20 text-ims-bullish border-ims-bullish",
      DIVIDEND: "bg-ims-warning/20 text-ims-warning border-ims-warning",
      BONUS: "bg-ims-text-secondary/20 text-ims-text-secondary border-ims-text-secondary",
      SPLIT: "bg-ims-text-secondary/20 text-ims-text-secondary border-ims-text-secondary",
    };
    return colors[type] || "bg-ims-bg-card text-ims-text-secondary border-ims-border";
  };

  const highAlerts = alerts.filter(a => a.alert_severity === "HIGH");

  return (
    <div className="min-h-screen bg-ims-bg">
      <nav className="border-b border-ims-border bg-ims-bg-panel px-4 py-2 flex items-center gap-4 text-xs">
        <Link href="/" className="text-ims-text-secondary hover:text-ims-teal">← Dashboard</Link>
        <span className="text-ims-teal font-semibold">Corporate Actions Calendar</span>
      </nav>

      {/* Alert Banner */}
      {highAlerts.length > 0 && (
        <div className="bg-ims-warning/10 border-b border-ims-warning/30 px-4 py-2">
          <div className="flex items-center gap-2 text-xs">
            <span className="text-ims-warning font-bold">⚠ PRE-EVENT ALERTS:</span>
            {highAlerts.map((a, i) => (
              <span key={i} className="text-ims-text-primary">
                {a.ticker as string} — {a.event_type as string} ({a.days_until === 0 ? "TODAY" : "TOMORROW"})
                {i < highAlerts.length - 1 ? " | " : ""}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="p-4 max-w-7xl mx-auto">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Event List */}
          <div className="lg:col-span-2 terminal-panel p-4">
            <h3 className="text-sm font-semibold text-ims-text-secondary mb-3 uppercase tracking-wider">
              Upcoming Events (30 Days)
            </h3>
            <div className="space-y-2">
              {actions.map((a, i) => {
                const daysUntil = Math.max(0, Math.ceil(
                  (new Date(a.event_date as string).getTime() - Date.now()) / 86400000
                ));
                return (
                  <button
                    key={i}
                    onClick={() => a.action_type === "RESULT" && loadResult(a.ticker as string)}
                    className="w-full text-left terminal-panel p-3 hover:border-ims-teal transition-colors flex items-center justify-between"
                  >
                    <div className="flex items-center gap-3">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${chipColor(a.action_type as string)}`}>
                        {a.action_type as string}
                      </span>
                      <span className="font-mono font-bold text-sm text-ims-teal">{a.ticker as string}</span>
                      <span className="text-xs text-ims-text-secondary">{a.event_date as string}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      {a.momentum_label && (
                        <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${
                          (a.momentum_label as string).includes("BUY") ? "text-ims-bullish bg-ims-bullish/10" :
                          (a.momentum_label as string).includes("SELL") ? "text-ims-bearish bg-ims-bearish/10" :
                          "text-ims-text-secondary"
                        }`}>{a.momentum_label as string}</span>
                      )}
                      <span className={`text-xs font-mono ${daysUntil <= 1 ? "text-ims-warning font-bold" : "text-ims-text-secondary"}`}>
                        {daysUntil === 0 ? "TODAY" : daysUntil === 1 ? "TMRW" : `${daysUntil}d`}
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Result Analysis / Buybacks */}
          <div className="space-y-4">
            {resultAnalysis && (
              <div className="terminal-panel p-4">
                <h3 className="text-sm font-semibold text-ims-teal mb-3">
                  Result Analysis: {selectedTicker}
                </h3>
                <div className="space-y-2 text-xs">
                  <div className="flex justify-between">
                    <span className="text-ims-text-secondary">Score</span>
                    <span className="font-mono font-bold">{resultAnalysis.score as number}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-ims-text-secondary">Momentum</span>
                    <span className={`font-mono font-bold ${
                      (resultAnalysis.momentum_label as string)?.includes("BUY") ? "text-ims-bullish" :
                      (resultAnalysis.momentum_label as string)?.includes("SELL") ? "text-ims-bearish" : ""
                    }`}>{resultAnalysis.momentum_label as string}</span>
                  </div>
                  {resultAnalysis.pe_ratio && (
                    <div className="flex justify-between">
                      <span className="text-ims-text-secondary">P/E</span>
                      <span className="font-mono">{(resultAnalysis.pe_ratio as number)?.toFixed(1)}</span>
                    </div>
                  )}
                  {resultAnalysis.roe && (
                    <div className="flex justify-between">
                      <span className="text-ims-text-secondary">ROE</span>
                      <span className="font-mono">{(resultAnalysis.roe as number)?.toFixed(1)}%</span>
                    </div>
                  )}
                  <a href={resultAnalysis.screener_url as string} target="_blank" rel="noopener noreferrer"
                    className="text-ims-teal text-[10px] hover:underline block mt-2">
                    View on Screener.in →
                  </a>
                </div>
              </div>
            )}

            {/* Buyback Opportunities */}
            <div className="terminal-panel p-4">
              <h3 className="text-sm font-semibold text-ims-text-secondary mb-3 uppercase tracking-wider">
                Buyback Opportunities
              </h3>
              {buybacks.filter(b => b.is_opportunity).length > 0 ? (
                <div className="space-y-2">
                  {buybacks.filter(b => b.is_opportunity).map((b, i) => (
                    <div key={i} className="terminal-panel p-3 border-l-2 border-l-ims-bullish">
                      <div className="font-mono font-bold text-ims-teal text-sm">{b.ticker as string}</div>
                      <div className="grid grid-cols-2 gap-2 mt-1 text-[10px]">
                        <span>Premium: <span className="text-ims-bullish font-bold">{(b.premium_pct as number)?.toFixed(1)}%</span></span>
                        <span>Size: {(b.size_pct_mcap as number)?.toFixed(1)}% mcap</span>
                        <span>Method: {b.method as string}</span>
                        <span>Date: {b.event_date as string}</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-xs text-ims-text-secondary text-center py-4">
                  No active buyback opportunities
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
