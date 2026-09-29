# Milky Way 2.0

A local conversational Retail Agent for the **Summit Field synthetic retail dataset**. Ask questions about your data, definitions and business; request analytics, charts and playbooks; investigate business changes through editable, testable hypotheses.

**Installing from Git?** Follow [INSTALL.md](INSTALL.md) for the source, runtime, synthetic warehouse and local configuration requirements. The current application release is **2.1.1**.

**For developers:** start with the [detailed developer handbook](retail_app/docs/developer/README.md), [system architecture diagram](retail_app/docs/developer/diagrams/system-architecture.svg), [low-level design](retail_app/docs/developer/LOW_LEVEL_DESIGN.md), and [release/verification record](retail_app/docs/developer/RELEASE.md). The [extension guide](retail_app/docs/developer/EXTENDING.md) explains where ontology, skills, evaluations and answer examples fit today. The approved improvement workspace is implemented in application release **2.1.0**. Start with the [user/admin guide](retail_app/docs/developer/USER_ADMIN_GUIDE.md) for the five admin sections, publishing, evaluation and rollback. The [plan delivery record](retail_app/docs/developer/UI_IMPROVEMENT_PLAN.md) maps implementation to the approved phases.

**Open the app:** http://127.0.0.1:8766/

This folder is a separate working copy. The original Retail Data Agent at port 8765 is preserved. Existing conversations and saved conventions were copied using SQLite's consistent backup API; subsequent changes belong to this app.

## Start

On this Mac, double-click **Start Milky Way.command**, or run:

```sh
./retail_app/start.sh
```

The included `.venv-runtime` is installed for this Mac. On a different machine, recreate the Python environment from the lockfile:

```sh
python3.12 -m venv .venv-runtime
.venv-runtime/bin/python -m pip install -r retail_app/requirements.lock.txt
cp retail_app/.env.example retail_app/.env
./retail_app/start.sh
```

Set `OPENAI_API_KEY` and `OPENAI_MODEL` in `retail_app/.env` on a new machine. This Mac's existing connection is already configured. Restart after changing settings. The frontend is prebuilt; Node is needed only when rebuilding it.

Optional macOS login service:

```sh
.venv-runtime/bin/python retail_app/service.py install
.venv-runtime/bin/python retail_app/service.py status
.venv-runtime/bin/python retail_app/service.py restart
```

The service label is `com.milkyway.retailagent.v2`. It runs while this Mac is awake and logged in. It does not provide cloud uptime.

## Ask naturally

- “What does customer_key mean, and why is zero special?”
- “Show Web Footwear sales and units for July 2025 versus July 2024. Plot the comparison.”
- “Same for Mobile app.”
- “What drove that change? Test the competing explanations.”
- “Change hypothesis H1 to test whether units fell. Retest it.”
- “Exclude the promotion hypothesis and investigate product mix.”
- “Remember to display monetary values in USD.”

One Retail Agent chooses data explanation, analytics or investigation from your question and context. It can use the 19 playbooks, 18 starting hypothesis templates, catalog, metric definitions, statistics and read-only data tools. The bank is a starting point; new hypotheses can be created from available data.

For investigations, an editable panel shows each hypothesis, test, falsifier, evidence and verdict. Add, edit, exclude or restore hypotheses, then use **Continue / retest**. You can also make these corrections conversationally. Editing a running investigation stops the old run; affected results become stale. A revised hypothesis must be tested again.

## Improve the experience

Open **Improve workspace** in the sidebar. Add knowledge and ontology, duplicate a skill, tune response profiles, and create good/bad examples. Save and preview drafts, freeze a candidate, compare its evaluations, record review, then publish. New answers capture the published release; use **Why this answer?** to inspect its versions. Feedback can become a regression draft. Restore a previously published release to undo a content change. These are trusted-local admin capabilities, not authenticated enterprise roles.

## What remembers what

- Conversation messages, answers, evidence and charts persist in `retail_app/state/app.sqlite3`.
- Session state preserves active filters, dates, metrics, return basis and a concise conversation summary across follow-ups and restarts.
- Investigations preserve hypothesis revisions, immutable test history and partial progress. Continuation reloads valid evidence with fresh answer references.
- An explicit “remember” request saves a convention in local memory. Session scope/history are saved automatically; ordinary model guesses are not saved as durable preferences.
- Recent conversation text is bounded. Stored investigation/scope state is separate from that window; this is not unlimited verbatim context or model training.

## Folder contents

| Path | Contents |
|---|---|
| `retail_app/backend/` | FastAPI, single agent loop, scope queries, investigation storage, analytics and presentation |
| `retail_app/frontend/` | React conversational UI, editable investigation panel, charts and evidence |
| `retail_app/static/` | Built browser bundle and styles |
| `retail_app/tests/` | Deterministic warehouse, API, workflow and rendering checks; opt-in live harness |
| `retail_app/knowledge/` | Hypothesis templates and 76-case enterprise runtime suite |
| `retail_app/docs/` | Architecture, coverage, domain-asset inventory and verification notes |
| `retail-data-analyst/` | 19 source playbooks, executable baseline recipes and visual specifications |
| `retail_data/` | Synthetic data generator, schemas, catalog, validation records and generated data |
| `retail_data/data/full/retail.duckdb` | The actual local analytical warehouse |
| `retail_app/requirements.lock.txt` | Locked Python dependencies |
| `retail_app/pnpm-lock.yaml` | Locked frontend dependencies |
| `retail_app/state/` | Private local chats, investigations, logs and test receipts |

The data and installed runtime are present in this local folder. Generated data, credentials, chat history, dependencies and logs are excluded from Git. Dataset generation and schema sources are included in Git; `DELIVERY_MANIFEST.json` records the local warehouse checksum.

## Maintain the local installation

The current hardening release is **2.1.1**. Read [local production readiness and OpenAI guidance](retail_app/docs/developer/PRODUCTION_READINESS.md) for implemented safeguards and acceptance limits. The [repository maintenance guide](retail_app/docs/developer/REPOSITORY_MAINTENANCE.md) identifies source, generated output, private state and cleanup commands.

## Build and verify

From this folder:

```sh
.venv-runtime/bin/python -m retail_app.tests.run_all
cd retail_app
pnpm install --frozen-lockfile
pnpm test:frontend
pnpm run build
```

## Scope and limitations

Sales cover 2024–2025; linked returns extend through March 1, 2026. Metric definitions distinguish sales before returns, sale-cohort realized sales and return-date activity. Customer key 0 is anonymous; inventory snapshots are not additive across time.

The structured query layer supports validated combinations of available retail dimensions and metrics. All 19 original baseline playbooks remain available. Filtered adapters currently cover trend, growth contribution, margin, scorecard and concentration. For other filtered methods, the agent must adapt the documented analysis using available scoped data or report the precise missing method/data; it never silently substitutes an all-business result. The bound `scoped_sales` relation supports custom aggregates and joins while retaining selected dates and filters. It does not supply unavailable inventory/event histories or experimental controls.

A hypothesis verdict confirms or contradicts its declared measured predicate. It does not establish causal identification. Accounting partitions can be reconciled; mechanism hypotheses can overlap. Missing traffic, actual-delivery, lost-demand and experimental-control data remain explicit gaps.

This is a local single-user application. See [the Milky Way 2.0 verification notes](retail_app/docs/MILKY_WAY_2_VERIFICATION.md) for measured results and remaining acceptance limits.
