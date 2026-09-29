"""Render the shareable, code-native overview SVG; no external assets required."""
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
parts = ['''<svg xmlns="http://www.w3.org/2000/svg" width="1800" height="1550" viewBox="0 0 1800 1550" role="img" aria-labelledby="title desc">
<title id="title">Milky Way 2.0 implemented architecture</title>
<desc id="desc">A local React interface connects through FastAPI and bounded jobs to one LangGraph Retail Agent and the OpenAI Responses API. Twenty-seven tools access context, SQLite memory and read-only DuckDB. Measured evidence is validated, rendered and saved atomically.</desc>
<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 Z" fill="#64748b"/></marker></defs>
<style>text{font-family:Arial,Helvetica,sans-serif;fill:#172b40}.title{font-size:34px;font-weight:700}.subtitle{font-size:19px;fill:#536478}.label{font-size:16px;letter-spacing:1.3px;font-weight:700}.heading{font-size:23px;font-weight:700}.body{font-size:18px}.small{font-size:16px;fill:#536478}.edge{fill:none;stroke:#64748b;stroke-width:2.2;marker-end:url(#arrow)}.both{marker-start:url(#arrow)}</style>
<rect width="1800" height="1550" fill="#f5f7fb"/>
<text x="55" y="52" class="title">Milky Way 2.0 · Implemented system architecture</text>
<text x="55" y="83" class="subtitle">One Retail Agent · 27 tools · versioned domain workspace · isolated evaluations · measured evidence</text>
<rect x="45" y="108" width="1280" height="1325" rx="22" fill="#ffffff" stroke="#ccd8e4" stroke-width="2"/>
<text x="70" y="136" class="label" fill="#42627b">TRUSTED LOCAL MACHINE · SINGLE USER · PORT 8766</text>
''']


def text(x, y, value, cls="body"):
    parts.append(f'<text x="{x}" y="{y}" class="{cls}">{escape(value)}</text>')


def box(x, y, w, h, title, lines, fill="#fff", stroke="#ccd8e4", tag=None):
    parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>')
    offset = 32
    if tag:
        text(x+20, y+28, tag, "label")
        offset = 62
    text(x+20, y+offset, title, "heading")
    for i, line in enumerate(lines):
        text(x+20, y+offset+33+i*27, line)


def edge(path, both=False):
    parts.append(f'<path d="{path}" class="edge{" both" if both else ""}"/>')


box(80,155,1210,95,"React chat + Improve workspace",[
    "Chat + shared controls · Deferred admin modules · Knowledge · Skills · Answer design · Evaluations · Releases"
],fill="#edf5ff",stroke="#9dbce0")
box(80,315,350,135,"FastAPI application",["Bounded HTTP intake; local controls","Chat / jobs / history / investigation","API and public guide references"],fill="#eef4fa")
box(475,315,345,135,"Bounded job execution",["2 chat workers + 1 evaluation worker","Stop / Retry; bounded job deadlines","Frozen release; revision-checked saves"],fill="#eef4fa")
box(870,315,420,135,"One Retail Agent",["LangGraph: agent ↔ tools loop","Plan scope → inspect → query → correct","Explanation / analysis / investigation"],fill="#e7f0ff",stroke="#7f9fcc")
box(1415,315,330,135,"OpenAI Responses API",["Configured model; HTTPS","Bounded context / evidence preview","Key held by local backend"],fill="#f4edff",stroke="#b6a0d1")

box(80,555,350,330,"Frozen context snapshots",[
    "26 imported baseline documents",
    "Published ontology + knowledge",
    "19 stable-ID skills + custom methods",
    "3 profiles + versioned examples",
    "Original source bodies and hashes",
    "Lexical, section-aware retrieval",
    "D# references with exact version",
    "Evaluation goldens excluded"
],fill="#f0f8f5",stroke="#9ac3b4",tag="REFERENCE KNOWLEDGE")
box(475,555,345,330,"27 registered tools",[
    "6 context / inspection interfaces",
    "5 query / analysis interfaces",
    "10 investigation / test interfaces",
    "1 scope-planning interface",
    "2 memory interfaces",
    "3 visual / answer interfaces",
    "Validated scope and SQL boundaries",
    "Allowlist + strict argument contracts"
],fill="#edf4ff",stroke="#a2bad9",tag="ACTIVE CAPABILITIES")
box(870,555,420,330,"SQLite state and memory",[
    "Chats, answers and explicit memories",
    "Session scope + investigation state",
    "Mutable drafts with revision checks",
    "Immutable asset versions + releases",
    "Active pointer + activation history",
    "Structured feedback and regressions",
    "Evaluation outputs + review records",
    "No automatic training or full recall"
],fill="#fff7e9",stroke="#d9bf8f",tag="PERSISTENT LOCAL STATE")

box(80,995,350,140,"Read-only DuckDB",[
    "23 tables · 5 million transactions",
    "10.995 million merchandise lines",
    "Synthetic data + Parquet exports"
],fill="#f0f8f5",stroke="#9ac3b4")
box(475,995,345,140,"Evidence and presentation",[
    "E# rows + SQL + parameters + scope",
    "Measured values and chart checks",
    "Profile display; evidence preserved"
],fill="#edf4ff",stroke="#a2bad9")
box(870,995,420,140,"Atomic answer completion",[
    "Save answer + message + job result",
    "Reject obsolete scope / investigation",
    "Record release, skill, profile, sources"
],fill="#fff7e9",stroke="#d9bf8f")

# Edges are routed through gutters, outside text boxes.
edge("M255 250 V315")
text(274,288,"HTTP and job polling", "small")
edge("M430 382 H475")
edge("M820 382 H870")
edge("M1290 382 H1415",True)
text(1337,365,"HTTPS", "small")
edge("M920 450 C920 500 750 495 750 555",True)
text(742,491,"tool calls / results", "small")
edge("M430 708 H475",True)
edge("M820 708 H870",True)
edge("M550 885 V936 H255 V995")
text(98,925,"Bound dates, filters and query limits", "small")
edge("M430 1062 H475")
edge("M650 995 V885")
text(670,944,"measured results", "small")
edge("M820 1062 H870")
edge("M1080 995 V885",True)
text(1100,944,"persistent records", "small")

parts.append('<rect x="1390" y="505" width="380" height="590" rx="18" fill="#ffffff" stroke="#ccd8e4"/>')
text(1410,535,"SAME LOCAL APP PROCESS", "label")
box(1415,555,330,230,"Evaluation workbench",[
    "Frozen baseline vs candidate",
    "76 bundled runtime contracts",
    "Temporary conversation / memories",
    "Separate bounded worker + queue",
    "Optional live calls require consent",
    "Persist outputs, limits and review"
],fill="#f0f8f5",stroke="#9ac3b4")
box(1415,825,330,230,"Meaningful boundaries",[
    "Local operator; no login roles",
    "Methods use approved tools only",
    "Untrusted context stays in input",
    "Deterministic pass is not semantic QA",
    "No model judge or causal proof",
    "No external ingestion / tenancy"
],fill="#ffffff")
text(80,1160,"Generation is offline; warehouse access stays read-only. Evaluation expectations never become answer context.","small")
box(80,1230,350,160,"1. Author and preview",[
    "Save drafts with expected revision",
    "Check mappings and dependencies",
    "Preview sources and measured output",
    "Freeze an immutable candidate"
],fill="#edf5ff",stroke="#9dbce0")
box(475,1230,345,160,"2. Evaluate and review",[
    "Run complete core + custom checks",
    "Inspect changes, failures, coverage",
    "Record reviewer and rationale",
    "Failed hard checks block release"
],fill="#f0f8f5",stroke="#9ac3b4")
box(870,1230,420,160,"3. Publish or restore",[
    "Recheck candidate and runtime hashes",
    "Atomically switch active release",
    "Next answer captures new snapshot",
    "Earlier answers keep their provenance"
],fill="#fff7e9",stroke="#d9bf8f")
edge("M430 1310 H475")
edge("M820 1310 H870")
text(55,1480,"Milky Way 2.0 · Application release 2.1.1 · Implemented September 26, 2026", "small")
text(55,1510,"User/admin guide, low-level design, complete feature status, data summary and release evidence: retail_app/docs/developer/", "small")
parts.append("</svg>")
(HERE / "system-architecture.svg").write_text("\n".join(parts))
