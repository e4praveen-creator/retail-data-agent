# Remaining capabilities and data gaps

Milky Way 2.0 adds one conversational entry point, persisted analysis scope, editable hypothesis trees and investigation continuation. See the [current product guide](../../README.md), [architecture](MILKY_WAY_2_ARCHITECTURE.md) and [verification record](MILKY_WAY_2_VERIFICATION.md). The data, causal and operational limits below still apply; historical test references describe inherited baseline work.

The app now provides conversational retail analysis with bounded execution and persistent local history. Its deployment scope is one trusted user on one computer. The implemented safeguards do not make it an authenticated public service or establish complete ChatGPT feature parity. [FEATURE_COVERAGE.md](FEATURE_COVERAGE.md) separates delivered features from absent ones.

## 1. Model setup and broader answer evaluation

- This installation now has a locally configured API key and GPT-5.4 Mini. Fresh clones need their own server configuration; credentials are never committed.
- Historical live smoke checks covered the original primary loop and optional specialist tools; see `TEST_REPORT.md`. Milky Way 2.0 uses a single conversational agent and its current validation is recorded separately in `MILKY_WAY_2_VERIFICATION.md`. An initial natural-language evaluation harness now uses independent golden queries for headline totals, filtered slices, explicit dates, a recent correction and causal-gap abstention. A broader evaluation still needs an agreed question set and acceptable answer criteria. A handful of successful runs does not establish general accuracy.
- Product decisions for acceptable response time, model spend, required clarification behavior and who approves durable learned conventions. The current local app uses explicit user-confirmed notes and stores feedback without automatic retraining. The 18 retail hypotheses are runnable starter templates, not the deck’s full enterprise bank.

These items do not block local playbook use.

## 2. Enterprise context missing from the synthetic ecosystem

Available: normalized/curated facts and dimensions, SQL views, DDL, the Python generator, business rules, all 23 catalog tables, metric dictionary, all 19 playbooks and visual recipes, worked examples, all 18 hypothesis templates, and saved validation artifacts. Section-aware retrieval distinguishes their roles and preserves source locations; see [DOMAIN_ASSETS.md](DOMAIN_ASSETS.md). The original Milky Way design remains a reference, and unseen historical chats or enterprise libraries are not claimed as ingested.

Absent: separate raw event ingestion tables, transformation schedules, production lineage and usage telemetry, a business-event chronology, competing operational/finance/comp-store definitions, data owners and SME annotations. Do not invent those from the article's illustrative examples. The generator code is indexed as implementation evidence; it is not relabeled as a raw-to-curated production pipeline.

A helpful next deliverable is a small set of documented scenarios, each with a generator control, affected entities, start/end dates, expected accounting movements, and independent truth labels. The current +$3 price rule is a construction rule, not evidence of learned demand elasticity.

## 3. Missing data by question

| Desired question | Missing evidence |
|---|---|
| Incremental promotion or loyalty impact | Random assignment/holdout or credible quasi-experimental design |
| Price elasticity | Exogenous price variation and a defensible demand model |
| Lost sales / stockout effects | Daily or intraday availability, demand signals, unmet demand |
| Web conversion / abandonment | Sessions, views, carts, checkout events and attribution |
| Delivery reliability | Actual ship and delivery events; carrier/service promises |
| True order/channel profitability | Shipping, fulfillment, labor and operating costs |
| Market share / ACV / competitive distribution | External market universe and competitor distribution |
| New launch / delist / store-assortment decisions | Genuine launch/delist dates, distribution ramps, availability and assortment history |
| Budget/target attainment | Plan, forecast, target and accountability dimensions |
| Comparable-store reporting | Opening/closure/remodel history and an approved comp-store definition |

## 4. Baseline playbook coverage versus complete workflows

All 19 original executable recipes remain unchanged. The app now adds measured chart datasets and a seven-part answer presentation drawn from the playbook design. Primary coverage includes channel growth/margin, six-metric scorecards, promotion timelines, monthly lapse/reactivation states, repeat and return heatmaps, price distributions, loyalty/fulfillment mix, and historical inventory stock/flow panels. [OUTPUT_DESIGN.md](OUTPUT_DESIGN.md) distinguishes rendered charts from supporting evidence and remaining extensions.

Remaining limits include:

- Source of growth still uses divisions for its named baseline. Arbitrary product/channel/store slices require correctly scoped agent SQL; offline dimension filter controls are not implemented.
- The channel scatter is rendered; matched POS-store growth/margin metrics are also queried and available as evidence. A separate interactive store scatter and broader geographic drill remain extensions.
- Monthly active/lapsed/reactivated states use one transparent, illustrative 90-day rule. Category-relative thresholds, an all-state transition matrix and a validated churn model are not implemented.
- The promotion timeline selects the highest associated-sales campaign in the current scope. It does not extend the user's dates to guarantee pre/post coverage, handle every campaign as a full event study, or estimate incrementality.
- Inventory now shows complete weekly buckets within the current selected period, with stock balances separated from flows. It does not supply daily stockout duration or lost-demand evidence.
- Repeat cohorts render eligible 90/180-day cells. A general cohort-age retention matrix and enrollment-cohort loyalty follow-ups remain extensions.
- Current-versus-comparison results appear only where both are queried. Pricing compares actual and regular price for the selected sales window; it is not automatically a prior-period price comparison. Several current-window mix/profile visuals have no prior overlay.
- Some secondary visual recipes remain partial: L4/L13/L52 growth panels, SKU-level price/quantity scatter, prior-period concentration change, return-reason facets and separate fulfillment-outcome dot plots are examples. Supporting data is shown where available, without claiming an unrendered chart exists.
- A weekly business-review synthesis is not a separate implemented workflow. New arbitrary analytical questions can need different SQL and chart fields from the baseline recipes.
- Older saved reports may lack the new chart datasets. They must be rerun; the app does not invent or backfill measurements in old history.

## 5. Quality and operational work

Current checks cover deterministic recipes, selected independent accounting/denominator reconciliations, API/history/export behavior, bounded execution, cancellation, backups, read-only restrictions and agent correction. The natural-language harness grades measured values rather than a particular SQL string and includes manual review criteria. See [TEST_REPORT.md](TEST_REPORT.md) for actual results and runtime versions.

Extend evaluations across entity ambiguity, joins/cardinality, conflicting documents, empty results, unsupported causal claims, wider retrieval relevance, chart/denominator consistency, long conversations and adversarial instructions in sources. Unknown evidence/document IDs are marked unverified, and comparisons must use measured cells. Those controls still cannot prove that the cited result supports each sentence or that both compared metrics share a valid basis. Add claim-to-evidence scoring, reviewed semantic SQL checks and recurring live-model regression evaluation. OpenAI describes traces, structured grading and repeatable datasets as complementary evaluation tools; this app does not claim integration with those hosted services. [Official agent-evaluation guide](https://developers.openai.com/api/docs/guides/agent-evals).

Browser visual/click-through verification is blocked by an administrator-enforced browser policy check that the tool could not verify. Component rendering and API tests are useful but do not establish layout or interaction correctness in the real browser. Docker build/run is also unverified.

Already delivered: Stop/Retry, confirmed deletion, paginated history, bounded job admission, query/result limits, five-minute deadlines, usage counters, health endpoints, a persistent local service and an integrity-checked manual SQLite backup. Remaining operational work includes:

- Authentication, authorization, tenant isolation and TLS for any shared or internet-facing deployment.
- Durable execution checkpoints/resumption, worker supervision across multiple processes and a supported distributed job queue.
- Central monitoring, alerting, incident runbooks, cost budgets and dollar-cost accounting; token/model-call counters are not a spend cap.
- Backup scheduling, retention, encryption choices and a tested restore procedure. Local logs/state also need disk-capacity management.
- Measured performance/load budgets, dependency/security monitoring and platform-specific release validation. Passing a dependency audit does not prove absence of vulnerabilities.

## 6. Broader product capabilities not implemented

There is no arbitrary CSV/XLSX/PDF upload flow, sandboxed general-purpose Python/notebook workspace, interactive chart editor, token-by-token streaming, remote warehouse connector, external Drive/Slack source connector, scheduled refresh/report delivery, collaborative sharing, voice, web browsing or general file-generation service. The app works with its configured Summit Field warehouse and local references. None of these missing capabilities are represented by placeholder controls.

Before expanding to public access, choose and implement the identity/deployment model and complete its operational validation. For the current trusted local use, the next quality step is a wider reviewed question set and real browser acceptance testing when policy permits.

## Update for application release 2.1.0

The local improvement workspace is now implemented: versioned knowledge/ontology, stable skills, response profiles/examples, candidate comparison over 76 runtime contracts, structured feedback, review, publication and rollback. These features address local authoring and release traceability. Enterprise identity/roles, external connectors, new business data, calibrated semantic/model judges and a human-reviewed live benchmark remain gaps. See the current [feature map](developer/FEATURES.md) and [release notes](developer/RELEASE.md).
