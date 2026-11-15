import { type FormEvent, useEffect, useState } from "react";

import { prefersReducedMotion } from "../art/dither";
import type { CatalogMetric } from "../types";

const STATIC_PLACEHOLDER = "Ask about orders, revenue, customers, deliveries…";
const TICK_MS = 45;
const PAUSE_TICKS = 34; // how long a finished question stays, in ticks

interface AskBoxProps {
  question: string;
  disabled: boolean;
  catalog: CatalogMetric[]; // its example questions are typed into the placeholder
  onChange: (question: string) => void;
  onSubmit: () => void;
}

export function AskBox({ question, disabled, catalog, onChange, onSubmit }: AskBoxProps) {
  const [placeholder, setPlaceholder] = useState(STATIC_PLACEHOLDER);
  const [focused, setFocused] = useState(false);

  useEffect(() => {
    // Type each example question, pause, delete it, move on. Not while the visitor is
    // typing, and not for visitors who prefer reduced motion.
    const examples = catalog.map((metric) => metric.example);
    if (examples.length === 0 || focused || prefersReducedMotion()) {
      setPlaceholder(STATIC_PLACEHOLDER);
      return;
    }
    let index = 0;
    let length = 0;
    let deleting = false;
    let pause = 0;
    const timer = setInterval(() => {
      const text = examples[index];
      if (pause > 0) {
        pause -= 1;
        return;
      }
      length += deleting ? -3 : 1;
      if (!deleting && length >= text.length) {
        deleting = true;
        pause = PAUSE_TICKS;
      } else if (deleting && length <= 0) {
        length = 0;
        deleting = false;
        index = (index + 1) % examples.length;
        pause = 8;
      }
      setPlaceholder(`Try: ${text.slice(0, length)}▍`);
    }, TICK_MS);
    return () => clearInterval(timer);
  }, [catalog, focused]);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (question.trim()) {
      onSubmit();
    }
  }

  return (
    <form className="ask-box" onSubmit={handleSubmit}>
      <input
        type="text"
        value={question}
        maxLength={300}
        placeholder={placeholder}
        aria-label="Your question"
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        onChange={(event) => onChange(event.target.value)}
      />
      <button type="submit" disabled={disabled || !question.trim()}>
        Ask
      </button>
    </form>
  );
}
