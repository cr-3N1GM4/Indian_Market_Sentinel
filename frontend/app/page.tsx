"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface MarketTicker {
  label: string;
  value: number;
  change: number;
  changePct: number;
}

interface NewsItem {
  headline: string;
  snippet: string;
  source: string;
  sentiment_score: number;
  sentiment_label: string;
  url: string;
  time: string;
}

interface MarketMood {
  score: number;
  label: string;
  color: string;
  components: {
    advance_decline: number;
    vix: number;
    fii_flow: number;
    news_sentiment: number;
  };
  raw: {
    advances: number;
    declines: number;
    vix: number;
    fii_net_crores: number;
  };
}

interface FIIDIIDay {
  date: string;
  fii_net_crores: number;
  dii_net_crores: number;
  fii_buy?: number;
  fii_sell?: number;
  dii_buy?: number;
  dii_sell?: number;
}

interface CorpAction {
  id: string;
  ticker: string;
  action_type: string;
  event_date: string;
  ex_date?: string;
  details?: Record<string, string>;
  subject?: string;
  momentum_label?: string;
}

export default function Dashboard() {
  const [market, setMarket] = useState<MarketTicker[]>([]);
  const [mood, setMood] = useState<MarketMood | null>(null);
  const [news, setNews] = useState<NewsItem[]>([]);
  const [fiiDii, setFiiDii] = useState<FIIDIIDay[]>([]);
  const [calendar, setCalendar] = useState<CorpAction[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadAll() {
      try {
        const [mktRes, moodRes, newsRes, fiiRes, calRes] = await Promise.allSettled([
          fetch(`${API}/api/v1/market-data`).then((r) => r.json()),
          fetch(`${API}/api/v1/sentiment/market-mood`).then((r) => r.json()),
          fetch(`${API}/api/v1/sentiment/trending-news?limit=15`).then((r) => r.json()),
          fetch(`${API}/api/v1/institutional/fii-dii-flows?days=10`).then((r) => r.json()),
          fetch(`${API}/api/v1/calendar/upcoming?days=7`).then((r) => r.json()),
        ]);

        if (mktRes.status === "fulfilled") {
          const m = mktRes.value.data;
          setMarket([
            { label: "NIFTY 50", value: m.nifty50?.last || 0, change: m.nifty50?.change || 0, changePct: m.nifty50?.pChange || 0 },
            { label: "SENSEX", value: m.sensex?.last || 0, change: m.sensex?.change || 0, changePct: m.sensex?.pChange || 0 },
            { label: "BANK NIFTY", value: m.niftyBank?.last || 0, change: m.niftyBank?.change || 0, changePct: m.niftyBank?.pChange || 0 },
            { label: "INDIA VIX", value: m.indiaVix || 0, change: 0, changePct: 0 },
          ]);
        }
        if (moodRes.status === "fulfilled") setMood(moodRes.value.data);
        if (newsRes.status === "fulfilled") setNews(newsRes.value.data || []);
        if (fiiRes.status === "fulfilled") setFiiDii(fiiRes.value.data || []);
        if (calRes.status === "fulfilled") setCalendar(calRes.value.data || []);
      } catch (err) {
        console.error("Dashboard load error:", err);
      }
      setLoading(false);
    }

    loadAll();
    const interval = setInterval(loadAll, 60000);
    return () => clearInterval(interval);
  }, []);

  const sentimentColor = (score: number) => {
    if (score > 0.1) return "#00FF88";
    if (score < -0.1) return "#FF3B5C";
    return "#94A3B8";
  };

  const sentimentBg = (score: number) => {
    if (score > 0.1) return "rgba(0,255,136,0.08)";
    if (score < -0.1) return "rgba(255,59,92,0.08)";
    return "rgba(148,163,184,0.05)";
  };

  const sentimentLabel = (label: string) => {
    if (label === "POSITIVE" || label === "positive") return "🟢 Bullish";
    if (label === "NEGATIVE" || label === "negative") return "🔴 Bearish";
    return "⚪ Neutral";
  };

  const moodGaugeRotation = mood ? (mood.score / 100) * 180 - 90 : -90;

  return (
    <div className="min-h-screen bg-ims-bg flex flex-col">
      {/* ============ TOP BAR ============ */}
      <header className="border-b border-ims-border bg-ims-bg-panel px-4 py-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded bg-ims-teal flex items-center justify-center">
              <span className="text-ims-bg font-bold text-sm">IMS</span>
            </div>
            <span className="font-semibold text-sm text-ims-text-primary tracking-wide">
              Indian Market Sentinel
            </span>
          </div>

          {/* Live Ticker Strip */}
          <div className="hidden lg:flex items-center gap-4">
            {market.map((m) => (
              <div key={m.label} className="flex items-center gap-2 text-xs font-mono">
                <span className="text-ims-text-secondary">{m.label}</span>
                <span className="text-ims-text-primary font-semibold">
                  {m.value ? m.value.toLocaleString("en-IN", { maximumFractionDigits: 2 }) : "—"}
                </span>
                {m.label !== "INDIA VIX" && (
                  <span className={m.change >= 0 ? "text-ims-bullish" : "text-ims-bearish"}>
                    {m.change >= 0 ? "+" : ""}{m.change.toFixed(2)} ({m.changePct.toFixed(2)}%)
                  </span>
                )}
              </div>
            ))}
          </div>

          {/* Market Mood Badge */}
          {mood && (
            <div className="flex items-center gap-2 px-3 py-1 rounded border border-ims-border">
              <div className="w-2 h-2 rounded-full" style={{ backgroundColor: mood.color }} />
              <span className="text-xs font-semibold" style={{ color: mood.color }}>{mood.label}</span>
              <span className="text-xs text-ims-text-secondary font-mono">{mood.score.toFixed(0)}</span>
            </div>
          )}
        </div>
      </header>

      {/* ============ NAV ============ */}
      <nav className="border-b border-ims-border bg-ims-bg-panel px-4 py-1.5 flex gap-4 text-xs font-medium">
        <Link href="/" className="text-ims-teal">Dashboard</Link>
        <Link href="/regime" className="text-ims-text-secondary hover:text-ims-text-primary">Regime</Link>
        <Link href="/signals" className="text-ims-text-secondary hover:text-ims-text-primary">Signals</Link>
        <Link href="/portfolio" className="text-ims-text-secondary hover:text-ims-text-primary">Portfolio</Link>
        <Link href="/calendar" className="text-ims-text-secondary hover:text-ims-text-primary">Calendar</Link>
        <Link href="/analyze" className="text-ims-text-secondary hover:text-ims-text-primary">Analyze</Link>
      </nav>

      {/* ============ MAIN GRID ============ */}
      <main className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-2 p-2">

        {/* LEFT: Market Mood Gauge + FII/DII (3 cols) */}
        <div className="lg:col-span-3 space-y-2">
          {/* Market Mood Gauge */}
          <div className="terminal-panel p-4">
            <h2 className="text-xs font-semibold text-ims-text-secondary uppercase tracking-wider mb-3">
              Market Mood
            </h2>
            {mood ? (
              <div className="flex flex-col items-center">
                {/* Gauge */}
                <div className="relative w-44 h-24 overflow-hidden mb-2">
                  <div className="absolute inset-0 rounded-t-full"
                    style={{
                      background: "conic-gradient(from 180deg, #FF3B5C 0deg, #FF6B35 36deg, #FFB800 72deg, #88FF00 108deg, #00FF88 144deg, #00FF88 180deg, transparent 180deg)",
                      opacity: 0.3,
                    }}
                  />
                  <div className="absolute bottom-0 left-1/2 w-1 h-20 origin-bottom"
                    style={{
                      transform: `translateX(-50%) rotate(${moodGaugeRotation}deg)`,
                      transition: "transform 1s ease-out",
                    }}
                  >
                    <div className="w-1 h-16 rounded" style={{ backgroundColor: mood.color }} />
                    <div className="w-3 h-3 rounded-full -ml-1 -mt-1" style={{ backgroundColor: mood.color }} />
                  </div>
                </div>
                <div className="text-2xl font-bold font-mono" style={{ color: mood.color }}>{mood.score.toFixed(0)}</div>
                <div className="text-sm font-semibold mt-1" style={{ color: mood.color }}>{mood.label}</div>

                {/* Components */}
                <div className="grid grid-cols-2 gap-2 mt-4 w-full text-[10px]">
                  {[
                    { label: "Adv/Dec", value: mood.components.advance_decline },
                    { label: "VIX", value: mood.components.vix },
                    { label: "FII Flow", value: mood.components.fii_flow },
                    { label: "Sentiment", value: mood.components.news_sentiment },
                  ].map((c) => (
                    <div key={c.label} className="terminal-panel p-2 text-center">
                      <div className="text-ims-text-secondary">{c.label}</div>
                      <div className="font-mono font-bold text-ims-text-primary">{c.value.toFixed(0)}</div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="text-center text-ims-text-secondary text-xs py-8">Loading...</div>
            )}
          </div>

          {/* FII/DII Flows */}
          <div className="terminal-panel p-4">
            <h3 className="text-xs font-semibold text-ims-text-secondary mb-3 uppercase tracking-wider">
              FII / DII Flows (Last 10 Days)
            </h3>
            <div className="flex items-end gap-1 h-32">
              {fiiDii.slice(-10).map((day, i) => {
                const maxVal = Math.max(
                  ...fiiDii.slice(-10).map((d) =>
                    Math.max(Math.abs(d.fii_net_crores || 0), Math.abs(d.dii_net_crores || 0))
                  )
                ) || 1;
                const fiiH = (Math.abs(day.fii_net_crores || 0) / maxVal) * 100;
                const diiH = (Math.abs(day.dii_net_crores || 0) / maxVal) * 100;

                return (
                  <div key={i} className="flex-1 flex flex-col items-center gap-0.5">
                    <div className="flex gap-0.5 items-end h-24">
                      <div
                        className="w-2 rounded-t transition-all duration-500"
                        style={{
                          height: `${Math.max(fiiH, 4)}%`,
                          backgroundColor: (day.fii_net_crores || 0) >= 0 ? "#00D4FF" : "#FF3B5C",
                          opacity: 0.8,
                        }}
                        title={`FII: ₹${(day.fii_net_crores || 0).toFixed(0)} Cr`}
                      />
                      <div
                        className="w-2 rounded-t transition-all duration-500"
                        style={{
                          height: `${Math.max(diiH, 4)}%`,
                          backgroundColor: (day.dii_net_crores || 0) >= 0 ? "#FFB800" : "#FF3B5C80",
                          opacity: 0.8,
                        }}
                        title={`DII: ₹${(day.dii_net_crores || 0).toFixed(0)} Cr`}
                      />
                    </div>
                    <span className="text-[8px] text-ims-text-secondary font-mono">
                      {(day.date || "").slice(-5)}
                    </span>
                  </div>
                );
              })}
            </div>
            <div className="flex gap-4 mt-2 text-[10px]">
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded bg-ims-teal" /> FII</span>
              <span className="flex items-center gap-1"><span className="w-2 h-2 rounded bg-ims-warning" /> DII</span>
            </div>
            {fiiDii.length > 0 && (
              <div className="mt-2 grid grid-cols-2 gap-2 text-[10px] font-mono">
                <div className="terminal-panel p-2 text-center">
                  <div className="text-ims-text-secondary">FII Net Today</div>
                  <div className={`font-bold ${(fiiDii[fiiDii.length - 1]?.fii_net_crores || 0) >= 0 ? "text-ims-bullish" : "text-ims-bearish"}`}>
                    ₹{(fiiDii[fiiDii.length - 1]?.fii_net_crores || 0).toFixed(0)} Cr
                  </div>
                </div>
                <div className="terminal-panel p-2 text-center">
                  <div className="text-ims-text-secondary">DII Net Today</div>
                  <div className={`font-bold ${(fiiDii[fiiDii.length - 1]?.dii_net_crores || 0) >= 0 ? "text-ims-bullish" : "text-ims-bearish"}`}>
                    ₹{(fiiDii[fiiDii.length - 1]?.dii_net_crores || 0).toFixed(0)} Cr
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* CENTRE: Trending News (6 cols) */}
        <div className="lg:col-span-6 space-y-2">
          <div className="terminal-panel p-4 overflow-y-auto" style={{ maxHeight: "calc(100vh - 140px)" }}>
            <h2 className="text-xs font-semibold text-ims-text-secondary uppercase tracking-wider mb-3">
              📰 Trending Market News & Sentiment
            </h2>
            <div className="space-y-2">
              {news.map((item, i) => (
                <a
                  key={i}
                  href={item.url || "#"}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block terminal-panel p-3 hover:border-ims-teal transition-all duration-200"
                  style={{ borderLeft: `3px solid ${sentimentColor(item.sentiment_score)}`, background: sentimentBg(item.sentiment_score) }}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1">
                      <div className="text-sm text-ims-text-primary font-medium leading-snug">
                        {item.headline}
                      </div>
                      {item.snippet && (
                        <div className="text-xs text-ims-text-secondary mt-1 line-clamp-2">{item.snippet}</div>
                      )}
                    </div>
                    <div className="text-right shrink-0 ml-2">
                      <div className="text-[10px] font-semibold px-2 py-0.5 rounded"
                        style={{ color: sentimentColor(item.sentiment_score), backgroundColor: sentimentBg(item.sentiment_score) }}>
                        {sentimentLabel(item.sentiment_label)}
                      </div>
                      <div className="text-[10px] font-mono mt-1" style={{ color: sentimentColor(item.sentiment_score) }}>
                        {item.sentiment_score > 0 ? "+" : ""}{item.sentiment_score.toFixed(2)}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 mt-2 text-[9px] text-ims-text-secondary">
                    <span className="uppercase font-semibold">{item.source}</span>
                    <span>·</span>
                    <span>{new Date(item.time).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })}</span>
                  </div>
                </a>
              ))}
              {news.length === 0 && !loading && (
                <div className="text-center text-ims-text-secondary text-xs py-12">
                  No trending news available. System is fetching data...
                </div>
              )}
              {loading && (
                <div className="text-center text-ims-text-secondary text-xs py-12">
                  <div className="animate-pulse">Loading market news...</div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* RIGHT: Corporate Actions (3 cols) */}
        <div className="lg:col-span-3 terminal-panel p-3 overflow-y-auto" style={{ maxHeight: "calc(100vh - 140px)" }}>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-xs font-semibold text-ims-text-secondary uppercase tracking-wider">
              Corporate Actions This Week
            </h2>
            <Link href="/calendar" className="text-[10px] text-ims-teal hover:underline">
              Full Calendar →
            </Link>
          </div>

          <div className="space-y-2">
            {calendar.slice(0, 15).map((action) => {
              const isHighSeverity = ["RESULT", "BUYBACK"].includes(action.action_type);
              const eventDate = action.event_date || action.ex_date || "";

              return (
                <div
                  key={action.id}
                  className={`terminal-panel p-2.5 ${isHighSeverity ? "border-l-2 border-l-ims-warning" : ""}`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                      <span>{actionTypeIcon(action.action_type)}</span>
                      <span className="font-mono font-bold text-sm text-ims-teal">{action.ticker}</span>
                    </div>
                    <span className="text-[10px] font-mono text-ims-text-secondary">{eventDate.slice(0, 10)}</span>
                  </div>
                  <div className="text-xs text-ims-text-secondary mt-1">
                    {action.details?.subject || action.subject || action.action_type}
                  </div>
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
    </div>
  );
}

function actionTypeIcon(t: string) {
  const icons: Record<string, string> = {
    RESULT: "📊", DIVIDEND: "💰", BUYBACK: "🔄",
    BONUS: "🎁", SPLIT: "✂️", AGM: "🏛️", RIGHTS: "📋", OTHER: "📌",
  };
  return icons[t] || "📌";
}
