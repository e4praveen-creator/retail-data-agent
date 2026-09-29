# Retail Analyst — a local conversational data app

A ChatGPT-style local interface over the existing Summit Field synthetic warehouse, with black system typography, persistent conversations, follow-up questions, playbook-shaped answers with visible charts and supporting tables, inspectable SQL/evidence, and 19 executable retail playbooks. This is a hardened **local single-user app**; it is not a claim of complete ChatGPT feature parity or approval for public deployment. See [feature coverage](docs/FEATURE_COVERAGE.md).

**Architecture preserved:** one primary Retail Data Agent in LangGraph, supported by context, tools and playbooks. Hypothesis, EDA and RCA specialists are callable tools inside that flexible loop. The Milky Way deck is an analytical/UX reference, not a replacement system architecture.

## Start

From the project directory:

```sh
./retail_app/start.sh
```

Open **http://127.0.0.1:8765**. Keep the terminal open; Control-C stops the server. On macOS, `retail_app/Start Retail App.command` also starts it. If already running, open the address rather than launching another instance.

The frontend is prebuilt. Node is not needed to run the app. Python 3.12 is the supported runtime for the current dependency lock. On a new machine:

```sh
python3.12 -m venv .venv-runtime
.venv-runtime/bin/python -m pip install -r retail_app/requirements.lock.txt
./retail_app/start.sh
```

`start.sh` prefers `.venv-runtime`, then falls back to the older `.venv` if present; `RETAIL_PYTHON` can select another compatible interpreter. Install the locked requirements in the runtime you actually start.

Keep the sibling dataset source, playbooks and documents with the app. Generated warehouse files are **not in Git**. Use the existing `retail_data/data/full/retail.duckdb`, or generate it using `retail_data/README.md`. `RETAIL_DB` can point to another warehouse with the same schema and a sibling `manifest.json`.

## Enable open-ended reasoning

Create `retail_app/.env` from `.env.example`:

```text
OPENAI_API_KEY=your-key
OPENAI_MODEL=your-model-id
```

Use a model available to your account that supports Responses API function calling. Restart the server after changing configuration. For the installed macOS service: `.venv-runtime/bin/python retail_app/service.py restart`. Environment variables take precedence over `.env`. The parser reads only allowlisted settings and never executes the file. Credentials are excluded from Git and are never returned to the browser or saved in analysis history.

**No key is configured by default.** Local playbooks and all 18 named hypothesis data tests work without it. Open-ended questions clearly offer baseline suggestions until a model is connected. The app does not impersonate a working LLM or silently apply free-text filters it cannot interpret.

With credentials, relevant questions, source excerpts and bounded query-result previews are sent to OpenAI with `store=false`; query execution stays local. This installation has passed live smoke checks with GPT-5.4 Mini; see `docs/TEST_REPORT.md` for the tested scope. New installations still need their own configuration and checks. Integration follows the [official function-calling guide](https://developers.openai.com/api/docs/guides/function-calling).

Temporary OpenAI rate limits receive up to three bounded retries, with waiting progress shown in chat. Exhausted API quota is reported separately and is not retried. Calculated differences and percentage changes are saved as evidence alongside their input values.

## Chat and investigation

- **New chat / history / rename / delete:** conversations persist in SQLite. Deletion requires confirmation and is refused while its analysis is active. History loads in bounded pages; **Load earlier messages** retrieves the preceding page.
- **Follow-ups:** the newest conversation messages and previous scope are prioritized within a bounded model context. This is not unlimited recall of every message.
- **Stop / Retry:** Stop cooperatively cancels work, including interruptible warehouse queries. An in-flight provider request can take until its bounded timeout to finish. Retry reuses the last unanswered question when eligible.
- **Exports:** individual analyses export JSON or evidence CSV. The chat download retrieves all conversation pages and exports Markdown with answers, specialist findings and SQL references.
- **Auto:** the primary analyst chooses tools and can call specialists when useful.
- **Deep investigation:** requests more thorough hypothesis testing and alternative explanations within the same primary-agent loop. It does not impose a rigid multi-agent pipeline.
- **Hypothesis Agent:** consults the retail bank and proposes falsifiable explanations. Candidate ideas are not facts.
- **EDA Agent:** explores actual distributions, missingness and relevant bivariate patterns, with statistical-design guardrails.
- **RCA Agent:** quantifies measured drivers, tests alternatives and distinguishes accounting contribution from causal evidence.
- **Evidence:** source data, SQL, parameters, checks, traces, specialist findings and exports remain inspectable. Verified reference IDs open the evidence or source document; unknown IDs are marked unverified. Markdown tables render directly in the answer. The Checks view includes model-call/token usage, without estimating price.
- **Feedback:** helpful/review ratings are recorded for human review, without claiming automatic learning or prompt optimization.

The original eight core tools are extended with dataset profiling, statistical analysis, a hypothesis-bank lookup/executor, callable specialists, and source-derived answer-design tools. Specialists cannot recursively spawn other specialists. A shared model-call budget and five-minute job deadline bound the entire investigation, and query errors return to the primary loop for correction. Evidence and document IDs are shared across the primary agent and specialists. Calculated comparisons must reference existing numeric evidence cells; user/model-supplied numbers cannot be promoted directly into measured calculation evidence. Reference validation checks that cited IDs exist, not that each claim is supported or causally valid.

## Retail-specific hypothesis bank

18 candidate hypotheses are grounded in actual Summit Field fields and documented generator rules. Every entry contains required tables, scope, metric basis, an executable test, falsifier and limitation. The bank includes SKU/channel PVM, Q4 markdowns, the App price-book offset, digital Apparel/Footwear returns, damaged-return recovery, cohort margin, anonymous coverage, loyalty attachment, mature repeat, seasonal divisions, private-label classification, campaign eligibility, channel baskets, weekends, fulfillment, stock/velocity, inventory reconciliation and division contribution.

**Run data test** executes a named real-data query without an API key. **Investigate deeply** stages a conversational investigation for the configured model. Query completion does not automatically mark a hypothesis supported. Generator rules are construction assumptions, not discovered causal truths. The bank is not claimed to be Milky Way's historical enterprise library.

## Answers follow your playbook design

Measured analysis is presented in the same seven-part decision structure as the playbook library: **headline → scope and metric → primary visual → supporting values → interpretation → limitations → next question**. The primary visual and an evidence table appear directly in the answer. A single measured total uses metric cards; a documentation-only or unsupported causal question does not receive an invented chart.

The agent reads the matching playbook's output template, visual specification, interpretation and next drills through `get_playbook_design`, then submits evidence-bound sections through `present_answer`. These are tools in the existing primary-agent loop. When a structured presentation is unavailable, the app identifies the fallback layout; a fallback is not a completed playbook analysis.

All 19 playbooks now have a dedicated visual treatment. Examples include reconciled PVM/margin waterfalls, six-metric scorecards, growth-versus-margin channel plots, actual-versus-regular price distributions, campaign timelines, maturity-aware repeat/return heatmaps, monthly customer states and separate inventory stock/flow panels. Additional chart datasets are queried at their correct grains alongside the unchanged original recipes. Exact dates, metric basis, source units and limitations remain visible. See [output design and per-playbook coverage](docs/OUTPUT_DESIGN.md).

The source library now retrieves section-level playbook/visual guidance, metric definitions, all 18 hypothesis records, all 23 catalog tables and saved validation records. Historical worked examples, synthetic construction rules and untested hypotheses are explicitly distinguished from fresh measured findings. [Domain asset integration](docs/DOMAIN_ASSETS.md) lists the actual included assets and remaining context gaps.

Rerun older saved analyses to obtain the added visual datasets. Existing history is not silently recomputed. Named baseline playbooks remain all-business analyses using the date controls; narrower user questions require query evidence and visuals for exactly that requested slice.

## Data workspace

The chat sidebar opens the existing overview, playbook library, knowledge search, confirmed local notes, live catalog, column profiler, and readiness page.

The default comparison is **51 complete retail weeks**, 2025-01-05–2025-12-27 versus 2024-01-07–2024-12-28. This is not the whole calendar year. The model can use explicit dates in a question, with the actual SQL recording its scope; fixed playbook and bank tests use the controls. Omitted details use documented defaults and are disclosed rather than creating a mandatory clarification stage.

- Source money is integer US cents; charts/cards convert aggregates to USD. Evidence tables/CSV keep source units.
- Sales/AOV exclude returns, tax and shipping unless stated otherwise.
- Merchandise margin uses mature original-sale cohorts and excludes operating/fulfillment expenses.
- The original return-reasons table uses return dates; the added cohort-reasons table and elapsed-return heatmap use original sale dates. Their bases are labeled separately.
- Inventory keeps the latest completed snapshot and adds a series of complete Monday–Sunday buckets in the selected period. Ending balances are never summed across weeks.
- Numeric key/code profiles are identifiers, not meaningful continuous measurements.

The 19 baseline recipes plus their added visual evidence cover the primary output designs, while larger A–I workflows remain partial. Campaign timelines use only the selected current window; monthly customer states use an illustrative global 90-day rule. A full event study, category-specific lapse thresholds, arbitrary offline slicing and some secondary diagnostics still require additional work; [coverage boundaries](docs/OUTPUT_DESIGN.md) are explicit.

## Statistical tools

Measured result rows support descriptive statistics, Spearman correlation, Welch two-sample t-tests with 95% difference intervals and Hedges' g, Mann–Whitney comparisons, classical one-way ANOVA with a variance diagnostic and eta-squared, and Kruskal–Wallis.

Inferential tests require a stated observation unit, independence assumption and design note; truncated result sets are rejected. These checks do not prove that a model's design assumptions are correct. P-values are explicitly exploratory/unadjusted for multiplicity. A synthetic frozen census often calls for descriptive effects and construction-rule interpretation rather than significance testing.

## State, limits and safety

Completed analyses, conversations, confirmed notes, feedback and chat-job status live in `retail_app/state/app.sqlite3`. The original DuckDB opens read-only. Parsed single-SELECT SQL disables external file/network access and limits concurrency, queue waiting, time, memory, result rows and bytes. Agent SQL has a 30-second timeout, 500-row cap and 1 MiB preview cap; baseline recipes have 60 seconds/5,000 rows. Long cells and previews are marked truncated. A parsed-join guard rejects disconnected model joins and a known invalid retail channel relationship; it does not prove join cardinality, grain or business semantics.

The server binds to loopback, checks mutation origins/headers, adds security response headers, limits request size, and allows at most two active analysis jobs. Sanitized errors avoid returning raw provider exceptions. `/health/live` checks process availability and `/health/ready` checks local data/state access; neither proves the model account has available quota.

Completed chat survives restart. Interrupted jobs are marked as interrupted; tool execution does not silently restart or recover mid-step. Progress is polled and Stop is cooperative; token-by-token streaming is not implemented. SQLite state and local service logs still need retention and disk-capacity management. Public authentication, authorization, tenant isolation and TLS termination are outside this local deployment. Do not expose its port publicly.

## Tests

```sh
.venv-runtime/bin/python -m retail_app.tests.run_all
cd retail_app
pnpm test:frontend
```

Tests run all 19 recipes and 18 hypothesis tests against the full warehouse, independently reconcile key metrics, exercise date/SQL constraints, check chat persistence/follow-ups/exports, verify statistical calculations, and mock specialist delegation/self-correction. The combined runner writes `state/eval_report.json` and generates the fixtures used by `test:frontend`; test state uses a temporary SQLite database.

The React bundle compiles and components are server-render-tested, including GFM tables, source references, exports and API error handling. Interactive browser/visual QA is blocked by an administrator-enforced browser policy check that the tool could not verify; layout and click-through correctness are not confirmed. Docker build/run remains unverified. Live API smoke checks are distinct from browser QA and broad answer-quality evaluation.

For explicit, billable live checks against the running service, run `.venv-runtime/bin/python -m retail_app.tests.live_smoke baseline`, then `followup`, `investigation`, `statistics`, and `gaps` one at a time. These create local test conversations and save evidence under ignored `retail_app/state/live_smoke/`. They never print credentials. Inspect the results as well as the assertions; these few questions are not a general accuracy benchmark.

A separate evidence-based natural-language evaluation runner lists its cases without using the model:

```sh
.venv-runtime/bin/python -m retail_app.tests.evaluate_agent --list
```

`--live` explicitly runs billable model checks. It compares measured outputs with independent golden queries, and still requires human review of the answer, scope and evidence meaning. See [TEST_REPORT](docs/TEST_REPORT.md) for what has actually passed; the presence of an evaluation harness is not a general accuracy guarantee.

## Code and development

```sh
cd retail_app
pnpm install
pnpm run build
```

The code is in this `retail_app/` directory:

- `frontend/chat.jsx`, `frontend/app.jsx`, `frontend/api.js`: chat, data workspace, request/export helpers.
- `frontend/answer-report.jsx`, `frontend/playbook-charts.jsx`: seven-part answers, evidence tables and playbook-specific charts.
- `static/`: deployable UI bundle, styles and page shell.
- `backend/`: FastAPI, primary LangGraph agent, evidence, SQL/analytical tools and persistence.
- `backend/presentation.py`, `backend/visual_data.py`, `backend/context.py`: source-derived output contracts, additional chart evidence and domain retrieval.
- `knowledge/hypotheses.json`: 18 dataset-specific hypothesis templates.
- `tests/`: deterministic checks, frontend checks and opt-in live evaluations.
- `service.py`, `maintenance.py`, `start.sh`: local service and backup operations.

Python and frontend dependencies are locked. Built assets use no remote fonts or chart CDN. Model/source Markdown cannot trigger automatic external image requests.

```sh
docker compose -f retail_app/compose.yaml up --build
```

The supplied container runs as a non-root user, publishes only host loopback, mounts the original warehouse read-only and uses a separate named `retail-state` Docker volume. It does **not** reuse the Mac app’s `retail_app/state` directory. The root filesystem is read-only with a bounded temporary directory and resource/log limits. Pass model settings through the Compose environment; the Mac `.env` is not copied into the image. Docker build/run remains unverified on this host.

For an optional macOS login service, run `.venv-runtime/bin/python retail_app/service.py install`. It creates a user LaunchAgent to restart the app at login and after process failure; `service.py stop` stops it and `service.py uninstall` removes only that registration. Run with the project's Python. This is local availability while the computer is running, not a cloud uptime promise.

## Back up local conversations

From the project directory:

```sh
.venv-runtime/bin/python -m retail_app.maintenance backup
```

This uses SQLite’s backup API while the app may be running, verifies database integrity, and creates a new file under `retail_app/state/backups/` by default. Use `--output /path/to/new-backup.sqlite3` for a different location. It refuses to overwrite an existing file. The backup contains conversations/evidence and excludes API keys, the synthetic warehouse, source code and configuration. Backups can contain private questions and result data; keep them under the same access controls as the app state. Automated backup schedules and a tested restore workflow remain to be established.

See [output design](docs/OUTPUT_DESIGN.md), [domain assets](docs/DOMAIN_ASSETS.md), [remaining gaps](docs/MISSING.md), [implementation](docs/IMPLEMENTATION.md), [feature coverage](docs/FEATURE_COVERAGE.md) and [Milky Way reference](docs/MILKY_WAY_REFERENCE.md).
