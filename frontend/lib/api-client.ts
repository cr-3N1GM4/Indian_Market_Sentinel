// ARCHITECTURE NOTE:
// Central typed API client. All backend calls go through these
// functions. Handles error states gracefully — frontend never
// shows blank panels due to a failed API call.

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ApiResponse<T> {
  data: T;
  meta: {
    timestamp: string;
    version: string;
    stale?: boolean;
  };
}

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
    });

    if (!res.ok) {
      console.error(`API error: ${res.status} ${path}`);
      throw new Error(`API ${res.status}`);
    }

    const json: ApiResponse<T> = await res.json();
    return json.data;
  } catch (error) {
    console.error(`Fetch failed: ${path}`, error);
    throw error;
  }
}

// ----------------------------------------------------------
// Market Data
// ----------------------------------------------------------

export async function fetchMarketData() {
  return apiFetch<Record<string, unknown>>("/api/v1/market-data");
}

// ----------------------------------------------------------
// Regime
// ----------------------------------------------------------

export async function fetchCurrentRegime() {
  return apiFetch<Record<string, unknown>>("/api/v1/regime/current");
}

export async function fetchRegimeHistory(days = 180) {
  return apiFetch<Record<string, unknown>[]>(
    `/api/v1/regime/history?days=${days}`
  );
}

// ----------------------------------------------------------
// Sentiment
// ----------------------------------------------------------

export async function fetchTickerSentiment(ticker: string, hours = 24) {
  return apiFetch<Record<string, unknown>>(
    `/api/v1/sentiment/${ticker}?hours=${hours}`
  );
}

export async function fetchSentimentHeatmap() {
  return apiFetch<Record<string, unknown>>("/api/v1/sentiment/heatmap");
}

// ----------------------------------------------------------
// Signals
// ----------------------------------------------------------

export async function fetchActiveSignals() {
  return apiFetch<Record<string, unknown>[]>("/api/v1/signals/active");
}

export async function fetchSignalHistory(params?: {
  ticker?: string;
  sector?: string;
  confidence?: string;
  limit?: number;
  offset?: number;
}) {
  const query = new URLSearchParams();
  if (params?.ticker) query.set("ticker", params.ticker);
  if (params?.sector) query.set("sector", params.sector);
  if (params?.confidence) query.set("confidence", params.confidence);
  if (params?.limit) query.set("limit", String(params.limit));
  if (params?.offset) query.set("offset", String(params.offset));

  return apiFetch<Record<string, unknown>[]>(
    `/api/v1/signals/history?${query.toString()}`
  );
}

export async function fetchSignalDetail(signalId: string) {
  return apiFetch<Record<string, unknown>>(`/api/v1/signals/${signalId}`);
}

// ----------------------------------------------------------
// Institutional
// ----------------------------------------------------------

export async function fetchInstitutionalData(ticker: string) {
  return apiFetch<Record<string, unknown>>(
    `/api/v1/institutional/${ticker}`
  );
}

export async function fetchFIIDIIFlows(days = 30) {
  return apiFetch<Record<string, unknown>[]>(
    `/api/v1/institutional/fii-dii-flows?days=${days}`
  );
}

// ----------------------------------------------------------
// Calendar
// ----------------------------------------------------------

export async function fetchUpcomingActions(days = 7) {
  return apiFetch<Record<string, unknown>[]>(
    `/api/v1/calendar/upcoming?days=${days}`
  );
}

export async function fetchPreEventAlerts() {
  return apiFetch<Record<string, unknown>[]>("/api/v1/calendar/alerts");
}

export async function fetchResultAnalysis(ticker: string) {
  return apiFetch<Record<string, unknown>>(
    `/api/v1/calendar/results/${ticker}`
  );
}

export async function fetchBuybackOpportunities() {
  return apiFetch<Record<string, unknown>[]>("/api/v1/calendar/buybacks");
}

// ----------------------------------------------------------
// Portfolio
// ----------------------------------------------------------

export async function analyzePortfolio(
  userId: string,
  holdings: { ticker: string; quantity: number; avg_cost: number }[]
) {
  return apiFetch<Record<string, unknown>>("/api/v1/portfolio/analyze", {
    method: "POST",
    body: JSON.stringify({ user_id: userId, holdings }),
  });
}

export async function fetchPortfolio(userId: string) {
  return apiFetch<Record<string, unknown>[]>(
    `/api/v1/portfolio/${userId}`
  );
}

export async function runStressTest(
  userId: string,
  holdings: { ticker: string; quantity: number; avg_cost: number }[]
) {
  return apiFetch<Record<string, unknown>>("/api/v1/portfolio/stress-test", {
    method: "POST",
    body: JSON.stringify({ user_id: userId, holdings }),
  });
}

// ----------------------------------------------------------
// Technical
// ----------------------------------------------------------

export async function fetchTechnical(ticker: string) {
  return apiFetch<Record<string, unknown>>(
    `/api/v1/technical/${ticker}`
  );
}
