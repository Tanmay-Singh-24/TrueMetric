import type { Audit } from "../types";

interface AuditPanelProps {
  audit: Audit;
}

function describeParameters(parameters: Record<string, string>): string[] {
  const { start_date, end_date, ...others } = parameters;
  const lines = start_date && end_date ? [`Dates: ${start_date} to ${end_date}`] : [];
  for (const [name, value] of Object.entries(others)) {
    lines.push(`${name.replace("_", " ")}: ${value}`);
  }
  return lines;
}

export function AuditPanel({ audit }: AuditPanelProps) {
  const parameters = describeParameters(audit.parameters);
  const title = audit.path === "metric" ? audit.metric_name : "Free-form query";
  return (
    <section className="audit-panel">
      <h2>How this was calculated</h2>
      <p className="audit-title">
        <strong>{title}</strong>
        <span className={`badge ${audit.path}`}>{audit.check}</span>
      </p>
      {audit.definition && <p>{audit.definition}</p>}
      {parameters.length > 0 && (
        <ul className="parameters">
          {parameters.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      )}
      {audit.notes.length > 0 && (
        <ul className="notes">
          {audit.notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      )}
      <p className="muted">
        {audit.row_count} {audit.row_count === 1 ? "row" : "rows"} in{" "}
        {(audit.duration_ms / 1000).toFixed(1)} s
        {audit.attempts > 1 && ` · ${audit.attempts} attempts`} · model {audit.model}
      </p>
      <details>
        <summary>SQL that ran</summary>
        <pre>{audit.sql}</pre>
      </details>
    </section>
  );
}
