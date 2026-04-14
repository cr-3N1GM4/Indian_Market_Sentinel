"use client";

import { useState } from "react";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Holding { ticker: string; quantity: number; avg_cost: number; }

const riskColor = (level: string) => {
  if (level === "HIGH") return "bg-ims-bearish/20 text-ims-bearish border-ims-bearish";
  if (level === "MEDIUM") return "bg-ims-warning/20 text-ims-warning border-ims-warning";
  return "bg-ims-bullish/20 text-ims-bullish border-ims-bullish";
};

export default function PortfolioPage() {
  const [holdings, setHoldings] = useState<Holding[]>([
    { ticker: "SUNPHARMA", quantity: 100, avg_cost: 1050 },
    { ticker: "ONGC", quantity: 500, avg_cost: 220 },
    { ticker: "PAGEIND", quantity: 25, avg_cost: 42000 },
  ]);
  const [analysis, setAnalysis] = useState<Record<string, Record<string, unknown>> | null>(null);
  const [stress, setStress] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [newTicker, setNewTicker] = useState("");
  const [newQty, setNewQty] = useState("");
  const [newCost, setNewCost] = useState("");

  const runAnalysis = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/v1/portfolio/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: "operator-001", holdings }),
      });
      const json = await res.json();
      setAnalysis(json.data?.holdings_analysis || {});
    } catch (err) { console.error(err); }
    setLoading(false);
  };

  const runStress = async () => {
    try {
      const res = await fetch(`${API}/api/v1/portfolio/stress-test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: "operator-001", holdings }),
      });
      const json = await res.json();
      setStress(json.data);
    } catch (err) { console.error(err); }
  };

  const addHolding = () => {
    if (newTicker && newQty && newCost) {
      setHoldings([...holdings, { ticker: newTicker.toUpperCase(), quantity: parseInt(newQty), avg_cost: parseFloat(newCost) }]);
      setNewTicker(""); setNewQty(""); setNewCost("");
    }
  };

  return (
    <div className="min-h-screen bg-ims-bg">
      <nav className="border-b border-ims-border bg-ims-bg-panel px-4 py-2 flex items-center gap-4 text-xs">
        <Link href="/" className="text-ims-text-secondary hover:text-ims-teal">← Dashboard</Link>
        <span className="text-ims-teal font-semibold">Portfolio Vulnerability</span>
      </nav>

      <div className="p-4 max-w-7xl mx-auto space-y-4">
        {/* Holdings Input */}
        <div className="terminal-panel p-4">
          <h3 className="text-sm font-semibold text-ims-text-secondary mb-3 uppercase tracking-wider">Portfolio Holdings</h3>
          <div className="space-y-2">
            {holdings.map((h, i) => (
              <div key={i} className="flex items-center gap-3 text-xs font-mono">
                <span className="text-ims-teal font-bold w-24">{h.ticker}</span>
                <span className="text-ims-text-secondary">Qty: {h.quantity}</span>
                <span className="text-ims-text-secondary">Avg: ₹{h.avg_cost.toLocaleString()}</span>
                <button onClick={() => setHoldings(holdings.filter((_, j) => j !== i))}
                  className="text-ims-bearish text-[10px] hover:underline">Remove</button>
              </div>
            ))}
          </div>
          <div className="flex gap-2 mt-3">
            <input placeholder="Ticker" value={newTicker} onChange={e => setNewTicker(e.target.value)}
              className="bg-ims-bg-card border border-ims-border rounded px-2 py-1 text-xs w-24 text-ims-text-primary" />
            <input placeholder="Qty" type="number" value={newQty} onChange={e => setNewQty(e.target.value)}
              className="bg-ims-bg-card border border-ims-border rounded px-2 py-1 text-xs w-20 text-ims-text-primary" />
            <input placeholder="Avg Cost" type="number" value={newCost} onChange={e => setNewCost(e.target.value)}
              className="bg-ims-bg-card border border-ims-border rounded px-2 py-1 text-xs w-28 text-ims-text-primary" />
            <button onClick={addHolding}
              className="bg-ims-teal/20 text-ims-teal px-3 py-1 rounded text-xs font-semibold hover:bg-ims-teal/30">Add</button>
          </div>
          <div className="flex gap-3 mt-4">
            <button onClick={runAnalysis} disabled={loading}
              className="bg-ims-teal text-ims-bg px-4 py-2 rounded text-xs font-bold hover:bg-ims-teal/90 disabled:opacity-50">
              {loading ? "Analysing..." : "Analyse Vulnerability"}
            </button>
            <button onClick={runStress}
              className="bg-ims-warning/20 text-ims-warning px-4 py-2 rounded text-xs font-bold border border-ims-warning/30 hover:bg-ims-warning/30">
              Run Stress Scenarios
            </button>
          </div>
        </div>

        {/* Vulnerability Heatmap Table */}
        {analysis && (
          <div className="terminal-panel p-4 overflow-x-auto">
            <h3 className="text-sm font-semibold text-ims-text-secondary mb-3 uppercase tracking-wider">Vulnerability Heatmap</h3>
            <table className="w-full text-xs font-mono">
              <thead>
                <tr className="text-ims-text-secondary border-b border-ims-border">
                  <th className="text-left py-2 px-2">Ticker</th>
                  <th className="text-center py-2 px-2">Macro</th>
                  <th className="text-center py-2 px-2">Supply Chain</th>
                  <th className="text-center py-2 px-2">FII Flight</th>
                  <th className="text-center py-2 px-2">Earnings</th>
                  <th className="text-center py-2 px-2">Technical</th>
                  <th className="text-center py-2 px-2">Overall</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(analysis).map(([ticker, vuln]) => (
                  <tr key={ticker} className="border-b border-ims-border/30 hover:bg-ims-bg-card">
                    <td className="py-2 px-2 font-bold text-ims-teal">{ticker}</td>
                    {["macro_sensitivity", "supply_chain_risk", "fii_flight_risk", "earnings_risk", "technical_risk"].map(dim => {
                      const val = dim === "macro_sensitivity"
                        ? (vuln[dim] as Record<string, unknown>)?.label as string
                        : dim === "earnings_risk"
                        ? (vuln[dim] as Record<string, unknown>)?.label as string
                        : vuln[dim] as string;
                      return (
                        <td key={dim} className="py-2 px-2 text-center">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-semibold border ${riskColor(val || "LOW")}`}>
                            {val || "LOW"}
                          </span>
                        </td>
                      );
                    })}
                    <td className="py-2 px-2 text-center">
                      <span className={`font-bold text-base ${
                        (vuln.overall_vulnerability_score as number) >= 7 ? "text-ims-bearish" :
                        (vuln.overall_vulnerability_score as number) >= 4 ? "text-ims-warning" : "text-ims-bullish"
                      }`}>
                        {(vuln.overall_vulnerability_score as number)?.toFixed(1)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Stress Test Results */}
        {stress && (
          <div className="terminal-panel p-4">
            <h3 className="text-sm font-semibold text-ims-text-secondary mb-3 uppercase tracking-wider">Stress Test Results</h3>
            <div className="text-xs text-ims-text-secondary mb-3">
              Portfolio Value: ₹{((stress as Record<string, unknown>).total_portfolio_value as number)?.toLocaleString("en-IN")}
            </div>
            <div className="space-y-2">
              {((stress as Record<string, unknown>).scenarios as Record<string, unknown>[])?.map((s, i) => (
                <div key={i} className="terminal-panel p-3 flex items-center justify-between">
                  <div>
                    <div className="text-xs font-semibold text-ims-text-primary">{s.scenario_name as string}</div>
                    <div className="text-[10px] text-ims-text-secondary">{s.description as string}</div>
                  </div>
                  <div className="text-right">
                    <div className={`font-mono font-bold ${(s.portfolio_pnl_inr as number) < 0 ? "text-ims-bearish" : "text-ims-bullish"}`}>
                      ₹{(s.portfolio_pnl_inr as number)?.toLocaleString("en-IN")} ({(s.portfolio_pnl_pct as number)?.toFixed(1)}%)
                    </div>
                    <div className="text-[10px] text-ims-text-secondary">
                      Most affected: {s.most_affected_ticker as string} ({(s.most_affected_pnl_pct as number)?.toFixed(1)}%)
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
