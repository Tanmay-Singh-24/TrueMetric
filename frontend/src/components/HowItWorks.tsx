import { useEffect, useState } from "react";

import { startHalftone } from "../art/halftone";

const STEPS = [
  {
    number: "01",
    title: "Route",
    text: "One LLM call reads the question. It picks one of ten verified metrics, asks which one you mean when two could fit, or hands over to free-form SQL. It must pass on every filter it hears; code checks the metric can honour them.",
  },
  {
    number: "02",
    title: "Compute",
    text: "A metric runs a fixed SQL file with bound values: the model never writes it. Free-form SQL must pass a validator with a function allowlist, then runs as a read-only role that is cut off after five seconds.",
  },
  {
    number: "03",
    title: "Show the working",
    text: "Every answer carries its definition, date range, filters, inclusion rules and the exact SQL that ran. A single number is formatted by code, so the figure you read first never passes through the model.",
  },
];

const WORDS = ["routing", "verified code", "showing its working"];

export function HowItWorks() {
  const [section, setSection] = useState<HTMLElement | null>(null);
  const [canvas, setCanvas] = useState<HTMLCanvasElement | null>(null);
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (!section || !canvas) {
      return;
    }
    return startHalftone(canvas, section, setStep);
  }, [section, canvas]);

  return (
    <section id="how" className="how" ref={setSection}>
      <div className="how-sticky">
        <p className="eyebrow">How it works</p>
        <h2>
          Answering through{" "}
          <em key={step} className="swap">
            {WORDS[step]}
          </em>
        </h2>
        <canvas
          ref={setCanvas}
          className="halftone"
          role="img"
          aria-label="Halftone illustration that changes with each step: a fork, a database, a magnifying glass."
        />
      </div>
      <ol className="how-steps">
        {STEPS.map((item, index) => (
          <li key={item.number} className={index === step ? "is-active" : ""}>
            <span className="step-number">{item.number}</span>
            <h3>{item.title}</h3>
            <p>{item.text}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}
