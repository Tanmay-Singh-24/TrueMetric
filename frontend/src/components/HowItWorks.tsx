const STEPS = [
  {
    number: "01",
    title: "Route",
    text: "One LLM call reads the question. It picks one of ten verified metrics, asks which one you mean, or hands over to free-form SQL.",
  },
  {
    number: "02",
    title: "Compute",
    text: "A metric runs a fixed SQL file with bound values. Free-form SQL must pass a validator, then runs read-only with a five-second limit.",
  },
  {
    number: "03",
    title: "Show the working",
    text: "Every answer lists its definition, date range, filters and the exact SQL. Single numbers are formatted by code, never by the model.",
  },
];

const FACTS = [
  { value: "10", label: "verified metrics" },
  { value: "33 / 33", label: "reference cases match an independent Python computation" },
  { value: "3", label: "safety layers: validator, read-only role, time limit" },
  { value: "99,441", label: "orders, 2016–2018" },
];

export function HowItWorks() {
  return (
    <section id="how" className="how">
      <p className="eyebrow">How it works</p>
      <h2>
        The model decides <em>what</em> you asked. Verified code decides <em>how</em> to compute
        it.
      </h2>
      <ol className="steps">
        {STEPS.map((step) => (
          <li key={step.number}>
            <span className="step-number">{step.number}</span>
            <h3>{step.title}</h3>
            <p>{step.text}</p>
          </li>
        ))}
      </ol>

      <div className="trap">
        <div>
          <p className="eyebrow">The mistake this prevents</p>
          <p>
            An order can have several items and several payments. Join both tables and every
            payment is counted once per item. The query runs without error and returns a
            confident, wrong total. A verified metric cannot make this mistake.
          </p>
        </div>
        <dl>
          <div>
            <dt>Payments, counted correctly</dt>
            <dd>R$ 15,739,137.01</dd>
          </div>
          <div className="wrong">
            <dt>After joining order items</dt>
            <dd>R$ 20,156,175.58</dd>
          </div>
        </dl>
      </div>

      <ul className="facts">
        {FACTS.map((fact) => (
          <li key={fact.label}>
            <strong>{fact.value}</strong>
            <span>{fact.label}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
