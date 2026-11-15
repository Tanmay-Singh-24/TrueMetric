// Real figures from backend/tests/reference_values.json (computed from the raw Olist CSVs
// and matched by the metric SQL). They drive the pixel art and the ticker, so even the
// decoration on this page is true.

export interface MonthRevenue {
  month: string; // e.g. "Nov 2017"
  question: string; // asked when the bar is clicked
  revenue: number;
}

const MONTHS: [string, string, number][] = [
  ["Jan 2017", "January 2017", 120098.27],
  ["Feb 2017", "February 2017", 244959.35],
  ["Mar 2017", "March 2017", 368341.32],
  ["Apr 2017", "April 2017", 353842.98],
  ["May 2017", "May 2017", 503159.19],
  ["Jun 2017", "June 2017", 429916.61],
  ["Jul 2017", "July 2017", 492287.3],
  ["Aug 2017", "August 2017", 568245.79],
  ["Sep 2017", "September 2017", 621415.91],
  ["Oct 2017", "October 2017", 660179.62],
  ["Nov 2017", "November 2017", 1003862.14],
  ["Dec 2017", "December 2017", 742183.79],
  ["Jan 2018", "January 2018", 945456.29],
  ["Feb 2018", "February 2018", 837895.43],
  ["Mar 2018", "March 2018", 981051.06],
  ["Apr 2018", "April 2018", 993592.98],
  ["May 2018", "May 2018", 992871.75],
  ["Jun 2018", "June 2018", 863265.53],
  ["Jul 2018", "July 2018", 878044.27],
  ["Aug 2018", "August 2018", 848860.1],
];

export const MONTHLY_REVENUE: MonthRevenue[] = MONTHS.map(([month, fullMonth, revenue]) => ({
  month,
  question: `What was our revenue in ${fullMonth}?`,
  revenue,
}));

export interface TickerMetric {
  value: string;
  label: string;
  question: string;
}

export const TICKER_METRICS: TickerMetric[] = [
  { value: "R$ 7,341,182.41", label: "Merchandise revenue, 2018", question: "What were total sales in 2018?" },
  { value: "98,207", label: "Valid orders, all data", question: "How many orders were placed in total?" },
  { value: "R$ 137.42", label: "Average order value", question: "What is the average order value?" },
  { value: "3.04%", label: "Repeat customer rate", question: "What share of customers came back for a second order?" },
  { value: "6.77%", label: "Late delivery rate", question: "How often did deliveries arrive late?" },
  { value: "4.09 / 5", label: "Average review score", question: "What is our average customer rating?" },
  { value: "R$ 1,003,862.14", label: "Best month: November 2017", question: "What was our revenue in November 2017?" },
];
