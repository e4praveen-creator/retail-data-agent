import React, { useState } from "react";
import { Plus, X } from "lucide-react";
import {
  ISSUE_TYPES,
  words,
  plain,
  contextExcerpt,
  validateChatDates,
  filterValue,
} from "./workspace/values.js";
import { Field, Choices, JsonDetails } from "./workspace/shared.jsx";

export function WhyThisAnswer({ result }) {
  const workspace = result?.workspace || result?.workspace_provenance || {};
  const scope =
    result?.session_scope ||
    result?.scope ||
    result?.effective_scope ||
    result?.period ||
    {};
  return (
    <div className="why-answer-panel">
      <h3>Why this answer?</h3>
      <p>
        The answer keeps the scope, context and workspace version captured when
        it was produced.
      </p>
      <dl>
        <dt>Workspace release</dt>
        <dd>{workspace.release_id || "Not recorded for this older answer"}</dd>
        <dt>Answer profile</dt>
        <dd>
          {plain(
            workspace.output_profile?.name ||
              workspace.output_profile?.id ||
              workspace.output_profile ||
              workspace.output_profile_id ||
              "Default",
          )}
        </dd>
        <dt>Selected skills</dt>
        <dd>
          {(
            workspace.selected_skills ||
            Object.keys(workspace.skill_versions || {})
          )
            .map((s) => (typeof s === "string" ? s : s.name || s.id))
            .join(", ") || "No additional skill recorded"}
        </dd>
      </dl>
      <details open>
        <summary>Effective scope and metric</summary>
        <dl>
          {Object.entries(scope.dates || scope)
            .filter(([, value]) => typeof value !== "object")
            .map(([key, value]) => (
              <React.Fragment key={key}>
                <dt>{words(key)}</dt>
                <dd>{plain(value)}</dd>
              </React.Fragment>
            ))}
        </dl>
        {scope.metric && (
          <p>
            Metric: {words(scope.metric)} · {words(scope.return_basis)}
          </p>
        )}
        {!!scope.filters?.length && (
          <ul>
            {scope.filters.map((f, i) => (
              <li key={i}>
                {words(f.field)} {words(f.op)} {f.values?.join(", ")}
              </li>
            ))}
          </ul>
        )}
      </details>
      <details>
        <summary>
          Retrieved definitions and source excerpts ·{" "}
          {(result?.context || []).length}
        </summary>
        {(result?.context || []).map((source, i) => (
          <article className="improve-retrieved" key={i}>
            <h4>
              {source.source_id} ·{" "}
              {source.title || source.source || source.name}
            </h4>
            <p>
              {contextExcerpt(source.text || source.snippet || source.content)}
            </p>
            <small>
              {source.role || source.source_role} {source.version_id}
            </small>
          </article>
        ))}
        {!result?.context?.length && (
          <p>No source excerpts recorded for this answer.</p>
        )}
      </details>
      <details>
        <summary>Measured evidence · {(result?.outputs || []).length}</summary>
        <ul>
          {(result?.outputs || []).map((o, i) => (
            <li key={i}>
              <b>{o.evidence_id || `Output ${i + 1}`}</b> {o.name || o.title} ·{" "}
              {o.row_count ?? o.rows?.length ?? 0} rows{" "}
              {o.truncated ? "(truncated)" : ""}
            </li>
          ))}
        </ul>
        <p>
          Open Evidence & SQL to inspect the actual query and returned values.
        </p>
      </details>
      <JsonDetails
        title="Version IDs, context provenance and trace details"
        value={{
          asset_versions: workspace.asset_versions,
          context_sources: workspace.context_sources,
          workspace,
          scope,
          analysis_id: result?.id,
        }}
      />
    </div>
  );
}

export function FeedbackForm({ onSubmit, onCancel }) {
  const [issues, setIssues] = useState([]),
    [correction, setCorrection] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  return (
    <form
      className="answer-feedback-form"
      onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        setError("");
        try {
          if (await onSubmit({ issue_types: issues, correction })) onCancel();
          else setError("Feedback was not saved. Please try again.");
        } catch (err) {
          setError(err.message);
        } finally {
          setBusy(false);
        }
      }}
    >
      <h3>What needs improvement?</h3>
      <Choices
        label="Choose the issues"
        choices={ISSUE_TYPES}
        value={issues}
        onChange={setIssues}
      />
      <Field
        label="What should the answer do differently?"
        value={correction}
        onChange={setCorrection}
        multiline
        required
        hint="Include the intended scope, definition or correction. This is saved for admin review."
      />
      {error && (
        <p className="improve-error" role="alert">
          {error}
        </p>
      )}
      <div className="improve-actions">
        <button
          className="improve-button primary"
          disabled={busy || !issues.length || !correction.trim()}
        >
          Save for review
        </button>
        <button className="improve-button" type="button" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}

export function ScopeEditor({ scope = {}, capabilities = {}, busy, onSave }) {
  const [draft, setDraft] = useState(() => ({
    dates: { ...(scope.dates || scope) },
    metric: scope.metric || "sales_cents",
    return_basis: scope.return_basis || "before_returns",
    filters: structuredClone(scope.filters || []),
  }));
  const [error, setError] = useState("");
  const fields = Object.keys(capabilities.filters || {});
  function filter(index, key, value) {
    setDraft((d) => ({
      ...d,
      filters: d.filters.map((f, i) =>
        i === index
          ? {
              ...f,
              [key]: value,
              ...(key === "field" ? { op: "eq", raw: "", values: [] } : {}),
            }
          : f,
      ),
    }));
  }
  return (
    <form
      className="improve-scope-editor"
      onSubmit={async (e) => {
        e.preventDefault();
        setError("");
        try {
          validateChatDates(draft.dates);
          const filters = draft.filters.map((f) => {
            const values =
              f.raw === undefined
                ? f.values
                : f.raw
                    .split(",")
                    .map((v) => v.trim())
                    .filter(Boolean);
            const type = capabilities.filters?.[f.field]?.type;
            return {
              field: f.field,
              op: f.op,
              values: values.map((v) => filterValue(v, type)),
            };
          });
          await onSave({ ...draft, filters, reset_filters: true });
        } catch (err) {
          setError(err.message);
        }
      }}
    >
      <p>
        Use a validated scope for the next question. Changing a saved chat marks
        affected investigation tests stale.
      </p>
      <div className="chat-date-grid">
        {[
          ["start", "Current start"],
          ["end", "Current end"],
          ["compare_start", "Comparison start"],
          ["compare_end", "Comparison end"],
        ].map(([key, title]) => (
          <Field
            key={key}
            type="date"
            label={title}
            value={draft.dates[key] || ""}
            onChange={(value) =>
              setDraft({
                ...draft,
                dates: { ...draft.dates, [key]: value || null },
              })
            }
            min="2024-01-01"
            max="2025-12-31"
            required={key === "start" || key === "end"}
          />
        ))}
      </div>
      <div className="improve-grid">
        <Field
          label="Metric"
          value={draft.metric}
          options={(capabilities.measures || ["sales_cents"]).map((v) => [
            v,
            words(v),
          ])}
          onChange={(metric) => setDraft({ ...draft, metric })}
        />
        <Field
          label="Returns basis"
          value={draft.return_basis}
          options={Object.entries(
            capabilities.return_bases || {
              before_returns: "Before returns",
              sales_cohort: "After linked returns",
              return_date: "Return date",
            },
          )}
          onChange={(return_basis) => setDraft({ ...draft, return_basis })}
        />
      </div>
      <h3>Filters</h3>
      {draft.filters.map((f, i) => (
        <div className="scope-filter-row" key={i}>
          <Field
            label="Field"
            value={f.field}
            options={fields.map((v) => [v, words(v)])}
            onChange={(v) => filter(i, "field", v)}
          />
          <Field
            label="Condition"
            value={f.op}
            options={
              capabilities.filters?.[f.field]?.operators || [
                "eq",
                "ne",
                "in",
                "not_in",
              ]
            }
            onChange={(v) => filter(i, "op", v)}
          />
          <Field
            label="Values"
            value={f.raw ?? f.values?.join(", ")}
            onChange={(v) => filter(i, "raw", v)}
            hint="Separate multiple values with commas."
          />
          <button
            className="improve-button"
            type="button"
            aria-label={`Remove filter ${i + 1}`}
            onClick={() =>
              setDraft({
                ...draft,
                filters: draft.filters.filter((_, n) => n !== i),
              })
            }
          >
            <X size={15} />
          </button>
        </div>
      ))}
      <button
        className="improve-button"
        type="button"
        disabled={!fields.length}
        onClick={() =>
          setDraft({
            ...draft,
            filters: [
              ...draft.filters,
              { field: fields[0], op: "eq", values: [], raw: "" },
            ],
          })
        }
      >
        <Plus size={14} />
        Add filter
      </button>
      {error && (
        <p role="alert" className="improve-error">
          {error}
        </p>
      )}
      <div className="improve-actions">
        <button className="improve-button primary" disabled={busy}>
          Apply scope
        </button>
      </div>
    </form>
  );
}
