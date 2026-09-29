import React from "react";
import { renderToString } from "react-dom/server";
import assert from "node:assert/strict";
import fs from "node:fs";
import { Chart, QueryChart, Evidence } from "../frontend/app.jsx";
import { waterfallRows, monthlyMix } from "../frontend/playbook-charts.jsx";

const reports = JSON.parse(
  fs.readFileSync(
    new URL("../tmp/frontend-fixtures.json", import.meta.url),
    "utf8",
  ),
);
const titles = {
  trend: "Weekly sales before returns: aligned period comparison",
  pvm: "Sales change: price, volume and mix bridge",
  growth: "Where sales changed: division contributions",
  margin: "Merchandise margin: original sale cohort bridge",
  seasonality: "Seasonal sales by retail week",
  scorecard: "Retail scorecard: six complementary measures",
  channels: "Channel sales growth versus merchandise margin",
  concentration: "Style sales concentration: contribution and cumulative share",
  pricing: "Unit-weighted actual and effective regular price distribution",
  promotions: "Affected-scope sales around the selected campaign",
  cohorts: "Repeat purchase by first observed purchase cohort",
  lapse: "Monthly observed customer states",
  segments: "Behavior segment profiles",
  affinity: "Category-pair affinity: lift and joint orders",
  loyalty: "Monthly merchandise sales by loyalty attachment",
  returns: "Original sale cohort: returns within 60 days",
  velocity: "Observed item velocity versus weeks of supply",
  inventory: "Weekly ending inventory: stock levels",
  fulfillment: "Monthly completed-order mix by fulfillment method",
};
assert.equal(reports.length, 19);
for (const report of reports) {
  const html = renderToString(
    <Chart
      slug={report.slug}
      outputs={report.outputs}
      period={report.period}
    />,
  );
  assert(
    html.includes(titles[report.slug]),
    `${report.slug} must use its primary playbook visual; refresh fixtures after backend visual data changes`,
  );
  assert(!html.includes("NaN"), report.slug);
  assert(!html.includes("Infinity"), report.slug);
  assert(
    html.includes('role="figure"') || html.includes("<table"),
    `${report.slug} has a figure or accessible matrix`,
  );
}

const waterfall = waterfallRows(10000, 11625, [
  ["Rate", 2125],
  ["Volume", -500],
]);
assert.equal(waterfall.residual, 0);
assert.deepEqual(waterfall.rows[1].range, [100, 121.25]);
assert.deepEqual(waterfall.rows[2].range, [116.25, 121.25]);
assert.equal(waterfall.rows.at(-1).cents, 11625);
assert.equal(waterfallRows(100, 100, [["Missing driver", -10]]).residual, 10);
assert.deepEqual(
  waterfallRows(-100, -300, [["Decline", -200]]).rows[1].range,
  [-3, -1],
);

const mix = monthlyMix(
  [
    { month: "2025-01-01", method: "Pickup", orders: 4 },
    { month: "2025-01-01", method: "Ship", orders: 6 },
    { month: "2025-02-01", method: "Ship", orders: 8 },
  ],
  "orders",
  "method",
);
assert.deepEqual(mix.groups, ["Pickup", "Ship"]);
assert.equal(mix.data[0].Pickup, 40);
assert.equal(mix.data[0].Ship, 60);
assert.equal(mix.data[0].base, 10);
assert.equal(mix.data[1].Pickup, 0);
assert.equal(mix.data[1].Ship, 100);
assert.equal(
  monthlyMix([{ month: "2025-01", group: "A", units: 0 }], "units", "group")
    .data[0].A,
  null,
);

const cohort = renderToString(
  <Chart
    slug="cohorts"
    outputs={[
      {
        rows: [
          {
            cohort_month: "2025-12-01",
            identified_buyers: 100,
            eligible_90: 0,
            repeat_buyers_90: 0,
            eligible_180: 50,
            repeat_buyers_180: 10,
          },
        ],
      },
    ]}
  />,
);
assert(cohort.includes("Not mature"));
assert(cohort.includes("20%"));
assert(cohort.includes("10 repeat / 50 eligible"));

const returns = renderToString(
  <Chart
    slug="returns"
    outputs={[
      { name: "base", rows: [{ original_units: 10 }] },
      {
        name: "return_cohort_elapsed",
        rows: [
          {
            sale_month: "2025-12-01",
            elapsed_day_bin: "0–30 days",
            returned_units: 2,
            original_units: 10,
            fully_mature_60d: false,
          },
        ],
      },
    ]}
  />,
);
assert(returns.includes("Not mature"));
assert(returns.includes("2 returned / 10 original units"));
assert(!returns.includes(">20%<"));

const affinity = renderToString(
  <Chart
    slug="affinity"
    outputs={[
      {
        rows: [
          {
            category_a: "A",
            category_b: "B",
            joint_baskets: 2,
            total_baskets: 1000,
            lift: 99,
          },
        ],
      },
    ]}
  />,
);
assert(affinity.includes("Insufficient base"));
assert(!affinity.includes("99× lift"));
assert(affinity.includes("Minimum joint order count"));

const scorecard = renderToString(
  <Chart
    slug="scorecard"
    outputs={[
      {
        rows: [
          {
            period: "current",
            division_name: "A",
            realized_sales_cents: 10000,
            identified_buyers: 100,
          },
          {
            period: "current",
            division_name: "B",
            realized_sales_cents: 5000,
            identified_buyers: 100,
          },
        ],
      },
      {
        name: "scorecard_summary",
        rows: [
          {
            period: "current",
            realized_sales_cents: 15000,
            sold_units: 50,
            merchandise_margin_cents: 7500,
            margin_rate_pct: 50,
            returned_units: 5,
            unit_return_rate_pct: 10,
            identified_buyers: 125,
            orders: 150,
          },
        ],
      },
    ]}
  />,
);
assert(scorecard.includes("<strong>125</strong>"));
assert(!scorecard.includes("<strong>200</strong>"));
assert(scorecard.includes("Unique identified buyers across the scope"));
assert(scorecard.includes("5 returned / 50 sold units"));

const output = {
  evidence_id: "E1",
  rows: [
    {
      category: "A",
      period: "Jan",
      sales_cents: 10000,
      numerator: 1,
      denominator: 10,
    },
    {
      category: "B",
      period: "Jan",
      sales_cents: 20000,
      numerator: 2,
      denominator: 20,
    },
  ],
};
for (const kind of [
  "bar",
  "line",
  "scatter",
  "stacked",
  "pareto",
  "waterfall",
  "heatmap",
]) {
  const spec =
    kind === "heatmap"
      ? {
          kind,
          x: "period",
          y: "category",
          value: "sales_cents",
          numerator: "numerator",
          denominator: "denominator",
        }
      : {
          kind,
          x: kind === "scatter" ? "denominator" : "category",
          y: "sales_cents",
          series: "period",
        };
  const html = renderToString(<QueryChart spec={spec} output={output} />);
  assert(html.includes("USD"), kind);
  assert(!html.includes("NaN"), kind);
  if (kind === "waterfall")
    assert(html.includes("no measured opening or closing total is implied"));
  if (kind === "pareto") assert(html.includes("not an unqueried population"));
  if (kind === "heatmap") assert(html.includes("1 / 10"));
}
const duplicate = renderToString(
  <QueryChart
    spec={{ kind: "heatmap", x: "period", y: "category", value: "sales_cents" }}
    output={{ rows: [output.rows[0], output.rows[0]] }}
  />,
);
assert(duplicate.includes("Duplicate cell"));
assert(!duplicate.includes("$200.00"));
for (const kind of ["line", "bar"]) {
  const comparison = renderToString(
    <QueryChart
      spec={{
        kind,
        x: "week",
        y: "current_sales_cents",
        comparison_y: "comparison_sales_cents",
      }}
      output={{
        evidence_id: "E2",
        rows: [
          {
            week: "2025-W01",
            current_sales_cents: 12000,
            comparison_sales_cents: 10000,
          },
        ],
      }}
    />,
  );
  assert(comparison.includes("Comparison Sales (USD)"));
  assert(comparison.includes("missing comparison observations remain gaps"));
}
const mismatched = renderToString(
  <QueryChart
    spec={{
      kind: "line",
      x: "week",
      y: "current_sales_cents",
      comparison_y: "sold_units",
    }}
    output={{
      rows: [{ week: "2025-W01", current_sales_cents: 12000, sold_units: 10 }],
    }}
  />,
);
assert(mismatched.includes("same metric units"));
const horizontal = renderToString(
  <QueryChart
    spec={{
      kind: "bar",
      orientation: "horizontal",
      x: "division",
      y: "change_cents",
    }}
    output={{
      evidence_id: "E3",
      rows: [
        { division: "Footwear", change_cents: -12000 },
        { division: "Apparel", change_cents: 9000 },
      ],
    }}
  />,
);
assert(
  horizontal.includes(
    "X: Change (USD) · Y: Division · signed values around zero",
  ),
);
assert(horizontal.includes("Change (USD) by Division"));
assert(!horizontal.includes("NaN"));
assert(horizontal.includes("Monetary values converted from cents to USD"));
const negativePareto = renderToString(
  <QueryChart
    spec={{ kind: "pareto", x: "category", y: "sales_cents" }}
    output={{ rows: [{ category: "A", sales_cents: -1 }] }}
  />,
);
assert(negativePareto.includes("nonnegative"));

const p = {
  headline: "Measured finding",
  scope: "2025 selected scope",
  metric_basis: "Sales before returns",
  supporting_evidence_ids: ["E1"],
  interpretation: "Read the observed comparison",
  limitations: ["Synthetic data"],
  next_questions: ["Which divisions account for the change?"],
  visual_status: "metric_cards",
};
const workspace = renderToString(
  <Evidence
    result={{
      id: "t",
      question: "Sales?",
      mode: "agent",
      outputs: [{ ...output, rows: [output.rows[0]] }],
      presentation: p,
    }}
    onOpenDoc={() => {}}
  />,
);
const sections = [
  "Measured finding",
  "Scope and metric",
  "Primary visual",
  "Supporting values",
  "Interpretation",
  "Limitations",
  "Next question",
];
let previous = -1;
for (const section of sections) {
  const position = workspace.indexOf(section);
  assert(position > previous, section);
  previous = position;
}
console.log(
  "Playbook visuals passed: all 19 primary designs, reconciled waterfall values, monthly share denominators, cohort maturity, affinity support suppression, deduplicated buyer reach, seven query-chart kinds, duplicate-cell protection, and seven-section workspace output order. Rendering tests do not claim browser layout verification.",
);
