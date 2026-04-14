"use client";

import { useEffect, useState } from "react";
import RegimeBadge from "@/components/regime/RegimeBadge";
import SectorHeatmap from "@/components/heatmaps/SectorHeatmap";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface MarketTicker {
  label: string;
  value: number;
  change: number;
  changePct: number;
}

interface Signal {
  signal_id: string;
  timestamp: string;
  ticker: string;
  sector?: string;
  pattern: string;
  signal_type: string;
  confidence: string;
  regime?: string;
  crss?: number;
  ics?: number;
  supporting_evidence: string[];
}

interface CorpAction {
  id: string;
  ticker: string;
  action_type: string;
  event_date: string;
  momentum_label?: string;
}

interface FIIDIIDay {
  date: string;
  fii_net_crores: number;
  dii_net_crores: number;
}

export default function Dashboard() {
  const [regime, setRegime] = useState<Record<string, unknown> | null>(null);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [calendar, setCalendar] = useState<CorpAction[]>([]);
  const [fiiDii, setFiiDii] = useState<FIIDIIDay[]>([]);
  const [market, setMarket] = useState<MarketTicker[]>([]);
  const [selectedSignal, setSelectedSignal] = useState<Signal | null>(null);

  useEffect(() => {
    async function loadAll() {
      try {
        const [regimeRes, signalsRes, calRes, fiiRes, mktRes] = await Promise.allSettled([
          fetch(`${API}/api/v1/regime/current`).then(r => r.json()),
          fetch(`${API}/api/v1/signals/active`).then(r => r.json()),
          fetch(`${API}/api/v1/calendar/upcoming?days=7`).then(r => r.json()),
          fetch(`${API}/api/v1/institutional/fii-dii-flows?days=10`).then(r => r.json()),
          fetch(`${API}/api/v1/market-data`).then(r => r.json()),
        ]);

        if (regimeRes.status === "fulfilled") setRegime(regimeRes.value.data);
        if (signalsRes.status === "fulfilled") setSignals(signalsRes.value.data || []);
        if (calRes.status === "fulfilled") setCalendar(calRes.value.data || []);
        if (fiiRes.status === "fulfilled") setFiiDii(fiiRes.value.data || []);
        if (mktRes.status === "fulfilled") {
          const m = mktRes.value.data;
          setMarket([
            { label: "NIFTY 50", value: m.nifty50?.last || 22150, change: m.nifty50?.change || 45, changePct: m.nifty50?.pChange || 0.2 },
            { label: "SENSEX", value: m.sensex?.last || 72800, change: m.sensex?.change || 150, changePct: m.sensex?.pChange || 0.21 },
            { label: "BANK NIFTY", value: m.niftyBank?.last || 47200, change: m.niftyBank?.change || -80, changePct: m.niftyBank?.pChange || -0.17 },
            { label: "USD/INR", value: m.usdInr || 83.25, change: -0.12, changePct: -0.14 },
            { label: "BRENT", value: m.brentCrude || 75.40, change: 0.85, changePct: 1.14 },
            { label: "GOLD MCX", value: m.goldMcx || 62500, change: 350, changePct: 0.56 },
          ]);
        }
      } catch (err) {
        console.error("Dashboard load error:", err);
      }
    }

    loadAll();
    const interval = setInterval(loadAll, 30000);
    return () => clearInterval(interval);
  }, []);

  // WebSocket for live signals
  useEffect(() => {
    const wsUrl = (process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000") + "/ws/live-signals";
    let ws: WebSocket;
    try {
      ws = new WebSocket(wsUrl);
      ws.onmessage = (event) => {
        try {
          const signal = JSON.parse(event.data);
          setSignals(prev => [signal, ...prev].slice(0, 20));
        } catch {}
      };
    } catch {}
    return () => { if (ws) ws.close(); };
  }, []);

  const confidenceColor = (c: string) => {
    if (c === "HIGH") return "text-ims-bearish";
    if (c === "MEDIUM_HIGH") return "text-ims-warning";
    return "text-ims-text-secondary";
  };

  const actionTypeIcon = (t: string) => {
    const icons: Record<string, string> = {
      RESULT: "📊", DIVIDEND: "💰", BUYBACK: "🔄",
      BONUS: "🎁", SPLIT: "✂️", AGM: "🏛️", EGM: "📋",
    };
    return icons[t] || "📌";
  };

  return (
    <div className="min-h-screen bg-ims-bg flex flex-col">
      {/* ============ TOP BAR ============ */}
      <header className="border-b border-ims-border bg-ims-bg-panel px-4 py-2">
        <div className="flex items-center justify-between">
          {/* Logo */}
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded bg-ims-teal flex items-center justify-center">
              <span className="text-ims-bg font-bold text-sm">IMS</span>
            </div>
            <div>
              <span className="font-semibold text-sm text-ims-text-primary tracking-wide">
                Indian Market Sentinel
              </span>
            </div>
          </div>

          {/* Live Ticker Strip */}
          <div className="hidden lg:flex items-center gap-4">
            {market.map((m) => (
              <div key={m.label} className="flex items-center gap-2 text-xs font-mono">
                <span className="text-ims-text-secondary">{m.label}</span>
                <span className="text-ims-text-primary font-semibold">
                  {m.value.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
                </span>
                <span className={m.change >= 0 ? "text-ims-bullish" : "text-ims-bearish"}>
                  {m.change >= 0 ? "+" : ""}{m.change.toFixed(2)} ({m.changePct.toFixed(2)}%)
                </span>
              </div>
            ))}
          </div>

          {/* Regime Badge */}
          <RegimeBadge
            regime={(regime?.regime as string) || "neutral_watchful"}
            confidence={regime?.confidence as number}
            size="md"
          />
        </div>
      </header>

      {/* ============ NAV ============ */}
      <nav className="border-b border-ims-border bg-ims-bg-panel px-4 py-1.5 flex gap-4 text-xs font-medium">
        <Link href="/" className="text-ims-teal">Dashboard</Link>
        <Link href="/regime" className="text-ims-text-secondary hover:text-ims-text-primary">Regime</Link>
        <Link href="/signals" className="text-ims-text-secondary hover:text-ims-text-primary">Signals</Link>
        <Link href="/portfolio" className="text-ims-text-secondary hover:text-ims-text-primary">Portfolio</Link>
        <Link href="/calendar" className="text-ims-text-secondary hover:text-ims-text-primary">Calendar</Link>
      </nav>

      {/* ============ MAIN GRID ============ */}
      <main className="flex-1 grid grid-cols-1 lg:grid-cols-4 gap-2 p-2">
        {/* LEFT: Active Signals (25%) */}
        <div className="terminal-panel p-3 overflow-y-auto" style={{ maxHeight: "calc(100vh - 160px)" }}>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-xs font-semibold text-ims-text-secondary uppercase tracking-wider">
              Active Signals
            </h2>
            <Link href="/signals" className="text-[10px] text-ims-teal hover:underline">
              View All →
            </Link>
          </div>

          <div className="space-y-2">
            {signals.slice(0, 15).map((sig) => (
              <button
                key={sig.signal_id}
                onClick={() => setSelectedSignal(sig)}
                className="w-full text-left terminal-panel p-2.5 hover:border-ims-teal transition-colors animate-slide-in"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono font-bold text-sm text-ims-teal">{sig.ticker}</span>
                  <span className={`text-[10px] font-semibold ${confidenceColor(sig.confidence)}`}>
                    {sig.confidence}
                  </span>
                </div>
                <div className="text-xs text-ims-text-secondary mt-1">{sig.pattern.replace(/_/g, " ")}</div>
                <div className="flex items-center gap-3 mt-1.5 text-[10px] font-mono">
                  {sig.crss != null && (
                    <span>CRSS: <span style={{ color: sig.crss > 0 ? "#00FF88" : "#FF3B5C" }}>
                      {sig.crss > 0 ? "+" : ""}{sig.crss.toFixed(2)}
                    </span></span>
                  )}
                  {sig.ics != null && (
                    <span>ICS: <span style={{ color: sig.ics > 0 ? "#00FF88" : "#FF3B5C" }}>
                      {sig.ics > 0 ? "+" : ""}{sig.ics.toFixed(2)}
                    </span></span>
                  )}
                </div>
                <div className="text-[9px] text-ims-text-secondary mt-1">
                  {new Date(sig.timestamp).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}
                  {sig.regime && ` · ${sig.regime.replace(/_/g, " ")}`}
                </div>
              </button>
            ))}
            {signals.length === 0 && (
              <div className="text-xs text-ims-text-secondary text-center py-8">
                No active signals. System monitoring...
              </div>
            )}
          </div>
        </div>

        {/* CENTRE: Heatmap + FII/DII (50%) */}
        <div className="lg:col-span-2 space-y-2">
          <SectorHeatmap />

          {/* FII/DII Flow Chart */}
          <div className="terminal-panel p-4">
            <h3 className="text-xs font-semibold text-ims-text-secondary mb-3 uppercase tracking-wider">
              FII / DII Flows (Last 10 Days)
            </h3>
            <div className="flex items-end gap-1 h-32">
              {fiiDii.slice(-10).map((day, i) => {
                const maxVal = Math.max(
                  ...fiiDii.slice(-10).map(d => Math.max(Math.abs(d.fii_net_crores), Math.abs(d.dii_net_crores)))
                ) || 1;
                const fiiH = Math.abs(day.fii_net_crores) / maxVal * 100;
                const diiH = Math.abs(day.dii_net_crores) / maxVal * 100;

                return (
                  <div key={i} className="flex-1 flex flex-col items-center gap-0.5">
                    <div className="flex gap-0.5 items-end h-24">
                      <div
                        className="w-2 rounded-t"
                        style={{
                          height: `${fiiH}%`,
                          backgroundColor: day.fii_net_crores >= 0 ? "#00D4FF" : "#FF3B5C",
                          opacity: 0.8,
                        }}
                        title={`FII: ₹${day.fii_net_crores.toFixed(0)} Cr`}
                      />
                      <div
                        className="w-2 rounded-t"
                        style={{
                          height: `${diiH}%`,
                          backgroundColor: day.dii_net_crores >= 0 ? "#FFB800" : "#FF3B5C80",
                          opacity: 0.8,
                        }}
                        title={`DII: ₹${day.dii_net_crores.toFixed(0)} Cr`}
                      />
                    </div>
                    <span className="text-[8px] text-ims-text-secondary font-mono">
                      {day.date.slice(5)}
                    </span>
                  </div>
                );
              })}
            </div>
            <div className="flex gap-4 mt-2 text-[10px]">
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded bg-ims-teal" /> FII</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded bg-ims-warning" /> DII</span>
            </div>
          </div>
        </div>

        {/* RIGHT: Calendar (25%) */}
        <div className="terminal-panel p-3 overflow-y-auto" style={{ maxHeight: "calc(100vh - 160px)" }}>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-xs font-semibold text-ims-text-secondary uppercase tracking-wider">
              Corporate Actions
            </h2>
            <Link href="/calendar" className="text-[10px] text-ims-teal hover:underline">
              Full Calendar →
            </Link>
          </div>

          <div className="space-y-2">
            {calendar.slice(0, 12).map((action) => {
              const isHighSeverity = ["RESULT", "BUYBACK"].includes(action.action_type);
              const daysUntil = Math.max(0, Math.ceil(
                (new Date(action.event_date).getTime() - Date.now()) / 86400000
              ));

              return (
                <div
                  key={action.id}
                  className={`terminal-panel p-2.5 ${isHighSeverity ? "border-l-2 border-l-ims-warning" : ""}`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                      <span>{actionTypeIcon(action.action_type)}</span>
                      <span className="font-mono font-bold text-sm text-ims-text-primary">
                        {action.ticker}
                      </span>
                    </div>
                    <span className={`text-[10px] font-mono ${daysUntil <= 1 ? "text-ims-warning font-bold" : "text-ims-text-secondary"}`}>
                      {daysUntil === 0 ? "TODAY" : daysUntil === 1 ? "TOMORROW" : `${daysUntil}d`}
                    </span>
                  </div>
                  <div className="text-xs text-ims-text-secondary mt-1">
                    {action.action_type} · {action.event_date}
                  </div>
                  {action.momentum_label && (
                    <span className={`text-[10px] font-mono mt-1 inline-block px-1.5 rounded ${
                      action.momentum_label.includes("BUY") ? "text-ims-bullish bg-ims-bullish/10" :
                      action.momentum_label.includes("SELL") ? "text-ims-bearish bg-ims-bearish/10" :
                      "text-ims-text-secondary bg-ims-bg-card"
                    }`}>
                      {action.momentum_label}
                    </span>
                  )}
                </div>
              );
            })}
            {calendar.length === 0 && (
              <div className="text-xs text-ims-text-secondary text-center py-8">
                No upcoming events
              </div>
            )}
          </div>
        </div>
      </main>

      {/* ============ BOTTOM STRIP: Macro Indicators ============ */}
      <footer className="border-t border-ims-border bg-ims-bg-panel px-4 py-2">
        <div className="flex items-center justify-between text-[10px] font-mono text-ims-text-secondary flex-wrap gap-x-4">
          {regime && (
            <>
              <span>CPI YoY: <span className="text-ims-text-primary">{(regime.cpi_yoy as number)?.toFixed(1) || "—"}%</span></span>
              <span>Repo: <span className="text-ims-text-primary">{(regime.repo_rate as number)?.toFixed(2) || "—"}%</span></span>
              <span>10Y G-Sec: <span className="text-ims-text-primary">{(regime.gsec_10y as number)?.toFixed(2) || "—"}%</span></span>
              <span>2Y G-Sec: <span className="text-ims-text-primary">{(regime.gsec_2y as number)?.toFixed(2) || "—"}%</span></span>
              <span>Yield Slope: <span className="text-ims-text-primary">{(regime.yield_curve_slope as number)?.toFixed(2) || "—"}</span></span>
              <span>USD/INR: <span className="text-ims-text-primary">{(regime.usd_inr as number)?.toFixed(2) || "—"}</span></span>
              <span>VIX: <span className="text-ims-text-primary">{(regime.nifty_vix as number)?.toFixed(1) || "—"}</span></span>
            </>
          )}
        </div>
      </footer>

      {/* ============ SIGNAL DETAIL MODAL ============ */}
      {selectedSignal && (
        <div
          className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4"
          onClick={() => setSelectedSignal(null)}
        >
          <div
            className="terminal-panel p-6 max-w-lg w-full max-h-[80vh] overflow-y-auto"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <div>
                <span className="font-mono text-xl font-bold text-ims-teal">
                  {selectedSignal.ticker}
                </span>
                <span className="text-sm text-ims-text-secondary ml-2">
                  {selectedSignal.sector}
                </span>
              </div>
              <button
                onClick={() => setSelectedSignal(null)}
                className="text-ims-text-secondary hover:text-ims-text-primary text-lg"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3">
              <div className="flex gap-2 flex-wrap">
                <span className="px-2 py-0.5 rounded text-xs font-mono bg-ims-bg-card border border-ims-border">
                  {selectedSignal.pattern.replace(/_/g, " ")}
                </span>
                <span className={`px-2 py-0.5 rounded text-xs font-semibold ${confidenceColor(selectedSignal.confidence)}`}>
                  {selectedSignal.confidence}
                </span>
                {selectedSignal.regime && (
                  <RegimeBadge regime={selectedSignal.regime} size="sm" />
                )}
              </div>

              <div className="grid grid-cols-3 gap-3 text-center">
                <div className="terminal-panel p-2">
                  <div className="text-[10px] text-ims-text-secondary">CRSS</div>
                  <div className="font-mono font-bold" style={{ color: (selectedSignal.crss || 0) > 0 ? "#00FF88" : "#FF3B5C" }}>
                    {selectedSignal.crss?.toFixed(2) || "—"}
                  </div>
                </div>
                <div className="terminal-panel p-2">
                  <div className="text-[10px] text-ims-text-secondary">ICS</div>
                  <div className="font-mono font-bold" style={{ color: (selectedSignal.ics || 0) > 0 ? "#00FF88" : "#FF3B5C" }}>
                    {selectedSignal.ics?.toFixed(2) || "—"}
                  </div>
                </div>
                <div className="terminal-panel p-2">
                  <div className="text-[10px] text-ims-text-secondary">Signal Type</div>
                  <div className="font-mono text-xs text-ims-warning">
                    {selectedSignal.signal_type.replace(/_/g, " ")}
                  </div>
                </div>
              </div>

              <div>
                <h4 className="text-xs text-ims-text-secondary uppercase mb-2">Supporting Evidence</h4>
                <div className="space-y-1.5">
                  {selectedSignal.supporting_evidence.map((ev, i) => (
                    <div key={i} className="text-xs text-ims-text-primary flex gap-2">
                      <span className="text-ims-teal shrink-0">▸</span>
                      <span>{ev}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="text-[10px] text-ims-text-secondary mt-3">
                Signal fired: {new Date(selectedSignal.timestamp).toLocaleString("en-IN")}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
