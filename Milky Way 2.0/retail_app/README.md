# Milky Way 2.0 — application code

One conversational Retail Agent answers questions about the Summit Field synthetic dataset, performs analysis, plots measured results, selects playbooks and investigates business changes through editable hypotheses. The agent chooses its tools from the question and conversation context; there is no user-facing mode or specialist selector.

See the [product and setup guide](../README.md), [implemented architecture](docs/MILKY_WAY_2_ARCHITECTURE.md), [feature coverage](docs/FEATURE_COVERAGE.md) and [Milky Way 2.0 verification notes](docs/MILKY_WAY_2_VERIFICATION.md).

## Run locally

From the **Milky Way 2.0** folder:

```sh
./retail_app/start.sh
```

Open **http://127.0.0.1:8766/**. The root **Start Milky Way.command** launcher runs the same script. Keep the terminal open unless you install the optional login service. If that service is already running, open the app instead of starting a second server on the same port.

The local folder includes the generated DuckDB warehouse, a built frontend and an environment installed for this Mac. The environment uses this Mac's existing Python installation; it is not a portable interpreter bundle. On another machine, create an environment from the lockfile:

```sh
python3.12 -m venv .venv-runtime
.venv-runtime/bin/python -m pip install -r retail_app/requirements.lock.txt
cp retail_app/.env.example retail_app/.env
```

Set `OPENAI_API_KEY` and `OPENAI_MODEL` in `retail_app/.env`, then start the app. This local installation's existing connection was copied during setup. Environment variables take precedence over the file. Restart after changing configuration; never commit credentials. Model questions, relevant document excerpts, bounded evidence previews and recent conversation context are sent to the configured OpenAI API; warehouse queries execute locally.

The generated data is present in this delivered folder and excluded from Git. A source-only checkout must generate or restore `retail_data/data/full/retail.duckdb` using the [dataset instructions](../retail_data/README.md). `RETAIL_DB` may point to a compatible warehouse with its sibling `manifest.json`; `RETAIL_STATE_DIR` may select a separate local state directory.

Optional macOS service:

```sh
.venv-runtime/bin/python retail_app/service.py install
.venv-runtime/bin/python retail_app/service.py status
.venv-runtime/bin/python retail_app/service.py restart
```

The service label is `com.milkyway.retailagent.v2`. `stop` stops it; `uninstall` removes only its registration. It runs while this Mac is awake and logged in.

## Conversation and investigations

Ask for definitions, business explanations, summaries, comparisons, charts, insights or a playbook by name. Follow-ups such as “same for Mobile app” update the retained scope. The structured query layer supports channel, merchandise hierarchy, stores and regions, customers, loyalty, promotions and fulfillment with validated field/operator combinations.

Business diagnostic questions automatically enter an investigation. Each hypothesis has a stable ID, parent, test, falsifier, scope, declared measured criterion, revision, evidence and verdict. The editable investigation panel supports adding, correcting, excluding and restoring hypotheses. **Continue / retest** resumes the saved investigation; corrections can also be given in chat. Changed statements, scope and dependencies invalidate affected findings. A descriptive test verdict does not establish causality.

Definitions receive concise explanations. Measured analyses use the relevant playbook structure, evidence tables and charts; single totals use metric cards. Investigations additionally expose their hypotheses and findings. Source SQL, parameters, documents and limits remain inspectable.

All 19 baseline playbooks remain available. Validated filtered adapters cover trend, growth contribution, margin, scorecard and concentration. Other filtered methods need an explicit scoped adaptation or an explanation of the missing method/data. The application does not silently run an all-business recipe under a filtered label. Custom queries over `scoped_sales` retain selected dates and filters; their formulas and join cardinality still require review.

## History and memory

Messages, completed answers, evidence, charts and confirmed notes persist in SQLite. Session state separately preserves active dates, filters, metric, return basis and a concise summary. Investigations save their revisions, immutable test history and partial progress for continuation after a restart. Recent text sent to the model is bounded; saved history is not unlimited verbatim model context.

Explicit “remember” requests can save a local convention. Normal session scope and history persist automatically. Feedback records a review signal; it does not retrain the model.

New chats, paginated history, rename/delete, cooperative Stop and eligible Retry remain available. Exports include analysis JSON, evidence CSV and conversation Markdown. Old saved reports can require a rerun to collect newer chart datasets.

## Development and checks

From the product folder:

```sh
.venv-runtime/bin/python -m retail_app.tests.run_all
cd retail_app
pnpm install --frozen-lockfile
pnpm test:frontend
pnpm run build
```

The backend runner generates the fixtures used by rendering tests. Live model checks are opt-in and billable; deterministic/component tests do not prove general answer correctness. Current results and remaining browser/container acceptance limits belong in the [Milky Way 2.0 verification notes](docs/MILKY_WAY_2_VERIFICATION.md). [TEST_REPORT.md](docs/TEST_REPORT.md) records inherited baseline work.

Key modules are `backend/agent.py` and `backend/conversation.py` for the single agent loop; `backend/scope.py` for scope and bound queries; `backend/investigations.py` for durable investigations; `backend/presentation.py` for grounded answers; and `frontend/chat.jsx` / `frontend/investigation.jsx` for conversation and hypothesis editing. [Domain assets](docs/DOMAIN_ASSETS.md) and [output design](docs/OUTPUT_DESIGN.md) describe the data-specific methods and visuals.

## Local operations and boundaries

The service binds to loopback for one trusted local user. It uses a read-only warehouse, bounded jobs and query results, cooperative cancellation, mutation-origin checks and health endpoints. It does not provide public authentication, tenant isolation or cloud uptime. Missing traffic, experimental controls, actual delivery events and daily lost-demand data cannot be inferred from the synthetic warehouse.

Back up conversations from the product folder:

```sh
.venv-runtime/bin/python -m retail_app.maintenance backup
```

This creates a verified SQLite backup under `retail_app/state/backups/`. It excludes credentials, code and warehouse data. Backup retention and restore drills remain operational tasks.

A container configuration is provided:

```sh
docker compose -f retail_app/compose.yaml up --build
```

It uses port 8766, a read-only warehouse mount and a separate `milkyway2-state` volume; it does not reuse the Mac conversation directory. Pass model settings through the Compose environment. Container execution remains subject to the recorded verification status.

## Versioned improvement workspace — application 2.1.0

Open **Improve workspace** in the chat sidebar to add ontology/context, skills, answer profiles/examples, evaluation cases and reviewed feedback. Drafts are previewed and evaluated before publication. New answers pin the active release and expose their versions in **Why this answer?**. The local operator can restore a prior published release. Start with the [user/admin guide](docs/developer/USER_ADMIN_GUIDE.md), [architecture](docs/developer/ARCHITECTURE.md), [technical design](docs/developer/IMPROVEMENT_WORKSPACE_DESIGN.md), and [release notes](docs/developer/RELEASE.md). The built browser bundle and all new source/tests are in this folder.
