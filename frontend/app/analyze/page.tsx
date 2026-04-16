"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Article {
  source: string;
  headline: string;
  snippet: string;
  url: string;
  sentiment_score: number;
  sentiment_label: string;
  published_at: string;
  upvotes?: number;
  comments?: number;
}

interface AnalysisResult {
  ticker: string;
  company_name: string;
  current_price: number | null;
  price_change?: number;
  price_pchange?: number;
  day_high?: number;
  day_low?: number;
  previous_close?: number;
  total_articles: number;
  avg_sentiment: number;
  verdict: string;
  verdict_color: string;
  sentiment_breakdown: {
    positive: number;
    negative: number;
    neutral: number;
  };
  source_counts: {
    moneycontrol: number;
    economic_times: number;
    reddit: number;
  };
  articles: Article[];
  llm_summary?: string;
}

function AnalyzeContent() {
  const searchParams = useSearchParams();
  const [ticker, setTicker] = useState(searchParams.get("ticker") || "");
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const t = searchParams.get("ticker");
    if (t) {
      setTicker(t);
      runAnalysis(t);
    }
  }, [searchParams]);

  const runAnalysis = async (t?: string) => {
    const symbol = (t || ticker).toUpperCase().trim();
    if (!symbol) return;
    setLoading(true);
    setError("");
    setResult(null);

    try {
      const res = await fetch(`${API}/api/v1/analyze/${symbol}`);
      if (!res.ok) throw new Error("Failed to analyze");
      const json = await res.json();
      setResult(json.data);
    } catch (err) {
      setError("Failed to analyze stock. Please try again.");
      console.error(err);
    }
    setLoading(false);
  };

  const sentimentColor = (score: number) => {
    if (score > 0.1) return "#00FF88";
    if (score < -0.1) return "#FF3B5C";
    return "#94A3B8";
  };

  return (
    <div className="min-h-screen bg-ims-bg">
      <nav className="border-b border-ims-border bg-ims-bg-panel px-4 py-2 flex items-center gap-4 text-xs">
        <Link href="/" className="text-ims-text-secondary hover:text-ims-teal">← Dashboard</Link>
        <span className="text-ims-teal font-semibold">Stock Analyzer</span>
      </nav>

      <div className="p-4 max-w-5xl mx-auto space-y-4">
        {/* Search Bar */}
        <div className="terminal-panel p-4">
          <h2 className="text-sm font-semibold text-ims-text-secondary uppercase tracking-wider mb-3">
            🔍 Analyze Any Stock
          </h2>
          <p className="text-xs text-ims-text-secondary mb-3">
            Enter a ticker symbol to scrape MoneyControl, Economic Times, and Reddit for news and sentiment analysis.
          </p>
          <div className="flex gap-2">
            <input
              placeholder="Enter ticker (e.g. RELIANCE, TCS, INFY)"
              value={ticker}
              onChange={e => setTicker(e.target.value)}
              onKeyDown={e => e.key === "Enter" && runAnalysis()}
              className="flex-1 bg-ims-bg-card border border-ims-border rounded px-4 py-2.5 text-sm text-ims-text-primary focus:border-ims-teal outline-none font-mono"
            />
            <button
              onClick={() => runAnalysis()}
              disabled={loading || !ticker.trim()}
              className="bg-ims-teal text-ims-bg px-6 py-2.5 rounded text-sm font-bold hover:bg-ims-teal/90 disabled:opacity-50 transition-colors"
            >
              {loading ? "⏳ Analyzing..." : "Analyze"}
            </button>
          </div>
          {error && <div className="text-ims-bearish text-xs mt-2">{error}</div>}
        </div>

        {loading && (
          <div className="terminal-panel p-8 text-center">
            <div className="animate-pulse text-ims-text-secondary">
              <div className="text-lg mb-2">🔍</div>
              <div className="text-sm">Scraping MoneyControl, Economic Times, Reddit...</div>
              <div className="text-xs mt-1">This may take 10-15 seconds</div>
            </div>
          </div>
        )}

        {result && (
          <>
            {/* Overview Card */}
            <div className="terminal-panel p-4">
              <div className="flex items-start justify-between flex-wrap gap-4">
                <div>
                  <div className="font-mono text-2xl font-bold text-ims-teal">{result.ticker}</div>
                  <div className="text-sm text-ims-text-secondary">{result.company_name}</div>
                  {result.current_price && (
                    <div className="mt-2">
                      <span className="text-xl font-mono font-bold text-ims-text-primary">
                        ₹{result.current_price.toLocaleString()}
                      </span>
                      {result.price_change !== undefined && (
                        <span className={`ml-2 font-mono text-sm font-bold ${(result.price_change || 0) >= 0 ? "text-ims-bullish" : "text-ims-bearish"}`}>
                          {(result.price_change || 0) >= 0 ? "+" : ""}{result.price_change?.toFixed(2)} ({result.price_pchange?.toFixed(2)}%)
                        </span>
                      )}
                    </div>
                  )}
                </div>

                <div className="text-center">
                  <div className="text-xs text-ims-text-secondary uppercase mb-1">AI Verdict</div>
                  <div
                    className="text-xl font-bold px-4 py-2 rounded border-2"
                    style={{ color: result.verdict_color, borderColor: result.verdict_color, backgroundColor: `${result.verdict_color}15` }}
                  >
                    {result.verdict}
                  </div>
                  <div className="text-xs font-mono mt-1" style={{ color: result.verdict_color }}>
                    Sentiment: {result.avg_sentiment > 0 ? "+" : ""}{result.avg_sentiment.toFixed(3)}
                  </div>
                </div>
              </div>

              {/* Sentiment Breakdown */}
              <div className="grid grid-cols-3 gap-3 mt-4">
                <div className="terminal-panel p-3 text-center">
                  <div className="text-xs text-ims-text-secondary">Positive</div>
                  <div className="text-lg font-bold text-ims-bullish">{result.sentiment_breakdown.positive}</div>
                </div>
                <div className="terminal-panel p-3 text-center">
                  <div className="text-xs text-ims-text-secondary">Neutral</div>
                  <div className="text-lg font-bold text-ims-text-primary">{result.sentiment_breakdown.neutral}</div>
                </div>
                <div className="terminal-panel p-3 text-center">
                  <div className="text-xs text-ims-text-secondary">Negative</div>
                  <div className="text-lg font-bold text-ims-bearish">{result.sentiment_breakdown.negative}</div>
                </div>
              </div>

              {/* Source Counts */}
              <div className="flex gap-4 mt-3 text-[10px] text-ims-text-secondary">
                <span>MoneyControl: {result.source_counts.moneycontrol} articles</span>
                <span>·</span>
                <span>Economic Times: {result.source_counts.economic_times} articles</span>
                <span>·</span>
                <span>Reddit: {result.source_counts.reddit} posts</span>
              </div>
            </div>

            {/* LLM Summary */}
            {result.llm_summary && (
              <div className="terminal-panel p-4 border-l-2 border-l-ims-teal">
                <h3 className="text-xs font-semibold text-ims-teal uppercase tracking-wider mb-2">🤖 AI Analysis</h3>
                <div className="text-sm text-ims-text-primary leading-relaxed whitespace-pre-wrap">
                  {result.llm_summary}
                </div>
              </div>
            )}

            {/* Articles List */}
            <div className="terminal-panel p-4">
              <h3 className="text-sm font-semibold text-ims-text-secondary uppercase tracking-wider mb-3">
                📰 News Articles ({result.total_articles} found)
              </h3>
              <div className="space-y-2 max-h-[60vh] overflow-y-auto">
                {result.articles.map((article, i) => (
                  <a
                    key={i}
                    href={article.url || "#"}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block terminal-panel p-3 hover:border-ims-teal transition-colors"
                    style={{ borderLeft: `3px solid ${sentimentColor(article.sentiment_score)}` }}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1">
                        <div className="text-sm text-ims-text-primary font-medium">{article.headline}</div>
                        {article.snippet && (
                          <div className="text-xs text-ims-text-secondary mt-1 line-clamp-2">{article.snippet}</div>
                        )}
                      </div>
                      <div className="text-right shrink-0">
                        <div className="font-mono text-xs font-bold" style={{ color: sentimentColor(article.sentiment_score) }}>
                          {article.sentiment_score > 0 ? "+" : ""}{article.sentiment_score.toFixed(2)}
                        </div>
                        <div className="text-[9px] text-ims-text-secondary mt-0.5">{article.sentiment_label}</div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 mt-2 text-[9px] text-ims-text-secondary">
                      <span className="uppercase font-semibold">{article.source}</span>
                      {article.upvotes !== undefined && <span>⬆ {article.upvotes}</span>}
                      {article.comments !== undefined && <span>💬 {article.comments}</span>}
                    </div>
                  </a>
                ))}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default function AnalyzePage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-ims-bg flex items-center justify-center text-ims-text-secondary">Loading...</div>}>
      <AnalyzeContent />
    </Suspense>
  );
}
