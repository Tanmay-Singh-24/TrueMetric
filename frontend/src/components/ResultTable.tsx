import type { Cell } from "../types";

const MAX_ROWS_SHOWN = 50;

interface ResultTableProps {
  columns: string[];
  rows: Cell[][];
}

function formatCell(value: Cell): string {
  if (value === null) {
    return "—";
  }
  if (typeof value === "number") {
    return value.toLocaleString("en-US", { maximumFractionDigits: 2 });
  }
  return String(value);
}

export function ResultTable({ columns, rows }: ResultTableProps) {
  if (rows.length === 0) {
    return <p className="muted">The query returned no rows.</p>;
  }
  const shown = rows.slice(0, MAX_ROWS_SHOWN);
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column}>{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {shown.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {row.map((value, columnIndex) => (
                <td key={columnIndex} className={typeof value === "number" ? "number" : ""}>
                  {formatCell(value)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > MAX_ROWS_SHOWN && (
        <p className="muted">
          Showing the first {MAX_ROWS_SHOWN} of {rows.length} rows.
        </p>
      )}
    </div>
  );
}
