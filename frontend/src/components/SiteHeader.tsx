import { REPO_URL } from "../links";

export function SiteHeader() {
  return (
    <header className="site-header">
      <a className="wordmark" href="#top">
        <svg viewBox="0 0 24 24" width="26" height="26" aria-hidden="true">
          <rect x="3" y="13" width="4" height="8" />
          <rect x="10" y="8" width="4" height="13" />
          <rect x="17" y="3" width="4" height="18" />
        </svg>
        TrueMetric
      </a>
      <nav>
        <a href="#ask">Ask</a>
        <a href="#how">How it works</a>
        <a href={`${REPO_URL}/blob/main/backend/evals/REPORT.md`} target="_blank" rel="noreferrer">
          Evaluation
        </a>
      </nav>
      <a className="pill-button" href={REPO_URL} target="_blank" rel="noreferrer">
        View source
      </a>
    </header>
  );
}
