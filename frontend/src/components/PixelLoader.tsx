import type { CSSProperties } from "react";

export function PixelLoader() {
  return (
    <div className="pixel-loader" role="status">
      <span className="pixel-row" aria-hidden="true">
        {Array.from({ length: 8 }, (_, index) => (
          <i key={index} style={{ "--i": index } as CSSProperties} />
        ))}
      </span>
      <span>Working on it…</span>
    </div>
  );
}
