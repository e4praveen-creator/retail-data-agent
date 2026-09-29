import { api, conversationMarkdown } from "./api.js";
import React, { useState, useEffect, useRef, useMemo } from "react";
import { createRoot } from "react-dom/client";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  MessageSquare,
  SquarePen,
  Search,
  PanelLeftClose,
  PanelLeftOpen,
  ArrowUp,
  ArrowRight,
  ChevronDown,
  ChevronRight,
  Download,
  Copy,
  Check,
  FlaskConical,
  GitBranch,
  ChartNoAxesCombined,
  BookOpen,
  Database,
  Settings2,
  X,
  LoaderCircle,
  Triangle,
  Library,
  Lightbulb,
  SlidersHorizontal,
  ArrowLeft,
  ShieldCheck,
  Pencil,
  ThumbsUp,
  ThumbsDown,
  Square,
  Trash2,
  RotateCcw,
} from "lucide-react";
import { App as Workspace, Evidence, Chart, QueryChart } from "./app.jsx";
import { AnswerReport } from "./answer-report.jsx";
const initialScope = {
  start: "2025-01-05",
  end: "2025-12-27",
  compare_start: "2024-01-07",
  compare_end: "2024-12-28",
};

function Rich({ text, references = {}, onReference }) {
  const content = (text || "").replace(/\[([ED]\d+)\](?!\()/g, (match, id) =>
    references[id] ? `[${id}](#reference-${id})` : match,
  );
  return (
    <div className="chat-markdown">
      <Markdown
        skipHtml
        remarkPlugins={[remarkGfm]}
        components={{
          // Model/source Markdown must never trigger an automatic external image request.
          img: ({ src, alt }) => (
            <a href={src} target="_blank" rel="noopener noreferrer">
              {alt || "Open image reference"}
            </a>
          ),
          a: ({ children, href, ...props }) =>
            href?.startsWith("#reference-") && references[href.slice(11)] ? (
              <button
                className="inline-reference"
                onClick={() => onReference?.(href.slice(11))}
                title="Inspect supporting evidence"
              >
                {children}
              </button>
            ) : (
              <a
                {...props}
                href={href}
                target="_blank"
                rel="noopener noreferrer"
              >
                {children}
              </a>
            ),
        }}
      >
        {content}
      </Markdown>
    </div>
  );
}
function Answer({ message, onPlaybook, onDocument, onFollowUp, onFeedback }) {
  const [inspect, setInspect] = useState(false),
    [copied, setCopied] = useState(false),
    [special, setSpecial] = useState(null),
    [rating, setRating] = useState(null);
  const a = message.analysis;
  const references = Object.fromEntries([
    ...(a?.outputs || [])
      .filter((o) => o.evidence_id)
      .map((o) => [o.evidence_id, o]),
    ...(a?.context || [])
      .filter((c) => c.source_id)
      .map((c) => [c.source_id, c]),
  ]);
  function openReference(id) {
    if (references[id]?.source) onDocument(references[id].source);
    else setInspect(true);
  }
  return (
    <article className="chat-answer">
      <div className="answer-avatar">
        <Triangle size={18} fill="currentColor" />
      </div>
      <div className="answer-body">
        <div className="answer-byline">
          Retail Analyst{" "}
          <span>
            {a?.mode === "agent"
              ? "Grounded in your data"
              : a?.mode === "playbook"
                ? "Computed playbook"
                : "Setup needed"}
          </span>
        </div>
        {a?.presentation ? (
          <AnswerReport
            result={a}
            renderText={(text) => (
              <Rich
                text={text}
                references={references}
                onReference={openReference}
              />
            )}
            onFollowUp={onFollowUp}
          />
        ) : (
          <>
            <Rich
              text={message.text}
              references={references}
              onReference={openReference}
            />
            {a?.report && (
              <div className="chat-result-chart">
                <Chart
                  slug={a.report.slug}
                  outputs={a.outputs}
                  period={a.period}
                />
              </div>
            )}
            {!a?.report &&
              (a?.charts || []).map((c, i) => (
                <div className="chat-result-chart" key={i}>
                  <QueryChart spec={c} output={a.outputs[c.output_index]} />
                </div>
              ))}
          </>
        )}
        {!!a?.specialists?.length && (
          <div className="specialist-results">
            {a.specialists.map((s, i) => (
              <div key={i} className="specialist-result">
                <button
                  aria-expanded={special === i}
                  onClick={() => setSpecial(special === i ? null : i)}
                >
                  {s.role === "hypothesis" ? (
                    <Lightbulb size={16} />
                  ) : s.role === "eda" ? (
                    <ChartNoAxesCombined size={16} />
                  ) : (
                    <GitBranch size={16} />
                  )}
                  <span>
                    {s.role === "hypothesis"
                      ? "Hypotheses"
                      : s.role === "eda"
                        ? "Exploratory analysis"
                        : "Root-cause investigation"}
                  </span>
                  <small>
                    {s.evidence_ids?.length || 0} evidence references
                  </small>
                  <ChevronDown size={14} />
                </button>
                {special === i && (
                  <div className="specialist-detail">
                    <Rich
                      text={s.answer}
                      references={references}
                      onReference={openReference}
                    />
                    <p className="small muted">
                      {s.evidence_ids?.join(" · ") ||
                        "No query evidence collected by this specialist."}
                    </p>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
        {!!a?.warnings?.length && (
          <details className="analysis-notes">
            <summary>Notes and limitations · {a.warnings.length}</summary>
            <ul>
              {a.warnings.map((warning, i) => (
                <li key={i}>{warning}</li>
              ))}
            </ul>
          </details>
        )}
        {a?.mode === "suggestions" && (
          <div className="chat-suggestions">
            {a.suggestions?.map((s) => (
              <button key={s} onClick={() => onPlaybook(s)}>
                Run {s} baseline <ArrowRight size={13} />
              </button>
            ))}
          </div>
        )}
        <div className="answer-actions">
          <button
            title="Copy answer"
            aria-label={copied ? "Answer copied" : "Copy answer"}
            onClick={async () => {
              try {
                await navigator.clipboard.writeText(message.text);
                setCopied(true);
                setTimeout(() => setCopied(false), 1500);
              } catch {
                setCopied(false);
              }
            }}
          >
            {copied ? <Check size={15} /> : <Copy size={15} />}
          </button>
          {a?.id && (
            <>
              <button
                aria-expanded={inspect}
                onClick={() => setInspect(!inspect)}
              >
                <Database size={14} />
                {inspect ? "Hide evidence" : "Evidence & SQL"}
                {a.outputs?.length ? ` · ${a.outputs.length}` : ""}
              </button>
              <a
                title="Download full analysis"
                aria-label="Download full analysis JSON"
                href={`/api/export/${a.id}`}
              >
                <Download size={15} />
              </a>
              <button
                title="Helpful answer"
                aria-label="Helpful answer"
                aria-pressed={rating === "helpful"}
                onClick={async () => {
                  if (await onFeedback(a.id, "helpful")) setRating("helpful");
                }}
              >
                <ThumbsUp size={14} />
              </button>
              <button
                title="Needs improvement"
                aria-label="Needs improvement"
                aria-pressed={rating === "needs_review"}
                onClick={async () => {
                  if (await onFeedback(a.id, "needs_review"))
                    setRating("needs_review");
                }}
              >
                <ThumbsDown size={14} />
              </button>
            </>
          )}
        </div>
        {inspect && a && <Evidence result={a} onOpenDoc={onDocument} />}{" "}
        {a?.mode === "agent" && (
          <div className="follow-up-chips">
            <button
              onClick={() =>
                onFollowUp(
                  "Break that down by category, retaining the same dates and filters.",
                )
              }
            >
              Break down by category
            </button>
            <button
              onClick={() =>
                onFollowUp(
                  "Which alternative explanations remain unresolved, and what evidence would distinguish them?",
                )
              }
            >
              Test alternatives
            </button>
          </div>
        )}
      </div>
    </article>
  );
}
const MemoAnswer = React.memo(Answer);
class AppErrorBoundary extends React.Component {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    if (this.state.failed)
      return (
        <div className="app-recovery" role="alert">
          <h1>This view could not be displayed.</h1>
          <p>Your saved chats remain available. Reload the app to try again.</p>
          <button onClick={() => window.location.reload()}>Reload app</button>
        </div>
      );
    return this.props.children;
  }
}
function ChatApp() {
  const [status, setStatus] = useState(null),
    [conversations, setConversations] = useState([]),
    [conversation, setConversation] = useState(null),
    [question, setQuestion] = useState(""),
    [mode, setMode] = useState("auto"),
    [scope, setScope] = useState(initialScope),
    [scopeDraft, setScopeDraft] = useState(initialScope),
    [busy, setBusy] = useState(false),
    [activeJob, setActiveJob] = useState(null),
    [stopping, setStopping] = useState(false),
    [retryRequest, setRetryRequest] = useState(null),
    [progress, setProgress] = useState(""),
    [error, setError] = useState(""),
    [sidebar, setSidebar] = useState(
      typeof window === "undefined" || window.innerWidth > 760,
    ),
    [workspace, setWorkspace] = useState(false),
    [modal, setModal] = useState(null),
    [bank, setBank] = useState(null),
    [bankQuery, setBankQuery] = useState(""),
    [chatSearch, setChatSearch] = useState(""),
    [doc, setDoc] = useState(null),
    [toast, setToast] = useState(""),
    [rename, setRename] = useState(""),
    [modalError, setModalError] = useState(""),
    [modalBusy, setModalBusy] = useState(false);
  const [earlierBusy, setEarlierBusy] = useState(false),
    [exportBusy, setExportBusy] = useState(false);
  const bottom = useRef(null),
    actionRef = useRef(null),
    dialog = useRef(null),
    scroll = useRef(null),
    followScroll = useRef(true),
    input = useRef(null),
    activeId = useRef(null),
    pollToken = useRef(0);
  const refresh = () => api("/conversations").then(setConversations);
  useEffect(() => {
    api("/status")
      .then(setStatus)
      .catch((e) => {
        setStatus({ load_failed: true });
        setError(e.message);
      });
    refresh().catch((e) => setError(e.message));
    const saved = localStorage.getItem("retail-conversation");
    if (saved) load(saved);
    return () => {
      pollToken.current++;
    };
  }, []);
  useEffect(() => {
    if (followScroll.current)
      bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [conversation?.messages?.length, progress]);
  useEffect(() => {
    if (!input.current) return;
    input.current.style.height = "auto";
    input.current.style.height = `${Math.min(input.current.scrollHeight, 200)}px`;
  }, [question, workspace]);
  useEffect(() => {
    if (!modal && !doc) return;
    setModalError("");
    const previous = document.activeElement;
    const container = dialog.current;
    const selectable =
      'button:not(:disabled), [href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex="0"]';
    const frame = requestAnimationFrame(() =>
      container?.querySelector(selectable)?.focus(),
    );
    function onKey(event) {
      if (event.key === "Escape") {
        event.preventDefault();
        setModal(null);
        setDoc(null);
      }
      if (event.key !== "Tab") return;
      const items = [...(container?.querySelectorAll(selectable) || [])].filter(
        (item) => item.offsetParent !== null,
      );
      if (!items.length) return;
      const first = items[0],
        last = items[items.length - 1];
      if (
        event.shiftKey &&
        (document.activeElement === first ||
          !container.contains(document.activeElement))
      ) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
    document.addEventListener("keydown", onKey);
    return () => {
      cancelAnimationFrame(frame);
      document.removeEventListener("keydown", onKey);
      if (previous?.isConnected) previous.focus();
    };
  }, [modal, doc]);
  function openScope() {
    setScopeDraft({ ...scope });
    setModal("scope");
  }
  function dismissMobileSidebar() {
    if (window.innerWidth <= 760) setSidebar(false);
  }
  async function monitor(job, id) {
    const token = ++pollToken.current;
    setBusy(true);
    setActiveJob(job);
    setStopping(false);
    try {
      for (let i = 0; i < 2000; i++) {
        if (token !== pollToken.current) return;
        const s = await api("/chat/jobs/" + job);
        if (token !== pollToken.current) return;
        setProgress(s.message);
        if (s.status === "complete") {
          const c = await api("/conversations/" + id);
          if (token !== pollToken.current) return;
          setConversation(c);
          setRetryRequest(null);
          await refresh();
          break;
        }
        if (s.status === "cancelled") {
          setToast(s.message || "Answer stopped");
          setTimeout(() => setToast(""), 4000);
          break;
        }
        if (!["running", "cancelling"].includes(s.status))
          throw Error(s.error || s.message);
        setStopping(s.status === "cancelling");
        await new Promise((r) => setTimeout(r, 800));
      }
    } catch (e) {
      if (token === pollToken.current) setError(e.message);
    } finally {
      if (token === pollToken.current) {
        setBusy(false);
        setActiveJob(null);
        setStopping(false);
        setProgress("");
      }
    }
  }
  async function load(id) {
    const token = ++pollToken.current;
    setBusy(true);
    setProgress("Loading conversation");
    setError("");
    setRetryRequest(null);
    setActiveJob(null);
    setStopping(false);
    followScroll.current = true;
    dismissMobileSidebar();
    try {
      const c = await api("/conversations/" + id);
      if (token !== pollToken.current) return;
      activeId.current = id;
      setConversation(c);
      const last = c.messages?.at(-1);
      if (last?.role === "user") {
        setRetryRequest({
          question: last.text,
          conversation_id: id,
          mode,
          ...scope,
          retry: true,
        });
      }
      localStorage.setItem("retail-conversation", id);
      if (c.active_job) monitor(c.active_job.id, id);
      else {
        setBusy(false);
        setProgress("");
      }
    } catch (e) {
      if (token === pollToken.current) {
        setError(e.message);
        setBusy(false);
        setProgress("");
        localStorage.removeItem("retail-conversation");
      }
    }
  }
  function newChat() {
    pollToken.current++;
    activeId.current = null;
    setConversation(null);
    setQuestion("");
    setError("");
    setBusy(false);
    setProgress("");
    setActiveJob(null);
    setRetryRequest(null);
    setStopping(false);
    followScroll.current = true;
    dismissMobileSidebar();
    localStorage.removeItem("retail-conversation");
    input.current?.focus();
  }
  async function send(
    text = question,
    playbook = null,
    hypothesis_id = null,
    retry = null,
  ) {
    if (!text.trim() || busy) return;
    const requestToken = ++pollToken.current;
    setQuestion("");
    setError("");
    setBusy(true);
    followScroll.current = true;
    setProgress("Retrieving business context");
    const payload = retry || {
      question: text,
      conversation_id: activeId.current,
      mode,
      ...scope,
      playbook,
      hypothesis_id,
    };
    setRetryRequest({ ...payload });
    try {
      const r = await api("/chat", payload);
      if (requestToken !== pollToken.current) return;
      activeId.current = r.conversation_id;
      setRetryRequest({
        ...payload,
        conversation_id: r.conversation_id,
        retry: true,
      });
      localStorage.setItem("retail-conversation", r.conversation_id);
      const updatedConversation =
        r.conversation || (await api("/conversations/" + r.conversation_id));
      if (requestToken !== pollToken.current) return;
      setConversation(updatedConversation);
      await refresh();
      if (requestToken !== pollToken.current) return;
      if (r.job_id) {
        monitor(r.job_id, r.conversation_id);
      } else {
        setBusy(false);
        setProgress("");
        setRetryRequest(null);
      }
    } catch (e) {
      if (requestToken === pollToken.current) {
        // A lost response may hide an already accepted job. Recover that job
        // before presenting a retry that would repeat a persisted question.
        if (payload.conversation_id) {
          try {
            const recovered = await api(
              "/conversations/" + payload.conversation_id,
            );
            if (requestToken !== pollToken.current) return;
            setConversation(recovered);
            const last = recovered.messages?.at(-1);
            if (last?.role === "user" && last.text === payload.question) {
              setRetryRequest({ ...payload, retry: true });
              if (recovered.active_job) {
                monitor(recovered.active_job.id, payload.conversation_id);
                return;
              }
            }
          } catch {
            /* Keep the original actionable request error. */
          }
        }
        if (requestToken !== pollToken.current) return;
        setError(e.message);
        setBusy(false);
        setProgress("");
      }
    }
  }
  async function stop() {
    if (!activeJob || stopping) return;
    const id = activeId.current;
    setStopping(true);
    try {
      await api("/chat/jobs/" + activeJob + "/cancel", {});
      if (id === activeId.current)
        setProgress("Stopping the current analysis…");
    } catch (e) {
      if (id === activeId.current) {
        setError(e.message);
        setStopping(false);
      }
    }
  }
  async function deleteConversation() {
    setModalBusy(true);
    setModalError("");
    try {
      await api("/conversations/" + conversation.id, undefined, {
        method: "DELETE",
      });
      setModal(null);
      newChat();
      await refresh();
    } catch (e) {
      setModalError(e.message);
    } finally {
      setModalBusy(false);
    }
  }
  async function loadEarlier() {
    if (!conversation?.has_older || earlierBusy) return;
    const id = conversation.id;
    setEarlierBusy(true);
    try {
      const page = await api(
        `/conversations/${id}?before=${conversation.older_cursor}&limit=50`,
      );
      if (id !== activeId.current) return;
      const container = scroll.current,
        height = container?.scrollHeight || 0;
      followScroll.current = false;
      setConversation((current) => ({
        ...current,
        messages: [...page.messages, ...current.messages],
        has_older: page.has_older,
        older_cursor: page.older_cursor,
      }));
      requestAnimationFrame(() => {
        if (container) container.scrollTop += container.scrollHeight - height;
      });
    } catch (e) {
      if (id === activeId.current) setError(e.message);
    } finally {
      setEarlierBusy(false);
    }
  }
  async function exportConversation() {
    if (!conversation) return;
    setExportBusy(true);
    try {
      const full = { ...conversation, messages: [...conversation.messages] };
      let previousCursor = null;
      while (full.has_older) {
        if (!full.older_cursor || previousCursor === full.older_cursor)
          throw Error(
            "Could not retrieve the complete conversation. Please reload the chat and try again.",
          );
        previousCursor = full.older_cursor;
        const page = await api(
          `/conversations/${full.id}?before=${full.older_cursor}&limit=50`,
        );
        full.messages = [...page.messages, ...full.messages];
        full.has_older = page.has_older;
        full.older_cursor = page.older_cursor;
      }
      const blob = new Blob([conversationMarkdown(full)], {
        type: "text/markdown;charset=utf-8",
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download =
        (full.title || "retail-analysis")
          .replace(/[^a-z0-9 -]/gi, "")
          .slice(0, 80) + ".md";
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      setError(e.message);
    } finally {
      setExportBusy(false);
    }
  }
  async function openDoc(path) {
    try {
      const r = await fetch("/api/document?" + new URLSearchParams({ path }));
      if (!r.ok) throw Error("Source is unavailable");
      setDoc({ path, text: await r.text() });
    } catch (e) {
      setError(e.message);
    }
  }
  async function openBank() {
    setModal("bank");
    try {
      setBank(await api("/hypotheses"));
    } catch (e) {
      setError(e.message);
    }
  }
  async function feedback(id, rating) {
    try {
      await api("/feedback", { analysis_id: id, rating, comment: "" });
      setToast("Feedback saved for review");
      setTimeout(() => setToast(""), 2500);
      return true;
    } catch (e) {
      setError(e.message);
      return false;
    }
  }
  actionRef.current = { send, openDoc, feedback };
  // Typing a draft should not rerender every Markdown answer and chart.
  const answerActions = useMemo(
    () => ({
      onPlaybook: (slug) =>
        actionRef.current.send(
          "Run the " + slug + " playbook for the selected date scope.",
          slug,
        ),
      onDocument: (path) => actionRef.current.openDoc(path),
      onFollowUp: (text) => actionRef.current.send(text),
      onFeedback: (id, rating) => actionRef.current.feedback(id, rating),
    }),
    [],
  );
  if (workspace)
    return (
      <div className="workspace-shell">
        <button className="back-chat" onClick={() => setWorkspace(false)}>
          <ArrowLeft size={15} /> Back to chat
        </button>
        <Workspace />
      </div>
    );
  const messages = conversation?.messages || [];
  const statusLabel = !status
    ? "Checking workspace…"
    : status.load_failed
      ? "Workspace unavailable"
      : status.agent_ready
        ? "Model configured"
        : "Local playbooks";
  const modes = [
    [
      "auto",
      "Auto",
      "The analyst chooses tools and can call Hypothesis, EDA and RCA specialists.",
    ],
    [
      "deep",
      "Deep investigation",
      "The primary analyst investigates deeply and calls specialists when useful. Uses more model calls.",
    ],
  ];
  return (
    <div className={"chat-app " + (!sidebar ? "sidebar-hidden" : "")}>
      {sidebar && (
        <button
          className="mobile-sidebar-backdrop"
          aria-label="Close sidebar"
          onClick={() => setSidebar(false)}
        />
      )}
      <aside className="chat-sidebar" aria-label="Chat navigation">
        <div className="chat-brand">
          <span className="chat-logo">
            <Triangle size={21} fill="currentColor" />
          </span>
          <b>Retail Analyst</b>
          <button aria-label="Hide sidebar" onClick={() => setSidebar(false)}>
            <PanelLeftClose size={18} />
          </button>
        </div>
        <button className="new-chat" onClick={newChat}>
          <SquarePen size={18} />
          New chat
        </button>
        <div className="chat-search">
          <Search size={15} />
          <input
            aria-label="Search conversations"
            placeholder="Search chats"
            value={chatSearch}
            onChange={(e) => setChatSearch(e.target.value)}
          />
        </div>
        <div className="chat-tools">
          <button
            onClick={() => {
              dismissMobileSidebar();
              setWorkspace(true);
            }}
          >
            <ChartNoAxesCombined size={17} />
            Data workspace
            <ArrowRight size={13} />
          </button>
          <button onClick={openBank}>
            <Lightbulb size={17} />
            Hypothesis bank<span>{status?.hypothesis_count || 18}</span>
          </button>
        </div>
        <div className="chats-label">Your conversations</div>
        <div className="conversation-list">
          {conversations
            .filter((c) =>
              c.title.toLowerCase().includes(chatSearch.toLowerCase()),
            )
            .map((c) => (
              <button
                key={c.id}
                className={conversation?.id === c.id ? "active" : ""}
                aria-current={conversation?.id === c.id ? "page" : undefined}
                title={c.title}
                onClick={() => load(c.id)}
              >
                <MessageSquare size={14} />
                <span>{c.title}</span>
              </button>
            ))}
          {!conversations.length && <p>Your conversations are saved here.</p>}
          {!!conversations.length &&
            !conversations.some((c) =>
              c.title.toLowerCase().includes(chatSearch.toLowerCase()),
            ) && <p>No chats match your search.</p>}
        </div>
        <div className="chat-sidebar-bottom">
          <button onClick={() => setModal("settings")}>
            <Settings2 size={17} />
            <div>
              Model & workspace
              <small>
                {!status || status.load_failed
                  ? statusLabel
                  : status.agent_ready
                    ? status.model
                    : "Connect a model to ask anything"}
              </small>
            </div>
          </button>
          <div className="local-foot">
            <span /> Local app · synthetic retail data
          </div>
        </div>
      </aside>
      <section className="chat-main">
        <header className="chat-header">
          <div>
            {!sidebar && (
              <button
                aria-label="Show sidebar"
                onClick={() => setSidebar(true)}
              >
                <PanelLeftOpen size={20} />
              </button>
            )}
            <button className="model-name" onClick={() => setModal("settings")}>
              Retail Analyst <ChevronDown size={15} />
            </button>
            <span className="chat-mode-pill">{statusLabel}</span>
          </div>
          <div>
            <button className="scope-toggle" onClick={openScope}>
              <SlidersHorizontal size={15} />
              Data scope
            </button>
            {conversation && (
              <button
                title="Rename chat"
                aria-label="Rename chat"
                onClick={() => {
                  setRename(conversation.title);
                  setModal("rename");
                }}
              >
                <Pencil size={16} />
              </button>
            )}
            {conversation && (
              <>
                <button
                  title="Export full conversation Markdown"
                  aria-label="Export full conversation Markdown"
                  disabled={exportBusy}
                  onClick={exportConversation}
                >
                  {exportBusy ? (
                    <LoaderCircle size={17} className="spin" />
                  ) : (
                    <Download size={17} />
                  )}
                </button>
                <button
                  title={
                    busy
                      ? "Stop the analysis before deleting this chat"
                      : "Delete chat"
                  }
                  aria-label="Delete chat"
                  disabled={busy}
                  onClick={() => setModal("delete")}
                >
                  <Trash2 size={17} />
                </button>
              </>
            )}
            <button
              className="chat-avatar"
              aria-label="Model and workspace settings"
              onClick={() => setModal("settings")}
            >
              SF
            </button>
          </div>
        </header>
        <div
          className="chat-scroll"
          ref={scroll}
          onScroll={() => {
            const el = scroll.current;
            followScroll.current =
              el.scrollHeight - el.scrollTop - el.clientHeight < 120;
          }}
        >
          <div className="chat-transcript">
            {conversation?.has_older && (
              <div className="earlier-messages">
                <button disabled={earlierBusy} onClick={loadEarlier}>
                  {earlierBusy ? "Loading…" : "Load earlier messages"}
                </button>
              </div>
            )}
            {!messages.length && !busy ? (
              <div className="chat-empty">
                <div className="welcome-symbol">
                  <Triangle size={32} fill="currentColor" />
                </div>
                <h1>What would you like to understand?</h1>
                <p>
                  Ask your retail data. Explore an idea. Follow the evidence.
                </p>
                <div className="prompt-grid">
                  {[
                    [
                      ChartNoAxesCombined,
                      "Understand performance",
                      "How are sales doing, and what explains the change?",
                    ],
                    [
                      GitBranch,
                      "Investigate a change",
                      "Why is merchandise margin different from last year? Test the competing explanations.",
                    ],
                    [
                      FlaskConical,
                      "Explore the data",
                      "Explore category sales and returns. Which patterns deserve a closer look?",
                    ],
                    [
                      Lightbulb,
                      "Test a hypothesis",
                      "Is product mix or realized price contributing more to sales growth?",
                    ],
                  ].map(([Icon, label, q]) => (
                    <button key={label} onClick={() => send(q)} disabled={busy}>
                      <Icon size={20} />
                      <strong>{label}</strong>
                      <span>{q}</span>
                    </button>
                  ))}
                </div>
                <div className="agent-capabilities">
                  <span>
                    <Lightbulb size={13} />
                    Hypothesis agent
                  </span>
                  <span>
                    <FlaskConical size={13} />
                    EDA & statistics
                  </span>
                  <span>
                    <GitBranch size={13} />
                    RCA agent
                  </span>
                </div>
              </div>
            ) : (
              messages.map((m) =>
                m.role === "user" ? (
                  <div className="user-message" key={m.id}>
                    <div>{m.text}</div>
                  </div>
                ) : (
                  <MemoAnswer key={m.id} message={m} {...answerActions} />
                ),
              )
            )}
            {busy && (
              <div className="chat-working" role="status">
                <div className="answer-avatar">
                  <LoaderCircle size={19} className="spin" />
                </div>
                <div>
                  <b>{progress || "Working on your question"}</b>
                  <span>
                    Inspecting context, testing ideas, and collecting evidence.
                  </span>
                </div>
              </div>
            )}
            {error && (
              <div className="chat-error" role="alert">
                <span>{error}</span>
                <button onClick={() => setError("")} aria-label="Dismiss error">
                  <X size={16} />
                </button>
              </div>
            )}
            {!busy && retryRequest && (
              <div className="retry-question">
                <span>The last question has no completed answer.</span>
                <button
                  onClick={() =>
                    send(retryRequest.question, null, null, retryRequest)
                  }
                >
                  <RotateCcw size={15} />
                  Retry question
                </button>
              </div>
            )}
            <div ref={bottom} />
          </div>
        </div>
        <div className="chat-compose-area">
          <div className="chat-compose-inner">
            <div className="scope-summary">
              <Database size={12} />
              <span>
                {scope.start} – {scope.end} · comparison {scope.compare_start} –{" "}
                {scope.compare_end}
              </span>
              <button onClick={openScope}>Change</button>
            </div>
            <form
              className="chat-composer"
              onSubmit={(e) => {
                e.preventDefault();
                send();
              }}
            >
              <textarea
                ref={input}
                aria-label="Message Retail Analyst"
                placeholder="Ask anything about your retail data…"
                value={question}
                maxLength={8000}
                rows={2}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => {
                  if (
                    e.key === "Enter" &&
                    !e.shiftKey &&
                    !e.nativeEvent.isComposing
                  ) {
                    e.preventDefault();
                    send();
                  }
                }}
              />
              <div className="composer-bottom">
                <select
                  aria-label="Investigation mode"
                  value={mode}
                  onChange={(e) => setMode(e.target.value)}
                >
                  {modes.map(([id, label]) => (
                    <option key={id} value={id}>
                      {label}
                    </option>
                  ))}
                </select>
                <span>
                  {mode === "deep"
                    ? "Evidence-led investigation"
                    : "Specialists available as needed"}
                </span>
                {busy ? (
                  <button
                    type="button"
                    title={
                      stopping
                        ? "Stopping analysis"
                        : activeJob
                          ? "Stop analysis"
                          : "Preparing request"
                    }
                    aria-label={
                      stopping ? "Stopping analysis" : "Stop analysis"
                    }
                    disabled={!activeJob || stopping}
                    onClick={stop}
                  >
                    {stopping || !activeJob ? (
                      <LoaderCircle size={19} className="spin" />
                    ) : (
                      <Square size={14} fill="currentColor" />
                    )}
                  </button>
                ) : (
                  <button
                    type="submit"
                    aria-label="Send message"
                    disabled={!question.trim()}
                  >
                    <ArrowUp size={21} />
                  </button>
                )}
              </div>
            </form>
            <p className="chat-disclaimer">
              {!status
                ? "Checking your model and local retail data…"
                : status.load_failed
                  ? "The workspace status could not be loaded. Refresh after starting the local app."
                  : status.agent_ready
                    ? "AI can make mistakes. Check evidence and SQL. Relevant data is sent to your configured OpenAI model."
                    : "Connect a model for open-ended answers. Local playbooks work now. Hypotheses are explanations to test, not facts."}
            </p>
          </div>
        </div>
      </section>
      {toast && (
        <div className="chat-toast" role="status">
          <Check size={16} />
          {toast}
        </div>
      )}
      {(modal || doc) && (
        <div
          className="chat-modal-overlay"
          onClick={() => {
            setModal(null);
            setDoc(null);
          }}
        >
          <div
            ref={dialog}
            className={"chat-modal " + (modal === "bank" || doc ? "wide" : "")}
            role="dialog"
            aria-modal="true"
            aria-label={doc ? "Source document" : modal}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="chat-modal-header">
              <h2>
                {doc
                  ? doc.path
                  : modal === "settings"
                    ? "Your local analyst"
                    : modal === "scope"
                      ? "Set the analysis scope"
                      : modal === "rename"
                        ? "Rename conversation"
                        : modal === "delete"
                          ? "Delete conversation?"
                          : "Hypothesis bank"}
              </h2>
              <button
                aria-label="Close dialog"
                onClick={() => {
                  setModal(null);
                  setDoc(null);
                }}
              >
                <X size={20} />
              </button>
            </div>
            {modalError && (
              <div className="chat-error" role="alert">
                <span>{modalError}</span>
              </div>
            )}
            {doc ? (
              <pre>{doc.text}</pre>
            ) : modal === "settings" ? (
              <>
                <p>
                  This app combines your retail data and playbooks with
                  conversational analysis, hypothesis development, exploratory
                  analysis, and RCA.
                </p>
                <div className="settings-status">
                  <span className="status-dot" />
                  <b>
                    {!status || status.load_failed
                      ? statusLabel
                      : status.agent_ready
                        ? "Model configured"
                        : "Open-ended reasoning needs a model"}
                  </b>
                  <span>
                    {!status
                      ? "Please wait"
                      : status?.model || "Not configured"}
                  </span>
                </div>
                <p>
                  Set these values in <code>retail_app/.env</code>, then restart
                  the app. Keep your key private.
                </p>
                <pre>
                  OPENAI_API_KEY=your-key{"\n"}OPENAI_MODEL=your-model-id
                </pre>
                <p className="small">
                  Without credentials, questions suggest local playbooks. With
                  credentials, the agents can inspect schema, write read-only
                  SQL, perform EDA/statistics, test hypotheses, create charts
                  and retain conversation context.
                </p>
                <div className="settings-agents">
                  <span>
                    <Lightbulb size={17} />
                    Hypothesis Agent
                  </span>
                  <span>
                    <FlaskConical size={17} />
                    EDA Agent
                  </span>
                  <span>
                    <GitBranch size={17} />
                    RCA Agent
                  </span>
                </div>
                <p className="small">
                  Your warehouse stays read-only. The app sends relevant context
                  and query results to OpenAI only when the reasoning model is
                  configured. This is a local single-user workspace.
                </p>
              </>
            ) : modal === "scope" ? (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  if (
                    scopeDraft.start > scopeDraft.end ||
                    scopeDraft.compare_start > scopeDraft.compare_end ||
                    scopeDraft.compare_end >= scopeDraft.start ||
                    scopeDraft.compare_start < "2024-01-01" ||
                    scopeDraft.end > "2025-12-31" ||
                    new Date(scopeDraft.end) - new Date(scopeDraft.start) !==
                      new Date(scopeDraft.compare_end) -
                        new Date(scopeDraft.compare_start)
                  ) {
                    setModalError(
                      "Choose equal-length, nonoverlapping periods within 2024–2025.",
                    );
                    return;
                  }
                  setScope({ ...scopeDraft });
                  setModal(null);
                }}
              >
                <p>
                  Sales end December 2025. These dates are the default context;
                  explicit dates in a question can override them.
                </p>
                <div className="chat-date-grid">
                  {[
                    ["start", "Current start"],
                    ["end", "Current end"],
                    ["compare_start", "Comparison start"],
                    ["compare_end", "Comparison end"],
                  ].map(([k, l]) => (
                    <label key={k}>
                      {l}
                      <input
                        type="date"
                        value={scopeDraft[k]}
                        required
                        min="2024-01-01"
                        max="2025-12-31"
                        onChange={(e) =>
                          setScopeDraft({ ...scopeDraft, [k]: e.target.value })
                        }
                      />
                    </label>
                  ))}
                </div>
                <button className="chat-primary">Apply scope</button>
              </form>
            ) : modal === "rename" ? (
              <form
                onSubmit={async (e) => {
                  e.preventDefault();
                  try {
                    setModalBusy(true);
                    await api("/conversations/" + conversation.id + "/rename", {
                      title: rename.trim(),
                    });
                    setConversation({ ...conversation, title: rename.trim() });
                    await refresh();
                    setModal(null);
                  } catch (e) {
                    setModalError(e.message);
                  } finally {
                    setModalBusy(false);
                  }
                }}
              >
                <input
                  aria-label="Conversation title"
                  className="chat-text-input"
                  value={rename}
                  onChange={(e) => setRename(e.target.value)}
                  required
                  maxLength={100}
                />
                <button
                  className="chat-primary"
                  disabled={modalBusy || !rename.trim()}
                >
                  Save title
                </button>
              </form>
            ) : modal === "delete" ? (
              <>
                <p>
                  Delete “{conversation?.title}” from your saved chats? This
                  permanently removes its conversation history. Export a copy
                  first if you want to keep it.
                </p>
                <div className="dialog-actions">
                  <button
                    className="chat-secondary"
                    disabled={modalBusy}
                    onClick={() => setModal(null)}
                  >
                    Keep chat
                  </button>
                  <button
                    className="chat-primary destructive"
                    disabled={modalBusy}
                    onClick={deleteConversation}
                  >
                    {modalBusy ? "Deleting…" : "Delete chat"}
                  </button>
                </div>
              </>
            ) : (
              <>
                <p>
                  A starter bank tailored to the available retail dataset. These
                  are candidate explanations with tests and falsifiers, not
                  validated conclusions.
                </p>
                <div className="chat-search bank-search">
                  <Search size={15} />
                  <input
                    aria-label="Search hypothesis bank"
                    value={bankQuery}
                    onChange={(e) => setBankQuery(e.target.value)}
                    placeholder="Search hypotheses…"
                  />
                </div>
                <div className="hypothesis-bank">
                  {!bank && <p role="status">Loading retail hypotheses…</p>}
                  {bank?.hypotheses
                    .filter((h) =>
                      JSON.stringify(h)
                        .toLowerCase()
                        .includes(bankQuery.toLowerCase()),
                    )
                    .map((h) => (
                      <div key={h.id} className="hypothesis-card">
                        <span>{h.domain} · untested template</span>
                        <h3>{h.hypothesis}</h3>
                        <p>
                          <b>Test:</b> {h.test}
                        </p>
                        <p>
                          <b>Would challenge it:</b> {h.falsifier}
                        </p>
                        <p>
                          <b>Limits:</b> {h.limitation}
                        </p>
                        <small>{h.evidence}</small>
                        <div className="hypothesis-actions">
                          <button
                            disabled={busy}
                            onClick={() => {
                              setModal(null);
                              send(
                                "Run the evidence test: " + h.hypothesis,
                                null,
                                h.id,
                              );
                            }}
                          >
                            Run data test <Database size={14} />
                          </button>
                          <button
                            onClick={() => {
                              setMode("deep");
                              setQuestion(
                                "Test this hypothesis: " +
                                  h.hypothesis +
                                  " Use this proposed test: " +
                                  h.test,
                              );
                              setModal(null);
                              input.current?.focus();
                            }}
                          >
                            Investigate deeply <ArrowRight size={14} />
                          </button>
                        </div>
                      </div>
                    ))}
                </div>
                <p className="small">{bank?.provenance}</p>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
export { ChatApp, Answer, Rich };
if (typeof document !== "undefined")
  createRoot(document.getElementById("root")).render(
    <AppErrorBoundary>
      <ChatApp />
    </AppErrorBoundary>,
  );
