# Testing and evaluation guide

[Handbook](README.md) · [Fresh release receipts](RELEASE.md) · [Every source test method](reference/TEST_INVENTORY.md)

## What each layer establishes

| Layer | What it checks | What it does not establish |
|---|---|---|
| Warehouse validation | Keys, relationships, arithmetic, date/price/promotion rules, header/line/return/inventory reconciliation | Real retailer validity or causal identification |
| Data integration | Same-seed reproduction, Parquet round trips, constrained DDL, example SQL, data API/graph | Current browser or model quality |
| Backend regressions | Recipes, semantic checks, context, evidence, API/state, cancellation and investigation behavior | Universal interpretation accuracy with a live model |
| Frontend component suites | Rendered structure, labels, measured visual bindings and error contracts | Real browser geometry, clicking, scrolling or keyboard completion |
| Production bundle build | JSX and package bundling | Runtime acceptance in a browser or container |
| Live golden evaluation | Selected actual model questions against independent measured expectations | General accuracy or unattended release approval |
| Browser acceptance | Actual interaction, responsive layout and user recovery flows | Correctness across the untested question space |
| Docker/platform acceptance | Packaged startup, configuration, health and persistence on that host | Public deployment readiness |

## Backend test map

The current offline runner executes **317 tests**, including generated per-playbook cases. The static source inventory lists individual Python test methods; dynamically constructed recipe tests explain why that list's count can differ from the executed count. The runner isolates `RETAIL_STATE_DIR` before importing the app, uses the full local warehouse and mocks model calls. It writes a summary and frontend fixtures after running.

| File | Main coverage |
|---|---|
| `test_app.py` | Nineteen baseline recipes, independent financial reconciliations, catalog/SQL guards, API, memory, mocked agent correction, hypothesis bank/statistics and conversation behavior |
| `test_context.py` | Correct domain retrieval, source lines, roles, maturity/metric definitions, duplication bounds and allowlisting |
| `test_scope.py` | Bound scope, label normalization, grouped totals/distinct counts, filtered adapters and protected scoped SQL relation |
| `test_sql_checks.py` | Channel joins, header fan-out, CTE/subquery lineage and selected invalid SQL structures |
| `test_conversation_v2.py` | Single-agent planning, durable follow-ups, explanations, memory intent, investigation tool behavior and measured binding |
| `test_investigations.py` | Revisions, declared criteria, immutable tests, stale dependencies, exclusions, reconciliation and completed-state requirements |
| `test_runtime.py` | Request/provider/job boundaries, cancellation and fault handling |
| `test_operations.py` | Conversation/history/export, local controls, bounded admission, persistence faults and backup behavior |
| `test_presentation.py` | Answer contract, charts, units, measured values, fallback and monetary checks |
| `test_visual_data.py` | Measured visual datasets, denominators, inventory flow/stock, campaign/return/cohort/reach reconciliation |
| `test_evaluation.py` | Golden-case grading, currency units, result matching, SQL replay, review requirements and redaction |
| `test_workspace_assets.py` | Migrations, immutable records, stale revisions, conflict/mapping/dependency validation, source freezing, publication/restore and feedback conversion |
| `test_workspace_evaluations.py` | All 76 core runtime contracts on both versions, honest grading, fingerprints, human review gates, budgets, cancellation/restart and isolated memory |
| `test_workspace_integration.py` | Chat snapshot capture, source/profile integration, scope conflicts/date compatibility, evidence preservation, provider budgets and feedback deletion |

Legacy specialist dispatch was removed. Regression checks reject those undeclared names; compatibility arguments cannot enable new executable tools. Use [API/tool reference](API_AND_TOOLS.md) to determine the active topology.

## Running the deterministic application checks

From the **Milky Way 2.0 directory**, with the existing warehouse and installed Python dependencies:

```sh
.venv-runtime/bin/python -m retail_app.tests.run_all
```

From its **retail_app directory**, with Node and locked frontend dependencies available:

```sh
pnpm install --frozen-lockfile
pnpm test:frontend
pnpm run build
```

`pnpm install` is needed on a clean checkout, not for every test. The six frontend suites are `test_frontend.jsx`, `test_playbook_visuals.jsx`, `test_answer_report.jsx`, `test_milkyway_frontend.jsx`, `test_improvement_frontend.jsx` and `test_frontend_delivery.jsx`. They use esbuild and Node; having a pnpm launcher without Node on PATH is insufficient.

For documentation-only verification, the production bundle can be built into a temporary path to avoid replacing the checked-in `static/app.js`. For an actual frontend release, build and review the production artifact intended for delivery.

## Data validation and reproducibility

From **Milky Way 2.0**:

```sh
.venv-runtime/bin/python retail_data/src/validate.py --data retail_data/data/full
.venv-runtime/bin/python retail_data/src/verify_parquet.py --data retail_data/data/full
```

The validator opens DuckDB read-only and prints its result. The Parquet check compares all exported table contents to the database; it is a separate check from schema/arithmetic validation. Historical full results are in `retail_data/docs/full_validation_report.json` and `full_parquet_report.json`.

For reproduction, generate two small datasets into distinct empty temporary directories using the same seed/dimensions and differing supported thread settings, then use `retail_data/tests/test_integration.py --data <sample> --replica <replica>`. Never point generation at the populated application dataset. See [the data kit README](../../../retail_data/README.md) for supported generator arguments.

## Live-model evaluation

From **Milky Way 2.0**:

```sh
.venv-runtime/bin/python -m retail_app.tests.evaluate_agent --list
```

Listing makes no model calls and writes no report. To intentionally run the billable harness with server-side configuration:

```sh
.venv-runtime/bin/python -m retail_app.tests.evaluate_agent --live
```

Use repeatable `--case` arguments for a focused subset. The five current IDs are `base_total`, `filtered_channel_division`, `explicit_date_override`, `followup_recent_correction` and `causal_gap_abstention`. Goldens are computed from independent queries and are not sent in the model prompt. Results go to private local `state/evaluation/` with automatic and manual-review fields; successful automatic matching does not set release approval.

The suite currently passes constructed prior text to `run_agent` rather than exercising every persistent chat API journey. It therefore complements, rather than replaces, conversation/investigation tests and live browser scenarios. The new improvement workspace adds a separate 76-case deterministic runtime suite, guided suite authoring, frozen baseline/candidate jobs and review gates. See [the workbench design](IMPROVEMENT_WORKSPACE_DESIGN.md) for deterministic and live case schemas. The legacy five-case CLI remains a complementary harness.

Historical live Milky Way scenarios are recorded in [MILKY_WAY_2_VERIFICATION.md](../MILKY_WAY_2_VERIFICATION.md). Keep those dates and scopes visible. No fresh provider-quality claim is implied by rerunning offline tests.

## Browser acceptance scenarios

These are acceptance scenarios for a browser-enabled release check. Mark each passed, failed or not run with environment and evidence. The current release record includes fresh browser interaction results for the improvement workspace. Historical browser-policy limitations remain dated evidence for earlier deliveries. Component tests alone do not imply browser approval.

1. Create a chat, submit a definition question, inspect its actual document citation and return to the transcript.
2. Ask Web Footwear July current/prior sales and units; verify visible scope, separate units, chart/table consistency and evidence access.
3. Ask “same for Mobile app”; verify only the channel changes and the composer remains usable.
4. Start an investigation, watch progress, edit a hypothesis, confirm stale findings, continue and inspect the new verdict/history.
5. Stop an active answer and retry the eligible unanswered question without duplication.
6. Navigate away while polling, return/reload and confirm the right conversation/job state.
7. Load earlier messages and export the complete conversation; verify source/table labels.
8. Check desktop/narrow screens, keyboard-only navigation, modal focus/Escape, scrolling and large tables.
9. Exercise unavailable network/model, empty results, unknown filter, rejected revision and server restart.
10. Rename and explicitly delete a test chat; verify it disappears without affecting unrelated chats or global memory.

Use temporary state for destructive/recovery scenarios. Do not conduct these checks by deleting a user's real conversation.

## Adding meaningful regressions

Start with the concrete failure and define an independent expected outcome. A metric test should use a simpler independent aggregation or invariant, not paste the production expression and assert equality to itself. A scope test should demonstrate that changing/removing one filter affects the intended slice and leaves other constraints intact. A hypothesis test should demonstrate a revision or criterion error that could otherwise publish a false verdict.

For output quality, assert exact unit/denominator and evidence relationships plus useful rendering structure. Avoid brittle tests that demand identical prose from a model. Maintain separate expectations for deterministic correctness, semantic support, readability and browser interaction.

## Documentation/reference verification

`refresh_reference.py` snapshots the active tools, OpenAPI, scoped query capabilities, context inventory, state DDL, source test inventory and measured answer examples. It imports the app with temporary SQLite state and makes no model calls. The source manifest records the baseline commit and hashes of relevant code.

After changing runtime contracts, regenerate reference snapshots, update narrative sections and diagrams, check internal links, parse JSON/SVG and visually inspect the shareable diagram. A generated reference is a dated snapshot; it is not a second implementation to edit independently.

From **Milky Way 2.0**, refresh the contract snapshots and canonical SVG:

```sh
.venv-runtime/bin/python retail_app/docs/developer/refresh_reference.py
.venv-runtime/bin/python retail_app/docs/developer/diagrams/render_overview.py
```

The committed PNG is a raster copy of the SVG for viewers that do not display SVG; regenerate it with an SVG-capable image renderer after visual changes. The SVG uses no remote fonts or images. The handbook includes Mermaid sources for additional diagrams; render them in a Mermaid-capable Markdown viewer.

From **retail_app**, rebuild the offline HTML copy using the existing frontend dependencies:

```sh
pnpm exec esbuild docs/developer/render_handbook.jsx --bundle --platform=node --format=esm --packages=external --outfile=tmp/render-handbook.mjs
node tmp/render-handbook.mjs
```

Then, from **Milky Way 2.0**, run:

```sh
.venv-runtime/bin/python retail_app/docs/developer/verify_docs.py
```

The verifier checks local links remain inside the intended Milky Way copy, parses generated JSON/SVG and compares the contract snapshot's source hashes. It does not automatically rerun application/model tests, render Mermaid, or certify narrative claims. Update the release record and fresh verification receipt only for checks actually performed.

## Improvement release acceptance

1. Start with isolated application state and model calls disabled. Verify baseline migration and existing API behavior.
2. Save a knowledge draft, validate and preview its retrieval; verify active context is unchanged.
3. Freeze a candidate; run the complete 76-case foundation baseline/candidate comparison.
4. Review deterministic outputs and coverage with an honest operator label. Publish only with the matching approved run.
5. Verify source changes after a run block promotion and require rerunning. Verify hard failures and missing reviews cannot be overridden.
6. Restore the prior published release; verify old answer provenance and history remain.
7. Preview a measured answer profile, edit scope with revision/date validation, and report structured feedback.
8. Check responsive geometry and keyboard entry. Record screenshots and actual limitations.
9. Run registry, evaluation and runtime integration tests, then the full backend and six frontend suites.

Actual test totals and screenshots are recorded in [Release](RELEASE.md). No billable live benchmark is implied by these offline/UI checks. Reviewed UI activation during automated acceptance is labeled automated acceptance; it is not a human approval of enterprise business semantics.

## Hardening regressions (2.1.1)

`test_agent_boundaries.py` exercises all declared strict schemas, invalid tool calls, optional-null/default handling, reference-input separation and preservation of tool/reasoning history. `test_http_boundary.py` exercises streaming/body time limits, cache rules and linked-file privacy. `test_maintenance.py` exercises cleanup allowlists, retained data, symlinks, hardlinks and changed-file races.

Use the unified check workflow in [repository maintenance](REPOSITORY_MAINTENANCE.md). The frontend build test inspects emitted dependencies and verifies that optional admin/workspace screens stay outside the startup graph; see [build scripts](../../scripts/build-frontend.mjs). New tests remain offline and do not establish live-model resistance to every adversarial prompt.
