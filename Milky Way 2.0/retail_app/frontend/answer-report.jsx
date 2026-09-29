import React, { useState } from "react";
import { Chart, QueryChart, Table } from "./chart-table.jsx";
const label = (value) =>
  String(value || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
const slugs = new Set([
  "trend",
  "pvm",
  "growth",
  "margin",
  "seasonality",
  "scorecard",
  "channels",
  "concentration",
  "pricing",
  "promotions",
  "cohorts",
  "lapse",
  "segments",
  "affinity",
  "loyalty",
  "returns",
  "velocity",
  "inventory",
  "fulfillment",
]);

function MetricCards({ outputs }) {
  const output = outputs.find(
    (o) => o.rows?.length === 1 && o.name !== "dataset_inspection",
  );
  if (!output)
    return (
      <p className="caption">
        A reliable chart was not produced for this result. Review the measured
        table below; no values have been invented.
      </p>
    );
  const values = Object.entries(output.rows[0])
    .filter(
      ([key, value]) =>
        typeof value === "number" &&
        Number.isFinite(value) &&
        !/_key$|_id$/.test(key),
    )
    .slice(0, 6);
  return (
    <div className="answer-metric-cards" aria-label="Measured totals">
      {values.map(([key, value]) => (
        <div className="answer-metric-card" key={key}>
          <span>{label(key.replace(/_cents$/, ""))}</span>
          <strong>
            {/_cents$/.test(key)
              ? new Intl.NumberFormat("en-US", {
                  style: "currency",
                  currency: "USD",
                }).format(value / 100)
              : new Intl.NumberFormat("en-US", {
                  maximumFractionDigits: 3,
                }).format(value)}
          </strong>
          <small>
            {/_cents$/.test(key) ? "USD · " : ""}
            {output.evidence_id} · one measured total
          </small>
        </div>
      ))}
    </div>
  );
}

export function AnswerReport({ result, renderText, onFollowUp }) {
  const p = result.presentation;
  const [selected, setSelected] = useState(0),
    [expanded, setExpanded] = useState(false);
  const display = p.display || {};
  const [showCharts, setShowCharts] = useState(
    display.chart_preference !== "table",
  );
  const rowLimit = expanded
    ? Infinity
    : Math.max(1, Number(display.table_rows) || 20);
  const outputs = result.outputs || [];
  const supports = new Set(p.supporting_evidence_ids || []);
  const tables = outputs.filter((o) => supports.has(o.evidence_id));
  const chosen = tables[Math.min(selected, Math.max(0, tables.length - 1))];
  const isPlaybook = result.report && slugs.has(result.report.slug);
  const visualReports = (result.playbook_visuals || []).filter((r) =>
    r.evidence_ids?.some((id) => supports.has(id)),
  );
  const queryCharts = (result.charts || []).filter(
    (c) => outputs[c.output_index],
  );
  const hasVisual = isPlaybook || queryCharts.length || visualReports.length;
  return (
    <div
      className="playbook-answer"
      data-output-structure="playbook-seven-sections"
      data-answer-detail={display.detail_level || "standard"}
    >
      {display.detail_level && (
        <p className="answer-profile-caption">
          {label(display.detail_level)} answer · scope and evidence retained
        </p>
      )}
      {p.fallback && (
        <p className="caption">
          Standard output layout · the full analyst narrative is retained under
          Interpretation; exact scope is stated in the answer and evidence.
        </p>
      )}
      {p.playbook_slug && (
        <div className="answer-design-tag">
          {p.contract?.title || label(p.playbook_slug)} · playbook output
        </div>
      )}
      <section className="answer-headline" aria-label="Headline">
        {renderText(p.headline)}
      </section>
      <section className="answer-scope" aria-label="Scope and metric">
        <h3>Scope and metric</h3>
        {renderText(p.scope)}
        {renderText(p.metric_basis)}
      </section>
      <section className="answer-visual" aria-label="Primary visual">
        <h3>Primary visual</h3>
        {display.chart_preference === "table" && (
          <>
            <p className="caption">
              This answer profile prefers the measured supporting table below.
            </p>
            {!!hasVisual && (
              <button
                className="answer-drill-button"
                onClick={() => setShowCharts(!showCharts)}
              >
                {showCharts ? "Collapse chart" : "Show chart as well"}
              </button>
            )}
          </>
        )}
        {showCharts && isPlaybook && (
          <Chart
            slug={result.report.slug}
            outputs={outputs}
            period={result.report.period || result.period}
          />
        )}
        {showCharts &&
          !isPlaybook &&
          visualReports.map((report, i) => (
            <div key={i} className="chat-result-chart">
              <h4>{report.title}</h4>
              <p className="caption">
                {report.scope} · {report.period.start}–{report.period.end};
                comparison {report.period.compare_start}–
                {report.period.compare_end}. {report.basis}
              </p>
              <Chart
                slug={report.slug}
                outputs={report.evidence_ids
                  .map((id) => outputs.find((o) => o.evidence_id === id))
                  .filter(Boolean)}
                period={report.period}
              />
            </div>
          ))}
        {showCharts &&
          !isPlaybook &&
          queryCharts.map((spec, i) => (
            <div className="chat-result-chart" key={i}>
              <QueryChart spec={spec} output={outputs[spec.output_index]} />
            </div>
          ))}
        {showCharts &&
          !hasVisual &&
          (p.visual_status === "metric_cards" ? (
            <MetricCards outputs={tables.length ? tables : outputs} />
          ) : (
            <p className="caption">
              {outputs.length
                ? "The supporting table is the available measured view; no unsupported chart is shown."
                : "No measured data supports a chart for this answer. The documented limitation is explained below."}
            </p>
          ))}
        {!!p.sources?.length && (
          <p className="answer-source-caption">
            Source: {p.sources.join(", ")} · Run {p.generated_at?.slice(0, 10)}.
            Exact filters and units are retained in the evidence.{" "}
            {p.limitations?.[0]}
          </p>
        )}
      </section>
      <section className="answer-values" aria-label="Supporting values">
        <h3>Supporting values</h3>
        {tables.length > 1 && (
          <label className="answer-table-picker">
            Evidence table
            <select
              aria-label="Supporting evidence table"
              value={Math.min(selected, tables.length - 1)}
              onChange={(e) => setSelected(Number(e.target.value))}
            >
              {tables.map((out, i) => (
                <option key={out.evidence_id} value={i}>
                  {out.evidence_id} · {label(out.name)}
                </option>
              ))}
            </select>
          </label>
        )}
        {chosen ? (
          <>
            <p className="caption">
              {chosen.evidence_id} · {label(chosen.name)} · monetary columns
              retain their labeled source units
            </p>
            <Table
              output={{ ...chosen, rows: chosen.rows?.slice(0, rowLimit) }}
            />
            {chosen.rows?.length > (Number(display.table_rows) || 20) && (
              <button
                className="answer-drill-button"
                onClick={() => setExpanded(!expanded)}
              >
                {expanded
                  ? "Show fewer values"
                  : `Show all ${chosen.rows.length} returned values`}
              </button>
            )}
          </>
        ) : (
          <p className="caption">
            This is a documentation-grounded answer; there is no measured result
            table.
          </p>
        )}
      </section>
      <section className="answer-interpretation" aria-label="Interpretation">
        <h3>
          Interpretation
          {p.interpretation_is_guidance ? " · playbook guidance" : ""}
        </h3>
        {renderText(p.interpretation)}
      </section>
      <section className="answer-limitations" aria-label="Limitations">
        <h3>Limitations</h3>
        {p.limitations?.length ? (
          <ul>
            {p.limitations.map((item, i) => (
              <li key={i}>{renderText(item)}</li>
            ))}
          </ul>
        ) : (
          <p>
            Review the metric basis and query scope before making a decision.
          </p>
        )}
      </section>
      {display.show_method && (
        <details className="answer-method">
          <summary>Calculation method and source queries</summary>
          {outputs
            .filter((o) => o.sql)
            .map((o, i) => (
              <div key={o.evidence_id || i}>
                <p>
                  {o.evidence_id} · {label(o.name)}
                </p>
                <pre>{o.sql}</pre>
              </div>
            ))}
          {!outputs.some((o) => o.sql) && (
            <p>
              No SQL was recorded for this answer. See source excerpts in Why
              this answer.
            </p>
          )}
        </details>
      )}
      <section className="answer-next" aria-label="Next question">
        <h3>Next question</h3>
        {p.next_questions?.map((question, i) => (
          <div key={i}>
            {renderText(question)}
            {onFollowUp && (
              <button
                onClick={() =>
                  onFollowUp(
                    question +
                      " Retain the same effective dates, filters and metric basis unless explicitly changed.",
                  )
                }
                className="answer-drill-button"
              >
                Explore this next →
              </button>
            )}
          </div>
        ))}
      </section>
    </div>
  );
}
