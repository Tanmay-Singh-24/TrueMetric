import { TICKER_METRICS } from "../data";

interface MetricTickerProps {
  disabled: boolean;
  onAsk: (question: string) => void;
}

/** A moving band of real metric values; clicking one asks the question behind it. */
export function MetricTicker({ disabled, onAsk }: MetricTickerProps) {
  // The list is drawn twice so the band can loop without a gap; the copy is hidden from
  // screen readers and the keyboard.
  const items = (isCopy: boolean) =>
    TICKER_METRICS.map((metric) => (
      <button
        key={`${isCopy}-${metric.label}`}
        type="button"
        className="ticker-item"
        disabled={disabled}
        tabIndex={isCopy ? -1 : undefined}
        aria-hidden={isCopy || undefined}
        onClick={() => onAsk(metric.question)}
      >
        <strong>{metric.value}</strong>
        <span>{metric.label}</span>
      </button>
    ));

  return (
    <div className="ticker" aria-label="Verified metric values. Choose one to ask about it.">
      <div className="ticker-track">
        {items(false)}
        {items(true)}
      </div>
    </div>
  );
}
