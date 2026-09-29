import React, { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { words } from "./values.js";
import { Field, Validation, Empty, JsonDetails, Status } from "./shared.jsx";
import { api } from "../api.js";

export function FeedbackReleases({
  assets,
  releases,
  activeRelease,
  reload,
  onNotice,
  onEdit,
}) {
  const [feedback, setFeedback] = useState([]),
    [runs, setRuns] = useState([]),
    [selection, setSelection] = useState([]),
    [name, setName] = useState(""),
    [rationale, setRationale] = useState(""),
    [operator, setOperator] = useState("Local admin"),
    [evaluationRun, setEvaluationRun] = useState(""),
    [working, setWorking] = useState(false),
    [error, setError] = useState("");
  const drafts = assets.filter((a) => !a.built_in && a.draft);
  async function refresh() {
    try {
      const [f, r] = await Promise.all([
        api("/workspace/feedback"),
        api("/evaluations/runs"),
      ]);
      setFeedback(f.feedback || []);
      setRuns(r.runs || []);
    } catch (e) {
      setError(e.message);
    }
  }
  useEffect(() => {
    refresh();
  }, []);
  async function act(action) {
    setError("");
    setWorking(true);
    try {
      await action();
      await refresh();
      await reload();
    } catch (e) {
      setError(e.message);
    } finally {
      setWorking(false);
    }
  }
  return (
    <div className="improve-release-view">
      {error && (
        <div role="alert" className="improve-error">
          {error}
        </div>
      )}
      <section>
        <div className="improve-heading">
          <div>
            <h2>Feedback inbox</h2>
            <p>
              Retain the original answer and evidence, review the correction,
              then create a regression case.
            </p>
          </div>
          <button className="improve-button" onClick={refresh}>
            <RefreshCw size={15} />
            Refresh
          </button>
        </div>
        {!feedback.length && (
          <Empty>
            No feedback yet. In chat, choose “Needs improvement” on an answer
            and describe the issue.
          </Empty>
        )}
        {feedback.map((item) => (
          <article key={item.id} className="improve-feedback-card">
            <div className="improve-heading">
              <h3>
                {item.original_question ||
                  item.question ||
                  item.analysis_id ||
                  "Answer feedback"}
              </h3>
              <Status value={item.status} />
            </div>
            <p>{(item.issue_types || []).map(words).join(" · ")}</p>
            <Field
              label="Reviewer correction"
              value={item.correction || ""}
              onChange={(v) =>
                setFeedback((items) =>
                  items.map((f) =>
                    f.id === item.id ? { ...f, correction: v } : f,
                  ),
                )
              }
              multiline
            />
            <div className="improve-actions">
              <button
                className="improve-button"
                disabled={working}
                onClick={() =>
                  act(() =>
                    api(
                      `/workspace/feedback/${encodeURIComponent(item.id)}`,
                      {
                        expected_revision: item.revision,
                        status: item.status,
                        correction: item.correction,
                      },
                      { method: "PUT" },
                    ),
                  )
                }
              >
                Save correction
              </button>
              <Field
                label="Review status"
                value={item.status || "new"}
                options={["new", "reviewed", "resolved", "dismissed"]}
                onChange={(status) =>
                  act(() =>
                    api(
                      `/workspace/feedback/${encodeURIComponent(item.id)}`,
                      { status, expected_revision: item.revision },
                      { method: "PUT" },
                    ),
                  )
                }
                disabled={working}
              />
              <button
                className="improve-button"
                disabled={
                  working ||
                  item.status !== "reviewed" ||
                  !!item.linked_asset_id ||
                  !!item.linked_case_id
                }
                onClick={() =>
                  act(async () => {
                    const r = await api(
                      `/workspace/feedback/${encodeURIComponent(item.id)}/convert`,
                      { expected_revision: item.revision },
                    );
                    onNotice(
                      "Regression draft created. Add reviewed pass conditions before running it.",
                    );
                    if (r.asset) onEdit(r.asset);
                  })
                }
              >
                Create regression draft
              </button>
            </div>
            <JsonDetails
              title="Original answer, evidence and versions"
              value={{
                analysis_id: item.analysis_id,
                original_answer: item.original_answer,
                workspace: item.provenance || item.workspace,
                evidence: item.evidence,
                linked_asset_id: item.linked_asset_id,
                revision: item.revision,
              }}
            />
          </article>
        ))}
      </section>
      <section>
        <h2>Prepare a release candidate</h2>
        <p>
          Select saved drafts, create an immutable candidate, then run and
          review an evaluation against that candidate in Evaluations.
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            act(async () => {
              const r = await api("/workspace/releases", {
                asset_ids: selection,
                name,
                rationale,
              });
              setSelection([]);
              setName("");
              onNotice(
                `Candidate created: ${r.name || r.id}. Compare and review it in Evaluations before publishing.`,
              );
            });
          }}
        >
          <Field
            label="Release name"
            value={name}
            onChange={setName}
            required
          />
          <Field
            label="What changes and why?"
            value={rationale}
            onChange={setRationale}
            multiline
            required
          />
          {drafts.length ? (
            <fieldset className="improve-choices">
              <legend>Saved drafts to include</legend>
              {drafts.map((a) => (
                <label key={a.id}>
                  <input
                    type="checkbox"
                    checked={selection.includes(a.id)}
                    onChange={(e) =>
                      setSelection((s) =>
                        e.target.checked
                          ? [...s, a.id]
                          : s.filter((id) => id !== a.id),
                      )
                    }
                  />
                  {a.name} · revision {a.draft_revision ?? a.draft?.revision}
                </label>
              ))}
            </fieldset>
          ) : (
            <Empty>
              Save a custom draft in Knowledge, Skills, Answer design or
              Evaluations to prepare a release.
            </Empty>
          )}
          <button
            className="improve-button primary"
            disabled={working || !selection.length}
          >
            Create candidate
          </button>
        </form>
      </section>
      <section>
        <h2>Version history</h2>
        <p>
          Publish promotes a reviewed candidate for new answers. Rollback
          restores a prior release. Existing answer provenance remains attached
          to its original version.
        </p>
        <div className="improve-grid">
          <Field
            label="Operator label"
            value={operator}
            onChange={setOperator}
          />
          <Field
            label="Reviewed evaluation run for publication"
            value={evaluationRun}
            onChange={setEvaluationRun}
            options={[
              ["", "Choose a reviewed run"],
              ...runs.map((r) => [
                r.id,
                `${r.id.slice(0, 18)} · ${r.status} · ${r.review?.status || r.review?.decision || "unreviewed"}`,
              ]),
            ]}
          />
        </div>
        <Field
          label="Publication or rollback reason"
          value={rationale}
          onChange={setRationale}
          multiline
        />
        {!releases.length && <Empty>No releases have been created yet.</Empty>}
        {releases.map((release) => (
          <article className="improve-release-card" key={release.id}>
            <div className="improve-heading">
              <div>
                <h3>{release.name || release.id}</h3>
                <small>
                  {release.id} · {release.created_at || release.created || ""}
                </small>
              </div>
              <Status
                value={release.id === activeRelease ? "active" : release.status}
              />
            </div>
            <p>{release.rationale}</p>
            <Validation value={release.validation} />
            <JsonDetails
              title="Immutable asset versions and provenance"
              value={{
                asset_versions: release.asset_versions,
                snapshot_hash: release.snapshot_hash,
                parent_release_id: release.parent_release_id,
                evaluation_run_id: release.evaluation_run_id,
              }}
            />
            {release.id !== activeRelease && (
              <button
                className="improve-button"
                disabled={
                  working ||
                  !operator.trim() ||
                  !rationale.trim() ||
                  (release.status === "candidate" && !evaluationRun)
                }
                onClick={() =>
                  act(async () => {
                    const action =
                      release.status === "candidate" ? "publish" : "rollback";
                    await api(
                      `/workspace/releases/${encodeURIComponent(release.id)}/${action}`,
                      {
                        expected_active_release_id: activeRelease,
                        operator,
                        rationale,
                        ...(action === "publish"
                          ? { evaluation_run_id: evaluationRun }
                          : {}),
                      },
                    );
                    onNotice(
                      action === "publish"
                        ? "Release published. New questions use this version."
                        : "Previous release restored for new questions.",
                    );
                  })
                }
              >
                {release.status === "candidate"
                  ? "Publish reviewed candidate"
                  : "Restore this release"}
              </button>
            )}
          </article>
        ))}
      </section>
    </div>
  );
}
