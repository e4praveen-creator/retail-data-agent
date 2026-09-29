import React, { useEffect, useState } from "react";
import { FlaskConical, RefreshCw } from "lucide-react";
import { Field } from "./shared.jsx";
import { EvaluationResults } from "./evaluations.jsx";
import { api } from "../api.js";

export function EvaluationWorkbench({
  releases,
  activeRelease,
  suiteAssets = [],
  onNotice,
}) {
  const [suites, setSuites] = useState([]),
    [runs, setRuns] = useState([]),
    [suite, setSuite] = useState(""),
    [baseline, setBaseline] = useState(activeRelease || ""),
    [candidate, setCandidate] = useState(""),
    [mode, setMode] = useState("deterministic"),
    [count, setCount] = useState(120),
    [calls, setCalls] = useState(5),
    [tokens, setTokens] = useState(12000),
    [billable, setBillable] = useState(false),
    [run, setRun] = useState(null),
    [error, setError] = useState(""),
    [working, setWorking] = useState(false),
    [reviewer, setReviewer] = useState("Local admin"),
    [notes, setNotes] = useState("");
  async function refresh() {
    try {
      const [a, b] = await Promise.all([
        api("/evaluations/suites"),
        api("/evaluations/runs"),
      ]);
      setSuites([
        ...(a.suites || []),
        ...suiteAssets
          .filter((asset) => !(a.suites || []).some((s) => s.id === asset.id))
          .map((asset) => ({
            id: asset.id,
            name: asset.name + " · candidate draft",
            case_count: asset.content?.cases?.length || 0,
            content: asset.content,
          })),
      ]);
      setRuns(b.runs || []);
      setSuite((s) => s || a.suites?.[0]?.id || "");
    } catch (e) {
      setError(e.message);
    }
  }
  useEffect(() => {
    refresh();
  }, []);
  useEffect(() => {
    if (!baseline && activeRelease) setBaseline(activeRelease);
  }, [activeRelease]);
  useEffect(() => {
    if (!run || !["queued", "running", "cancelling"].includes(run.status))
      return;
    let stopped = false;
    const timer = setTimeout(async () => {
      try {
        const r = await api(`/evaluations/runs/${encodeURIComponent(run.id)}`);
        if (!stopped) {
          setRun(r);
          if (!["queued", "running", "cancelling"].includes(r.status))
            refresh();
        }
      } catch (e) {
        if (!stopped) setError(e.message);
      }
    }, 1000);
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [run]);
  async function act(action) {
    setWorking(true);
    setError("");
    try {
      await action();
    } catch (e) {
      setError(e.message);
    } finally {
      setWorking(false);
    }
  }
  async function start(event) {
    event.preventDefault();
    await act(async () => {
      const r = await api("/evaluations/runs", {
        suite_id: suite,
        baseline_release_id: baseline || undefined,
        candidate_release_id: candidate || undefined,
        candidate_version_ids: [],
        mode,
        max_cases: Number(count),
        max_model_calls: mode === "live" ? Number(calls) : 0,
        max_tokens: mode === "live" ? Number(tokens) : 0,
        confirm_billable: mode === "live" && billable,
      });
      setRun(r);
      await refresh();
      onNotice("Evaluation started. It uses a frozen workspace snapshot.");
    });
  }
  return (
    <section className="improve-evaluations">
      <div className="improve-heading">
        <div>
          <h2>Compare baseline and candidate</h2>
          <p>
            Deterministic checks run locally. Live evaluations send bounded
            requests to the configured model.
          </p>
        </div>
        <button className="improve-button" onClick={refresh}>
          <RefreshCw size={15} />
          Refresh
        </button>
      </div>
      {error && (
        <div role="alert" className="improve-error">
          {error}
        </div>
      )}
      <form onSubmit={start} className="improve-run-form">
        <div className="improve-grid">
          <Field
            label="Evaluation suite"
            value={suite}
            onChange={setSuite}
            required
            options={[
              ["", "Choose a suite"],
              ...suites.map((s) => [
                s.id,
                `${s.name} (${s.case_count ?? s.content?.cases?.length ?? 0} cases)`,
              ]),
            ]}
          />
          <Field
            label="Check mode"
            value={mode}
            onChange={setMode}
            options={[
              ["deterministic", "Deterministic · no model usage"],
              ["live", "Live model · billable"],
            ]}
          />
          <Field
            label="Baseline release"
            value={baseline}
            onChange={setBaseline}
            options={[
              ["", "Active release"],
              ...releases.map((r) => [r.id, r.name || r.id]),
            ]}
          />
          <Field
            label="Candidate release"
            value={candidate}
            onChange={setCandidate}
            options={[
              ["", "Active release (baseline check)"],
              ...releases.map((r) => [r.id, `${r.name || r.id} · ${r.status}`]),
            ]}
          />
          <Field
            label="Maximum cases"
            type="number"
            min={1}
            max={120}
            value={count}
            onChange={setCount}
            required
          />
        </div>
        {mode === "live" && (
          <>
            <div className="improve-grid">
              <Field
                label="Maximum model calls"
                type="number"
                min={1}
                max={40}
                value={calls}
                onChange={setCalls}
              />
              <Field
                label="Maximum tokens"
                type="number"
                min={1}
                max={200000}
                value={tokens}
                onChange={setTokens}
              />
            </div>
            <label className="improve-checkbox">
              <input
                type="checkbox"
                checked={billable}
                onChange={(e) => setBillable(e.target.checked)}
                required
              />
              I understand this run uses the configured model and may incur
              charges within these limits.
            </label>
          </>
        )}
        <button
          className="improve-button primary"
          type="submit"
          disabled={working || !suite || (mode === "live" && !billable)}
        >
          <FlaskConical size={15} />
          Run comparison
        </button>
      </form>
      <div className="improve-grid">
        <Field
          label="Inspect a previous run"
          value={run?.id || ""}
          onChange={(id) =>
            act(async () =>
              setRun(await api(`/evaluations/runs/${encodeURIComponent(id)}`)),
            )
          }
          options={[
            ["", "Select a run"],
            ...runs.map((r) => [
              r.id,
              `${r.id.slice(0, 18)} · ${r.status} · ${r.mode}`,
            ]),
          ]}
        />
        {run && ["queued", "running", "cancelling"].includes(run.status) && (
          <button
            className="improve-button danger"
            disabled={working || run.status === "cancelling"}
            onClick={() =>
              act(async () =>
                setRun(
                  await api(
                    `/evaluations/runs/${encodeURIComponent(run.id)}/cancel`,
                    {},
                  ),
                ),
              )
            }
          >
            Cancel run
          </button>
        )}
      </div>
      <EvaluationResults run={run} />
      {run && ["completed", "complete", "failed"].includes(run.status) && (
        <form className="improve-review" onSubmit={(e) => e.preventDefault()}>
          <h3>Human review</h3>
          <p>
            Inspect failed checks and unresolved claims before approving.
            Approval cannot override deterministic hard failures.
          </p>
          <div className="improve-grid">
            <Field
              label="Reviewer label"
              value={reviewer}
              onChange={setReviewer}
            />
            <Field
              label="Review notes"
              value={notes}
              onChange={setNotes}
              multiline
            />
          </div>
          <div className="improve-actions">
            {["approved", "rejected"].map((decision) => (
              <button
                key={decision}
                className="improve-button"
                disabled={working || !reviewer.trim() || !notes.trim()}
                onClick={() =>
                  act(async () => {
                    const updated = await api(
                      `/evaluations/runs/${encodeURIComponent(run.id)}/review`,
                      { reviewer, decision, notes },
                    );
                    setRun(updated);
                    onNotice(`Review recorded: ${decision}.`);
                  })
                }
              >
                {decision === "approved"
                  ? "Approve reviewed run"
                  : "Request changes"}
              </button>
            ))}
          </div>
        </form>
      )}
    </section>
  );
}
