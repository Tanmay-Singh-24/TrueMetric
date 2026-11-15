import type { Status } from "../types";

interface AnswerCardProps {
  status: Status;
  headline: string | null;
  answer: string;
}

export function AnswerCard({ status, headline, answer }: AnswerCardProps) {
  return (
    <section className={`answer-card ${status}`}>
      {headline && <p className="headline">{headline}</p>}
      <p className="answer">{answer}</p>
    </section>
  );
}
