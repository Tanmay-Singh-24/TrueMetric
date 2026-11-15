// Mirrors the API's response models in backend/src/orderlens/api.py.

export type Status = "answered" | "clarify" | "refused" | "failed";

export type Cell = string | number | boolean | null;

export interface Audit {
  path: "metric" | "freeform";
  metric_id: string | null;
  metric_name: string | null;
  definition: string | null;
  parameters: Record<string, string>;
  notes: string[];
  sql: string;
  check: string;
  attempts: number;
  row_count: number;
  duration_ms: number;
  model: string;
}

export interface ClarifyOption {
  metric_id: string;
  name: string;
  definition: string;
}

export interface AskResponse {
  status: Status;
  answer: string;
  headline: string | null;
  columns: string[];
  rows: Cell[][];
  audit: Audit | null;
  options: ClarifyOption[];
}

export interface CatalogMetric {
  id: string;
  name: string;
  definition: string;
  args: string[];
  example: string;
}
