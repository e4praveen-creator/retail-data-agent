import { api } from "./api.js";
import React, { useState, useEffect } from "react";
import { createRoot } from "react-dom/client";
import {
  LayoutDashboard,
  MessageSquare,
  BookOpen,
  Database,
  Library,
  ShieldCheck,
  ArrowUpRight,
  ArrowRight,
  Send,
  Plus,
  Check,
  ChevronRight,
  Search,
  Download,
  X,
  Triangle,
  LoaderCircle,
  Clock,
  Code,
  FileText,
  AlertCircle,
  Settings2,
} from "lucide-react";
import { PlaybookChart, StructuredQueryChart } from "./playbook-charts.jsx";
import { AnswerReport } from "./answer-report.jsx";
const GREEN = "#171717",
  GRAY = "#737373",
  RED = "#a8442f";
const fmt = (v, kind = "number") =>
  v == null
    ? "—"
    : kind === "money"
      ? new Intl.NumberFormat("en-US", {
          style: "currency",
          currency: "USD",
          maximumFractionDigits: 0,
        }).format(v / 100)
      : kind === "pct"
        ? `${v.toFixed(1)}%`
        : new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(
            v,
          );
const compact = (v) =>
  new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(v);
const title = (s) =>
  s.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());

const defaultScope = {
  start: "2025-01-05",
  end: "2025-12-27",
  compare_start: "2024-01-07",
  compare_end: "2024-12-28",
};
function Pill({ children, tone = "" }) {
  return <span className={"pill " + tone}>{children}</span>;
}
function Empty({ children }) {
  return <div className="empty">{children}</div>;
}
function Chart(props) {
  return <PlaybookChart {...props} />;
}
function QueryChart(props) {
  return <StructuredQueryChart {...props} />;
}
function Table({ output }) {
  const [page, setPage] = useState(0);
  useEffect(() => setPage(0), [output]);
  const rows = output?.rows || [],
    keys = rows.length ? Object.keys(rows[0]) : [];
  return (
    <>
      <div className="table-meta">
        <span>
          {fmt(output?.row_count)} rows{" "}
          {output?.truncated ? "· result truncated" : ""} · currency columns
          ending in cents are stored in US cents
        </span>
        <span>
          <button disabled={page === 0} onClick={() => setPage(page - 1)}>
            Previous
          </button>{" "}
          {page + 1} / {Math.max(1, Math.ceil(rows.length / 25))}{" "}
          <button
            disabled={(page + 1) * 25 >= rows.length}
            onClick={() => setPage(page + 1)}
          >
            Next
          </button>
        </span>
      </div>
      <div className="table-scroll">
        <table aria-label={output?.name ? title(output.name) : "Query results"}>
          <thead>
            <tr>
              {keys.map((k) => (
                <th key={k} scope="col">
                  {title(k)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.slice(page * 25, (page + 1) * 25).map((r, i) => (
              <tr key={i}>
                {keys.map((k) => (
                  <td key={k}>
                    {r[k] == null
                      ? "—"
                      : typeof r[k] === "number"
                        ? fmt(r[k])
                        : String(r[k])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!rows.length && <Empty>No rows returned.</Empty>}
    </>
  );
}
function Evidence({ result, onOpenDoc }) {
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
function ColumnProfile({ table, columns }) {
  const [column, setColumn] = useState(columns[0]?.column_name || ""),
    [profile, setProfile] = useState(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    setColumn(columns[0]?.column_name || "");
    setProfile(null);
    setError("");
  }, [table]);
  return (
    <div className="column-profile">
      <h3>Explore a column</h3>
      <div className="output-picker">
        <select
          aria-label="Column to profile"
          value={column}
          onChange={(e) => setColumn(e.target.value)}
        >
          {columns.map((c) => (
            <option key={c.column_name}>{c.column_name}</option>
          ))}
        </select>
        <button
          className="button secondary"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            setError("");
            try {
              setProfile(await api("/profile/" + table + "/" + column));
            } catch (e) {
              setError(e.message);
            } finally {
              setBusy(false);
            }
          }}
        >
          {busy ? "Profiling…" : "Run EDA profile"}
        </button>
      </div>
      {error && <p>{error}</p>}
      {profile && (
        <>
          <p className="small muted">{profile.scope}</p>
          <pre>{JSON.stringify(profile, null, 2)}</pre>
        </>
      )}
    </div>
  );
}
function App() {
  const [status, setStatus] = useState(null),
    [page, setPage] = useState("Overview"),
    [scope, setScope] = useState(defaultScope),
    [applied, setApplied] = useState(defaultScope),
    [overview, setOverview] = useState(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(""),
    [question, setQuestion] = useState(""),
    [result, setResult] = useState(null),
    [suggest, setSuggest] = useState(null),
    [history, setHistory] = useState([]),
    [docs, setDocs] = useState(null),
    [query, setQuery] = useState(""),
    [doc, setDoc] = useState(null),
    [catalog, setCatalog] = useState(null),
    [inspected, setInspected] = useState(null),
    [quality, setQuality] = useState(null),
    [mem, setMem] = useState([]),
    [note, setNote] = useState(""),
    [source, setSource] = useState(""),
    [search, setSearch] = useState("");
  const loadOverview = async () => {
    setError("");
    setOverview(null);
    try {
      setOverview(await api("/overview?" + new URLSearchParams(applied)));
    } catch (e) {
      setError(e.message);
    }
  };
  useEffect(() => {
    api("/status")
      .then(setStatus)
      .catch((e) => setError(e.message));
    api("/history")
      .then(setHistory)
      .catch(() => {});
  }, []);
  useEffect(() => {
    loadOverview();
  }, [applied]);
  useEffect(() => {
    if (page === "Knowledge") {
      api("/context")
        .then(setDocs)
        .catch((e) => setError(e.message));
      api("/memory")
        .then(setMem)
        .catch(() => {});
    }
    if (page === "Dataset")
      api("/catalog")
        .then(setCatalog)
        .catch((e) => setError(e.message));
    if (page === "Readiness")
      api("/quality")
        .then(setQuality)
        .catch((e) => setError(e.message));
  }, [page]);
  async function openDoc(path) {
    try {
      const r = await fetch("/api/document?" + new URLSearchParams({ path }));
      if (!r.ok) throw Error("Cannot open source");
      setDoc({ path, text: await r.text() });
    } catch (e) {
      setError(e.message);
    }
  }
  async function run(body, isQuestion = false) {
    setError("");
    setSuggest(null);
    setBusy("Loading context and querying the warehouse");
    setPage("Analysis");
    try {
      let j = await api(isQuestion ? "/ask" : "/analyze", {
        ...applied,
        ...body,
      });
      if (j.mode === "suggestions") {
        setSuggest(j);
        return;
      }
      const started = Date.now();
      while (true) {
        await new Promise((r) => setTimeout(r, 700));
        const s = await api("/jobs/" + j.job_id);
        setBusy(s.message);
        if (s.status === "error") throw Error(s.error);
        if (s.status === "complete") {
          setResult(s.result);
          setHistory(await api("/history"));
          break;
        }
        if (Date.now() - started > 15 * 60 * 1000)
          throw Error(
            "This run is taking longer than expected. Check the server; completed analyses will appear in history.",
          );
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy("");
    }
  }
  const nav = [
    ["Overview", LayoutDashboard],
    ["Analysis", MessageSquare],
    ["Playbooks", BookOpen],
    ["Knowledge", Library],
    ["Dataset", Database],
    ["Readiness", ShieldCheck],
  ];
  const scopeBar = (
    <div className="scope-controls">
      <label>
        Current period
        <input
          aria-label="Current start"
          type="date"
          value={scope.start}
          onChange={(e) => setScope({ ...scope, start: e.target.value })}
        />
      </label>
      <span className="date-dash">—</span>
      <label>
        Through
        <input
          aria-label="Current end"
          type="date"
          value={scope.end}
          onChange={(e) => setScope({ ...scope, end: e.target.value })}
        />
      </label>
      <span className="versus">vs</span>
      <label>
        Comparison
        <input
          aria-label="Comparison start"
          type="date"
          value={scope.compare_start}
          onChange={(e) =>
            setScope({ ...scope, compare_start: e.target.value })
          }
        />
      </label>
      <span className="date-dash">—</span>
      <label>
        Through
        <input
          aria-label="Comparison end"
          type="date"
          value={scope.compare_end}
          onChange={(e) => setScope({ ...scope, compare_end: e.target.value })}
        />
      </label>
      <button
        className="button secondary"
        disabled={!!busy}
        onClick={() => {
          const s = scope;
          if (
            !s.start ||
            !s.end ||
            !s.compare_start ||
            !s.compare_end ||
            s.start > s.end ||
            s.compare_start > s.compare_end ||
            s.compare_end >= s.start ||
            s.compare_start < "2024-01-01" ||
            s.end > "2025-12-31" ||
            new Date(s.end) - new Date(s.start) !==
              new Date(s.compare_end) - new Date(s.compare_start)
          ) {
            setError(
              "Choose equal-length, nonoverlapping periods within 2024–2025.",
            );
            return;
          }
          setApplied({ ...scope });
          setResult(null);
          setSuggest(null);
        }}
      >
        Apply
      </button>
    </div>
  );
  const composer = (
    <form
      className="composer"
      onSubmit={(e) => {
        e.preventDefault();
        if (question.trim())
          run({ question: question.trim(), previous_id: result?.id }, true);
      }}
    >
      <div className="composer-icon">
        <MessageSquare size={20} />
      </div>
      <input
        aria-label="Ask a retail question"
        placeholder="Ask a question about your retail business…"
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        maxLength={4000}
      />
      <button
        disabled={!!busy || !question.trim()}
        aria-label="Submit question"
      >
        <ArrowRight size={20} />
      </button>
    </form>
  );
  return (
    <div className="app-shell">
      <aside>
        <div className="brand">
          <div className="brand-mark">
            <Triangle size={23} fill="currentColor" />
          </div>
          <div>
            SUMMIT FIELD<small>RETAIL INTELLIGENCE</small>
          </div>
        </div>
        <div className="workspace-label">WORKSPACE</div>
        <nav>
          {nav.map(([p, Icon]) => (
            <button
              key={p}
              className={p === page ? "selected" : ""}
              onClick={() => {
                setPage(p);
                setError("");
              }}
            >
              <Icon size={18} />
              {p}
              {p === "Playbooks" && <span className="nav-count">19</span>}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="connected">
            <span />
            Local warehouse connected
          </div>
          <p>
            Synthetic data · USD
            <br />
            Sales through Dec 2025
          </p>
          <div className="profile">
            <div className="avatar">SF</div>
            <div>
              Summit Field<small>Local research workspace</small>
            </div>
          </div>
        </div>
      </aside>
      <main>
        <header>
          <div className="breadcrumb">
            Workspace <ChevronRight size={14} />
            <span>{page}</span>
          </div>
          <div className="header-right">
            <Pill tone="green">
              <span className="dot" />
              Read-only data
            </Pill>
            <span className="mode">
              {status?.agent_ready
                ? "Reasoning agent enabled"
                : "Local playbook mode"}
            </span>
          </div>
        </header>
        <div className="content">
          {error && (
            <div className="error" role="alert">
              <AlertCircle size={18} />
              {error}
              <button aria-label="Dismiss error" onClick={() => setError("")}>
                <X size={16} />
              </button>
            </div>
          )}
          {page === "Overview" && (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">THE BUSINESS, IN VIEW</div>
                  <h1>A clearer view of retail.</h1>
                  <p>Your data, playbooks, and evidence. One place to start.</p>
                </div>
                <button
                  className="button primary"
                  onClick={() => setPage("Analysis")}
                >
                  <Plus size={16} /> New analysis
                </button>
              </div>
              {scopeBar}
              {!overview ? (
                <Empty>
                  <LoaderCircle className="spin" />
                  Computing your business overview…
                </Empty>
              ) : (
                <>
                  <div className="kpi-grid">
                    {[
                      ["sales_cents", "Net merchandise sales", "money"],
                      ["orders", "Completed orders", "number"],
                      ["units", "Units sold", "number"],
                      ["aov", "Average order value", "money"],
                    ].map(([key, label, kind]) => {
                      const a =
                          overview.kpis.rows.find(
                            (r) => r.period === "current",
                          ) || {},
                        b =
                          overview.kpis.rows.find(
                            (r) => r.period === "comparison",
                          ) || {},
                        v = key === "aov" ? a.sales_cents / a.orders : a[key],
                        old = key === "aov" ? b.sales_cents / b.orders : b[key],
                        delta = old ? ((v - old) / old) * 100 : null;
                      return (
                        <div className="kpi card" key={key}>
                          <div className="kpi-label">{label}</div>
                          <div className="kpi-number">{fmt(v, kind)}</div>
                          <div>
                            <span
                              className={
                                "delta " + (delta < 0 ? "negative" : "")
                              }
                            >
                              {delta == null
                                ? "—"
                                : `${delta >= 0 ? "+" : ""}${delta.toFixed(1)}%`}
                            </span>
                            <span className="small muted"> vs comparison</span>
                          </div>
                          <span className="kpi-foot">
                            {kind === "money"
                              ? "Before returns · USD"
                              : "Original completed sales"}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                  <div className="dashboard-charts">
                    <section className="card">
                      <div className="card-heading">
                        <div>
                          <h2>Sales over time</h2>
                          <p>Matched periods · all channels</p>
                        </div>
                        <button
                          className="text-button"
                          disabled={!!busy}
                          onClick={() => run({ slug: "trend" })}
                        >
                          Explore <ArrowUpRight size={16} />
                        </button>
                      </div>
                      <Chart
                        slug="trend"
                        outputs={overview.trend.outputs}
                        period={applied}
                      />
                    </section>
                    <section className="card">
                      <div className="card-heading">
                        <div>
                          <h2>Where growth comes from</h2>
                          <p>Change in sales by division</p>
                        </div>
                      </div>
                      <Chart
                        slug="growth"
                        outputs={overview.growth.outputs}
                        period={applied}
                      />
                    </section>
                  </div>
                </>
              )}
              <section className="ask-section">
                <div className="eyebrow">START WITH A BETTER QUESTION</div>
                <h2>What would you like to understand?</h2>
                {composer}
                <div className="quick-prompts">
                  {[
                    ["pvm", "What explains the sales change?"],
                    ["margin", "How is merchandise margin moving?"],
                    ["inventory", "Where is inventory building?"],
                  ].map(([slug, q]) => (
                    <button
                      key={slug}
                      disabled={!!busy}
                      onClick={() => run({ slug })}
                    >
                      {q}
                      <ArrowUpRight size={14} />
                    </button>
                  ))}
                </div>
                <p className="small muted">
                  {status?.agent_ready
                    ? "Questions use the configured model; relevant context and query results are sent to OpenAI."
                    : "No API key needed for playbooks. Free-text questions suggest a baseline until the reasoning model is connected."}
                </p>
              </section>
            </>
          )}
          {page === "Analysis" && (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">FROM QUESTION TO EVIDENCE</div>
                  <h1>Analysis studio</h1>
                  <p>
                    Explore a question, then inspect the work behind the answer.
                  </p>
                </div>
              </div>
              {scopeBar}
              {composer}
              <div className="studio-grid">
                <div>
                  {busy && (
                    <div className="card progress" role="status">
                      <LoaderCircle className="spin" size={20} />
                      <div>
                        <b>Working with your data</b>
                        <p>{busy}</p>
                      </div>
                    </div>
                  )}
                  {suggest && (
                    <div className="card suggestions">
                      <Pill>Local mode</Pill>
                      <h2>A starting point for your question</h2>
                      <p>{suggest.message}</p>
                      {suggest.suggestions.map((s) => (
                        <button
                          key={s}
                          className="suggestion"
                          disabled={!!busy}
                          onClick={() => run({ slug: s })}
                        >
                          {status?.playbooks.find((p) => p.slug === s)?.title}
                          <ArrowRight size={16} />
                        </button>
                      ))}
                      {!!suggest.gaps?.length && (
                        <button
                          className="button secondary"
                          onClick={() => setPage("Readiness")}
                        >
                          View missing evidence
                        </button>
                      )}
                    </div>
                  )}
                  <Evidence result={result} onOpenDoc={openDoc} />
                  {!result && !suggest && !busy && (
                    <div className="card welcome">
                      <div className="big-icon">
                        <MessageSquare size={26} />
                      </div>
                      <h2>Every answer starts with evidence.</h2>
                      <p>
                        Run a trusted playbook, or ask a question to find a
                        starting point. Results include SQL, exact dates, source
                        context, and validation checks.
                      </p>
                      <button
                        className="button primary"
                        onClick={() => run({ slug: "trend" })}
                      >
                        Run sales trend <ArrowRight size={15} />
                      </button>
                    </div>
                  )}
                </div>
                <section className="history">
                  <h3>
                    <Clock size={15} /> Analysis history
                  </h3>
                  {!history.length ? (
                    <p className="small muted">
                      Completed analyses will appear here.
                    </p>
                  ) : (
                    history.map((h) => (
                      <button
                        key={h.id}
                        className={result?.id === h.id ? "active" : ""}
                        onClick={async () => {
                          try {
                            setResult(await api("/history/" + h.id));
                            setSuggest(null);
                          } catch (e) {
                            setError(e.message);
                          }
                        }}
                      >
                        <span>{h.question}</span>
                        <small>{h.created} UTC</small>
                      </button>
                    ))
                  )}
                </section>
              </div>
            </>
          )}
          {page === "Playbooks" && (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">YOUR ANALYTICAL LIBRARY</div>
                  <h1>19 ways to go deeper.</h1>
                  <p>
                    The recipes you created, connected to the full synthetic
                    warehouse.
                  </p>
                </div>
                <Pill tone="green">19 executable baselines</Pill>
              </div>
              {scopeBar}
              <div className="searchbox">
                <Search size={17} />
                <input
                  aria-label="Search playbooks"
                  placeholder="Find a playbook…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>
              <div className="playbook-grid">
                {status?.playbooks
                  .filter((p) =>
                    (p.title + " " + p.note)
                      .toLowerCase()
                      .includes(search.toLowerCase()),
                  )
                  .map((p) => (
                    <article className="card playbook" key={p.slug}>
                      <div className="playbook-top">
                        <span className="playbook-number">
                          {String(p.number).padStart(2, "0")}
                        </span>
                        <Pill>
                          {p.number <= 5
                            ? "Economic drivers"
                            : p.number <= 10
                              ? "Merchandise"
                              : p.number <= 15
                                ? "Customers"
                                : "Operations"}
                        </Pill>
                      </div>
                      <h2>{p.title}</h2>
                      <p>{p.note}</p>
                      <button
                        className="text-button"
                        disabled={!!busy}
                        onClick={() => run({ slug: p.slug })}
                      >
                        Run playbook <ArrowRight size={16} />
                      </button>
                    </article>
                  ))}
              </div>
              <p className="caption">
                Baseline queries implement part of each A–I recipe. Full
                playbook text and visual specifications are available in
                Knowledge. All baseline reports cover the whole business.
              </p>
            </>
          )}
          {page === "Knowledge" && (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">CONTEXT IS THE FOUNDATION</div>
                  <h1>The knowledge behind the numbers.</h1>
                  <p>
                    {status?.documents} indexed documents · source references
                    retained · duplicate content removed
                  </p>
                </div>
              </div>
              <form
                className="searchbox"
                onSubmit={async (e) => {
                  e.preventDefault();
                  try {
                    setDocs(
                      await api("/context?q=" + encodeURIComponent(query)),
                    );
                  } catch (e) {
                    setError(e.message);
                  }
                }}
              >
                <Search size={17} />
                <input
                  aria-label="Search knowledge"
                  placeholder="Search metric definitions, playbooks, joins, or generation rules…"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
                <button className="button primary">Search</button>
              </form>
              {docs?.matches?.map((c, i) => (
                <div className="card source" key={i}>
                  <button onClick={() => openDoc(c.source)}>
                    {c.source} : {c.line}
                    <ArrowUpRight size={15} />
                  </button>
                  <pre>{c.text}</pre>
                </div>
              ))}
              <div className="card document-list">
                <h2>Source library</h2>
                {docs?.documents.map((d) => (
                  <button key={d.path} onClick={() => openDoc(d.path)}>
                    <FileText size={17} />
                    <span>{d.path}</span>
                    <small>{d.lines} lines</small>
                    <ArrowUpRight size={15} />
                  </button>
                ))}
              </div>
              <div className="card memory">
                <h2>Confirmed local knowledge</h2>
                <p className="muted">
                  Add a convention or correction you have reviewed, with its
                  source. These notes are retrieved as context; they do not
                  change the warehouse.
                </p>
                <form
                  onSubmit={async (e) => {
                    e.preventDefault();
                    try {
                      await api("/memory", { text: note, source });
                      setNote("");
                      setSource("");
                      setMem(await api("/memory"));
                    } catch (e) {
                      setError(e.message);
                    }
                  }}
                >
                  <textarea
                    aria-label="Confirmed knowledge"
                    placeholder="A reviewed convention or correction…"
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                    required
                    minLength={3}
                    maxLength={2000}
                  />
                  <input
                    aria-label="Knowledge source"
                    placeholder="Source / reason this is confirmed"
                    value={source}
                    onChange={(e) => setSource(e.target.value)}
                    required
                    minLength={3}
                    maxLength={500}
                  />
                  <button className="button primary">
                    Save confirmed note
                  </button>
                </form>
                {mem.map((m) => (
                  <div className="memory-note" key={m.id}>
                    <p>{m.text}</p>
                    <small>
                      {m.source} · {m.created}
                    </small>
                  </div>
                ))}
              </div>
            </>
          )}
          {page === "Dataset" && (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">KNOW WHAT YOU ARE QUERYING</div>
                  <h1>Meet Summit Field.</h1>
                  <p>
                    A fictional US omnichannel retailer, built for analytical
                    research.
                  </p>
                </div>
                <Pill tone="green">Frozen synthetic extract</Pill>
              </div>
              <div className="dataset-stats">
                {[
                  [fmt(status?.orders), "completed orders"],
                  [fmt(status?.skus), "SKUs"],
                  [fmt(status?.stores), "stores"],
                  ["23", "warehouse tables"],
                ].map(([v, l]) => (
                  <div className="card" key={l}>
                    <strong>{v}</strong>
                    <p>{l}</p>
                  </div>
                ))}
              </div>
              <div className="note">
                <AlertCircle size={18} />
                <p>
                  Sales: 2024-01-01–2025-12-31. Returns through 2026-03-01. USD
                  stored as integer cents. Inventory is weekly; customer 0 is
                  anonymous. This data does not represent a real retailer.
                </p>
              </div>
              <div className="catalog-layout">
                <div className="card catalog-list">
                  <h2>Tables & grains</h2>
                  {catalog &&
                    Object.entries(catalog).map(([name, v]) => (
                      <button
                        key={name}
                        onClick={async () => {
                          setInspected({ loading: true, name });
                          try {
                            setInspected(await api("/inspect/" + name));
                          } catch (e) {
                            setError(e.message);
                            setInspected(null);
                          }
                        }}
                      >
                        <Database size={15} />
                        <div>
                          <b>{name}</b>
                          <small>{v.grain}</small>
                        </div>
                        <ChevronRight size={15} />
                      </button>
                    ))}
                </div>
                <div className="card">
                  {!inspected ? (
                    <Empty>
                      Select a table to inspect its live schema and sample rows.
                    </Empty>
                  ) : inspected.loading ? (
                    <Empty>
                      <LoaderCircle className="spin" /> Inspecting{" "}
                      {inspected.name}…
                    </Empty>
                  ) : (
                    <>
                      <h2>{inspected.table}</h2>
                      <p>
                        {fmt(inspected.row_count)} live rows ·{" "}
                        {inspected.metadata?.grain}
                      </p>
                      <ColumnProfile
                        table={inspected.table}
                        columns={inspected.columns}
                      />
                      <h3>Columns</h3>
                      <Table
                        output={{
                          rows: inspected.columns,
                          row_count: inspected.columns.length,
                        }}
                      />
                      <h3>Sample · first 3 rows</h3>
                      <Table
                        output={{
                          rows: inspected.sample,
                          row_count: inspected.sample.length,
                        }}
                      />
                    </>
                  )}
                </div>
              </div>
            </>
          )}
          {page === "Readiness" && (
            <>
              <div className="page-heading">
                <div>
                  <div className="eyebrow">WHAT WORKS. WHAT COMES NEXT.</div>
                  <h1>An honest view of readiness.</h1>
                  <p>
                    The local foundation is running. Here is what the full
                    blueprint still needs.
                  </p>
                </div>
              </div>
              <div className="readiness-grid">
                <div className="card">
                  <ShieldCheck size={28} color={GREEN} />
                  <h2>Local foundation</h2>
                  <p>
                    19 playbook baselines, full DuckDB data, source retrieval,
                    charts, SQL evidence, exports, saved analyses, and confirmed
                    notes.
                  </p>
                  <Pill tone="green">Working locally</Pill>
                </div>
                <div className="card">
                  <MessageSquare size={28} color={GREEN} />
                  <h2>Single reasoning agent</h2>
                  <p>
                    LangGraph tool loop with schema inspection, read-only SQL,
                    context retrieval and bounded correction. Configure the key
                    and model on the server.
                  </p>
                  <Pill>
                    {status?.agent_ready
                      ? "Configured · live evaluation pending"
                      : "Needs API key + model"}
                  </Pill>
                </div>
                <div className="card">
                  <Code size={28} color={GREEN} />
                  <h2>Regression checks</h2>
                  <p>
                    {quality?.app_evals
                      ? `${quality.app_evals.passed} / ${quality.app_evals.total} app checks passed. Includes independent golden SQL and guardrail tests.`
                      : "App checks have not been recorded yet."}
                  </p>
                  <Pill>
                    {quality?.app_evals?.failures?.length
                      ? "Review failures"
                      : "Live-model evaluation pending"}
                  </Pill>
                </div>
              </div>
              <div className="gap-list">
                {status?.gaps.map((g, i) => (
                  <div className="card gap" key={g.title}>
                    <span className="gap-number">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <div>
                      <Pill>{g.priority}</Pill>
                      <h2>{g.title}</h2>
                      <p>{g.detail}</p>
                    </div>
                  </div>
                ))}
              </div>
              <div className="card">
                <h2>Configuration & privacy</h2>
                <p>
                  Playbook mode stays on this computer. Agent mode sends your
                  question, relevant documentation and bounded query results to
                  OpenAI. Your key stays on the server, outside the browser and
                  saved history.
                </p>
                <pre>
                  export OPENAI_API_KEY='your-key'{"\n"}export
                  OPENAI_MODEL='your-model-id'{"\n"}./retail_app/start.sh
                </pre>
                <p className="muted">
                  Restart the server after configuring these values. Never paste
                  credentials into a question or a knowledge note.
                </p>
              </div>
            </>
          )}
          <footer>
            <span>
              <Triangle size={12} /> Summit Field · Synthetic retail research
            </span>
            <span>Evidence before interpretation.</span>
          </footer>
        </div>
      </main>
      {doc && (
        <div className="modal-backdrop" onClick={() => setDoc(null)}>
          <div
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-label="Source document"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="modal-header">
              <b>{doc.path}</b>
              <button aria-label="Close source" onClick={() => setDoc(null)}>
                <X size={20} />
              </button>
            </div>
            <pre>{doc.text}</pre>
          </div>
        </div>
      )}
    </div>
  );
}
export { App, Chart, Table, Evidence, QueryChart };
