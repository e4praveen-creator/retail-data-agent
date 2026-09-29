import React, { useEffect, useId, useState } from "react";
import { list, lines, words, label } from "./values.js";

export function Field({
  label: title,
  value = "",
  onChange,
  multiline = false,
  options,
  hint,
  required,
  type = "text",
  disabled = false,
  min,
  max,
}) {
  const id = useId();
  return (
    <label className="improve-field" htmlFor={id}>
      <span>
        {title}
        {required ? " *" : ""}
      </span>
      {options ? (
        <select
          id={id}
          value={value ?? ""}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
          required={required}
        >
          {options.map((option) => (
            <option
              key={typeof option === "string" ? option : option[0]}
              value={typeof option === "string" ? option : option[0]}
            >
              {typeof option === "string" ? words(option) : option[1]}
            </option>
          ))}
        </select>
      ) : multiline ? (
        <textarea
          id={id}
          value={value ?? ""}
          onChange={(e) => onChange(e.target.value)}
          rows={4}
          disabled={disabled}
          required={required}
        />
      ) : (
        <input
          id={id}
          value={value ?? ""}
          type={type}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled}
          required={required}
          min={min}
          max={max}
        />
      )}
      {hint && <small>{hint}</small>}
    </label>
  );
}
export function LinesField({ value, onChange, ...props }) {
  // Preserve blank lines during typing; normalize only on blur so Enter works.
  const [text, setText] = useState((value || []).join("\n"));
  useEffect(() => setText((value || []).join("\n")), [JSON.stringify(value)]);
  const id = useId();
  return (
    <label className="improve-field" htmlFor={id}>
      <span>{props.label}</span>
      <textarea
        id={id}
        rows={3}
        value={text}
        disabled={props.disabled}
        onChange={(e) => setText(e.target.value)}
        onBlur={() => onChange(lines(text))}
      />
      <small>
        {props.hint || "One item per line. Click outside this field to apply."}
      </small>
    </label>
  );
}
export function SourceRefs({ value = [], onChange, disabled }) {
  return (
    <section className="improve-source-refs">
      <h4>Source references</h4>
      <p className="improve-muted">
        Use document titles, source IDs or URLs for provenance. The app does not
        fetch these references.
      </p>
      {value.map((ref, i) => (
        <div className="improve-grid" key={i}>
          <Field
            label={`Reference ${i + 1}`}
            value={
              typeof ref === "string" ? ref : ref.source || ref.title || ""
            }
            onChange={(v) =>
              onChange(
                value.map((r, n) =>
                  n === i
                    ? typeof r === "object"
                      ? { ...r, source: v }
                      : v
                    : r,
                ),
              )
            }
            disabled={disabled}
          />
          <button
            type="button"
            className="improve-button"
            disabled={disabled}
            onClick={() => onChange(value.filter((_, n) => n !== i))}
          >
            Remove reference
          </button>
        </div>
      ))}
      <button
        type="button"
        className="improve-button"
        disabled={disabled}
        onClick={() => onChange([...value, ""])}
      >
        Add reference
      </button>
    </section>
  );
}
export function Choices({
  label: title,
  choices,
  value = [],
  onChange,
  disabled,
}) {
  return (
    <fieldset className="improve-choices">
      <legend>{title}</legend>
      {list(choices).length ? (
        list(choices).map((choice) => {
          const id = label(choice);
          return (
            <label key={id}>
              <input
                type="checkbox"
                checked={value.includes(id)}
                disabled={disabled}
                onChange={(e) =>
                  onChange(
                    e.target.checked
                      ? [...value, id]
                      : value.filter((v) => v !== id),
                  )
                }
              />
              {words(id)}
            </label>
          );
        })
      ) : (
        <p className="improve-muted">The capability catalog is loading.</p>
      )}
    </fieldset>
  );
}
export function Validation({ value }) {
  if (!value) return null;
  const errors = value.errors || [],
    warnings = value.warnings || [];
  return (
    <div
      className={`improve-validation ${value.valid ? "valid" : "invalid"}`}
      role="status"
    >
      <strong>
        {value.valid ? "Checks passed" : "Changes need attention"}
      </strong>
      {[...errors, ...warnings].map((e, i) => (
        <p key={i}>
          {e.field && <b>{words(e.field)}: </b>}
          {typeof e === "string" ? e : e.message || e.code}
        </p>
      ))}
      {value.valid && !warnings.length && (
        <p>
          These checks validate the asset. A reviewed evaluation run is still
          required for publication.
        </p>
      )}
    </div>
  );
}
export function Empty({ children }) {
  return <div className="improve-empty">{children}</div>;
}
export function JsonDetails({ value, title = "Developer details" }) {
  return (
    <details className="improve-details">
      <summary>{title}</summary>
      <pre>{JSON.stringify(value, null, 2)}</pre>
    </details>
  );
}
export function Status({ value }) {
  return (
    <span className={`improve-badge ${String(value).replaceAll(" ", "-")}`}>
      {words(value || "draft")}
    </span>
  );
}
