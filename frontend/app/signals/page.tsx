"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import RegimeBadge from "@/components/regime/RegimeBadge";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function SignalsPage() {
  const [signals, setSignals] = useState<Record<string, unknown>[]>([]);
  const [filter, setFilter] = useState({ sector: "", confidence: "", pattern: "" });
  const [selected, setSelected] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    async function load() {
      const params = new URLSearchParams();
      if (filter.sector) params.set("sector", filter.sector);
      if (filter.confidence) params.set("confidence", filter.confidence);
      params.set("limit", "20");
      try {
        const res = await fetch(`${API}/api/v1/signals/history?${params}`);
        const json = await res.json();
        setSignals(json.data || []);
      } catch {}
    }
    load();
  }, [filter]);

  const confColor = (c: string) =>
    c === "HIGH" ? "text-ims-bearish border-ims-bearish" :
    c === "MEDIUM_HIGH" ? "text-ims-warning border-ims-warning" :
    "text-ims-text-secondary border-ims-text-secondary";

  return (
    <div className="min-h-screen bg-ims-bg">
      <nav className="border-b border-ims-border bg-ims-bg-panel px-4 py-2 flex items-center gap-4 text-xs">
        <Link href="/" className="text-ims-text-secondary hover:text-ims-teal">← Dashboard</Link>
        <span className="text-ims-teal font-semibold">Alpha Signals</span>
      </nav>

      <div className="p-4 max-w-7xl mx-auto">
        {/* Filter Bar */}
        <div className="terminal-panel p-3 mb-4 flex flex-wrap gap-3 items-center">
          <select
            className="bg-ims-bg-card border border-ims-border rounded px-2 py-1 text-xs text-ims-text-primary"
            value={filter.sector}
            onChange={e => setFilter(f => ({ ...f, sector: e.target.value }))}
          >
            <option value="">All Sectors</option>
            <option value="Energy">Energy</option>
            <option value="Pharma">Pharma</option>
            <option value="Textile">Textile</option>
          </select>
          <select
            className="bg-ims-bg-card border border-ims-border rounded px-2 py-1 text-xs text-ims-text-primary"
            value={filter.confidence}
            onChange={e => setFilter(f => ({ ...f, confidence: e.target.value }))}
          >
            <option value="">All Confidence</option>
            <option value="HIGH">HIGH</option>
            <option value="MEDIUM_HIGH">MEDIUM_HIGH</option>
            <option value="MEDIUM">MEDIUM</option>
          </select>
        </div>

        {/* Signal Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {signals.map((sig) => (
            <button
              key={sig.signal_id as string}
              onClick={() => setSelected(sig)}
              className="text-left terminal-panel p-4 hover:border-ims-teal transition-colors"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="font-mono font-bold text-ims-teal">{sig.ticker as string}</span>
                  <span className="text-[10px] text-ims-text-secondary">{sig.sector as string}</span>
                </div>
                <span className={`text-[10px] font-semibold px-2 py-0.5 rounded border ${confColor(sig.confidence as string)}`}>
                  {sig.confidence as string}
                </span>
              </div>
              <div className="text-xs text-ims-text-primary mb-1">
                {(sig.pattern as string)?.replace(/_/g, " ")}
              </div>
              <div className="text-[10px] text-ims-text-secondary">
                {(sig.signal_type as string)?.replace(/_/g, " ")}
              </div>
              <div className="flex items-center gap-4 mt-2 text-[10px] font-mono">
                {sig.crss != null && <span>CRSS: {(sig.crss as number)?.toFixed(2)}</span>}
                {sig.ics != null && <span>ICS: {(sig.ics as number)?.toFixed(2)}</span>}
                {sig.is_resolved && (
                  <span className={`font-semibold ${
                    (sig.actual_return as number) > 0 ? "text-ims-bullish" : "text-ims-bearish"
                  }`}>
                    Return: {(sig.actual_return as number)?.toFixed(1)}%
                  </span>
                )}
              </div>
              <div className="text-[9px] text-ims-text-secondary mt-1">
                {new Date(sig.timestamp as string).toLocaleString("en-IN")}
                {sig.regime && <> · <RegimeBadge regime={sig.regime as string} size="sm" /></>}
              </div>
            </button>
          ))}
        </div>

        {signals.length === 0 && (
          <div className="terminal-panel p-12 text-center text-ims-text-secondary text-sm">
            No signals matching current filters
          </div>
        )}
      </div>

      {/* Detail Modal */}
      {selected && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4"
          onClick={() => setSelected(null)}>
          <div className="terminal-panel p-6 max-w-lg w-full max-h-[80vh] overflow-y-auto"
            onClick={e => e.stopPropagation()}>
            <div className="flex justify-between mb-4">
              <span className="font-mono text-xl font-bold text-ims-teal">{selected.ticker as string}</span>
              <button onClick={() => setSelected(null)} className="text-ims-text-secondary hover:text-white">✕</button>
            </div>
            <div className="space-y-3">
              <div className="text-sm text-ims-text-primary">{(selected.pattern as string)?.replace(/_/g, " ")}</div>
              <div className="text-xs text-ims-warning">{(selected.signal_type as string)?.replace(/_/g, " ")}</div>
              {selected.supporting_evidence && (
                <div className="space-y-1">
                  {(selected.supporting_evidence as string[]).map((ev, i) => (
                    <div key={i} className="text-xs flex gap-2">
                      <span className="text-ims-teal">▸</span>
                      <span>{ev}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
