import type { ClarifyOption } from "../types";

interface ClarifyOptionsProps {
  options: ClarifyOption[];
  disabled: boolean;
  onPick: (metricId: string) => void;
}

export function ClarifyOptions({ options, disabled, onPick }: ClarifyOptionsProps) {
  return (
    <div className="clarify-options">
      {options.map((option) => (
        <button
          key={option.metric_id}
          type="button"
          className="option"
          disabled={disabled}
          onClick={() => onPick(option.metric_id)}
        >
          <strong>{option.name}</strong>
          <span>{option.definition}</span>
        </button>
      ))}
    </div>
  );
}
