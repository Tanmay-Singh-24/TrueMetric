import { useEffect, useState } from "react";

import { type SkylineHover, startSkyline } from "../art/skyline";
import { MONTHLY_REVENUE } from "../data";

interface DataSkylineProps {
  disabled: boolean;
  onAsk: (question: string) => void;
}

function formatMoney(value: number): string {
  return `R$ ${value.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function DataSkyline({ disabled, onAsk }: DataSkylineProps) {
  const [canvas, setCanvas] = useState<HTMLCanvasElement | null>(null);
  const [hover, setHover] = useState<SkylineHover | null>(null);

  useEffect(() => {
    if (!canvas) {
      return;
    }
    return startSkyline(canvas, setHover);
  }, [canvas]);

  const month = hover ? MONTHLY_REVENUE[hover.index] : null;
  // Keep the tooltip on screen when the first or last bar is near the edge.
  const tipLeft = hover && canvas ? Math.min(Math.max(hover.x, 84), canvas.clientWidth - 84) : 0;
  return (
    <figure className="skyline">
      <div className="skyline-stage">
        <canvas
          ref={setCanvas}
          className={month ? "is-pointing" : ""}
          role="img"
          aria-label="Pixel-art skyline of monthly revenue from January 2017 to August 2018, rising from about R$ 120 thousand to a peak of R$ 1.0 million in November 2017."
          onClick={() => month && !disabled && onAsk(month.question)}
        />
        {month && hover && (
          <div className="skyline-tip" style={{ left: tipLeft, top: hover.y }}>
            <span>{month.month}</span>
            <strong>{formatMoney(month.revenue)}</strong>
            {!disabled && <em>Click to ask</em>}
          </div>
        )}
      </div>
      <figcaption>
        Monthly merchandise revenue, Jan 2017 – Aug 2018. Every bar is a real month; point at one,
        click to ask about it.
      </figcaption>
    </figure>
  );
}
