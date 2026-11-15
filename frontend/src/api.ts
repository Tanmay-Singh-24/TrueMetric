import type { AskResponse, CatalogMetric } from "./types";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export const RATE_LIMIT_MESSAGE =
  "You have asked a lot of questions in the last minute. Please wait a moment and try again.";
const SERVER_ERROR_MESSAGE = "The server could not answer just now. Please try again.";

/** True once the API answers /health; false while it is asleep or unreachable. */
export async function checkHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${API_URL}/health`);
    return response.ok;
  } catch {
    return false;
  }
}

/** The ten metrics, used for the example questions. */
export async function getCatalog(): Promise<CatalogMetric[]> {
  const response = await fetch(`${API_URL}/catalog`);
  if (!response.ok) {
    throw new Error(SERVER_ERROR_MESSAGE);
  }
  return response.json();
}

/** Ask one question; metricId is set when the user picked a clarify option. */
export async function askQuestion(question: string, metricId?: string): Promise<AskResponse> {
  const response = await fetch(`${API_URL}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, metric_id: metricId ?? null }),
  });
  if (response.status === 429) {
    throw new Error(RATE_LIMIT_MESSAGE);
  }
  if (!response.ok) {
    throw new Error(SERVER_ERROR_MESSAGE);
  }
  return response.json();
}
