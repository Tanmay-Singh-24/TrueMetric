import { useEffect, useState } from "react";

import { prefersReducedMotion } from "../art/dither";

const DURATION_MS = 900;

interface CountingNumberProps {
  value: number;
  decimals: number;
}

/** A number that counts smoothly to its new value whenever the value changes. */
export function CountingNumber({ value, decimals }: CountingNumberProps) {
  const [shown, setShown] = useState(value);
  // One object kept across renders, so a new count starts from the number on screen.
  const [tween] = useState({ current: value });

  useEffect(() => {
    const from = tween.current;
    if (from === value || prefersReducedMotion()) {
      tween.current = value;
      setShown(value);
      return;
    }
    const startedAt = performance.now();
    let frame = requestAnimationFrame(function step(now) {
      const t = Math.min(1, (now - startedAt) / DURATION_MS);
      tween.current = from + (value - from) * (1 - (1 - t) ** 3);
      setShown(tween.current);
      if (t < 1) {
        frame = requestAnimationFrame(step);
      }
    });
    return () => cancelAnimationFrame(frame);
  }, [value, tween]);

  return (
    <span className="counting">
      {shown.toLocaleString("en-US", {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      })}
    </span>
  );
}
