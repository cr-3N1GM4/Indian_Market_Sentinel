"use client";

import { useEffect, useState } from "react";

interface HeatmapData {
  sectors: Record<
    string,
    {
      tickers: Record<
        string,
        { crss: number; ics: number; crss_trend: string; data_points: number }
      >;
    }
  >;
}

function scoreToColor(score: number): string {
  if (score > 0.5) return "#00FF88";
  if (score > 0.2) return "#00FF8880";
  if (score > -0.2) return "#64748B";
  if (score > -0.5) return "#FF3B5C80";
  return "#FF3B5C";
}

function trendArrow(trend: string): string {
  if (trend === "RISING") return "↑";
  if (trend === "FALLING") return "↓";
  return "→";
}

export default function SectorHeatmap() {
  const [data, setData] = useState<HeatmapData | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1/sentiment/heatmap`
        );
        const json = await res.json();
        setData(json.data);
      } catch {
        // Mock data
        setData({
          sectors: {
            Energy: {
              tickers: {
                RELIANCE: { crss: 0.35, ics: 0.22, crss_trend: "RISING", data_points: 24 },
                ONGC: { crss: -0.15, ics: 0.45, crss_trend: "STABLE", data_points: 12 },
                NTPC: { crss: 0.52, ics: 0.31, crss_trend: "RISING", data_points: 18 },
                BPCL: { crss: -0.28, ics: -0.12, crss_trend: "FALLING", data_points: 8 },
              },
            },
            Pharma: {
              tickers: {
                SUNPHARMA: { crss: 0.72, ics: 0.15, crss_trend: "RISING", data_points: 32 },
                DRREDDY: { crss: 0.28, ics: 0.55, crss_trend: "STABLE", data_points: 15 },
                CIPLA: { crss: -0.1, ics: 0.62, crss_trend: "RISING", data_points: 20 },
                AUROPHARMA: { crss: -0.45, ics: -0.3, crss_trend: "FALLING", data_points: 6 },
              },
            },
            Textile: {
              tickers: {
                PAGEIND: { crss: 0.18, ics: 0.08, crss_trend: "STABLE", data_points: 5 },
                ARVIND: { crss: -0.32, ics: 0.25, crss_trend: "FALLING", data_points: 9 },
                RAYMOND: { crss: 0.05, ics: -0.15, crss_trend: "STABLE", data_points: 4 },
              },
            },
          },
        });
      }
    }
    load();
    const interval = setInterval(load, 60000);
    return () => clearInterval(interval);
  }, []);

  if (!data) {
    return (
      <div className="terminal-panel p-4 animate-pulse">
        <div className="h-48 bg-ims-bg-card rounded" />
      </div>
    );
  }

  return (
    <div className="terminal-panel p-4">
      <h3 className="text-sm font-semibold text-ims-text-secondary mb-3 uppercase tracking-wider">
        Regime × Sentiment Heatmap
      </h3>

      <div className="space-y-4">
        {Object.entries(data.sectors).map(([sectorName, sector]) => (
          <div key={sectorName}>
            <div className="text-xs text-ims-teal font-semibold mb-2 uppercase">
              {sectorName}
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5">
              {Object.entries(sector.tickers).map(([ticker, vals]) => (
                <div
                  key={ticker}
                  className="heatmap-cell rounded p-2 text-center"
                  style={{ backgroundColor: `${scoreToColor(vals.crss)}20` }}
                  title={`CRSS: ${vals.crss.toFixed(2)} | ICS: ${vals.ics.toFixed(2)} | ${vals.data_points} data points`}
                >
                  <div className="text-xs font-mono font-semibold text-ims-text-primary">
                    {ticker}
                  </div>
                  <div className="flex items-center justify-center gap-1 mt-1">
                    <span
                      className="text-sm font-mono font-bold"
                      style={{ color: scoreToColor(vals.crss) }}
                    >
                      {vals.crss > 0 ? "+" : ""}
                      {vals.crss.toFixed(2)}
                    </span>
                    <span className="text-xs">{trendArrow(vals.crss_trend)}</span>
                  </div>
                  <div className="text-[10px] text-ims-text-secondary mt-0.5 font-mono">
                    ICS: {vals.ics > 0 ? "+" : ""}{vals.ics.toFixed(2)}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
