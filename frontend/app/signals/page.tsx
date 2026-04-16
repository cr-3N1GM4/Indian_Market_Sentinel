"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface StockMover {
  symbol: string;
  lastPrice: number;
  change: number;
  pChange: number;
  tradedQuantity: number;
  openPrice: number;
  highPrice: number;
  lowPrice: number;
  previousClose: number;
}

export default function SignalsPage() {
  const [gainers, setGainers] = useState<StockMover[]>([]);
  const [losers, setLosers] = useState<StockMover[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<StockMover | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`${API}/api/v1/signals/market-movers`);
        const json = await res.json();
        setGainers(json.data?.gainers || []);
        setLosers(json.data?.losers || []);
      } catch (err) {
        console.error("Signals load error:", err);
      }
      setLoading(false);
    }
    load();
    const interval = setInterval(load, 60000);
    return () => clearInterval(interval);
  }, []);

  const formatVolume = (v: number) => {
    if (v >= 10000000) return `${(v / 10000000).toFixed(1)} Cr`;
    if (v >= 100000) return `${(v / 100000).toFixed(1)} L`;
    if (v >= 1000) return `${(v / 1000).toFixed(1)} K`;
    return v.toString();
  };

  return (
    <div className="min-h-screen bg-ims-bg">
      <nav className="border-b border-ims-border bg-ims-bg-panel px-4 py-2 flex items-center gap-4 text-xs">
        <Link href="/" className="text-ims-text-secondary hover:text-ims-teal">← Dashboard</Link>
        <span className="text-ims-teal font-semibold">Market Signals — Top Gainers & Losers</span>
      </nav>

      <div className="p-4 max-w-7xl mx-auto">
        {loading ? (
          <div className="text-center text-ims-text-secondary py-20 animate-pulse">Loading market movers...</div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* BULLISH — TOP GAINERS */}
            <div className="terminal-panel p-4">
              <h2 className="text-sm font-bold uppercase tracking-wider mb-4 flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-ims-bullish animate-pulse" />
                <span className="text-ims-bullish">Bullish — Top Gainers</span>
                <span className="text-ims-text-secondary text-[10px] ml-auto">{gainers.length} stocks</span>
              </h2>
              <div className="space-y-1">
                {gainers.map((stock, i) => (
                  <button
                    key={stock.symbol}
                    onClick={() => setSelected(stock)}
                    className="w-full text-left terminal-panel p-3 hover:border-ims-bullish/50 transition-all duration-200"
                    style={{ animationDelay: `${i * 50}ms` }}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span className="text-ims-text-secondary text-[10px] font-mono w-5">#{i + 1}</span>
                        <span className="font-mono font-bold text-ims-teal text-sm">{stock.symbol}</span>
                      </div>
                      <div className="text-right">
                        <div className="font-mono font-semibold text-sm text-ims-text-primary">
                          ₹{stock.lastPrice?.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center justify-between mt-1">
                      <span className="text-[10px] text-ims-text-secondary font-mono">
                        Vol: {formatVolume(stock.tradedQuantity || 0)}
                      </span>
                      <div className="flex items-center gap-2">
                        <span className="text-ims-bullish font-mono font-bold text-sm">
                          +{stock.change?.toFixed(2)}
                        </span>
                        <span className="bg-ims-bullish/15 text-ims-bullish font-mono text-xs font-bold px-2 py-0.5 rounded">
                          +{stock.pChange?.toFixed(2)}%
                        </span>
                      </div>
                    </div>
                  </button>
                ))}
                {gainers.length === 0 && (
                  <div className="text-center text-ims-text-secondary text-xs py-8">No gainers data available</div>
                )}
              </div>
            </div>

            {/* BEARISH — TOP LOSERS */}
            <div className="terminal-panel p-4">
              <h2 className="text-sm font-bold uppercase tracking-wider mb-4 flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-ims-bearish animate-pulse" />
                <span className="text-ims-bearish">Bearish — Top Losers</span>
                <span className="text-ims-text-secondary text-[10px] ml-auto">{losers.length} stocks</span>
              </h2>
              <div className="space-y-1">
                {losers.map((stock, i) => (
                  <button
                    key={stock.symbol}
                    onClick={() => setSelected(stock)}
                    className="w-full text-left terminal-panel p-3 hover:border-ims-bearish/50 transition-all duration-200"
                    style={{ animationDelay: `${i * 50}ms` }}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span className="text-ims-text-secondary text-[10px] font-mono w-5">#{i + 1}</span>
                        <span className="font-mono font-bold text-ims-teal text-sm">{stock.symbol}</span>
                      </div>
                      <div className="text-right">
                        <div className="font-mono font-semibold text-sm text-ims-text-primary">
                          ₹{stock.lastPrice?.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center justify-between mt-1">
                      <span className="text-[10px] text-ims-text-secondary font-mono">
                        Vol: {formatVolume(stock.tradedQuantity || 0)}
                      </span>
                      <div className="flex items-center gap-2">
                        <span className="text-ims-bearish font-mono font-bold text-sm">
                          {stock.change?.toFixed(2)}
                        </span>
                        <span className="bg-ims-bearish/15 text-ims-bearish font-mono text-xs font-bold px-2 py-0.5 rounded">
                          {stock.pChange?.toFixed(2)}%
                        </span>
                      </div>
                    </div>
                  </button>
                ))}
                {losers.length === 0 && (
                  <div className="text-center text-ims-text-secondary text-xs py-8">No losers data available</div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Stock Detail Modal */}
      {selected && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4" onClick={() => setSelected(null)}>
          <div className="terminal-panel p-6 max-w-md w-full" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <div className="font-mono text-xl font-bold text-ims-teal">{selected.symbol}</div>
              <button onClick={() => setSelected(null)} className="text-ims-text-secondary hover:text-ims-text-primary text-lg">✕</button>
            </div>

            <div className="text-2xl font-bold font-mono text-ims-text-primary mb-1">
              ₹{selected.lastPrice?.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
            </div>
            <div className={`text-lg font-mono font-bold mb-4 ${(selected.change || 0) >= 0 ? "text-ims-bullish" : "text-ims-bearish"}`}>
              {(selected.change || 0) >= 0 ? "+" : ""}{selected.change?.toFixed(2)} ({selected.pChange?.toFixed(2)}%)
            </div>

            <div className="grid grid-cols-2 gap-3 text-xs">
              {[
                { label: "Open", value: `₹${selected.openPrice?.toLocaleString()}` },
                { label: "Prev Close", value: `₹${selected.previousClose?.toLocaleString()}` },
                { label: "Day High", value: `₹${selected.highPrice?.toLocaleString()}` },
                { label: "Day Low", value: `₹${selected.lowPrice?.toLocaleString()}` },
                { label: "Volume", value: formatVolume(selected.tradedQuantity || 0) },
              ].map((item) => (
                <div key={item.label} className="terminal-panel p-2">
                  <div className="text-ims-text-secondary text-[10px]">{item.label}</div>
                  <div className="font-mono font-bold text-ims-text-primary">{item.value}</div>
                </div>
              ))}
            </div>

            <Link
              href={`/analyze?ticker=${selected.symbol}`}
              className="mt-4 block text-center bg-ims-teal/20 text-ims-teal px-4 py-2 rounded text-xs font-bold hover:bg-ims-teal/30"
            >
              Deep Analyze {selected.symbol} →
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
