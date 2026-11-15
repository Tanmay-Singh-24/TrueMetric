import { type CSSProperties, useState } from "react";

import { CountingNumber } from "./CountingNumber";

// A toy example small enough to see, then the real totals from docs/METRICS.md.
const TOY_ORDERS = [
  { id: "A", items: 1, payments: [100] },
  { id: "B", items: 3, payments: [240] },
  { id: "C", items: 2, payments: [30, 90] },
];
const REAL_TOTAL = 15739137.01;
const REAL_JOINED_TOTAL = 20156175.58;

const CORRECT_SQL = "SELECT SUM(payment_value) FROM order_payments";
const JOINED_SQL =
  "SELECT SUM(p.payment_value) FROM order_payments p JOIN order_items i USING (order_id)";

function toyTotal(joined: boolean): number {
  return TOY_ORDERS.reduce((total, order) => {
    const paid = order.payments.reduce((sum, amount) => sum + amount, 0);
    return total + paid * (joined ? order.items : 1);
  }, 0);
}

export function JoinTrap() {
  const [joined, setJoined] = useState(false);

  return (
    <section className="trap" data-reveal>
      <p className="eyebrow">The mistake this prevents</p>
      <h2>
        One join, <em>R$ 4.4 million</em> that was never paid.
      </h2>
      <p className="trap-lede">
        An order can have several items and several payments. Join both tables in one query and
        every payment is counted once per item. The query runs without an error. A verified
        metric cannot make this mistake.
      </p>

      <div className="trap-toggle" role="group" aria-label="Which query to run">
        <button type="button" aria-pressed={!joined} onClick={() => setJoined(false)}>
          Payments alone
        </button>
        <button type="button" aria-pressed={joined} onClick={() => setJoined(true)}>
          Joined with items
        </button>
      </div>
      <code className="trap-sql">{joined ? JOINED_SQL : CORRECT_SQL}</code>

      <div className="trap-board">
        <div className="toy">
          <p className="eyebrow">A toy example: three orders</p>
          {TOY_ORDERS.map((order) => (
            <div className="toy-row" key={order.id}>
              <span className="toy-label">Order {order.id}</span>
              <span className="toy-items" title={`${order.items} item rows`}>
                {Array.from({ length: order.items }, (_, index) => (
                  <i key={index} />
                ))}
              </span>
              <span className="toy-payments">
                {order.payments.flatMap((amount, payment) =>
                  Array.from({ length: joined ? order.items : 1 }, (_, copy) => (
                    <b
                      key={`${payment}-${copy}`}
                      className={copy > 0 ? "copy" : ""}
                      style={{ "--delay": `${copy * 110}ms` } as CSSProperties}
                    >
                      R$ {amount}
                    </b>
                  )),
                )}
              </span>
            </div>
          ))}
          <p className="toy-total">
            Total paid: <strong>R$ <CountingNumber value={toyTotal(joined)} decimals={0} /></strong>
          </p>
          <p className="toy-legend">
            <i /> item row <b>R$</b> payment <b className="copy">R$</b> repeated by the join
          </p>
        </div>
        <div className={joined ? "real is-wrong" : "real"}>
          <p className="eyebrow">On the real data, valid orders</p>
          <p className="real-total">
            R$ <CountingNumber value={joined ? REAL_JOINED_TOTAL : REAL_TOTAL} decimals={2} />
          </p>
          <p className="muted">
            {joined
              ? "Every payment repeated once per item: 28% too high, and no error."
              : "The true total of payment_value."}
          </p>
        </div>
      </div>
    </section>
  );
}
