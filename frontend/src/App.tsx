import { useEffect, useState } from "react";

import { askQuestion, checkHealth, getCatalog } from "./api";
import { AnswerCard } from "./components/AnswerCard";
import { AskBox } from "./components/AskBox";
import { AuditPanel } from "./components/AuditPanel";
import { ClarifyOptions } from "./components/ClarifyOptions";
import { ExampleQuestions } from "./components/ExampleQuestions";
import { HowItWorks } from "./components/HowItWorks";
import { ResultTable } from "./components/ResultTable";
import { SiteFooter } from "./components/SiteFooter";
import { SiteHeader } from "./components/SiteHeader";
import type { AskResponse, CatalogMetric } from "./types";

const HEALTH_RETRY_MS = 3000;

export function App() {
  const [serverReady, setServerReady] = useState(false);
  const [catalog, setCatalog] = useState<CatalogMetric[]>([]);
  const [question, setQuestion] = useState("");
  const [askedQuestion, setAskedQuestion] = useState("");
  const [result, setResult] = useState<AskResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // Render's free tier sleeps when idle, so keep calling /health until it wakes up.
    let cancelled = false;
    async function waitForServer() {
      while (!cancelled && !(await checkHealth())) {
        await new Promise((resolve) => setTimeout(resolve, HEALTH_RETRY_MS));
      }
      if (cancelled) {
        return;
      }
      setServerReady(true);
      setCatalog(await getCatalog().catch(() => []));
    }
    waitForServer();
    return () => {
      cancelled = true;
    };
  }, []);

  async function ask(text: string, metricId?: string) {
    setQuestion(text);
    setAskedQuestion(text);
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await askQuestion(text, metricId));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setLoading(false);
    }
  }

  const busy = !serverReady || loading;
  return (
    <div id="top">
      <SiteHeader />
      <main>
        <section className="hero" id="ask">
          <h1>
            ASK <em>in plain English.</em> VERIFIED CODE <em>does the</em> MATH.
          </h1>
          <p className="lede">
            Questions about 99,441 orders from a Brazilian online store (2016–2018). Verified
            metrics answer first; anything else becomes SQL that is checked and run read-only.
          </p>

          {!serverReady && (
            <p className="notice">Waking the server, this can take up to a minute…</p>
          )}

          <AskBox
            question={question}
            disabled={busy}
            onChange={setQuestion}
            onSubmit={() => ask(question)}
          />
          <ExampleQuestions
            examples={catalog.map((metric) => metric.example)}
            disabled={busy}
            onPick={(example) => ask(example)}
          />
        </section>

        <section className="results" aria-live="polite">
          {loading && <p className="muted">Working on it…</p>}
          {error && <p className="notice error">{error}</p>}

          {result && (
            <>
              <AnswerCard
                status={result.status}
                headline={result.headline}
                answer={result.answer}
              />
              {result.status === "clarify" && (
                <ClarifyOptions
                  options={result.options}
                  disabled={loading}
                  onPick={(metricId) => ask(askedQuestion, metricId)}
                />
              )}
              {(result.status === "refused" || result.status === "failed") && (
                <p className="muted">Try rephrasing, or pick one of the example questions.</p>
              )}
              {result.status === "answered" && (
                <ResultTable columns={result.columns} rows={result.rows} />
              )}
              {result.audit && <AuditPanel audit={result.audit} />}
            </>
          )}
        </section>

        <HowItWorks />
      </main>
      <SiteFooter />
    </div>
  );
}
