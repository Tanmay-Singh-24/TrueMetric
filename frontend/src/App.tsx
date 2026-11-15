import { useEffect, useState } from "react";

import { askQuestion, checkHealth, getCatalog } from "./api";
import { AnswerCard } from "./components/AnswerCard";
import { AuditPanel } from "./components/AuditPanel";
import { ClarifyOptions } from "./components/ClarifyOptions";
import { DataSkyline } from "./components/DataSkyline";
import { Facts } from "./components/Facts";
import { Hero } from "./components/Hero";
import { HowItWorks } from "./components/HowItWorks";
import { JoinTrap } from "./components/JoinTrap";
import { MetricTicker } from "./components/MetricTicker";
import { PixelLoader } from "./components/PixelLoader";
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

  useEffect(() => {
    // Sections marked data-reveal fade in the first time they scroll into view.
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        }
      },
      { threshold: 0.15 },
    );
    for (const element of document.querySelectorAll("[data-reveal]")) {
      observer.observe(element);
    }
    return () => observer.disconnect();
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

  // For questions asked from further down the page: bring the answer into view first.
  function askAndShow(text: string) {
    document.getElementById("results")?.scrollIntoView({ behavior: "smooth", block: "start" });
    ask(text);
  }

  const busy = !serverReady || loading;
  return (
    <div id="top">
      <SiteHeader />
      <main>
        <Hero
          serverReady={serverReady}
          busy={busy}
          question={question}
          catalog={catalog}
          onQuestionChange={setQuestion}
          onAsk={(text) => ask(text)}
        />

        <section id="results" className="results" aria-live="polite">
          {loading && <PixelLoader />}
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

        <DataSkyline disabled={busy} onAsk={askAndShow} />
        <MetricTicker disabled={busy} onAsk={askAndShow} />
        <HowItWorks />
        <JoinTrap />
        <Facts />
      </main>
      <SiteFooter />
    </div>
  );
}
