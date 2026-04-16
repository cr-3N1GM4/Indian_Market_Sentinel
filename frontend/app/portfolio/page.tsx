"use client";

import { useState, useEffect } from "react";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Holding {
  ticker: string;
  quantity: number;
  avg_cost: number;
  current_price?: number;
  change?: number;
  pChange?: number;
}

interface OptimizationResult {
  portfolio_health: string;
  health_score: number;
  sector_analysis: string;
  key_risks: string[];
  stocks_to_add: { ticker: string; reason: string; suggested_weight_pct: number }[];
  stocks_to_reduce: { ticker: string; reason: string }[];
  rebalancing_notes: string;
  summary: string;
}

interface RiskResult {
  overall_risk_level: string;
  overall_risk_score: number;
  holdings_risk: {
    ticker: string;
    risk_level: string;
    risk_score: number;
    risk_factors: string[];
    mitigation: string;
  }[];
  portfolio_risks: string[];
  recommendation: string;
}

export default function PortfolioPage() {
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [optimization, setOptimization] = useState<OptimizationResult | null>(null);
  const [riskAnalysis, setRiskAnalysis] = useState<RiskResult | null>(null);
  const [loading, setLoading] = useState("");
  const [newTicker, setNewTicker] = useState("");
  const [newQty, setNewQty] = useState("");
  const [newCost, setNewCost] = useState("");
  const [totalValue, setTotalValue] = useState(0);
  const [totalPnL, setTotalPnL] = useState(0);

  // Fetch current prices for all holdings
  const fetchPrices = async (currentHoldings: Holding[]) => {
    if (currentHoldings.length === 0) return;
    try {
      const tickers = currentHoldings.map(h => h.ticker);
      const res = await fetch(`${API}/api/v1/portfolio/current-prices`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(tickers),
      });
      const json = await res.json();
      const prices = json.data || {};

      const updated = currentHoldings.map(h => {
        const p = prices[h.ticker];
        if (p) {
          return { ...h, current_price: p.lastPrice, change: p.change, pChange: p.pChange };
        }
        return h;
      });
      setHoldings(updated);

      // Calculate totals
      let tv = 0, tc = 0;
      for (const h of updated) {
        const cp = h.current_price || h.avg_cost;
        tv += cp * h.quantity;
        tc += h.avg_cost * h.quantity;
      }
      setTotalValue(tv);
      setTotalPnL(tv - tc);
    } catch (err) {
      console.error("Price fetch error:", err);
    }
  };

  const addHolding = () => {
    if (newTicker && newQty && newCost) {
      const newH: Holding = {
        ticker: newTicker.toUpperCase().trim(),
        quantity: parseInt(newQty),
        avg_cost: parseFloat(newCost),
      };
      const updated = [...holdings, newH];
      setHoldings(updated);
      setNewTicker(""); setNewQty(""); setNewCost("");
      fetchPrices(updated);
    }
  };

  const removeHolding = (idx: number) => {
    const updated = holdings.filter((_, i) => i !== idx);
    setHoldings(updated);
    if (updated.length > 0) fetchPrices(updated);
    else { setTotalValue(0); setTotalPnL(0); }
  };

  const runOptimization = async () => {
    if (holdings.length === 0) return;
    setLoading("optimize");
    try {
      const res = await fetch(`${API}/api/v1/portfolio/optimize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: "operator-001", holdings }),
      });
      const json = await res.json();
      setOptimization(json.data);
    } catch (err) { console.error(err); }
    setLoading("");
  };

  const runRiskAnalysis = async () => {
    if (holdings.length === 0) return;
    setLoading("risk");
    try {
      const res = await fetch(`${API}/api/v1/portfolio/risk-analysis`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: "operator-001", holdings }),
      });
      const json = await res.json();
      setRiskAnalysis(json.data);
    } catch (err) { console.error(err); }
    setLoading("");
  };

  const riskColor = (level: string) => {
    if (level === "HIGH" || level === "NEEDS_ATTENTION") return "text-ims-bearish";
    if (level === "MEDIUM" || level === "MODERATE") return "text-ims-warning";
    return "text-ims-bullish";
  };

  const riskBg = (level: string) => {
    if (level === "HIGH" || level === "NEEDS_ATTENTION") return "bg-ims-bearish/10 border-ims-bearish/30";
    if (level === "MEDIUM" || level === "MODERATE") return "bg-ims-warning/10 border-ims-warning/30";
    return "bg-ims-bullish/10 border-ims-bullish/30";
  };

  return (
    <div className="min-h-screen bg-ims-bg">
      <nav className="border-b border-ims-border bg-ims-bg-panel px-4 py-2 flex items-center gap-4 text-xs">
        <Link href="/" className="text-ims-text-secondary hover:text-ims-teal">← Dashboard</Link>
        <span className="text-ims-teal font-semibold">Portfolio Manager</span>
      </nav>

      <div className="p-4 max-w-7xl mx-auto space-y-4">
        {/* Add Holdings */}
        <div className="terminal-panel p-4">
          <h3 className="text-sm font-semibold text-ims-text-secondary mb-3 uppercase tracking-wider">
            Your Portfolio
          </h3>

          {/* Input Row */}
          <div className="flex gap-2 mb-4 flex-wrap">
            <input
              placeholder="Ticker (e.g. RELIANCE)"
              value={newTicker}
              onChange={e => setNewTicker(e.target.value)}
              onKeyDown={e => e.key === "Enter" && addHolding()}
              className="bg-ims-bg-card border border-ims-border rounded px-3 py-2 text-sm w-40 text-ims-text-primary focus:border-ims-teal outline-none"
            />
            <input
              placeholder="Quantity"
              type="number"
              value={newQty}
              onChange={e => setNewQty(e.target.value)}
              className="bg-ims-bg-card border border-ims-border rounded px-3 py-2 text-sm w-28 text-ims-text-primary focus:border-ims-teal outline-none"
            />
            <input
              placeholder="Buy Price"
              type="number"
              value={newCost}
              onChange={e => setNewCost(e.target.value)}
              onKeyDown={e => e.key === "Enter" && addHolding()}
              className="bg-ims-bg-card border border-ims-border rounded px-3 py-2 text-sm w-32 text-ims-text-primary focus:border-ims-teal outline-none"
            />
            <button
              onClick={addHolding}
              className="bg-ims-teal text-ims-bg px-4 py-2 rounded text-sm font-bold hover:bg-ims-teal/90 transition-colors"
            >
              + Add Stock
            </button>
            {holdings.length > 0 && (
              <button
                onClick={() => fetchPrices(holdings)}
                className="bg-ims-bg-card border border-ims-border text-ims-text-primary px-4 py-2 rounded text-sm font-semibold hover:border-ims-teal transition-colors"
              >
                🔄 Refresh Prices
              </button>
            )}
          </div>

          {/* Holdings Table */}
          {holdings.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm font-mono">
                <thead>
                  <tr className="text-ims-text-secondary border-b border-ims-border text-xs">
                    <th className="text-left py-2 px-2">Ticker</th>
                    <th className="text-right py-2 px-2">Qty</th>
                    <th className="text-right py-2 px-2">Buy Price</th>
                    <th className="text-right py-2 px-2">Current Price</th>
                    <th className="text-right py-2 px-2">P&L</th>
                    <th className="text-right py-2 px-2">P&L %</th>
                    <th className="text-right py-2 px-2">Value</th>
                    <th className="text-center py-2 px-2"></th>
                  </tr>
                </thead>
                <tbody>
                  {holdings.map((h, i) => {
                    const cp = h.current_price || h.avg_cost;
                    const pnl = (cp - h.avg_cost) * h.quantity;
                    const pnlPct = ((cp - h.avg_cost) / h.avg_cost) * 100;
                    const value = cp * h.quantity;
                    return (
                      <tr key={i} className="border-b border-ims-border/30 hover:bg-ims-bg-card">
                        <td className="py-2.5 px-2 font-bold text-ims-teal">{h.ticker}</td>
                        <td className="py-2.5 px-2 text-right text-ims-text-primary">{h.quantity}</td>
                        <td className="py-2.5 px-2 text-right text-ims-text-secondary">₹{h.avg_cost.toLocaleString()}</td>
                        <td className="py-2.5 px-2 text-right text-ims-text-primary font-semibold">
                          {h.current_price ? `₹${h.current_price.toLocaleString()}` : "—"}
                        </td>
                        <td className={`py-2.5 px-2 text-right font-semibold ${pnl >= 0 ? "text-ims-bullish" : "text-ims-bearish"}`}>
                          {pnl >= 0 ? "+" : ""}₹{pnl.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
                        </td>
                        <td className={`py-2.5 px-2 text-right font-semibold ${pnlPct >= 0 ? "text-ims-bullish" : "text-ims-bearish"}`}>
                          {pnlPct >= 0 ? "+" : ""}{pnlPct.toFixed(2)}%
                        </td>
                        <td className="py-2.5 px-2 text-right text-ims-text-primary">
                          ₹{value.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
                        </td>
                        <td className="py-2.5 px-2 text-center">
                          <button onClick={() => removeHolding(i)} className="text-ims-bearish text-[10px] hover:underline">✕</button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
                <tfoot>
                  <tr className="border-t-2 border-ims-border font-bold">
                    <td className="py-2.5 px-2 text-ims-text-primary" colSpan={6}>Total Portfolio</td>
                    <td className="py-2.5 px-2 text-right text-ims-text-primary">₹{totalValue.toLocaleString("en-IN", { maximumFractionDigits: 0 })}</td>
                    <td></td>
                  </tr>
                  <tr>
                    <td className="py-1 px-2 text-ims-text-secondary text-xs" colSpan={6}>Total P&L</td>
                    <td className={`py-1 px-2 text-right font-bold ${totalPnL >= 0 ? "text-ims-bullish" : "text-ims-bearish"}`}>
                      {totalPnL >= 0 ? "+" : ""}₹{totalPnL.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
                    </td>
                    <td></td>
                  </tr>
                </tfoot>
              </table>
            </div>
          ) : (
            <div className="text-center text-ims-text-secondary py-8 text-sm">
              Add stocks to your portfolio to get started. Enter the ticker symbol, quantity, and your buy price.
            </div>
          )}

          {/* Action Buttons */}
          {holdings.length > 0 && (
            <div className="flex gap-3 mt-4 flex-wrap">
              <button
                onClick={runOptimization}
                disabled={loading === "optimize"}
                className="bg-ims-teal text-ims-bg px-4 py-2 rounded text-xs font-bold hover:bg-ims-teal/90 disabled:opacity-50 transition-colors"
              >
                {loading === "optimize" ? "⏳ Analyzing..." : "🤖 AI Portfolio Optimization"}
              </button>
              <button
                onClick={runRiskAnalysis}
                disabled={loading === "risk"}
                className="bg-ims-warning/20 text-ims-warning px-4 py-2 rounded text-xs font-bold border border-ims-warning/30 hover:bg-ims-warning/30 disabled:opacity-50 transition-colors"
              >
                {loading === "risk" ? "⏳ Analyzing..." : "⚠️ Risk Analysis"}
              </button>
            </div>
          )}
        </div>

        {/* Optimization Results */}
        {optimization && (
          <div className="terminal-panel p-4">
            <h3 className="text-sm font-semibold text-ims-text-secondary mb-3 uppercase tracking-wider flex items-center gap-2">
              🤖 AI Portfolio Optimization
              <span className={`text-xs px-2 py-0.5 rounded border ${riskBg(optimization.portfolio_health)} ${riskColor(optimization.portfolio_health)}`}>
                {optimization.portfolio_health} ({optimization.health_score}/10)
              </span>
            </h3>

            <div className="text-sm text-ims-text-primary mb-4">{optimization.summary}</div>

            {optimization.key_risks.length > 0 && (
              <div className="mb-4">
                <h4 className="text-xs text-ims-warning uppercase font-semibold mb-2">⚠️ Key Risks</h4>
                <div className="space-y-1">
                  {optimization.key_risks.map((risk, i) => (
                    <div key={i} className="text-xs text-ims-text-secondary flex gap-2">
                      <span className="text-ims-warning shrink-0">▸</span>
                      <span>{risk}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {optimization.stocks_to_add.length > 0 && (
              <div className="mb-4">
                <h4 className="text-xs text-ims-bullish uppercase font-semibold mb-2">✅ Stocks to Add</h4>
                <div className="space-y-2">
                  {optimization.stocks_to_add.map((s, i) => (
                    <div key={i} className="terminal-panel p-3 border-l-2 border-l-ims-bullish">
                      <div className="flex items-center justify-between">
                        <span className="font-mono font-bold text-ims-teal">{s.ticker}</span>
                        <span className="text-[10px] text-ims-text-secondary">Suggested: {s.suggested_weight_pct}%</span>
                      </div>
                      <div className="text-xs text-ims-text-secondary mt-1">{s.reason}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {optimization.stocks_to_reduce.length > 0 && (
              <div className="mb-4">
                <h4 className="text-xs text-ims-bearish uppercase font-semibold mb-2">🔴 Stocks to Reduce</h4>
                <div className="space-y-2">
                  {optimization.stocks_to_reduce.map((s, i) => (
                    <div key={i} className="terminal-panel p-3 border-l-2 border-l-ims-bearish">
                      <span className="font-mono font-bold text-ims-teal">{s.ticker}</span>
                      <div className="text-xs text-ims-text-secondary mt-1">{s.reason}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="text-xs text-ims-text-secondary italic">{optimization.rebalancing_notes}</div>
          </div>
        )}

        {/* Risk Analysis Results */}
        {riskAnalysis && (
          <div className="terminal-panel p-4">
            <h3 className="text-sm font-semibold text-ims-text-secondary mb-3 uppercase tracking-wider flex items-center gap-2">
              ⚠️ Risk Analysis
              <span className={`text-xs px-2 py-0.5 rounded border ${riskBg(riskAnalysis.overall_risk_level)} ${riskColor(riskAnalysis.overall_risk_level)}`}>
                {riskAnalysis.overall_risk_level} ({riskAnalysis.overall_risk_score}/10)
              </span>
            </h3>

            <div className="text-sm text-ims-text-primary mb-4">{riskAnalysis.recommendation}</div>

            <div className="space-y-2 mb-4">
              {riskAnalysis.holdings_risk.map((hr, i) => (
                <div key={i} className="terminal-panel p-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-mono font-bold text-ims-teal">{hr.ticker}</span>
                    <span className={`text-xs font-semibold px-2 py-0.5 rounded border ${riskBg(hr.risk_level)} ${riskColor(hr.risk_level)}`}>
                      {hr.risk_level} ({hr.risk_score}/10)
                    </span>
                  </div>
                  <div className="text-xs text-ims-text-secondary space-y-0.5">
                    {hr.risk_factors.map((f, j) => (
                      <div key={j} className="flex gap-1">
                        <span className="text-ims-warning shrink-0">▸</span>
                        <span>{f}</span>
                      </div>
                    ))}
                  </div>
                  <div className="text-[10px] text-ims-teal mt-1">💡 {hr.mitigation}</div>
                </div>
              ))}
            </div>

            {riskAnalysis.portfolio_risks.length > 0 && (
              <div>
                <h4 className="text-xs text-ims-text-secondary uppercase font-semibold mb-2">Systemic Risks</h4>
                {riskAnalysis.portfolio_risks.map((r, i) => (
                  <div key={i} className="text-xs text-ims-text-secondary mb-1 flex gap-1">
                    <span className="text-ims-bearish shrink-0">▸</span>
                    <span>{r}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
