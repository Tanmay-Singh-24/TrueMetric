import { Odometer } from "./Odometer";

const FACTS = [
  { value: "10", label: "verified metrics, each one fixed SQL file" },
  { value: "33/33", label: "reference cases matched by an independent Python computation" },
  { value: "3", label: "safety layers: validator, read-only role, 5-second limit" },
  { value: "99,441", label: "orders in the dataset, 2016–2018" },
];

export function Facts() {
  return (
    <section className="facts" data-reveal>
      <ul>
        {FACTS.map((fact) => (
          <li key={fact.label}>
            <strong>
              <Odometer value={fact.value} />
            </strong>
            <span>{fact.label}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
