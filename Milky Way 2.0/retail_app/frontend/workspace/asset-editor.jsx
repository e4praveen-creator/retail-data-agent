import React, { useEffect, useState } from "react";
import { Check, Copy, LoaderCircle, ShieldCheck, X } from "lucide-react";
import {
  KINDS,
  list,
  words,
  label,
  metricUnits,
  contextExcerpt,
} from "./values.js";
import {
  Field,
  LinesField,
  SourceRefs,
  Choices,
  Validation,
  Empty,
  JsonDetails,
} from "./shared.jsx";
import { draftFrom } from "./asset-models.js";
import { CaseEditor } from "./evaluations.jsx";
import { api } from "../api.js";
import { AnswerReport } from "../answer-report.jsx";

export function AssetEditor({
  asset,
  capabilities = {},
  onSaved,
  onCancel,
  onReload,
}) {
  const [form, setForm] = useState(() => draftFrom(asset)),
    [error, setError] = useState(""),
    [working, setWorking] = useState(false),
    [validation, setValidation] = useState(null),
    [preview, setPreview] = useState(null),
    [query, setQuery] = useState(""),
    [narrow, setNarrow] = useState(false),
    [fixture, setFixture] = useState("monthly-sales"),
    [versions, setVersions] = useState([]),
    [conflict, setConflict] = useState(false);
  useEffect(() => {
    let mounted = true;
    if (asset?.id)
      api(`/workspace/assets/${encodeURIComponent(asset.id)}/versions`)
        .then((r) => {
          if (mounted) setVersions(r.versions || []);
        })
        .catch((e) => {
          if (mounted) setError(e.message);
        });
    return () => {
      mounted = false;
    };
  }, [asset?.id, asset?.published_version_id]);
  const builtIn = !!asset?.built_in;
  const content = form.content;
  function update(key, value) {
    setForm((f) => ({
      ...f,
      content: {
        ...f.content,
        [key]: value,
        ...(key === "measure" ? { units: metricUnits(value) } : {}),
        ...(key === "detail"
          ? {
              detail_level: value,
              max_table_rows: { concise: 5, standard: 10, detailed: 25 }[value],
              table_rows: { concise: 5, standard: 10, detailed: 25 }[value],
              show_method: value === "detailed",
            }
          : {}),
      },
    }));
    setValidation(null);
    setPreview(null);
  }
  const textField = (key, title, opts = {}) => (
    <Field
      label={title}
      value={content[key]}
      onChange={(value) => update(key, value)}
      disabled={builtIn}
      {...opts}
    />
  );
  const linesField = (key, title, hint) => (
    <LinesField
      label={title}
      value={content[key]}
      onChange={(value) => update(key, value)}
      hint={hint}
      disabled={builtIn}
    />
  );
  async function save(event) {
    event?.preventDefault();
    setWorking(true);
    setError("");
    try {
      const saved = await api(
        asset?.id
          ? `/workspace/assets/${encodeURIComponent(asset.id)}`
          : "/workspace/assets",
        {
          ...(asset?.id
            ? {
                expected_revision:
                  asset.draft_revision ?? asset.draft?.revision ?? 0,
              }
            : { kind: form.kind, ...(form.id ? { id: form.id } : {}) }),
          name: form.name,
          content: form.content,
        },
        asset?.id ? { method: "PUT" } : {},
      );
      onSaved(saved);
      setValidation(
        await api(
          `/workspace/assets/${encodeURIComponent(saved.id)}/validate`,
          {},
        ),
      );
    } catch (e) {
      setError(
        e.message +
          (e.status === 409
            ? " Reload this asset to review the latest version before saving again."
            : ""),
      );
      setConflict(e.status === 409);
      if (e.errors) setValidation({ valid: false, errors: e.errors });
    } finally {
      setWorking(false);
    }
  }
  async function duplicate() {
    setWorking(true);
    setError("");
    try {
      const saved = await api("/workspace/assets", {
        kind: form.kind,
        name: `${form.name} — custom`,
        content: form.content,
      });
      onSaved(saved);
    } catch (e) {
      setError(e.message);
    } finally {
      setWorking(false);
    }
  }
  async function inspect(mode) {
    setWorking(true);
    setError("");
    try {
      if (mode === "validate")
        setValidation(
          await api(
            `/workspace/assets/${encodeURIComponent(asset.id)}/validate`,
            {},
          ),
        );
      else if (form.kind === "output_profile")
        setPreview(
          await api("/workspace/output-preview", {
            profile_id: asset.id,
            fixture_id: fixture,
            asset_ids: [asset.id],
          }),
        );
      else
        setPreview(
          await api("/workspace/preview", { query, asset_ids: [asset.id] }),
        );
    } catch (e) {
      setError(e.message);
    } finally {
      setWorking(false);
    }
  }
  return (
    <section className="improve-editor" aria-label="Asset editor">
      <div className="improve-heading">
        <div>
          <p className="improve-eyebrow">
            {KINDS[form.kind]} · {asset?.id ? asset.id : "New draft"}
          </p>
          <h2>{asset?.name || "Create a draft"}</h2>
        </div>
        <button type="button" onClick={onCancel} aria-label="Close editor">
          <X size={19} />
        </button>
      </div>
      {builtIn && (
        <div className="improve-callout">
          <strong>Built-in reference</strong>
          <p>
            Duplicate this asset to create your own editable version. The
            original remains available for comparison.
          </p>
          <button
            className="improve-button"
            type="button"
            disabled={working}
            onClick={duplicate}
          >
            <Copy size={15} />
            Duplicate built-in
          </button>
        </div>
      )}
      {error && (
        <div role="alert" className="improve-error">
          {error}
          {conflict && (
            <button
              type="button"
              className="improve-button"
              disabled={working}
              onClick={async () => {
                setWorking(true);
                try {
                  const latest = await api(
                    `/workspace/assets/${encodeURIComponent(asset.id)}`,
                  );
                  setForm(draftFrom(latest));
                  onReload?.(latest);
                  setConflict(false);
                  setError("");
                  setValidation(null);
                  setPreview(null);
                } catch (e) {
                  setError(e.message);
                } finally {
                  setWorking(false);
                }
              }}
            >
              Reload latest draft
            </button>
          )}
        </div>
      )}
      <form onSubmit={save}>
        <Field
          label="Name"
          value={form.name}
          onChange={(name) => setForm({ ...form, name })}
          required
          disabled={builtIn}
        />
        {!["example"].includes(form.kind) &&
          textField("description", "What does this mean?", {
            multiline: true,
            required: true,
          })}
        {form.kind === "knowledge" && (
          <>
            {textField("body", "Source content", {
              multiline: true,
              hint: "Paste business rules, definitions, approved policies or data caveats. This becomes reference context after publication.",
            })}
            {linesField("aliases", "Terms people use")}
            <SourceRefs
              value={content.source_refs || []}
              onChange={(v) => update("source_refs", v)}
              disabled={builtIn}
            />
          </>
        )}
        {form.kind === "ontology" && (
          <>
            {textField("concept_type", "Concept type", {
              options: [
                ["concept", "Documentary concept"],
                ["metric", "Metric with approved calculation"],
                ["entity", "Entity / dimension"],
                ["relationship", "Relationship"],
              ],
            })}
            {linesField("aliases", "Aliases and everyday terms")}
            {content.concept_type === "metric" && (
              <div className="improve-grid">
                {textField("measure", "Which approved measure supports it?", {
                  options: [
                    ["", "Choose a measure"],
                    ...list(capabilities.measures).map((m) => [
                      label(m),
                      words(label(m)),
                    ]),
                  ],
                })}
                <Field
                  label="Units"
                  value={metricUnits(content.measure)}
                  onChange={() => {}}
                  disabled
                  hint="Set by the approved calculation: cents, cents/order, cents/unit, percent, orders, customers or units. Display conversions are applied in the answer."
                />
                {textField("date_basis", "Date basis", {
                  options: [["sale_date", "Original sale date"]],
                })}
                {textField("return_basis", "Returns basis", {
                  options: [
                    ["before_returns", "Before returns"],
                    ["sales_cohort", "After linked returns, by original sale"],
                    ["return_date", "By return date — requires data support"],
                  ],
                })}
              </div>
            )}
            {content.concept_type === "entity" &&
              textField("field", "Which data field supports it?", {
                options: [
                  ["", "Choose a field"],
                  ...list(capabilities.dimensions).map((v) => [
                    label(v),
                    words(label(v)),
                  ]),
                ],
              })}
            {content.concept_type === "relationship" && (
              <div className="improve-grid">
                {textField("from_id", "From concept ID")}
                {textField("to_id", "To concept ID")}
              </div>
            )}
            <SourceRefs
              value={content.source_refs || []}
              onChange={(v) => update("source_refs", v)}
              disabled={builtIn}
            />
          </>
        )}
        {form.kind === "skill" && (
          <>
            {linesField(
              "trigger_examples",
              "Example questions that should select this skill",
            )}
            {textField(
              "method",
              "How should the agent carry out this method?",
              { multiline: true, required: true },
            )}
            {textField("handler", "Execution method", {
              options: [
                ["method_only", "Agent method using existing tools"],
                ...list(capabilities.handlers)
                  .filter((h) => label(h) !== "method_only")
                  .map((h) => [label(h), words(label(h))]),
              ],
              hint: "A new calculation or tool requires developer implementation. This form cannot upload executable code.",
            })}
            <Choices
              label="Approved tools"
              choices={capabilities.tools}
              value={content.approved_tools}
              onChange={(v) => update("approved_tools", v)}
              disabled={builtIn}
            />
            {linesField("required_concepts", "Required concept IDs")}
            {textField("output_profile_id", "Answer profile", {
              options: list(capabilities.profiles).map((p) => [
                label(p),
                typeof p === "object" ? p.name || words(label(p)) : words(p),
              ]),
            })}
            {linesField(
              "allowed_filters",
              "Allowed scope fields",
              "Use field names from the workspace capability catalog, one per line.",
            )}
            {linesField("caveats", "Limitations and missing-data behavior")}
          </>
        )}
        {form.kind === "output_profile" && (
          <>
            <div className="improve-grid">
              {textField("detail", "Answer detail", {
                options: [
                  ["concise", "Quick answer"],
                  ["standard", "Business review"],
                  ["detailed", "Analyst detail"],
                ],
              })}
              {textField("chart_preference", "Preferred visual", {
                options: [
                  ["auto", "Choose for the data"],
                  ["table", "Prefer a table"],
                  ["chart", "Prefer a chart"],
                ],
              })}
            </div>
            {linesField(
              "required_sections",
              "What should a good answer include?",
            )}
            <div className="improve-callout">
              <ShieldCheck size={16} /> Scope, evidence, units and material
              limitations remain visible in every profile.
            </div>
          </>
        )}
        {form.kind === "example" && (
          <>
            {textField("question", "User question", {
              multiline: true,
              required: true,
            })}
            {textField("answer", "Example answer", {
              multiline: true,
              required: true,
            })}
            {textField("quality", "Example type", {
              options: [
                ["good", "Good example to follow"],
                ["bad", "Weak answer to avoid"],
              ],
            })}
            {textField("notes", "Why is this good or bad?", {
              multiline: true,
            })}
            {textField("output_profile_id", "Answer profile", {
              options: [
                ["", "Any profile"],
                ...list(capabilities.profiles).map((p) => [
                  label(p),
                  words(label(p)),
                ]),
              ],
            })}
          </>
        )}
        {form.kind === "evaluation_suite" && (
          <CaseEditor
            cases={content.cases || []}
            onChange={(cases) => update("cases", cases)}
            disabled={builtIn}
          />
        )}
        <div className="improve-actions">
          {!builtIn && (
            <button
              className="improve-button primary"
              type="submit"
              disabled={working}
            >
              {working ? (
                <LoaderCircle className="spin" size={15} />
              ) : (
                <Check size={15} />
              )}
              Save draft
            </button>
          )}
          {asset?.id && (
            <button
              className="improve-button"
              type="button"
              disabled={working}
              onClick={() => inspect("validate")}
            >
              Validate saved version
            </button>
          )}
          <button className="improve-button" type="button" onClick={onCancel}>
            Close
          </button>
        </div>
      </form>
      <Validation value={validation} />
      {asset?.id && !["example", "evaluation_suite"].includes(form.kind) && (
        <div className="improve-preview">
          <h3>
            {form.kind === "output_profile"
              ? "Measured answer preview"
              : "Retrieval and selection preview"}
          </h3>
          <p>
            Preview the saved draft. Save your latest edits first. The active
            release is unchanged.
          </p>
          {form.kind !== "output_profile" ? (
            <Field label="Try a question" value={query} onChange={setQuery} />
          ) : (
            <Field
              label="Measured preview fixture"
              value={fixture}
              onChange={setFixture}
              options={[
                ["monthly-sales", "Monthly sales · January–March 2025"],
                ["channel-sales", "Channel sales · January–March 2025"],
              ]}
            />
          )}
          <div className="improve-actions">
            <button
              className="improve-button"
              disabled={
                working || (form.kind !== "output_profile" && !query.trim())
              }
              onClick={() => inspect("preview")}
            >
              Preview saved draft
            </button>
            {form.kind === "output_profile" && (
              <label className="improve-checkbox">
                <input
                  type="checkbox"
                  checked={narrow}
                  onChange={(e) => setNarrow(e.target.checked)}
                />
                Narrow screen preview
              </label>
            )}
          </div>
          {preview && (
            <div className={narrow ? "improve-narrow-preview" : ""}>
              {preview.result?.presentation ? (
                <AnswerReport
                  result={preview.result}
                  renderText={(t) => <p>{t}</p>}
                  onFollowUp={setQuery}
                />
              ) : preview.presentation ? (
                <AnswerReport
                  result={preview}
                  renderText={(t) => <p>{t}</p>}
                  onFollowUp={setQuery}
                />
              ) : (
                <>
                  {(preview.results || []).map((r, i) => (
                    <article className="improve-retrieved" key={i}>
                      <h4>
                        {r.name ||
                          r.title ||
                          r.source ||
                          r.asset_id ||
                          `Source ${i + 1}`}
                      </h4>
                      <p>{contextExcerpt(r.text || r.snippet || r.content)}</p>
                      <small>{r.source_id || r.version_id}</small>
                    </article>
                  ))}
                  {!preview.results?.length && (
                    <Empty>
                      No source matched this question. Try the exact term or add
                      a relevant alias.
                    </Empty>
                  )}
                </>
              )}
              <Validation value={preview.validation} />
              <JsonDetails
                value={preview}
                title="Preview provenance and checks"
              />
            </div>
          )}
        </div>
      )}
      {versions.length > 0 && (
        <details className="improve-details">
          <summary>
            Immutable asset history · {versions.length} versions
          </summary>
          {versions.map((version) => (
            <div className="improve-retrieved" key={version.id}>
              <b>{version.id}</b>
              <p>
                {version.name} · {version.created}
              </p>
              <JsonDetails value={version.content} title="Version content" />
            </div>
          ))}
        </details>
      )}
      <JsonDetails
        value={{
          asset_id: asset?.id,
          published_version_id: asset?.published_version_id,
          draft_revision: asset?.draft_revision,
          content: form.content,
        }}
        title="Asset fields and version details"
      />
    </section>
  );
}
