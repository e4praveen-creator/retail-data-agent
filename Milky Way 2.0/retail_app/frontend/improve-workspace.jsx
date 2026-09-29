import React, { useEffect, useState } from "react";
import {
  ArrowLeft,
  BookOpen,
  Copy,
  FlaskConical,
  History,
  Layers,
  LoaderCircle,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  X,
} from "lucide-react";
import { KINDS } from "./workspace/values.js";
import { Field, Empty, Status } from "./workspace/shared.jsx";
import { newContent } from "./workspace/asset-models.js";
import { AssetEditor } from "./workspace/asset-editor.jsx";
import { EvaluationWorkbench } from "./workspace/evaluation-workbench.jsx";
import { FeedbackReleases } from "./workspace/feedback-releases.jsx";
import { api } from "./api.js";

export const SECTIONS = [
  ["knowledge", "Knowledge & ontology", BookOpen],
  ["skill", "Skills", Layers],
  ["output_profile", "Answer design & examples", Copy],
  ["evaluation_suite", "Evaluations", FlaskConical],
  ["releases", "Feedback & releases", History],
];
export function ImproveWorkspace({ onBack, onChanged }) {
  const [section, setSection] = useState("knowledge"),
    [kind, setKind] = useState("knowledge"),
    [assets, setAssets] = useState([]),
    [capabilities, setCapabilities] = useState({}),
    [releases, setReleases] = useState([]),
    [activeRelease, setActiveRelease] = useState(null),
    [search, setSearch] = useState(""),
    [editor, setEditor] = useState(null),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  async function reload() {
    setError("");
    try {
      const [a, c, r] = await Promise.all([
        api("/workspace/assets"),
        api("/workspace/capabilities"),
        api("/workspace/releases"),
      ]);
      setAssets(a.assets || []);
      setCapabilities(c);
      setReleases(r.releases || []);
      setActiveRelease(r.active_release_id);
      onChanged?.();
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    reload();
  }, []);
  function select(value) {
    setSection(value);
    setKind(value);
    setEditor(null);
    setSearch("");
    setNotice("");
  }
  const visibleKinds =
    section === "knowledge"
      ? ["knowledge", "ontology"]
      : section === "output_profile"
        ? ["output_profile", "example"]
        : [section];
  const filtered = assets.filter(
    (a) =>
      visibleKinds.includes(a.kind) &&
      (a.name + " " + a.id + " " + (a.content?.description || ""))
        .toLowerCase()
        .includes(search.toLowerCase()),
  );
  async function saved(asset) {
    setEditor(asset);
    await reload();
    setNotice(
      "Draft saved. Validate, preview, then prepare a release candidate.",
    );
  }
  function edit(asset) {
    setSection(
      asset.kind === "ontology"
        ? "knowledge"
        : asset.kind === "example"
          ? "output_profile"
          : asset.kind,
    );
    setKind(asset.kind);
    setEditor(asset);
  }
  return (
    <main className="improve-workspace">
      <header className="improve-topbar">
        <button className="improve-button" onClick={onBack}>
          <ArrowLeft size={16} />
          Back to chat
        </button>
        <div className="improve-admin">
          <ShieldCheck size={16} />
          <span>
            Local admin workspace
            <small>Trusted local operator · no multi-user roles</small>
          </span>
        </div>
        <a
          className="improve-button"
          href="/guide"
          target="_blank"
          rel="noopener noreferrer"
        >
          User & admin guide
        </a>
        <span className="improve-active-release">
          Active version: {activeRelease?.slice(0, 20) || "Loading…"}
        </span>
      </header>
      <div className="improve-layout">
        <nav className="improve-nav" aria-label="Improve workspace sections">
          <div>
            <p className="improve-eyebrow">Milky Way 2.0</p>
            <h1>Improve workspace</h1>
            <p>Draft → Preview → Test → Publish</p>
          </div>
          {SECTIONS.map(([id, title, Icon]) => (
            <button
              key={id}
              aria-current={section === id ? "page" : undefined}
              onClick={() => select(id)}
            >
              <Icon size={18} />
              {title}
            </button>
          ))}
          <details className="improve-help">
            <summary>How to make an improvement</summary>
            <ol>
              <li>Create or duplicate an asset.</li>
              <li>Save, validate and preview the draft.</li>
              <li>Create a candidate in Feedback & releases.</li>
              <li>Compare it to the active release in Evaluations.</li>
              <li>Review results, then publish with that run.</li>
              <li>Ask a new question and inspect “Why this answer?”.</li>
            </ol>
          </details>
        </nav>
        <div className="improve-content">
          {error && (
            <div className="improve-error" role="alert">
              {error}
              <button className="improve-button" onClick={reload}>
                Retry loading
              </button>
            </div>
          )}
          {notice && (
            <div className="improve-notice" role="status">
              {notice}
              <button aria-label="Dismiss notice" onClick={() => setNotice("")}>
                <X size={16} />
              </button>
            </div>
          )}
          {loading ? (
            <Empty>
              <LoaderCircle className="spin" size={20} />
              Loading the versioned workspace…
            </Empty>
          ) : editor ? (
            <AssetEditor
              key={`${editor.id || "new"}:${editor.kind}`}
              asset={editor}
              capabilities={capabilities}
              onSaved={saved}
              onReload={async (latest) => {
                setEditor(latest);
                await reload();
                setNotice(
                  "Latest saved draft loaded. Reapply your changes to this version.",
                );
              }}
              onCancel={() => setEditor(null)}
            />
          ) : section === "releases" ? (
            <FeedbackReleases
              assets={assets}
              releases={releases}
              activeRelease={activeRelease}
              reload={reload}
              onNotice={setNotice}
              onEdit={edit}
            />
          ) : (
            <>
              <div className="improve-heading">
                <div>
                  <h2>{SECTIONS.find(([id]) => id === section)?.[1]}</h2>
                  <p>
                    {section === "knowledge"
                      ? "Give the agent business meaning, approved mappings and trusted source context."
                      : section === "skill"
                        ? "Define reusable methods and choose the existing tools they may use."
                        : section === "output_profile"
                          ? "Set response detail and teach answer quality with examples."
                          : "Author isolated tests, compare versions and review evidence."}
                  </p>
                </div>
                <button className="improve-button" onClick={reload}>
                  <RefreshCw size={15} />
                  Refresh
                </button>
              </div>
              <div className="improve-toolbar">
                <div className="improve-search">
                  <Search size={16} />
                  <input
                    aria-label="Search workspace assets"
                    placeholder="Search assets"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </div>
                {visibleKinds.length > 1 && (
                  <Field
                    label="Create type"
                    value={kind}
                    onChange={setKind}
                    options={visibleKinds.map((v) => [v, KINDS[v]])}
                  />
                )}
                <button
                  className="improve-button primary"
                  onClick={() => setEditor({ kind, content: newContent(kind) })}
                >
                  <Plus size={16} />
                  New {KINDS[kind]?.toLowerCase() || "draft"}
                </button>
              </div>
              <div className="improve-asset-list">
                {filtered.map((asset) => (
                  <button
                    className="improve-asset-card"
                    key={asset.id}
                    onClick={() => setEditor(asset)}
                  >
                    <div>
                      <small>
                        {KINDS[asset.kind]}
                        {asset.built_in ? " · built-in" : ""}
                      </small>
                      <h3>{asset.name}</h3>
                      <p>
                        {asset.draft?.content?.description ||
                          asset.content?.description ||
                          asset.content?.question ||
                          "Open to inspect this asset and its versions."}
                      </p>
                    </div>
                    <Status
                      value={
                        asset.status || (asset.draft ? "draft" : "published")
                      }
                    />
                    <span>
                      {asset.built_in ? "View / duplicate" : "Edit draft"} →
                    </span>
                  </button>
                ))}
                {!filtered.length && (
                  <Empty>
                    {search
                      ? "No matching assets. Try a shorter search or create a draft."
                      : "Create your first draft using the button above."}
                  </Empty>
                )}
              </div>
              {section === "evaluation_suite" && (
                <EvaluationWorkbench
                  releases={releases}
                  activeRelease={activeRelease}
                  suiteAssets={assets.filter(
                    (a) => a.kind === "evaluation_suite",
                  )}
                  onNotice={setNotice}
                />
              )}
            </>
          )}
        </div>
      </div>
    </main>
  );
}

// Public exports preserve imports used by developer tools and regression tests.
export { AssetEditor } from "./workspace/asset-editor.jsx";
export {
  CaseEditor,
  EvaluationResults,
  parseExpectedValue,
} from "./workspace/evaluations.jsx";
export { Field, Validation, Status } from "./workspace/shared.jsx";
export { newContent, draftFrom } from "./workspace/asset-models.js";
export {
  ISSUE_TYPES,
  metricUnits,
  contextExcerpt,
  validateChatDates,
  filterValue,
} from "./workspace/values.js";
export {
  WhyThisAnswer,
  FeedbackForm,
  ScopeEditor,
} from "./answer-controls.jsx";
