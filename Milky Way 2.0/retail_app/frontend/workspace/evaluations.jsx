import React, { useEffect, useState } from "react";
import { Plus, X } from "lucide-react";
import { words, plain } from "./values.js";
import { Field, LinesField, Empty, JsonDetails, Status } from "./shared.jsx";

const CONTRACTS = [
  "scope",
  "retrieval",
  "query",
  "chart",
  "presentation",
  "citations",
  "measured_values",
  "comparison",
  "playbook_contract",
  "workspace_profile",
  "workspace_skill",
  "live_answer",
];
function newCase(index) {
  return {
    id: `case-${index + 1}`,
    name: "",
    category: "retrieval",
    question: "",
    mode: "deterministic",
    contract: { type: "retrieval", inputs: { query: "" } },
    expected: { min_length: { sources: 1 } },
    requires_human_review: false,
  };
}
export function parseExpectedValue(value) {
  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
}
function RuleEditor({ value, onChange, disabled }) {
  const [path, setPath] = useState("answer"),
    [operation, setOperation] = useState("contains"),
    [expected, setExpected] = useState("");
  const rules = Object.entries(value || {})
    .filter(([op]) =>
      ["equals", "contains", "not_contains", "min_length"].includes(op),
    )
    .flatMap(([op, entries]) =>
      Object.entries(entries || {}).map(([key, v]) => ({ op, key, value: v })),
    );
  return (
    <section className="improve-rule-editor">
      <h4>Pass conditions</h4>
      <p>
        Choose an output field, a check, and its expected value. For example,
        scope.metric equals sales_cents, or answer contains a required caveat.
        Expected values stay outside model context.
      </p>
      {rules.map((rule) => (
        <div className="improve-rule" key={`${rule.op}:${rule.key}`}>
          <span>
            <b>{rule.key}</b> · {words(rule.op)} · {plain(rule.value)}
          </span>
          <button
            className="improve-button"
            type="button"
            disabled={disabled}
            aria-label={`Remove ${rule.key} ${rule.op} check`}
            onClick={() => {
              const next = structuredClone(value);
              delete next[rule.op][rule.key];
              if (!Object.keys(next[rule.op]).length) delete next[rule.op];
              onChange(next);
            }}
          >
            <X size={13} />
          </button>
        </div>
      ))}
      <div className="improve-grid">
        <Field
          label="Output field path"
          value={path}
          onChange={setPath}
          disabled={disabled}
          hint="Use a dot path such as metric (scope), session_scope.metric (live), answer or sources."
        />
        <Field
          label="Check"
          value={operation}
          onChange={setOperation}
          disabled={disabled}
          options={[
            ["equals", "Equals a value"],
            ["contains", "Contains text"],
            ["not_contains", "Does not contain text"],
            ["min_length", "Has at least this many items"],
          ]}
        />
        <Field
          label="Expected value"
          value={expected}
          onChange={setExpected}
          disabled={disabled}
          hint="Numbers and true/false are interpreted as typed values."
        />
      </div>
      <button
        className="improve-button"
        type="button"
        disabled={disabled || !path.trim() || !expected.trim()}
        onClick={() => {
          const typed = parseExpectedValue(expected);
          const next =
            operation === "contains" || operation === "not_contains"
              ? [...(value?.[operation]?.[path] || []), String(typed)]
              : operation === "min_length"
                ? Number(expected)
                : typed;
          if (
            operation === "min_length" &&
            (!Number.isFinite(next) || next < 0)
          )
            return;
          onChange({
            ...value,
            [operation]: { ...value?.[operation], [path]: next },
          });
          setExpected("");
        }}
      >
        Add pass condition
      </button>
      <Field
        label="Expected error message (for refusal tests)"
        value={value?.error_contains || ""}
        onChange={(v) => {
          const next = { ...value };
          if (v) next.error_contains = v;
          else delete next.error_contains;
          onChange(next);
        }}
        disabled={disabled}
      />
      <LinesField
        label="Required source roles"
        value={value?.required_source_roles || []}
        onChange={(v) => onChange({ ...value, required_source_roles: v })}
        disabled={disabled}
      />
    </section>
  );
}
function AdvancedObject({ label: title, value, onChange, disabled }) {
  const [text, setText] = useState(JSON.stringify(value || {}, null, 2)),
    [error, setError] = useState("");
  useEffect(
    () => setText(JSON.stringify(value || {}, null, 2)),
    [JSON.stringify(value)],
  );
  return (
    <details className="improve-details">
      <summary>{title}</summary>
      <label className="improve-field">
        <span>Structured contract fields</span>
        <textarea
          rows={10}
          value={text}
          disabled={disabled}
          onChange={(e) => setText(e.target.value)}
          onBlur={() => {
            try {
              const parsed = JSON.parse(text);
              if (
                !parsed ||
                Array.isArray(parsed) ||
                typeof parsed !== "object"
              )
                throw Error("Use an object with named fields.");
              onChange(parsed);
              setError("");
            } catch (e) {
              setError(e.message);
            }
          }}
        />
      </label>
      {error && (
        <p className="improve-error" role="alert">
          {error}
        </p>
      )}
    </details>
  );
}
export function CaseEditor({ cases = [], onChange, disabled }) {
  const [selected, setSelected] = useState(0);
  const current = cases[selected];
  function set(key, value) {
    onChange(
      cases.map((c, i) => (i === selected ? { ...c, [key]: value } : c)),
    );
  }
  function inputs(key, value) {
    set("contract", {
      ...current.contract,
      inputs: { ...current.contract?.inputs, [key]: value },
    });
  }
  const type =
    current?.contract?.type ||
    (current?.mode === "live" ? "live_answer" : "retrieval");
  return (
    <section className="improve-case-editor">
      <div className="improve-heading">
        <h3>Evaluation cases · {cases.length}</h3>
        <button
          type="button"
          className="improve-button"
          disabled={disabled}
          onClick={() => {
            onChange([
              ...cases,
              { ...newCase(cases.length), id: `case-${Date.now()}` },
            ]);
            setSelected(cases.length);
          }}
        >
          <Plus size={15} />
          Add case
        </button>
      </div>
      {!!cases.length && (
        <Field
          label="Choose a case"
          value={selected}
          options={cases.map((c, i) => [
            i,
            `${c.id}: ${c.question || c.name || "New question"}`,
          ])}
          onChange={(v) => setSelected(Number(v))}
        />
      )}
      {!current ? (
        <Empty>
          Add representative questions and explicit pass conditions. Expected
          answers are kept out of agent context.
        </Empty>
      ) : (
        <>
          <div className="improve-grid">
            <Field
              label="Case ID"
              value={current.id}
              onChange={(v) => set("id", v)}
              disabled={disabled}
            />
            <Field
              label="Case name"
              value={current.name || ""}
              onChange={(v) => set("name", v)}
              disabled={disabled}
            />
            <Field
              label="Category"
              value={current.category || "retrieval"}
              onChange={(v) => set("category", v)}
              disabled={disabled}
            />
            <Field
              label="Check type"
              value={type}
              options={CONTRACTS}
              onChange={(v) => {
                onChange(
                  cases.map((c, i) =>
                    i === selected
                      ? {
                          ...c,
                          mode: v === "live_answer" ? "live" : "deterministic",
                          contract: { type: v, inputs: {} },
                        }
                      : c,
                  ),
                );
              }}
              disabled={disabled}
            />
          </div>
          <Field
            label="Question"
            value={current.question}
            onChange={(v) => set("question", v)}
            multiline
            disabled={disabled}
          />
          {type === "retrieval" && (
            <Field
              label="Retrieval query"
              value={current.contract?.inputs?.query || ""}
              onChange={(v) => inputs("query", v)}
              disabled={disabled}
            />
          )}
          {type === "playbook_contract" && (
            <Field
              label="Playbook slug"
              value={current.contract?.inputs?.slug || "trend"}
              onChange={(v) => inputs("slug", v)}
              disabled={disabled}
            />
          )}
          {type === "citations" && (
            <Field
              label="Answer text to check"
              value={current.contract?.inputs?.answer || ""}
              onChange={(v) => inputs("answer", v)}
              multiline
              disabled={disabled}
            />
          )}
          {type === "workspace_profile" && (
            <Field
              label="Profile asset ID"
              value={current.contract?.inputs?.profile_id || "business-review"}
              onChange={(v) => inputs("profile_id", v)}
              disabled={disabled}
            />
          )}
          {type === "workspace_skill" && (
            <Field
              label="Skill asset ID"
              value={current.contract?.inputs?.skill_id || ""}
              onChange={(v) => inputs("skill_id", v)}
              disabled={disabled}
            />
          )}
          <LinesField
            label="Assets covered by this case"
            value={current.asset_ids || []}
            onChange={(v) => set("asset_ids", v)}
            disabled={disabled}
            hint="One workspace asset ID per line. The run reports changes without explicit coverage."
          />
          <AdvancedObject
            label="Advanced test inputs (scope, data or fixtures)"
            value={current.contract?.inputs || {}}
            onChange={(v) =>
              set("contract", { ...current.contract, inputs: v })
            }
            disabled={disabled}
          />
          <RuleEditor
            value={current.expected || {}}
            onChange={(v) => set("expected", v)}
            disabled={disabled}
          />
          <Field
            label="Expectation review state"
            value={current.review_status || "reviewed"}
            options={[
              ["needs_expected_result", "Expected result still needed"],
              ["reviewed", "Pass conditions reviewed"],
            ]}
            onChange={(v) => set("review_status", v)}
            disabled={disabled}
          />
          <label className="improve-checkbox">
            <input
              type="checkbox"
              checked={!!current.requires_human_review}
              onChange={(e) => set("requires_human_review", e.target.checked)}
              disabled={disabled}
            />
            Require a human to review this case
          </label>
          <Field
            label="Reviewer notes"
            value={current.notes || ""}
            onChange={(v) => set("notes", v)}
            multiline
            disabled={disabled}
          />
          <button
            type="button"
            className="improve-button danger"
            disabled={disabled}
            onClick={() => {
              onChange(cases.filter((_, i) => i !== selected));
              setSelected(0);
            }}
          >
            Remove this case
          </button>
        </>
      )}
    </section>
  );
}

function EvaluationOutput({ output = {} }) {
  const text = output.answer || output.presentation?.headline;
  const effective = output.session_scope || output.scope;
  const outputs = output.outputs || [];
  return (
    <div className="improve-output-summary">
      {text && <p>{text}</p>}
      {effective && (
        <p>
          <b>Scope:</b> {plain(effective.dates || effective)}
          {effective.metric ? " · " + words(effective.metric) : ""}
          {effective.return_basis ? " · " + words(effective.return_basis) : ""}
        </p>
      )}
      {outputs.length > 0 && (
        <p>
          <b>Measured evidence:</b>{" "}
          {outputs
            .map(
              (item) =>
                `${item.evidence_id || "output"}: ${item.row_count ?? item.rows?.length ?? 0} rows`,
            )
            .join("; ")}
        </p>
      )}
      {output.workspace?.release_id && (
        <p>
          <b>Release:</b> {output.workspace.release_id}
        </p>
      )}
    </div>
  );
}
export function EvaluationResults({ run }) {
  if (!run)
    return (
      <Empty>
        Select a run to inspect the question, evidence and pass conditions for
        each case.
      </Empty>
    );
  return (
    <div className="improve-run-detail">
      <div className="improve-heading">
        <h3>Comparison results</h3>
        <Status value={run.status} />
      </div>
      <p>
        {run.completed_cases ?? run.results?.length ?? 0} /{" "}
        {run.total_cases ?? run.results?.length ?? 0} cases ·{" "}
        {run.mode || "deterministic"} checks
      </p>
      {run.error && <p className="improve-error">{plain(run.error)}</p>}
      {run.coverage && (
        <div className="improve-callout">
          <b>Coverage of changed assets</b>
          <p>
            {run.coverage.changed_assets
              ?.map((a) => a.name || a.id)
              .join(", ") || "No custom assets changed."}
          </p>
          <p>
            {run.coverage.uncovered_assets?.length
              ? `Missing explicit case coverage: ${run.coverage.uncovered_assets.join(", ")}. Review applicability before approving.`
              : "All changed assets have declared case coverage."}
          </p>
          <p>{run.coverage.note}</p>
        </div>
      )}
      {run.summary && (
        <JsonDetails title="Run summary and gate outcome" value={run.summary} />
      )}
      {(run.results || []).map((result, i) => (
        <details className="improve-case-result" key={result.case_id || i}>
          <summary>
            <span>{result.name || result.case_id || `Case ${i + 1}`}</span>
            <Status value={result.candidate?.status || result.status} />
          </summary>
          {result.question && <p>{result.question}</p>}
          <p className="improve-muted">
            {words(result.category)} · review{" "}
            {words(result.review_status || "not_required")}
          </p>
          <div className="improve-comparison">
            {["baseline", "candidate"].map((side) => (
              <section key={side}>
                <h4>{side === "baseline" ? "Baseline" : "Candidate"}</h4>
                {!result[side] ? (
                  <p>No output recorded.</p>
                ) : (
                  <>
                    <Status value={result[side].status} />
                    <EvaluationOutput output={result[side].output} />
                    {(result[side].checks || []).map((check, n) => (
                      <div className="improve-check" key={n}>
                        <b>
                          {check.passed ? "Pass" : "Fail"} · {check.name}
                        </b>
                        <p>{plain(check.detail)}</p>
                      </div>
                    ))}
                    {!!result[side].failures?.length && (
                      <ul>
                        {result[side].failures.map((f, n) => (
                          <li key={n}>{plain(f)}</li>
                        ))}
                      </ul>
                    )}
                    <JsonDetails
                      title="Output and measured evidence"
                      value={result[side].output}
                    />
                    <JsonDetails
                      title="Source versions"
                      value={result[side].sources || []}
                    />
                  </>
                )}
              </section>
            ))}
          </div>
          {result.diff && (
            <p className="improve-muted">
              Changed:{" "}
              {Object.entries(result.diff)
                .filter(([, v]) => v)
                .map(([k]) => words(k))
                .join(" · ") || "No differences"}
            </p>
          )}
        </details>
      ))}
      {!(run.results || []).length && (
        <Empty>
          {["running", "queued"].includes(run.status)
            ? "Cases are running. Results appear as they complete."
            : "This run has no case results."}
        </Empty>
      )}
      <JsonDetails
        value={{
          id: run.id,
          baseline: run.baseline,
          candidate: run.candidate,
          limits: run.limits,
          review: run.review,
        }}
        title="Pinned versions, budgets and review record"
      />
    </div>
  );
}
