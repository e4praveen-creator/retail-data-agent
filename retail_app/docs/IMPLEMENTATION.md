# Implementation and source map

## Architecture

React interface → FastAPI → existing deterministic playbook runner **or** one primary Retail Analyst LangGraph reasoning/tool loop → read-only DuckDB. A local section-aware lexical index retrieves source excerpts; SQLite stores completed analyses and confirmed notes. The primary analyst may call Hypothesis, EDA and RCA specialists as tools. They cannot recursively delegate. The original primary-agent architecture is preserved; the Milky Way deck does not introduce a mandatory agent chain.

Core agent tools: `search_data_context`, `inspect_dataset`, `execute_sql`, `get_metric`, `run_playbook`, `analyze_result`, `search_memory`, `create_visualization`. Publishing/export is an app action. Durable memory writes are explicit user actions with a source, rather than unverified model self-instruction.

Additional tools provide an 18-entry dataset-specific hypothesis bank and executable tests, column EDA, statistical comparisons, and optional specialist calls. `get_playbook_design` loads the matching source-derived output contract; `present_answer` validates the structured answer and its measured evidence references. Both are ordinary tools within the same primary loop.

The graph uses one `agent` node and one `tools` node in a bounded loop. Failed queries return diagnostic errors to the same model. The primary and specialist calls share the call budget, measured evidence ledger and document source ledger. Deep investigation changes guidance within this architecture; it does not introduce a mandatory specialist sequence.

Completed answers, multi-turn messages, notes, feedback and chat-job status persist in SQLite. Progress is polled. Jobs can be cooperatively cancelled and are marked interrupted on restart rather than silently resumed. There is no durable interrupt/resume checkpointing or token streaming.

## Frontend and conversation lifecycle

The prebuilt React UI uses system fonts, black text, neutral surfaces and responsive layouts. It retains the separate data workspace with all original baseline recipes. Markdown supports tables while suppressing raw HTML and automatic remote images. Only known evidence/source IDs receive clickable reference controls. Answer components are memoized so drafting a new question does not redraw old chart components. Keyboard dialogs trap focus, close with Escape and restore focus; these code paths have not received real browser acceptance testing.

Chat actions include new/search/rename/delete, Stop, Retry, feedback, source inspection and analysis exports. Deletion is confirmed in the UI and refused by the backend while a job is active. Eligible retries reuse the unanswered user message. Default history pages contain up to 50 messages and are bounded by payload size; an older-message cursor retrieves prior pages. Conversation export collects every preceding page before writing Markdown. This does not export every evidence row; individual analysis JSON and evidence CSV provide the data exports.

The model receives the newest available conversation messages within a bounded character budget, up to 12 messages. Long older content cannot evict a newer correction merely because it appears earlier in serialized history. This is bounded context, not unlimited conversational memory.

## Source-derived answer presentation

`backend/presentation.py` reads all 19 normalized A–I playbooks and the matching detailed visual-specification chapters. The contract supplies required data, method, guardrails, the E output template, F visual design, H interpretation and I follow-ups, with source locations. It is delivered through `get_playbook_design`; the model supplies headline, scope, metric basis, interpretation, limitations, next questions and supporting evidence IDs through `present_answer`. Invalid or absent evidence IDs are rejected. Model narrative still requires claim-level review.

`frontend/answer-report.jsx` renders the seven sections in their documented order, placing the primary visual and a selectable measured table directly between scope and interpretation. Single-row totals become metric cards. A documentation-only or unsupported causal answer has no fabricated chart. If the model does not supply the structured contract, the fallback layout is identified; available measured rows may supply a conservative automatic visual. This fallback does not assert that the full playbook method was executed.

`frontend/playbook-charts.jsx` implements the 19 primary visual treatments using evidence returned by the analytical tools. `backend/visual_data.py` adds bounded, parameterized read-only datasets alongside the unchanged original runner outputs. These include deduplicated scorecard totals, channel/POS-store growth and margin, a selected campaign's affected-scope weekly timeline, actual/regular price distributions, monthly loyalty and fulfillment mix, return-cohort cells and reason totals, seven-metric segment profiles, monthly customer states, and inventory stock/flows.

The added queries preserve fact grains before joins: header metrics are aggregated independently from sale-line/cohort metrics, buyer reach excludes key 0 and deduplicates across divisions, return cells use original sold-unit denominators, and inventory balances remain separate snapshots. Source SQL, parameters, exact values and truncation are saved as evidence. They do not imply a causal effect or complete every secondary narrative workflow. [OUTPUT_DESIGN.md](OUTPUT_DESIGN.md) details coverage and scope boundaries.

## Evidence integrity and execution boundaries

- `E#` identifies measured query or calculation evidence; `D#` identifies retrieved document chunks. The shared source ledger deduplicates by source and line. Specialists can inspect evidence already collected by the primary analyst.
- Arithmetic comparisons reference an existing evidence ID, row and numeric column for both operands. The deterministic helper records source IDs and computes the difference/percentage change; supplied numeric operands are rejected. Matching units, grain and metric definitions still require review.
- Citation checks mark IDs absent from the run's evidence/source ledger as unverified and add a visible limitation. Existing IDs do not prove that the associated claim is true, relevant or causal.
- Model SQL is parsed to reject disconnected joins and header additive measures carried through sales-line expansion, including common CTE/subquery aliases. This is a conservative guard against observed errors, not a complete foreign-key, cardinality or grain proof. Current channel/division labels and canonical line-level metric joins are supplied from the warehouse; small dimensions return complete bounded samples.
- Structured previews are bounded before model transmission without cutting serialized JSON mid-object. The saved result retains its permitted query output and exposes model-preview truncation separately.
- Model SQL must parse as one SELECT. A narrow AST guard rejects disconnected joins and the invalid direct sales-line-to-channel path. It can reject unsupported valid structures for correction; it does not validate every foreign key, join cardinality, aggregation grain or analytic assumption.
- DuckDB is read-only with external access disabled, two threads and a 1 GB memory limit per connection. A two-session semaphore has bounded waiting. Queries are interruptible on cancellation/deadline; custom SQL has row, byte, column and cell limits. Baseline recipes retain their own validated SQL and longer time/row limits.
- At most two analyses are admitted concurrently. A five-minute job deadline and shared model-call budget bound investigations. Stop interrupts supported warehouse reads and retry waits; an already in-flight provider request can finish at its bounded timeout.
- Provider connections are reused, transient failures have bounded retries, and completed results record model-call/request/token counts. Those counters are observability, not billing enforcement.

## Runtime, state and deployment

Python 3.12 in `.venv-runtime` is preferred by `start.sh`; the dependency lock covers direct and transitive runtime dependencies. An older `.venv` is only a fallback and must still match compatible requirements. Node is needed only to rebuild the frontend. The launch script uses one application process with bounded HTTP concurrency.

FastAPI validates trusted hosts, local mutation origins and a required app header. Request bodies are bounded; range requests are rejected for bundled assets. Security headers restrict scripts, framing and external connections. Error responses are sanitized and assigned request IDs; logs omit raw request bodies and provider error text. Liveness and readiness endpoints distinguish the running process from local data/state access. These safeguards do not supply user authentication, access roles or tenant isolation.

The default state is `retail_app/state/app.sqlite3`. Manual backups use SQLite's consistent backup API and integrity verification, create files exclusively, and omit API keys/warehouse/configuration. Backup scheduling and restore verification remain deployment work.

The Docker definition uses Python 3.12, a non-root user, a read-only root filesystem, bounded temporary storage, dropped capabilities and loopback host publishing. Its named `retail-state` volume is separate from the local Mac state directory; it must not be assumed to contain the same conversations. Docker build/run has not been tested on this host. The supplied macOS LaunchAgent supports local restart/login availability while the computer is running, without promising cloud uptime.

## Referenced assets

| Asset | Use |
|---|---|
| `retail_data/data/full/retail.duckdb` | Actual read-only analytical warehouse |
| `retail_data/data/full/manifest.json` | Dataset identity, coverage and generated scale |
| `retail-data-analyst/scripts/run_analysis.py` | All 19 executable baseline recipes and exact Shapley PVM |
| `retail-data-analyst/references/playbooks.md`, `retail_playbook_library.md` | All 19 A–I goals, methods, output templates, caveats and follow-ups; normalized source supplies runtime presentation contracts |
| `retail-data-analyst/references/question-router.md` | Supported questions and data-gap routing |
| `retail-data-analyst/references/visual-specs.md` | Visual guidance and required denominators |
| `retail-data-analyst/references/worked-examples.md` | Historical worked examples; never substituted for fresh query results |
| `retail_data/docs/METRICS.md` | Canonical metrics, grains, return bases and aggregation rules |
| `retail_data/docs/MODEL.md` | Synthetic generation rules and limitations |
| `retail_data/docs/DATA_DICTIONARY.md`, `catalog.json` | Schema and relationships; catalog also exposed directly |
| `retail_data/sql/*.sql` | DDL, semantic views and example SQL |
| `retail_data/src/generate.py`, `catalog.py`, `validate.py`, `reports.py` | Code-based meaning and validation context |
| `retail_data/docs/SOURCES.md`, `DELIVERY_REPORT.md` and four allowlisted validation/integration JSON reports | Provenance and saved named validation checks; never presented as a fresh service validation |
| `retail_app/knowledge/hypotheses.json` | All 18 domain-specific candidate records, tests, falsifiers, scopes and limitations |
| `retail_app/docs/MILKY_WAY_REFERENCE.md` | Relevant deck adaptation with explicit reference-only limits |
| `retail_app/docs/architecture-reference.txt` | The user's pasted architectural proposal, preserved verbatim |

The explicit library contains 26 allowlisted documents. Retrieval preserves Markdown sections, metric/router table rows, hypothesis records and individual validation checks, with heading, role, exact source lines and interpretation notes. BM25-style word relevance, retail aliases and intent weighting prioritize useful domain material; duplicate snippets and per-source limits prevent copies from crowding out supporting definitions. Normal search returns at most six snippets, with a maximum of twelve and an 18,000-character text/heading budget. The static catalog and runtime schema inspection complement documents; no external embedding service is required. Restart to refresh the index. The app does not modify source documents or dataset files; secrets, state and raw customer rows are excluded. [DOMAIN_ASSETS.md](DOMAIN_ASSETS.md) records actual integration and context gaps.

## Verification and comparison contract

Named recipes bind dates as parameters. Dates must fall in the actual sales range, be equal-length and nonoverlapping. The inventory headline ignores the scope start for its single as-of snapshot; its added historical panel includes only complete Monday–Sunday buckets inside the selected current period. Customer recency uses all observed history through the end date, and monthly states inspect history through each observation cutoff using a global 90-day rule. Promotion timelines retain the selected current window rather than silently extending it; not every campaign has complete pre/post observations. Actual-versus-regular pricing uses the same selected sale rows, not an assumed prior-period comparison. These exceptions and bases are labeled.

Independent golden checks use header totals or raw fact joins that differ from the corresponding baseline views. PVM reconciles against the header-based headline change. Margin reconciles from original line sales/COGS and separately aggregated return deductions/recovered costs. Inventory selects one maximum completed snapshot. Customer counts exclude key 0.

## Component coverage against the proposal

| Blueprint area | Current state |
|---|---|
| Foundation / local deployment | React, FastAPI, Python 3.12 runtime, launch service, bounded jobs and health endpoints; Docker supplied but unverified |
| Synthetic enterprise | Existing curated model/generator; raw ingestion and truth-labeled incidents absent |
| Context engine | Section-aware domain retrieval, complete retail hypothesis/catalog metadata, source roles, metric/visual contracts, runtime inspection and confirmed notes; no production usage mining or formal lineage |
| Data tools | Original eight core tools plus hypothesis/EDA/statistics and playbook design/presentation tools; SELECT-only queries, narrow join guard, external access disabled and bounded execution |
| Agent / correction | Single-model LangGraph loop with live smoke checks; bounded rate-limit recovery and persisted calculation evidence |
| Workflows | All 19 unchanged baseline recipes with added chart evidence and seven-part answers; full A–I extensions and some secondary diagnostics remain partial |
| Product experience | Black-text conversational UI, Stop/Retry, confirmed deletion, paginated history, full-chat Markdown and per-analysis exports, charts, source links, catalog and gaps |
| Quality | Real-dataset regressions, independent golden SQL, an opt-in natural-language harness and representative live checks; broader claim/semantic evaluation and browser acceptance pending |
| Packaging | Built static assets and local scripts; no Node runtime needed after build |

## Validation limits

[TEST_REPORT.md](TEST_REPORT.md) records actual checks and results. Browser visual/click-through QA is blocked by the administrator-enforced browser policy verification step; server rendering does not substitute for it. The feature comparison in [FEATURE_COVERAGE.md](FEATURE_COVERAGE.md) is scoped to relevant analysis workflows and explicitly lists missing ChatGPT-like capabilities. The app remains a local single-user implementation, not a public production service or a complete ChatGPT clone.
