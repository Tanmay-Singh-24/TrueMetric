import type { FormEvent } from "react";

interface AskBoxProps {
  question: string;
  disabled: boolean;
  onChange: (question: string) => void;
  onSubmit: () => void;
}

export function AskBox({ question, disabled, onChange, onSubmit }: AskBoxProps) {
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
        placeholder="Ask about orders, revenue, customers, deliveries…"
        aria-label="Your question"
        onChange={(event) => onChange(event.target.value)}
      />
      <button type="submit" disabled={disabled || !question.trim()}>
        Ask
      </button>
    </form>
  );
}
