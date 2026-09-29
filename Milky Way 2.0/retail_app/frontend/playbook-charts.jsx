import React, { useState } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  BarChart,
  Bar,
  Cell,
  Legend,
  ScatterChart,
  Scatter,
  ZAxis,
  ReferenceLine,
  ReferenceArea,
  ComposedChart,
  LabelList,
} from "recharts";

// The source visual grammar applies to marks; interface text remains black.
const CURRENT = "#126B5A",
  PRIOR = "#7C8790",
  UP = "#178A7A",
  DOWN = "#C95145",
  OTHER = "#8E9BA3";
const COLORS = [CURRENT, PRIOR, UP, OTHER, DOWN];
const number = (v, digits = 2) =>
  v == null || !Number.isFinite(Number(v))
    ? "—"
    : new Intl.NumberFormat("en-US", { maximumFractionDigits: digits }).format(
        v,
      );
const compact = (v) =>
  new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(v);
const money = (cents) =>
  cents == null
    ? "—"
    : new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: 2,
      }).format(cents / 100);
const pct = (n, d) => (d > 0 && n != null ? (100 * n) / d : null);
const percent = (v) => (v == null ? "—" : `${number(v, 1)}%`);
const label = (s) =>
  String(s)
    .replaceAll("_", " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
const findRows = (outputs, name) =>
  outputs?.find((o) => o.name === name)?.rows || [];
const total = (rows, key) =>
  rows.reduce((s, r) => s + (Number(r[key]) || 0), 0);
const median = (values) => {
  const sorted = values
    .filter((v) => v != null && Number.isFinite(v))
    .sort((a, b) => a - b);
  if (!sorted.length) return null;
  const n = sorted.length;
  return n % 2 ? sorted[(n - 1) / 2] : (sorted[n / 2 - 1] + sorted[n / 2]) / 2;
};
const grid = (
  <CartesianGrid strokeDasharray="3 5" vertical={false} stroke="#e5e5e5" />
);
const common = {
  margin: { top: 24, right: 24, bottom: 22, left: 12 },
  accessibilityLayer: true,
};
const tips = (
  <Tooltip
    contentStyle={{
      color: "#171717",
      border: "1px solid #d4d4d4",
      borderRadius: 8,
      fontSize: 12,
    }}
    formatter={(v, n) => [typeof v === "number" ? number(v) : v, n]}
  />
);

function Empty({ children = "No observations for this scope." }) {
  return <p className="empty">{children}</p>;
}
function Frame({ title, unit, caption, children, height = 330 }) {
  return (
    <section className="playbook-chart" aria-label={title}>
      <h3>{title}</h3>
      <div className="chart-unit">{unit}</div>
      <div
        className="chart"
        role="figure"
        aria-label={`${title}. ${unit}. Exact values are available in the evidence table.`}
        style={{ height }}
      >
        <ResponsiveContainer width="100%" height="100%">
          {children}
        </ResponsiveContainer>
      </div>
      <p className="caption">{caption}</p>
    </section>
  );
}
function Matrix({
  title,
  columns,
  rows,
  caption,
  columnHeading = "Cohort / group",
}) {
  return (
    <section className="playbook-chart">
      <h3>{title}</h3>
      <div className="playbook-matrix-scroll">
        <table className="playbook-matrix" aria-label={title}>
          <thead>
            <tr>
              <th scope="col">{columnHeading}</th>
              {columns.map((c) => (
                <th scope="col" key={c}>
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.key}>
                <th scope="row">
                  {r.name}
                  {r.base != null && (
                    <small>{number(r.base, 0)} identified buyers</small>
                  )}
                </th>
                {r.cells.map((c, i) => (
                  <td
                    key={columns[i]}
                    style={{
                      background:
                        c.value == null
                          ? "#f3f3f3"
                          : `rgba(${c.negative ? "201,81,69" : "18,107,90"},${0.04 + Math.max(0, Math.min(1, c.intensity ?? c.value / 100)) * 0.28})`,
                    }}
                    title={c.detail || ""}
                  >
                    <b>
                      {c.display ??
                        (c.value == null ? "Not observed" : percent(c.value))}
                    </b>
                    {c.detail && <small>{c.detail}</small>}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="caption">{caption}</p>
    </section>
  );
}

export function waterfallRows(start, end, parts) {
  let cursor = start;
  const rows = [
    {
      name: "Comparison",
      range: [Math.min(0, start / 100), Math.max(0, start / 100)],
      cents: start,
      total: true,
    },
  ];
  for (const [name, cents] of parts) {
    const next = cursor + cents;
    rows.push({
      name,
      range: [Math.min(cursor, next) / 100, Math.max(cursor, next) / 100],
      cents,
      prior_share: pct(cents, start),
    });
    cursor = next;
  }
  rows.push({
    name: "Current",
    range: [Math.min(0, end / 100), Math.max(0, end / 100)],
    cents: end,
    total: true,
  });
  return { rows, residual: end - cursor };
}
function Waterfall({ start, end, parts, title, caption }) {
  const { rows, residual } = waterfallRows(start, end, parts);
  return (
    <Frame
      title={title}
      unit="USD · signed contribution"
      caption={
        <>
          {caption} Reconciliation residual: {number(residual, 4)} cents.
          Measured current total: {money(end)}. Exact cents are shown on hover.
        </>
      }
    >
      <BarChart data={rows} {...common}>
        {grid}
        <XAxis dataKey="name" tick={{ fontSize: 10 }} interval={0} />
        <YAxis tickFormatter={compact} width={72} />
        <ReferenceLine y={0} stroke={PRIOR} />
        <Tooltip
          content={({ active, payload }) =>
            active && payload?.[0] ? (
              <div className="playbook-tooltip">
                <b>{payload[0].payload.name}</b>
                <div>{money(payload[0].payload.cents)}</div>
                <div>{number(payload[0].payload.cents, 4)} unrounded cents</div>
                {!payload[0].payload.total && (
                  <div>
                    {percent(payload[0].payload.prior_share)} of comparison
                    sales
                  </div>
                )}
              </div>
            ) : null
          }
        />
        <Bar dataKey="range" maxBarSize={62}>
          {rows.map((r, i) => (
            <Cell key={i} fill={r.total ? PRIOR : r.cents >= 0 ? UP : DOWN} />
          ))}
          <LabelList
            dataKey="cents"
            position="top"
            formatter={(v) => `${v > 0 ? "+" : ""}${compact(v / 100)}`}
            style={{ fontSize: 10, fill: "#171717" }}
          />
        </Bar>
      </BarChart>
    </Frame>
  );
}
function SignedBars({ rows, x, y, title, caption }) {
  const data = [...rows]
    .sort((a, b) => Math.abs(b[y]) - Math.abs(a[y]))
    .map((r) => ({ ...r, dollars: r[y] / 100 }));
  return (
    <Frame
      title={title}
      unit="USD · signed dollar contribution"
      caption={caption}
      height={Math.max(270, data.length * 38 + 65)}
    >
      <BarChart layout="vertical" data={data} {...common}>
        <CartesianGrid
          strokeDasharray="3 5"
          horizontal={false}
          stroke="#e5e5e5"
        />
        <XAxis type="number" tickFormatter={compact} />
        <YAxis
          type="category"
          dataKey={x}
          width={110}
          tick={{ fontSize: 11 }}
        />
        {tips}
        <ReferenceLine x={0} stroke={PRIOR} />
        <Bar dataKey="dollars" name="Sales change (USD)" maxBarSize={28}>
          {data.map((r, i) => (
            <Cell key={i} fill={r.dollars >= 0 ? UP : DOWN} />
          ))}
          <LabelList
            dataKey="dollars"
            position="right"
            formatter={(v) => `${v >= 0 ? "+" : ""}${compact(v)}`}
            style={{ fontSize: 10 }}
          />
        </Bar>
      </BarChart>
    </Frame>
  );
}
export function monthlyMix(rows, value, group, month = "month") {
  const groups = [...new Set(rows.map((r) => r[group]))];
  const months = [...new Set(rows.map((r) => r[month]))].sort();
  return {
    groups,
    data: months.map((m) => {
      const observed = rows.filter((r) => r[month] === m),
        base = total(observed, value);
      return {
        month: String(m).slice(0, 7),
        base,
        ...Object.fromEntries(
          groups.map((g) => [
            g,
            base
              ? (100 *
                  total(
                    observed.filter((r) => r[group] === g),
                    value,
                  )) /
                base
              : null,
          ]),
        ),
      };
    }),
  };
}
function Mix({ rows, value, group, title, caption, baseUnit }) {
  const { groups, data } = monthlyMix(rows, value, group);
  return (
    <Frame title={title} unit={`% of monthly ${baseUnit}`} caption={caption}>
      <BarChart data={data} {...common}>
        {grid}
        <XAxis dataKey="month" tick={{ fontSize: 10 }} />
        <YAxis domain={[0, 100]} tickFormatter={(v) => `${v}%`} />
        <Tooltip
          formatter={(v, n) => [percent(v), n]}
          labelFormatter={(v, payload) =>
            `${v} · base ${value.includes("cents") ? money(payload?.[0]?.payload.base) : number(payload?.[0]?.payload.base)} ${value.includes("cents") ? "sales" : baseUnit}`
          }
        />
        <Legend />
        {groups.map((g, i) => (
          <Bar
            key={g}
            dataKey={g}
            name={g}
            stackId="mix"
            fill={COLORS[i % COLORS.length]}
          />
        ))}
      </BarChart>
    </Frame>
  );
}

function Cohorts({ rows }) {
  return (
    <Matrix
      title="Repeat purchase by first observed purchase cohort"
      columns={["90-day repeat", "180-day repeat"]}
      rows={rows.map((r) => ({
        key: r.cohort_month,
        name: String(r.cohort_month).slice(0, 7),
        base: r.identified_buyers,
        cells: [90, 180].map((days) => ({
          value: pct(r[`repeat_buyers_${days}`], r[`eligible_${days}`]),
          detail: `${number(r[`repeat_buyers_${days}`], 0)} repeat / ${number(r[`eligible_${days}`], 0)} eligible`,
          display:
            r[`eligible_${days}`] > 0
              ? percent(pct(r[`repeat_buyers_${days}`], r[`eligible_${days}`]))
              : "Not mature",
        })),
      }))}
      caption="Rates use eligible identified buyers only; customer 0 is excluded. A cohort without a mature denominator is unobserved, never a zero repeat rate. This observed dataset does not establish acquisition history before its start."
    />
  );
}
function ReturnCohorts({ rows }) {
  const columns = [...new Set(rows.map((r) => r.elapsed_day_bin))],
    months = [...new Set(rows.map((r) => r.sale_month))].sort();
  return (
    <Matrix
      title="Original sale cohort: returns within 60 days"
      columns={columns}
      columnHeading="Original sale month"
      rows={months.map((m) => ({
        key: m,
        name: String(m).slice(0, 7),
        cells: columns.map((c) => {
          const r = rows.find(
              (x) => x.sale_month === m && x.elapsed_day_bin === c,
            ),
            mature = r?.fully_mature_60d === true;
          return {
            value: mature ? pct(r.returned_units, r.original_units) : null,
            display: mature
              ? percent(pct(r.returned_units, r.original_units))
              : "Not mature",
            detail: r
              ? `${number(r.returned_units, 0)} returned / ${number(r.original_units, 0)} original units${mature ? "" : " · incomplete 60-day follow-up"}`
              : "No observation",
          };
        }),
      }))}
      caption="Numerators contain returned units in each elapsed-day bin; each denominator is the same original sale cohort. Incomplete 60-day cohorts are muted. Later returns are outside this 60-day panel and remain in the underlying cohort evidence; the 2026 return-only tail is not a new sales period."
    />
  );
}
function SegmentProfiles({ rows }) {
  const metrics = [
    ["avg_recency_days", "Recency · days", "number"],
    ["orders_per_buyer", "Orders / buyer", "number"],
    ["sales_per_buyer_cents", "Sales / buyer · USD", "money"],
    ["margin_per_buyer_cents", "Margin / buyer · USD", "money"],
    ["categories_per_buyer", "Categories / buyer", "number"],
    ["discount_share_pct", "Discount share · %", "pct"],
    ["unit_return_rate_pct", "Unit returns · %", "pct"],
  ];
  return (
    <Matrix
      title="Behavior segment profiles"
      columns={metrics.map((m) => m[1])}
      rows={rows.map((r) => ({
        key: r.segment,
        name: r.segment,
        base: r.identified_buyers,
        cells: metrics.map(([k, , format]) => {
          const values = rows
              .map((x) => x[k])
              .filter((v) => v != null && Number.isFinite(v)),
            min = Math.min(...values),
            max = Math.max(...values),
            value = r[k];
          return {
            value: value ?? null,
            intensity: max > min ? (value - min) / (max - min) : 0.5,
            display:
              value == null
                ? "Unavailable"
                : format === "money"
                  ? money(value)
                  : format === "pct"
                    ? percent(value)
                    : number(value),
            detail: "Per identified-buyer segment",
          };
        }),
      }))}
      caption="Color is scaled independently within each metric; darker cells indicate a higher value, not a better outcome. Segment definitions and bases remain in the evidence. Descriptive observed behavior only; no demographic or motivational inference."
    />
  );
}
function Affinity({ rows }) {
  const [floor, setFloor] = useState(30);
  const categories = [
    ...new Set(rows.flatMap((r) => [r.category_a, r.category_b])),
  ].sort();
  return (
    <>
      <label className="playbook-floor">
        Minimum joint order count{" "}
        <input
          type="number"
          min="1"
          max="10000000"
          value={floor}
          onChange={(e) =>
            setFloor(
              Math.max(1, Math.min(10000000, Number(e.target.value) || 1)),
            )
          }
        />
      </label>
      <Matrix
        title="Category-pair affinity: lift and joint orders"
        columns={categories}
        columnHeading="Category pair"
        rows={categories.map((a) => ({
          key: a,
          name: a,
          cells: categories.map((b) => {
            if (a === b)
              return { value: null, display: "—", detail: "Same category" };
            const r = rows.find(
              (r) =>
                (r.category_a === a && r.category_b === b) ||
                (r.category_a === b && r.category_b === a),
            );
            if (!r || r.joint_baskets < floor)
              return {
                value: null,
                display: "Insufficient base",
                detail: r
                  ? `${number(r.joint_baskets, 0)} joint orders; floor ${number(floor, 0)}`
                  : "No returned pair",
              };
            return {
              value: r.lift,
              intensity: Math.min(1, Math.abs(r.lift - 1) / 2),
              negative: r.lift < 1,
              display: `${number(r.lift)}× lift`,
              detail: `${number(r.joint_baskets, 0)} joint / ${number(r.total_baskets, 0)} total orders`,
            };
          }),
        }))}
        caption={`Minimum joint-order base: ${number(floor, 0)}. Lift = observed pair frequency / independent base frequency. Rows show only pairs returned by the recipe; hidden cells are not zero. The floor is configurable and should reflect the category's support. Association does not establish a cross-sell effect.`}
      />
    </>
  );
}

export function PlaybookChart({ slug, outputs, period = {} }) {
  const rows = outputs?.[0]?.rows || [];
  if (!rows.length) return <Empty />;
  if (slug === "trend") {
    const current = rows
        .filter((r) => r.period === "current")
        .sort((a, b) => a.week_start.localeCompare(b.week_start)),
      prior = rows
        .filter((r) => r.period === "comparison")
        .sort((a, b) => a.week_start.localeCompare(b.week_start));
    const data = current.map((r, i) => ({
      week: r.week_start,
      current: r.sales_before_returns_cents / 100,
      comparison:
        prior[i]?.sales_before_returns_cents == null
          ? null
          : prior[i].sales_before_returns_cents / 100,
      units: r.sold_units,
      orders: r.orders,
      comparison_week: prior[i]?.week_start,
    }));
    const partial = [
      ...current.map((r) => [r, period.start, period.end]),
      ...prior.map((r) => [r, period.compare_start, period.compare_end]),
    ].filter(
      ([r, start, end]) =>
        start &&
        end &&
        (r.week_start < start ||
          new Date(`${r.week_start}T00:00:00Z`).getTime() + 6 * 86400000 >
            new Date(`${end}T00:00:00Z`).getTime()),
    ).length;
    return (
      <Frame
        title="Weekly sales before returns: aligned period comparison"
        unit="USD · week starting date"
        caption={
          <>
            Current solid green; comparison dashed gray, aligned by week
            position.{" "}
            {partial
              ? `${partial} partial boundary weeks are included; inspect exact date scope before comparing.`
              : "No partial boundary weeks detected in the selected windows."}{" "}
            Last current point{" "}
            {money(current.at(-1)?.sales_before_returns_cents)}; matched
            comparison{" "}
            {money(prior[current.length - 1]?.sales_before_returns_cents)}.
            Weekly units and orders are available in the evidence.
          </>
        }
      >
        <LineChart data={data} {...common}>
          {grid}
          <XAxis
            dataKey="week"
            tickFormatter={(v) => String(v).slice(5)}
            minTickGap={35}
          />
          <YAxis tickFormatter={compact} width={72} />
          {tips}
          <Legend />
          <Line
            type="linear"
            dataKey="current"
            name="Current before returns (USD)"
            stroke={CURRENT}
            strokeWidth={2.5}
            dot={false}
          />
          <Line
            type="linear"
            dataKey="comparison"
            name="Matched comparison (USD)"
            stroke={PRIOR}
            strokeDasharray="5 4"
            strokeWidth={2}
            dot={false}
            connectNulls={false}
          />
        </LineChart>
      </Frame>
    );
  }
  if (slug === "pvm") {
    const r = rows[0];
    return (
      <Waterfall
        start={r.comparison_sales_cents}
        end={r.current_sales_cents}
        parts={[
          ["Realized rate", r.realized_rate_cents],
          ["Unit volume", r.volume_cents],
          ["Portfolio mix", r.mix_cents],
          ["Entry / exit", r.entry_exit_cents],
          ["Rounding", r.rounding_adjustment_cents],
        ]}
        title="Sales change: price, volume and mix bridge"
        caption="Exact three-factor Shapley allocation at SKU × channel grain. Realized rate already contains markdown and promotion effects; these are not added again."
      />
    );
  }
  if (slug === "growth")
    return (
      <SignedBars
        rows={rows}
        x="division_name"
        y="change_cents"
        title="Where sales changed: division contributions"
        caption="Mutually exclusive division contributions are ranked by absolute dollars and retain their sign. Their sum reconciles to the total change. This identifies where the movement occurred, not its cause."
      />
    );
  if (slug === "margin") {
    const value = (p, k) =>
        total(
          rows.filter((r) => r.period === p),
          k,
        ),
      delta = (k) => value("current", k) - value("comparison", k),
      priorRate = pct(
        value("comparison", "merchandise_margin_cents"),
        value("comparison", "realized_sales_cents"),
      ),
      currentRate = pct(
        value("current", "merchandise_margin_cents"),
        value("current", "realized_sales_cents"),
      );
    return (
      <>
        <Waterfall
          start={value("comparison", "merchandise_margin_cents")}
          end={value("current", "merchandise_margin_cents")}
          parts={[
            ["Original net sales", delta("original_net_sales_cents")],
            ["Return deductions", -delta("returned_revenue_cents")],
            ["Original COGS", -delta("original_cogs_cents")],
            ["Recovered cost", delta("recovered_cost_cents")],
          ]}
          title="Merchandise margin: original sale cohort bridge"
          caption="Original net sales − linked refunds − original COGS + recovered cost. Includes observed linked returns; excludes operating and fulfillment expenses."
        />
        <div className="playbook-rate-bridge">
          <span>
            Margin rate
            <br />
            <b>{percent(priorRate)} comparison</b>
          </span>
          <span aria-hidden="true">→</span>
          <span>
            <b>{percent(currentRate)} current</b>
            <br />
            {priorRate == null || currentRate == null
              ? "No comparable denominator"
              : `${number(currentRate - priorRate)} pp change`}
          </span>
        </div>
        <p className="caption">
          Margin-rate denominator: realized merchandise sales after linked
          returns.
        </p>
      </>
    );
  }
  if (slug === "seasonality") {
    const years = [...new Set(rows.map((r) => r.retail_year))].sort(),
      weeks = [...new Set(rows.map((r) => r.retail_week))].sort(
        (a, b) => a - b,
      ),
      data = weeks.map((week) => ({
        week,
        ...Object.fromEntries(
          years.map((year) => {
            const value = rows.find(
              (r) => r.retail_year === year && r.retail_week === week,
            )?.sales_before_returns_cents;
            return [String(year), value == null ? null : value / 100];
          }),
        ),
      }));
    return (
      <Frame
        title="Seasonal sales by retail week"
        unit="USD · retail week number"
        caption="Each line is a retail year; missing weeks remain gaps. Partial fiscal years and boundary weeks remain visible in the evidence, including days with sales. Week 53 is never folded into another week. Two years are insufficient to establish a stable seasonal model."
      >
        <LineChart data={data} {...common}>
          {grid}
          <XAxis dataKey="week" />
          <YAxis tickFormatter={compact} width={72} />
          {tips}
          <Legend />
          {years.map((y, i) => (
            <Line
              key={y}
              dataKey={String(y)}
              name={`Retail year ${y}`}
              stroke={i === years.length - 1 ? CURRENT : PRIOR}
              strokeDasharray={i === years.length - 1 ? undefined : "5 4"}
              strokeWidth={2}
              dot={false}
              connectNulls={false}
            />
          ))}
        </LineChart>
      </Frame>
    );
  }
  if (slug === "scorecard") {
    const summaries = findRows(outputs, "scorecard_summary"),
      current = summaries.find((r) => r.period === "current"),
      prior = summaries.find((r) => r.period === "comparison");
    const metrics = [
      ["realized_sales_cents", "Realized sales", "money"],
      ["sold_units", "Sold units", "number"],
      ["merchandise_margin_cents", "Merchandise margin", "money"],
      ["margin_rate_pct", "Margin rate", "pct"],
      ["unit_return_rate_pct", "Unit return rate", "pct"],
      ["identified_buyers", "Identified buyer reach", "number"],
    ];
    const divisions = [...new Set(rows.map((r) => r.division_name))],
      contributions = divisions.map((division_name) => ({
        division_name,
        change:
          total(
            rows.filter(
              (r) =>
                r.period === "current" && r.division_name === division_name,
            ),
            "realized_sales_cents",
          ) -
          total(
            rows.filter(
              (r) =>
                r.period === "comparison" && r.division_name === division_name,
            ),
            "realized_sales_cents",
          ),
      }));
    const format = (v, type) =>
      type === "money" ? money(v) : type === "pct" ? percent(v) : number(v, 0);
    return (
      <>
        <section className="playbook-chart">
          <h3>Retail scorecard: six complementary measures</h3>
          <div className="playbook-tiles">
            {metrics.map(([key, name, type]) => (
              <div className="playbook-tile" key={key}>
                <span>{name}</span>
                <strong>{format(current?.[key], type)}</strong>
                <small>Comparison {format(prior?.[key], type)}</small>
                <small>
                  Change{" "}
                  {current?.[key] == null || prior?.[key] == null
                    ? "Unavailable"
                    : type === "pct"
                      ? `${number(current[key] - prior[key])} pp`
                      : format(current[key] - prior[key], type)}
                </small>
                <small>
                  {key === "identified_buyers"
                    ? "Unique identified buyers across the scope; anonymous buyer 0 excluded"
                    : key === "unit_return_rate_pct"
                      ? `${number(current?.returned_units, 0)} returned / ${number(current?.sold_units, 0)} sold units`
                      : key === "margin_rate_pct"
                        ? `Base: ${money(current?.realized_sales_cents)} realized sales`
                        : `Base: ${number(current?.orders, 0)} completed orders`}
                </small>
              </div>
            ))}
          </div>
          {!summaries.length && (
            <p className="caption">
              This saved report predates deduplicated scorecard totals. Rerun it
              for the six tiles; division buyer counts must not be summed.
            </p>
          )}
        </section>
        <SignedBars
          rows={contributions}
          x="division_name"
          y="change"
          title="Realized sales contribution by division"
          caption="Division changes use sales after linked returns. Examine margin and unit-return tiles alongside growth; buyer reach is deduplicated across the full selected scope."
        />
      </>
    );
  }
  if (slug === "channels") {
    const d = findRows(outputs, "channels_growth_margin").filter(
      (r) => r.sales_growth_pct != null && r.margin_rate_pct != null,
    );
    if (!d.length)
      return (
        <Empty>
          This saved report has no matched channel margin panel. Rerun it to
          plot growth against margin; channel and physical-store tables remain
          in Evidence.
        </Empty>
      );
    return (
      <Frame
        title="Channel sales growth versus merchandise margin"
        unit="X: YoY sales growth % · Y: margin rate % · bubble area: current sales"
        caption="Median reference lines provide descriptive context. Margin rate uses realized sales after linked returns; growth uses sales before returns. Channels are shown separately from physical stores. Differences do not establish a channel effect."
      >
        <ScatterChart {...common}>
          {grid}
          <XAxis
            type="number"
            dataKey="sales_growth_pct"
            name="Sales growth (%)"
            tickFormatter={(v) => `${number(v, 1)}%`}
          />
          <YAxis
            type="number"
            dataKey="margin_rate_pct"
            name="Margin rate (%)"
            tickFormatter={(v) => `${number(v, 1)}%`}
            width={72}
          />
          <ZAxis
            dataKey="current_sales_cents"
            name="Current sales (cents)"
            range={[250, 1300]}
          />
          <ReferenceLine
            x={median(d.map((r) => r.sales_growth_pct))}
            stroke={PRIOR}
            strokeDasharray="4 4"
          />
          <ReferenceLine
            y={median(d.map((r) => r.margin_rate_pct))}
            stroke={PRIOR}
            strokeDasharray="4 4"
          />
          <Tooltip
            content={({ active, payload }) =>
              active && payload?.[0] ? (
                <div className="playbook-tooltip">
                  <b>{payload[0].payload.channel_name}</b>
                  <div>
                    Growth {percent(payload[0].payload.sales_growth_pct)}
                  </div>
                  <div>
                    Margin {percent(payload[0].payload.margin_rate_pct)}
                  </div>
                  <div>
                    Current sales{" "}
                    {money(payload[0].payload.current_sales_cents)}
                  </div>
                  <div>
                    {number(payload[0].payload.orders, 0)} orders · AOV{" "}
                    {money(payload[0].payload.aov_before_returns_cents)}
                  </div>
                  <div>
                    Returns {percent(payload[0].payload.unit_return_rate_pct)}
                  </div>
                </div>
              ) : null
            }
          />
          <Scatter data={d} fill={CURRENT} fillOpacity={0.72}>
            <LabelList
              dataKey="channel_name"
              position="top"
              style={{ fontSize: 11, fill: "#171717" }}
            />
          </Scatter>
        </ScatterChart>
      </Frame>
    );
  }
  if (slug === "concentration") {
    const d = [...rows]
        .sort((a, b) => b.sales_cents - a.sales_cents)
        .map((r, i) => ({
          ...r,
          rank: i + 1,
          sales: r.sales_cents / 100,
          share: pct(r.cumulative_sales_cents, r.total_sales_cents),
        })),
      topDecile = Math.max(1, Math.ceil(d.length / 10));
    return (
      <Frame
        title="Style sales concentration: contribution and cumulative share"
        unit="Left axis: USD · right axis: cumulative % of all sales · X: style rank"
        caption={`Styles ranked by sales before returns. Marker: top ${topDecile} of ${d.length} returned styles (top decile of the displayed set). The cumulative denominator is all style sales in scope; this does not diagnose portfolio health.`}
      >
        <ComposedChart data={d} {...common}>
          {grid}
          <XAxis dataKey="rank" />
          <YAxis yAxisId="sales" tickFormatter={compact} width={72} />
          <YAxis
            yAxisId="share"
            orientation="right"
            domain={[0, 100]}
            tickFormatter={(v) => `${v}%`}
          />
          {tips}
          <Legend />
          <ReferenceLine
            x={topDecile}
            yAxisId="sales"
            stroke={OTHER}
            strokeDasharray="4 4"
          />
          <Bar
            dataKey="sales"
            yAxisId="sales"
            name="Style sales (USD)"
            fill={PRIOR}
          />
          <Line
            dataKey="share"
            yAxisId="share"
            name="Cumulative sales share (%)"
            stroke={CURRENT}
            strokeWidth={2.3}
            dot={false}
          />
        </ComposedChart>
      </Frame>
    );
  }
  if (slug === "pricing") {
    const actual = findRows(outputs, "selling_price_buckets"),
      regular = findRows(outputs, "regular_price_buckets"),
      combined = findRows(outputs, "pricing_distribution");
    const a = combined.length
        ? combined.filter((r) => r.price_basis === "actual")
        : actual,
      b = combined.length
        ? combined.filter((r) => r.price_basis === "regular")
        : regular,
      bins = [...new Set([...a, ...b].map((r) => r.usd_bucket_start))].sort(
        (x, y) => x - y,
      );
    if (!bins.length)
      return (
        <Empty>
          No unit-weighted price distribution is available for this saved scope.
        </Empty>
      );
    const d = bins.map((price) => ({
      price,
      actual: total(
        a.filter((r) => r.usd_bucket_start === price),
        "units",
      ),
      regular: b.length
        ? total(
            b.filter((r) => r.usd_bucket_start === price),
            "units",
          )
        : null,
    }));
    return (
      <Frame
        title="Unit-weighted actual and effective regular price distribution"
        unit="X: USD price-band lower bound · Y: sold units"
        caption={`Fixed-width $10 price bands aggregate sold units, not SKU counts. Actual price includes markdown and promotion effects. ${b.length ? "Effective regular price uses the stored price key for the sale." : "This saved report contains actual-price bands only; rerun it for the effective regular-price comparison."} Band boundaries and division detail are retained in Evidence.`}
      >
        <BarChart data={d} {...common}>
          {grid}
          <XAxis dataKey="price" tickFormatter={(v) => `$${v}`} />
          <YAxis tickFormatter={compact} width={72} />
          {tips}
          <Legend />
          <Bar
            dataKey="actual"
            name="Actual selling price · units"
            fill={CURRENT}
          />
          <Bar
            dataKey="regular"
            name="Effective regular price · units"
            fill={PRIOR}
          />
        </BarChart>
      </Frame>
    );
  }
  if (slug === "promotions") {
    const timeline = findRows(outputs, "promotion_timeline");
    if (!timeline.length)
      return (
        <Empty>
          This saved report contains campaign-associated totals only. Rerun for
          the affected-scope weekly timeline and campaign date band. Association
          does not establish incremental lift.
        </Empty>
      );
    const campaign = timeline[0],
      d = timeline.map((r) => ({
        ...r,
        sales: r.scope_sales_before_returns_cents / 100,
        discount: r.promotion_discount_cents / 100,
        margin: r.associated_cohort_merchandise_margin_cents / 100,
      })),
      active = d.filter((r) => r.overlaps_campaign);
    const band = active.length ? (
      <ReferenceArea
        x1={active[0].week_start}
        x2={active.at(-1).week_start}
        fill={CURRENT}
        fillOpacity={0.1}
      />
    ) : null;
    return (
      <>
        <p className="playbook-event">
          <b>{campaign.promotion_name}</b> · {campaign.valid_from}–
          {campaign.valid_to}
          <br />
          Affected scope: {campaign.division_name} ·{" "}
          {campaign.channel_name || "all eligible channels"}
          {campaign.loyalty_only ? " · loyalty only" : ""}
        </p>
        <Frame
          title="Affected-scope sales around the selected campaign"
          unit="USD · week starting date"
          caption="Shaded weekly buckets intersect campaign-valid dates; exact dates appear above. The selected campaign is the highest associated-sales campaign in scope. This is an observed event timeline, not an estimated causal baseline."
        >
          <LineChart data={d} {...common}>
            {grid}
            <XAxis dataKey="week_start" tickFormatter={(v) => v.slice(5)} />
            <YAxis tickFormatter={compact} width={72} />
            {band}
            {tips}
            <Line
              dataKey="sales"
              name="Affected-scope sales before returns (USD)"
              stroke={CURRENT}
              strokeWidth={2.4}
              dot={false}
            />
          </LineChart>
        </Frame>
        <Frame
          title="Affected-scope units around the selected campaign"
          unit="Sold units · week starting date"
          caption="Sales and units use separate axes in separate panels. Partial weeks are identified in the timeline evidence."
        >
          <LineChart data={d} {...common}>
            {grid}
            <XAxis dataKey="week_start" tickFormatter={(v) => v.slice(5)} />
            <YAxis tickFormatter={compact} width={72} />
            {band}
            {tips}
            <Line
              dataKey="scope_units"
              name="Affected-scope sold units"
              stroke={CURRENT}
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </Frame>
        <Frame
          title="Campaign redemption economics"
          unit="USD · week starting date"
          caption="Redeemed discount dollars and associated cohort merchandise margin remain separate measures. No incremental-sales or program-impact claim."
        >
          <BarChart data={d} {...common}>
            {grid}
            <XAxis dataKey="week_start" tickFormatter={(v) => v.slice(5)} />
            <YAxis tickFormatter={compact} width={72} />
            {tips}
            <Legend />
            <Bar
              dataKey="discount"
              name="Redeemed discount (USD)"
              fill={PRIOR}
            />
            <Bar
              dataKey="margin"
              name="Associated merchandise margin (USD)"
              fill={CURRENT}
            />
          </BarChart>
        </Frame>
      </>
    );
  }
  if (slug === "cohorts") return <Cohorts rows={rows} />;
  if (slug === "lapse") {
    const d = findRows(outputs, "lapse_monthly_states");
    if (!d.length)
      return (
        <Frame
          title="Observed customer recency distribution"
          unit="Identified buyers"
          caption="This saved baseline contains recency bands, not monthly state transitions. Rerun the playbook for active, lapsed and reactivated states; recency alone does not establish churn."
        >
          <BarChart data={rows} {...common}>
            {grid}
            <XAxis dataKey="recency_band" />
            <YAxis tickFormatter={compact} />
            {tips}
            <Bar
              dataKey="identified_buyers"
              name="Identified buyers"
              fill={CURRENT}
            />
          </BarChart>
        </Frame>
      );
    return (
      <Frame
        title="Monthly observed customer states"
        unit={`Identified buyers · lapse rule: more than ${d[0].lapse_threshold_days} days since last order`}
        caption="States are mutually exclusive: reactivated buyers purchased in the month after a gap above the rule; active excludes reactivated; lapsed has no recent order at observation. The 90-day operational rule is transparent and is not a validated category-specific churn threshold. No lost-revenue forecast is implied."
      >
        <BarChart
          data={d.map((r) => ({ ...r, month: String(r.month).slice(0, 7) }))}
          {...common}
        >
          {grid}
          <XAxis dataKey="month" tick={{ fontSize: 10 }} />
          <YAxis tickFormatter={compact} width={72} />
          {tips}
          <Legend />
          <Bar
            dataKey="active_buyers"
            name="Active"
            stackId="states"
            fill={CURRENT}
          />
          <Bar
            dataKey="lapsed_buyers"
            name="Lapsed"
            stackId="states"
            fill={PRIOR}
          />
          <Bar
            dataKey="reactivated_buyers"
            name="Reactivated"
            stackId="states"
            fill={UP}
          />
        </BarChart>
      </Frame>
    );
  }
  if (slug === "segments") {
    const profiles = findRows(outputs, "segment_profiles");
    if (!profiles.length)
      return (
        <Empty>
          This saved report has segment counts and sales only. Rerun for the
          seven-metric profile, including recency, margin, category breadth and
          return bases.
        </Empty>
      );
    return <SegmentProfiles rows={profiles} />;
  }
  if (slug === "affinity") return <Affinity rows={rows} />;
  if (slug === "loyalty") {
    const d = findRows(outputs, "loyalty_monthly_mix");
    if (!d.length)
      return (
        <Empty>
          This saved report has total attachment only. Rerun for monthly
          loyalty-attached sales share; the full attachment totals remain in
          Evidence.
        </Empty>
      );
    return (
      <Mix
        rows={d}
        value="sales_before_returns_cents"
        group="loyalty_usage"
        title="Monthly merchandise sales by loyalty attachment"
        baseUnit="merchandise sales before returns"
        caption="Each month totals 100% of merchandise sales before returns. Attachment is recorded on the order and differs from enrollment or causal program impact. Monthly order counts and units are retained in Evidence."
      />
    );
  }
  if (slug === "returns") {
    const d = findRows(outputs, "return_cohort_elapsed");
    if (!d.length)
      return (
        <Empty>
          This saved report contains division × channel totals. Rerun for
          original sale month × elapsed-return-day heatmaps with 60-day maturity
          checks.
        </Empty>
      );
    return <ReturnCohorts rows={d} />;
  }
  if (slug === "velocity") {
    const weeks =
      (new Date(`${period.end}T00:00:00Z`) -
        new Date(`${period.start}T00:00:00Z`)) /
        604800000 +
      1 / 7;
    if (!(weeks > 0))
      return (
        <Empty>
          A valid observed sales window is required to compute units per week.
        </Empty>
      );
    const d = rows
      .filter((r) => r.sold_units > 0)
      .map((r) => ({
        ...r,
        rate: r.sold_units / weeks,
        wos: r.available_units / (r.sold_units / weeks),
      }));
    return (
      <Frame
        title="Observed item velocity versus weeks of supply"
        unit="X: sold units / observed week · Y: weeks of supply · bubble area: available units"
        caption={`Observed window: ${number(weeks)} weeks. Weeks of supply = latest available units / observed units per week. Zero-sale items remain in the table and are excluded from this undefined ratio. No external distribution benchmark, stockout inference or delisting recommendation.`}
      >
        <ScatterChart {...common}>
          {grid}
          <XAxis
            type="number"
            dataKey="rate"
            name="Observed units / week"
            tickFormatter={compact}
          />
          <YAxis
            type="number"
            dataKey="wos"
            name="Weeks of supply"
            width={72}
          />
          <ZAxis dataKey="available_units" range={[12, 130]} />
          <ReferenceLine
            x={median(d.map((r) => r.rate))}
            stroke={PRIOR}
            strokeDasharray="4 4"
          />
          <ReferenceLine
            y={median(d.map((r) => r.wos))}
            stroke={PRIOR}
            strokeDasharray="4 4"
          />
          <Tooltip
            content={({ active, payload }) =>
              active && payload?.[0] ? (
                <div className="playbook-tooltip">
                  <b>{payload[0].payload.sku_code}</b>
                  <div>{payload[0].payload.division_name}</div>
                  <div>
                    {number(payload[0].payload.sold_units, 0)} units /{" "}
                    {number(weeks)} observed weeks
                  </div>
                  <div>
                    {number(payload[0].payload.rate)} units/week ·{" "}
                    {number(payload[0].payload.wos)} weeks of supply
                  </div>
                  <div>
                    {number(payload[0].payload.available_units, 0)} available
                    units
                  </div>
                </div>
              ) : null
            }
          />
          <Scatter data={d} fill={CURRENT} fillOpacity={0.45} />
        </ScatterChart>
      </Frame>
    );
  }
  if (slug === "inventory") {
    const d = findRows(outputs, "inventory_weekly");
    if (!d.length)
      return (
        <Empty>
          This saved report contains the latest inventory snapshot only. Rerun
          for weekly stock and separate flow panels; weekly ending balances must
          not be stacked or summed over time.
        </Empty>
      );
    return (
      <>
        <Frame
          title="Weekly ending inventory: stock levels"
          unit="Units · weekly inventory bucket ending date"
          caption="Only complete inventory buckets entirely inside the selected dates are included. Ending on-hand is a point-in-time balance, never summed across weeks. Weekly inventory buckets are distinct from retail-calendar weeks. Available stock excludes reserved units."
        >
          <LineChart data={d} {...common}>
            {grid}
            <XAxis
              dataKey="week_end"
              tickFormatter={(v) => String(v).slice(5)}
              minTickGap={40}
            />
            <YAxis tickFormatter={compact} width={72} />
            {tips}
            <Legend />
            <Line
              dataKey="closing_units"
              name="Ending on-hand units"
              stroke={CURRENT}
              dot={false}
              strokeWidth={2.3}
            />
            <Line
              dataKey="available_units"
              name="Available units"
              stroke={PRIOR}
              strokeDasharray="5 4"
              dot={false}
            />
          </LineChart>
        </Frame>
        <Frame
          title="Weekly inventory movements: separate flows"
          unit="Units per weekly inventory bucket"
          caption="Opening + receipts + restocks − sold units − shrink = closing. Bars show each flow separately; exact opening/closing balances remain in the evidence. Weekly data cannot establish daily stockout duration."
        >
          <BarChart data={d} {...common}>
            {grid}
            <XAxis
              dataKey="week_end"
              tickFormatter={(v) => String(v).slice(5)}
              minTickGap={40}
            />
            <YAxis tickFormatter={compact} width={72} />
            {tips}
            <Legend />
            <Bar dataKey="receipt_units" name="Receipts" fill={CURRENT} />
            <Bar dataKey="restocked_units" name="Restocks" fill={UP} />
            <Bar dataKey="sold_units" name="Sold units" fill={PRIOR} />
            <Bar dataKey="shrink_units" name="Shrink" fill={DOWN} />
          </BarChart>
        </Frame>
      </>
    );
  }
  if (slug === "fulfillment") {
    const d = findRows(outputs, "fulfillment_monthly_mix");
    if (!d.length)
      return (
        <Empty>
          This saved report contains method totals only. Rerun for the monthly
          completed-order mix; on-time delivery and fulfillment costs are not
          present in this dataset.
        </Empty>
      );
    return (
      <Mix
        rows={d}
        value="orders"
        group="fulfillment_method"
        title="Monthly completed-order mix by fulfillment method"
        baseUnit="completed orders"
        caption="Each month totals 100% of completed orders. Method AOV, merchandise margin and unit-return bases remain in Evidence. Differences are descriptive; actual delivery events, delivery costs and causal method benefits are unavailable."
      />
    );
  }
  return <Empty>See the evidence table for this query.</Empty>;
}

export function StructuredQueryChart({ spec, output }) {
  const rows = output?.rows || [];
  if (!rows.length || !spec?.x || !spec?.y) return null;
  const { x, y } = spec,
    scale = y.endsWith("_cents") ? 100 : 1,
    xScale = x.endsWith("_cents") ? 100 : 1,
    comparisonScale = spec.comparison_y?.endsWith("_cents") ? 100 : 1,
    comparisonLabel = spec.comparison_y
      ? label(spec.comparison_y.replace(/_cents$/, "")) +
        (comparisonScale === 100 ? " (USD)" : "")
      : "",
    yLabel = label(y.replace(/_cents$/, "")) + (scale === 100 ? " (USD)" : ""),
    xLabel = label(x.replace(/_cents$/, "")) + (xScale === 100 ? " (USD)" : "");
  const raw = rows.slice(
      0,
      spec.kind === "bar" || spec.kind === "waterfall" ? 20 : 100,
    ),
    d = raw.map((r) => ({
      ...r,
      [y]: r[y] == null ? null : r[y] / scale,
      ...(xScale === 100 ? { [x]: r[x] == null ? null : r[x] / xScale } : {}),
      ...(spec.comparison_y
        ? {
            [spec.comparison_y]:
              r[spec.comparison_y] == null
                ? null
                : r[spec.comparison_y] / comparisonScale,
          }
        : {}),
    }));
  const caption = `${output.evidence_id || "Query"} · ${scale === 100 || xScale === 100 ? "Monetary values converted from cents to USD" : "Raw units as named in the query"} · first ${raw.length} returned rows${rows.length > raw.length || output.truncated ? "; result is truncated" : ""}. Inspect SQL for filters and metric definitions.${spec.comparison_y ? ` Comparison: ${comparisonLabel}, aligned on the same ${xLabel} values; missing comparison observations remain gaps.` : ""}`;
  if (spec.comparison_y && scale !== comparisonScale)
    return (
      <Empty>
        Comparison series must use the same metric units; review the supporting
        table.
      </Empty>
    );
  if ((spec.kind === "line" || spec.kind === "bar") && spec.series) {
    const groups=[...new Set(d.map(r=>String(r[spec.series])))];
    const unique=new Map();
    const aligned=x==='calendar_date' && output.scope?.dates?.start && groups.every(g=>['current','comparison'].includes(g));
    for(const row of d){
      const group=String(row[spec.series]);
      const start=group==='current'?output.scope?.dates?.start:output.scope?.dates?.compare_start;
      const key=aligned && start ? Math.round((Date.parse(row[x])-Date.parse(start))/86400000)+1 : row[x];
      if(!unique.has(key))unique.set(key,{axis:key});
      unique.get(key)['series_'+groups.indexOf(group)]=row[y];
    }
    const plotted=[...unique.values()].sort((a,b)=>typeof a.axis==='number'?a.axis-b.axis:String(a.axis).localeCompare(String(b.axis)));
    const ChartKind=spec.kind==='line'?LineChart:BarChart;
    return <Frame title={spec.title || `${yLabel} by ${xLabel}`} unit={yLabel}
      caption={`${caption} Separate series: ${groups.join(', ')}. ${aligned?'Aligned by day within each selected period; missing observations remain gaps.':'Original X values retained.'}`}>
      <ChartKind data={plotted} {...common}>{grid}
        <XAxis dataKey="axis" tick={{fontSize:11}}/><YAxis width={72} tickFormatter={compact}/><Tooltip/><Legend/>
        {groups.map((g,i)=>spec.kind==='line'?<Line key={g} dataKey={'series_'+i} name={g} stroke={i?PRIOR:CURRENT} dot={false} connectNulls={false} strokeDasharray={i?'5 4':undefined}/>:<Bar key={g} dataKey={'series_'+i} name={g} fill={i?PRIOR:CURRENT}/>)}
      </ChartKind>
    </Frame>;
  }
  if (spec.kind === "heatmap") {
    if (!spec.value)
      return <Empty>A heatmap requires a numeric value field.</Empty>;
    const columns = [...new Set(raw.map((r) => String(r[x])))],
      groups = [...new Set(raw.map((r) => String(r[y])))],
      values = raw.map((r) => r[spec.value]).filter((v) => Number.isFinite(v)),
      max = Math.max(0, ...values.map(Math.abs)),
      valueScale = spec.value.endsWith("_cents") ? 100 : 1;
    return (
      <Matrix
        title={`${label(spec.value)} by ${yLabel} and ${xLabel}`}
        columns={columns}
        rows={groups.map((g) => ({
          key: g,
          name: g,
          cells: columns.map((c) => {
            const matches = raw.filter(
                (r) => String(r[y]) === g && String(r[x]) === c,
              ),
              r = matches[0],
              value = matches.length === 1 ? r[spec.value] : null;
            return {
              value,
              intensity: max ? Math.abs(value) / max : 0,
              negative: value < 0,
              display:
                matches.length > 1
                  ? "Duplicate cell"
                  : value == null
                    ? "Not observed"
                    : valueScale === 100
                      ? money(value)
                      : number(value),
              detail:
                r && spec.numerator && spec.denominator
                  ? `${number(r[spec.numerator])} / ${number(r[spec.denominator])}`
                  : "",
            };
          }),
        }))}
        caption={`${caption} Duplicate cells are not silently aggregated. ${valueScale === 100 ? "Cell values: USD." : `Cell units: ${label(spec.value)}.`}`}
      />
    );
  }
  const axes = (
    <>
      {grid}
      <XAxis dataKey={x} tick={{ fontSize: 11 }} minTickGap={20} />
      <YAxis tickFormatter={compact} width={72} />
      {tips}
    </>
  );
  let chart;
  if (spec.kind === "line")
    chart = (
      <LineChart data={d} {...common}>
        {axes}
        {spec.comparison_y && <Legend />}
        <Line
          dataKey={y}
          name={yLabel}
          stroke={CURRENT}
          strokeWidth={2.2}
          dot={false}
          connectNulls={false}
        />
        {spec.comparison_y && (
          <Line
            dataKey={spec.comparison_y}
            name={comparisonLabel}
            stroke={PRIOR}
            strokeDasharray="5 4"
            strokeWidth={2}
            dot={false}
            connectNulls={false}
          />
        )}
      </LineChart>
    );
  else if (spec.kind === "bar" && spec.orientation === "horizontal")
    chart = (
      <BarChart data={d} layout="vertical" {...common}>
        <CartesianGrid
          strokeDasharray="3 5"
          horizontal={false}
          stroke="#e5e5e5"
        />
        <XAxis type="number" name={yLabel} tickFormatter={compact} />
        <YAxis
          type="category"
          dataKey={x}
          name={xLabel}
          width={125}
          tick={{ fontSize: 11 }}
        />
        {tips}
        <ReferenceLine x={0} stroke={PRIOR} />
        {spec.comparison_y && <Legend />}
        <Bar dataKey={y} name={yLabel} maxBarSize={30}>
          {d.map((r, i) => (
            <Cell key={i} fill={r[y] >= 0 ? UP : DOWN} />
          ))}
          <LabelList
            dataKey={y}
            position="right"
            formatter={(v) =>
              v == null ? "" : `${v > 0 ? "+" : ""}${compact(v)}`
            }
            style={{ fontSize: 10, fill: "#171717" }}
          />
        </Bar>
        {spec.comparison_y && (
          <Bar
            dataKey={spec.comparison_y}
            name={comparisonLabel}
            fill={PRIOR}
            maxBarSize={30}
          />
        )}
      </BarChart>
    );
  else if (spec.kind === "scatter")
    chart = (
      <ScatterChart {...common}>
        {grid}
        <XAxis
          type="number"
          dataKey={x}
          name={xLabel}
          tickFormatter={compact}
        />
        <YAxis
          type="number"
          dataKey={y}
          name={yLabel}
          tickFormatter={compact}
          width={72}
        />
        {spec.size && (
          <ZAxis
            dataKey={spec.size}
            name={label(spec.size)}
            range={[35, 500]}
          />
        )}
        {tips}
        <Scatter data={d} fill={CURRENT} fillOpacity={0.75} />
      </ScatterChart>
    );
  else if (spec.kind === "stacked") {
    if (!spec.series)
      return <Empty>A stacked chart requires a series field.</Empty>;
    const groups = [...new Set(raw.map((r) => r[spec.series]))],
      keys = [...new Set(raw.map((r) => r[x]))],
      pivot = keys.map((key) => ({
        [x]: key,
        ...Object.fromEntries(
          groups.map((g) => [
            g,
            total(
              d.filter((r) => r[x] === key && r[spec.series] === g),
              y,
            ),
          ]),
        ),
      }));
    chart = (
      <BarChart data={pivot} {...common}>
        {axes}
        <Legend />
        {groups.map((g, i) => (
          <Bar
            key={g}
            dataKey={g}
            name={String(g)}
            stackId="series"
            fill={COLORS[i % COLORS.length]}
          />
        ))}
      </BarChart>
    );
  } else if (spec.kind === "pareto") {
    if (d.some((r) => r[y] < 0))
      return <Empty>Pareto shares require nonnegative values.</Empty>;
    const sorted = [...d].sort((a, b) => b[y] - a[y]),
      base = total(sorted, y);
    let cumulative = 0;
    const data = sorted.map((r) => ({
      ...r,
      cumulative_share: base ? (100 * (cumulative += r[y])) / base : null,
    }));
    chart = (
      <ComposedChart data={data} {...common}>
        {grid}
        <XAxis dataKey={x} tick={{ fontSize: 10 }} />
        <YAxis yAxisId="value" tickFormatter={compact} width={72} />
        <YAxis
          yAxisId="share"
          orientation="right"
          domain={[0, 100]}
          tickFormatter={(v) => `${v}%`}
        />
        {tips}
        <Legend />
        <Bar yAxisId="value" dataKey={y} name={yLabel} fill={PRIOR} />
        <Line
          yAxisId="share"
          dataKey="cumulative_share"
          name="Cumulative % of displayed rows"
          stroke={CURRENT}
          dot={false}
        />
      </ComposedChart>
    );
  } else if (spec.kind === "waterfall") {
    let cursor = 0;
    const data = d.map((r) => {
      const next = cursor + r[y],
        item = {
          ...r,
          range: [Math.min(cursor, next), Math.max(cursor, next)],
        };
      cursor = next;
      return item;
    });
    chart = (
      <BarChart data={data} {...common}>
        {grid}
        <XAxis dataKey={x} tick={{ fontSize: 10 }} />
        <YAxis tickFormatter={compact} width={72} />
        <ReferenceLine y={0} />
        <Tooltip formatter={(v, n, p) => [number(p.payload[y]), yLabel]} />
        <Bar dataKey="range" name={yLabel}>
          {data.map((r, i) => (
            <Cell key={i} fill={r[y] >= 0 ? UP : DOWN} />
          ))}
        </Bar>
      </BarChart>
    );
  } else
    chart = (
      <BarChart data={d} {...common}>
        {axes}
        <ReferenceLine y={0} />
        {spec.comparison_y && <Legend />}
        <Bar
          dataKey={y}
          name={yLabel}
          fill={CURRENT}
          radius={[3, 3, 0, 0]}
          maxBarSize={56}
        />
        {spec.comparison_y && (
          <Bar
            dataKey={spec.comparison_y}
            name={comparisonLabel}
            fill={PRIOR}
            radius={[3, 3, 0, 0]}
            maxBarSize={56}
          />
        )}
      </BarChart>
    );
  return (
    <Frame
      title={`${yLabel} by ${xLabel}`}
      unit={
        spec.kind === "pareto"
          ? `${yLabel} · right axis: cumulative % of displayed rows`
          : spec.kind === "bar" && spec.orientation === "horizontal"
            ? `X: ${yLabel} · Y: ${xLabel} · signed values around zero`
            : yLabel
      }
      height={
        spec.kind === "bar" && spec.orientation === "horizontal"
          ? Math.max(330, d.length * 35 + 70)
          : 330
      }
      caption={`${caption}${spec.kind === "waterfall" ? " Running signed contributions start at zero; no measured opening or closing total is implied." : spec.kind === "pareto" ? " Cumulative share is based only on the displayed returned rows, not an unqueried population." : ""}`}
    >
      {chart}
    </Frame>
  );
}
