import { type CSSProperties, useEffect, useState } from "react";

const DIGITS = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"];

/** Digits that roll into place, like a mechanical counter, when they come into view. */
export function Odometer({ value }: { value: string }) {
  const [element, setElement] = useState<HTMLSpanElement | null>(null);
  const [rolled, setRolled] = useState(false);

  useEffect(() => {
    if (!element) {
      return;
    }
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setRolled(true);
          observer.disconnect();
        }
      },
      { threshold: 0.6 },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, [element]);

  let order = 0;
  return (
    <span ref={setElement} className={rolled ? "odometer is-rolled" : "odometer"} aria-label={value}>
      {[...value].map((character, position) => {
        if (!/\d/.test(character)) {
          return (
            <span key={position} aria-hidden="true">
              {character}
            </span>
          );
        }
        const style = { "--digit": Number(character), "--order": order++ } as CSSProperties;
        return (
          <span key={position} className="reel" aria-hidden="true">
            <span className="reel-strip" style={style}>
              {DIGITS.map((digit) => (
                <span key={digit}>{digit}</span>
              ))}
            </span>
          </span>
        );
      })}
    </span>
  );
}
