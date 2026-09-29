# Inherited baseline verification — September 26, 2026

This is the original Retail Data Agent verification record, retained as provenance for inherited recipes and components. It is not the final Milky Way 2.0 test count or release report. See [Milky Way 2.0 verification](MILKY_WAY_2_VERIFICATION.md) and the [current architecture](MILKY_WAY_2_ARCHITECTURE.md).

## Scope

The supported deployment is a trusted **local single-user application**. These checks do not approve an internet-facing service, establish complete ChatGPT parity or measure general answer accuracy. The primary LangGraph analyst architecture and original retail recipes remain intact.

## Deterministic and frontend checks

**168/168 application tests passed, with no skipped tests**, on Python 3.12.14 and the upgraded locked dependencies. The original run saved its machine-readable result under ignored `retail_app/state/eval_report.json`; repeat with `.venv-runtime/bin/python -m retail_app.tests.run_all`.

Coverage includes all 19 baseline playbooks and 18 dataset-specific hypothesis recipes on the full warehouse, independent accounting/denominator reconciliations, statistics, API/history/export behavior, cancellation and bounded admission, durable completion, storage-failure recovery, SQL limits and join guards, bounded recent context, measured-cell comparisons, specialist evidence reuse and source references. Model responses in these tests are mocked. The dataset's pre-existing 105 validation checks are separate and are not included in the application-test count.

Frontend compilation and server-rendered checks pass for the chat shell and all 19 evidence/report paths, safe GFM tables, evidence/document links, USD chart labels, complete-conversation Markdown export, and network/non-JSON/validation errors. These are code/component checks, not browser screenshots or click-through acceptance tests.

## Live checks and findings

Real Responses API calls use the locally configured GPT-5.4 Mini. Previously exercised operational phases include a basic retail question, a scoped follow-up with a chart, explicit Hypothesis/EDA/RCA delegation, a statistics tool call and refusal to invent causal loyalty lift. Those initial receipts remain under ignored `retail_app/state/live_smoke/`.

The new five-case natural-language suite independently checks all-business totals, Web/Footwear filtering, explicit March 2024 dates, a recent Mobile app/Footwear/July correction after long older context, and causal-gap abstention. Expected numeric values are not sent to the agent. Query results are replayed and compared with separate raw-fact golden SQL; narrative/semantic review remains required.

This evaluation exposed concrete defects rather than only checking that requests completed:

- A disconnected channel join named the requested channel without filtering the sales rows. Parsed SQL guards now reject joins without a relationship between their inputs and the known invalid sales-line/channel path.
- A three-row dimension sample omitted the fourth channel, Mobile app. Small dimensions now return complete bounded samples, and the analyst receives current channel/division labels and the canonical join path.
- A query projected whole-order measures after joining sales lines, inflating a product slice. Model instructions and a narrow SQL guard require line measures for line/product totals; advanced unsupported grain transformations may require rewriting the query.
- The evaluator's original table-name inspection could fail when binding a valid query through `v_product`. Parser-based source inspection and query replay distinguish that harness issue from genuine wrong results. Original failed receipts are retained.

These controls are not a complete semantic SQL validator: correct foreign keys, cardinality, filtered metric basis, claim-to-evidence support and causal interpretation still require evaluation. Citation checks establish that references exist, not that every cited sentence follows from them.

**Final observed results:** all five automated checks passed in `20260926T071211Z-92127176e7.json`. The corrected Mobile app / Footwear / July 2025 result is **79,488,977 cents and 6,423 units**, matching independent facts. The initial causal answer correctly abstained but added unrelated-period descriptive figures; the final instruction refinement and targeted rerun (`20260926T071332Z-e4bfadfa32.json`) produced a documentation-only causal-gap answer with no measured output. The coding assistant reviewed the effective scope, displayed values, SQL grain and causal qualifications; human release acceptance remains pending.

The final running-service investigation invoked **Hypothesis, EDA and RCA**, with no tool errors, preserved three evidence items and exported its answer. Its January sales change of **$1,208,099.26** reconciles independently to transaction headers, and the division contributions sum to the same amount. Findings describe accounting contributions rather than causal proof. The private review record is `state/production_review.json`; earlier failed evaluation receipts remain available. These are selected successful regressions, not a broad reliability percentage.

## Runtime and dependency checks

- Installed Python inventory: **48 packages, zero known advisory records, none skipped** in the 2026-09-26 scan. This includes all 46 locked libraries, pip 26.2.1 and the harmless leftover compatibility package exceptiongroup 1.3.1. `pip check` passes.
- Frontend dependency audit: **174 lockfile dependencies, zero reported advisories**. Scanner categories overlap. See [DEPENDENCY_REVIEW.md](DEPENDENCY_REVIEW.md) for methodology, primary advisory sources and limits.
- The macOS user service starts on Python 3.12. `/health/live`, `/health/ready`, `/api/status` and the application page return HTTP 200. Readiness confirms local data/state access and model configuration, not provider quota or answer quality.
- The response includes a restrictive content policy, no-sniff and no-referrer headers. Credentials remain in the ignored owner-only `.env`, outside browser assets and source control.
- A real SQLite backup was created through the backup API and passed integrity validation. It excludes the API key and warehouse. A disaster-recovery restore drill and scheduled backup retention remain outstanding.

## Unverified or not provided

- **Browser layout and interactions:** the desktop tool could not verify its administrator-enforced browser security policy. No bypass was attempted. Actual on-screen appearance, keyboard flows and mobile interactions remain unconfirmed.
- **Docker build/run:** configuration is supplied but the image was not built or run on this host.
- Public authentication, authorization, tenant isolation, TLS, distributed execution, load/uptime budgets and external monitoring.
- Broad natural-language reliability, arbitrary model-selected study designs and untested causal scenarios.

No numeric performance, accuracy or cost claims from the Milky Way corporate deck are attributed to this application. See [FEATURE_COVERAGE.md](FEATURE_COVERAGE.md) for delivered and missing product capabilities.

## Playbook output and domain-asset integration update

The app now reads all 19 source output/visual contracts and renders the seven-part decision structure: headline, scope/metric, primary visual, supporting values, interpretation, limitations and next question. The active analyst reserves its closing tool step for structured presentation. Old saved results missing the newly required visual evidence request a rerun.

Additional read-only queries supply chart-ready denominators and independently reconcile scorecard buyer reach, channel/store margins, promotion redemption, price-distribution units, cohort return shares, customer states, monthly mix, and weekly inventory flows. Eleven dedicated data tests cover those relationships. Fourteen retrieval tests cover the explicit domain-asset inventory, source lines, bounded context and reference-only labels. Presentation tests cover evidence IDs, horizontal contribution axes, Decimal-to-JSON numeric values, missing cells, USD conversion and unsupported currency claims.

All three frontend suites pass: existing UI/evidence rendering, all 19 primary visual mappings and their numerical transforms, and seven-section order with supporting tables, metric cards and honest no-data states. The final bundle builds successfully. These remain component/rendering checks; browser visual acceptance is still blocked by the desktop policy-verification restriction.

A live Source of Growth investigation retained January 2025 versus January 2024 and produced a signed horizontal division-contribution chart, supporting tables and structured interpretation. The plotted changes sum to **120,809,926 cents**, independently consistent with the earlier header reconciliation. A currency validator caught misleading monetary conversions in attempted prose; the final response retained the verified chart/tables and withheld unvalidated dollar claims. Currency matching is a limited transcription check, not proof of metric semantics, valid aggregation or causal support.

The restarted service also persisted a named growth-playbook answer with all seven output sections and measured evidence. The source asset inventory and known omissions are documented in [DOMAIN_ASSETS.md](DOMAIN_ASSETS.md), and delivered chart details are in [OUTPUT_DESIGN.md](OUTPUT_DESIGN.md). No year-plus chat archive or missing enterprise asset is claimed as imported.

After the final output-format changes, all five automated evidence checks passed again (`20260926T075522Z-1fb8879211.json`). Manual review nevertheless found a 100-fold cents transcription error in the all-business narrative. The monetary guard now also checks explicit cents, USD and dollar suffixes, including scaled and negative values. Thirteen presentation tests and the full 168-test suite pass after this fix. A targeted live rerun (`20260926T080006Z-310652aa62.json`) returned the correct **57,653,466,900 cents ($576,534,669.00)** and **2,429,986 completed orders**, with matching measured evidence, scope and metric cards and no tool errors. This finding reinforces that passing query checks alone does not certify answer accuracy. The source-control credential scan found no configured key in tracked or pending project files.
