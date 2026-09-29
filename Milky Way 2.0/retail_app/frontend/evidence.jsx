import React, { useEffect, useState } from "react";
import {
  ArrowUpRight,
  Check,
  Download,
  FileText,
  AlertCircle,
} from "lucide-react";
import { fmt, title } from "./format.js";
import { Chart, QueryChart, Table } from "./chart-table.jsx";
import { AnswerReport } from "./answer-report.jsx";

export function Pill({ children, tone = "" }) {
  return <span className={"pill " + tone}>{children}</span>;
}
export function Empty({ children }) {
  return <div className="empty">{children}</div>;
}
export function Evidence({ result, onOpenDoc }) {
  const [tab, setTab] = useState("Answer"),
    [out, setOut] = useState(0);
  useEffect(() => {
    setTab("Answer");
    setOut(0);
  }, [result?.id]);
  if (!result) return null;
  const outputs = result.outputs || [],
    report = result.report;
  return (
    <div className="card evidence">
      <div className="result-head">
        <div>
          <Pill tone="green">
            {result.mode === "agent" ? "Model analysis" : "Computed playbook"}
          </Pill>
          <h2>{result.question}</h2>
        </div>
        <a
          className="icon-button"
          href={`/api/export/${result.id}`}
          title="Export analysis JSON"
          aria-label="Export analysis JSON"
        >
          <Download size={18} />
        </a>
      </div>
      <div className="scope-line">
        {result.mode === "agent" ? "Default context · " : ""}
        {result.period?.start} — {result.period?.end} · vs{" "}
        {result.period?.compare_start} — {result.period?.compare_end}
      </div>
      {report && <div className="scope-line">{report.scope}</div>}
      {result.period_basis && (
        <div className="scope-line">{result.period_basis}</div>
      )}
      <div className="tabs">
        {["Answer", "Data", "SQL", "Context", "Checks"].map((t) => (
          <button
            className={tab === t ? "active" : ""}
            key={t}
            onClick={() => setTab(t)}
          >
            {t}
          </button>
        ))}
      </div>
      {tab === "Answer" && result.presentation && (
        <AnswerReport
          result={result}
          renderText={(text) => <p className="answer">{text}</p>}
        />
      )}
      {tab === "Answer" && !result.presentation && (
        <>
          <div className="answer">{result.answer}</div>
          {report && (
            <Chart
              slug={report.slug}
              outputs={outputs}
              period={result.period}
            />
          )}
          {!report &&
            (result.charts || []).map((c, i) => (
              <QueryChart key={i} spec={c} output={outputs[c.output_index]} />
            ))}
          <div className="note">
            <AlertCircle size={17} />
            <div>
              {(result.warnings || []).map((w, i) => (
                <p key={i}>{w}</p>
              ))}
            </div>
          </div>
        </>
      )}
      {["Data", "SQL"].includes(tab) && (
        <>
          <div className="output-picker">
            <select
              aria-label="Evidence table"
              value={out}
              onChange={(e) => setOut(+e.target.value)}
            >
              {outputs.map((o, i) => (
                <option key={i} value={i}>
                  {o.evidence_id ? o.evidence_id + " · " : ""}
                  {title(o.name)}
                </option>
              ))}
            </select>
            {outputs[out] && (
              <a
                className="button secondary"
                href={`/api/export/${result.id}?format=csv&output=${out}`}
              >
                <Download size={14} /> CSV
              </a>
            )}
          </div>
          {outputs[out] ? (
            tab === "Data" ? (
              <Table output={outputs[out]} />
            ) : (
              <>
                <pre>{outputs[out].sql}</pre>
                <h4>Bound parameters</h4>
                <pre>{JSON.stringify(outputs[out].parameters, null, 2)}</pre>
              </>
            )
          ) : (
            <Empty>No query evidence was produced.</Empty>
          )}
        </>
      )}
      {tab === "Context" && (
        <>
          <p className="muted">
            Relevant reference excerpts. Open a source to inspect its full text.
          </p>
          {(result.context || []).map((c, i) => (
            <div className="source" key={i}>
              <button onClick={() => onOpenDoc(c.source)}>
                <FileText size={15} />
                {c.source_id ? c.source_id + " · " : ""}
                {c.source} : {c.line}
                <ArrowUpRight size={14} />
              </button>
              <pre>{c.text}</pre>
            </div>
          ))}
        </>
      )}
      {tab === "Checks" && (
        <>
          {result.usage && (
            <p className="small muted">
              Model usage: {fmt(result.usage.model_calls)} calls ·{" "}
              {fmt(result.usage.input_tokens)} input tokens ·{" "}
              {fmt(result.usage.output_tokens)} output tokens.
            </p>
          )}
          {(report?.checks || []).map((c, i) => (
            <div className="check" key={i}>
              {c.passed ? <Check size={18} /> : <AlertCircle size={18} />}
              <span>{c.name}</span>
              <Pill tone={c.passed ? "green" : ""}>
                {c.passed ? "Passed" : "Review"}
              </Pill>
            </div>
          ))}
          {!report && (
            <p className="note">
              SQL is read-only and time-limited. The model’s interpretation has
              not received an independent semantic audit.
            </p>
          )}
          <h3>Execution trace</h3>
          {(result.trace || []).map((t, i) => (
            <details key={i}>
              <summary>
                {i + 1}. {title(t.tool)} · {t.status}
              </summary>
              <pre>{JSON.stringify(t.detail, null, 2)}</pre>
            </details>
          ))}
          {report && (
            <>
              <h3>Data sources</h3>
              <div className="tags">
                {report.sources.map((s) => (
                  <code key={s}>{s}</code>
                ))}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
