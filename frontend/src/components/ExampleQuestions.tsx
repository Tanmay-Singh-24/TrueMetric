import type { CSSProperties } from "react";

interface ExampleQuestionsProps {
  examples: string[];
  disabled: boolean;
  onPick: (question: string) => void;
}

export function ExampleQuestions({ examples, disabled, onPick }: ExampleQuestionsProps) {
  if (examples.length === 0) {
    return null;
  }
  return (
    <div className="examples">
      <span className="examples-label">Try:</span>
      {examples.map((example, index) => (
        <button
          key={example}
          type="button"
          className="chip"
          style={{ "--i": index } as CSSProperties}
          disabled={disabled}
          onClick={() => onPick(example)}
        >
          {example}
        </button>
      ))}
    </div>
  );
}
