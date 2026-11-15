import { DATASET_URL, REPO_URL } from "../links";

export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="footer-columns">
        <div>
          <p className="eyebrow">Explore</p>
          <a href="#ask">Ask a question</a>
          <a href="#how">How it works</a>
        </div>
        <div>
          <p className="eyebrow">Project</p>
          <a href={REPO_URL} target="_blank" rel="noreferrer">
            Source code ↗
          </a>
          <a href={`${REPO_URL}/blob/main/backend/evals/REPORT.md`} target="_blank" rel="noreferrer">
            Evaluation report ↗
          </a>
          <a href={`${REPO_URL}/blob/main/docs/METRICS.md`} target="_blank" rel="noreferrer">
            Metric definitions ↗
          </a>
        </div>
        <div>
          <p className="eyebrow">Data</p>
          <a href={DATASET_URL} target="_blank" rel="noreferrer">
            Olist dataset (MIT) ↗
          </a>
        </div>
      </div>
      <p className="footer-note">Built by Tanmay Singh · 2026 · A demo on public data</p>
    </footer>
  );
}
