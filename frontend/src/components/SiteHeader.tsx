import type { CSSProperties } from "react";

import { REPO_URL } from "../links";
import { ThemeToggle } from "./ThemeToggle";

// Heights of the four bars in the logo mark, in pixel blocks.
const LOGO_BARS = [2, 4, 3, 5];

export function SiteHeader() {
  return (
    <header className="site-header">
      <a className="wordmark" href="#top" aria-label="TrueMetric, back to top">
        <span className="logo-mark" aria-hidden="true">
          {LOGO_BARS.map((height, index) => (
            <i key={index} style={{ "--h": height, "--i": index } as CSSProperties} />
          ))}
        </span>
        <span className="logo-text">
          <b>True</b>Metric
        </span>
      </a>
      <nav>
        <a href="#ask">Ask</a>
        <a href="#how">How it works</a>
        <a href={`${REPO_URL}/blob/main/backend/evals/REPORT.md`} target="_blank" rel="noreferrer">
          Evaluation
        </a>
      </nav>
      <div className="header-actions">
        <ThemeToggle />
        <a className="pill-button" href={REPO_URL} target="_blank" rel="noreferrer">
          View source
        </a>
      </div>
    </header>
  );
}
