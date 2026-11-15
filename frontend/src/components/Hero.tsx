import { type CSSProperties, Fragment, useEffect, useState } from "react";

import { startClouds } from "../art/clouds";
import { toggleTheme } from "../theme";
import type { CatalogMetric } from "../types";
import { AskBox } from "./AskBox";
import { ExampleQuestions } from "./ExampleQuestions";

// The headline, word by word: [word, italic]. Each word drops in on its own.
const HEADLINE: [string, boolean][] = [
  ["ASK", false],
  ["in", true],
  ["plain", true],
  ["English.", true],
  ["VERIFIED", false],
  ["CODE", false],
  ["does", true],
  ["the", true],
  ["MATH.", false],
];

interface HeroProps {
  serverReady: boolean;
  busy: boolean;
  question: string;
  catalog: CatalogMetric[];
  onQuestionChange: (question: string) => void;
  onAsk: (question: string) => void;
}

export function Hero({ serverReady, busy, question, catalog, onQuestionChange, onAsk }: HeroProps) {
  const [area, setArea] = useState<HTMLDivElement | null>(null);
  const [canvas, setCanvas] = useState<HTMLCanvasElement | null>(null);

  useEffect(() => {
    if (!area || !canvas) {
      return;
    }
    // Clicking the sun or moon in the sky switches the theme, revealed from that spot.
    return startClouds(canvas, area, toggleTheme);
  }, [area, canvas]);

  return (
    <div className="hero-wrap" ref={setArea}>
      <canvas ref={setCanvas} className="hero-sky" aria-hidden="true" />
      <section className="hero" id="ask">
        <h1 className="headline-words" aria-label="Ask in plain English. Verified code does the math.">
          {HEADLINE.map(([word, italic], index) => (
            <Fragment key={word}>
              {index > 0 && " "}
              <span
                aria-hidden="true"
                className={italic ? "word italic" : "word"}
                style={{ "--i": index } as CSSProperties}
              >
                {word}
              </span>
            </Fragment>
          ))}
        </h1>
        <p className="lede">
          Questions about 99,441 orders from a Brazilian online store (2016–2018). Verified
          metrics answer first; anything else becomes SQL that is checked and run read-only.
        </p>

        {!serverReady && <p className="notice">Waking the server, this can take up to a minute…</p>}

        <AskBox
          question={question}
          disabled={busy}
          catalog={catalog}
          onChange={onQuestionChange}
          onSubmit={() => onAsk(question)}
        />
        <ExampleQuestions
          examples={catalog.map((metric) => metric.example)}
          disabled={busy}
          onPick={onAsk}
        />
      </section>
    </div>
  );
}
