# Feature coverage and proposed solutions

[Handbook](README.md) · [API/tool inventory](API_AND_TOOLS.md) · [Test inventory](reference/TEST_INVENTORY.md)

Status describes the current code. Test references are evidence for specific behaviors, not a promise of universal model correctness. The improvement workspace was approved and implemented in application release 2.1.0; see its [delivery status](UI_IMPROVEMENT_PLAN.md). Remaining work is called out separately.

## Product and platform capabilities

| ID | Capability / status | Current implementation and evidence | Remaining work / proposed solution |
|---|---|---|---|
| F01 | Conversational analysis — implemented | `agent.py`, `conversation.py`; `test_conversation_v2.py` | Expand reviewed natural-language coverage and domain ambiguity tests |
| F02 | Definitions and data-gap answers — implemented | Explanation tool plus published ontology/knowledge, alias and mapping validation; context/registry tests | Enterprise stewardship, effective dates and broader ambiguity review |
| F03 | Follow-up scope — implemented | Saved scope plus editable chips/form with revision conflicts and cancellation; scope/integration tests | Richer scope history comparison |
| F04 | Single-agent tool loop — implemented | 27 declared tools, LangGraph agent/tools nodes; mocked agent tests | Keep new capabilities registered explicitly; remove or clearly isolate dormant specialist paths during future refactor |
| F05 | Context retrieval — implemented | 26 frozen baseline references plus immutable custom assets, candidate preview and exact source hashes; context/registry tests | Evaluated embedding retrieval or external ingestion if future data requires it |
| F06 | Local ontology registry — implemented with limits | Concepts/metrics/entities/relationships, alias conflicts and approved measure/field mappings | Enterprise authority roles, temporal definitions and new formula/data support |
| F07 | Live inspection and EDA — implemented | Schema/sample/profile tools; `analytics.py`, app tests | Better UI discovery and reviewed inference design templates |
| F08 | Scoped retail metrics — implemented | Bound date/filter values and distinct counts; `scope.py` tests | Extend validated dimensions/measures and distinct event grains deliberately |
| F09 | Model SQL safeguards — implemented with limits | Read-only SELECT, parser/lineage checks, external access disabled; SQL/scope tests | Broader semantic checks and claim review; no blanket proof of query correctness |
| F10 | Retail playbooks — partial breadth | Nineteen baseline recipes and five validated filtered adapters | Add remaining filtered methods with independent expected results |
| F11 | Hypothesis templates — implemented | Eighteen bank templates; executable tests in `hypotheses.py` | Editable/versioned bank and additional enterprise scenarios |
| F12 | Persistent investigations — implemented | Hypothesis tree, criteria, tests, revisions, continuation; investigation/conversation tests | Better test-history UI and broader multi-turn evaluation |
| F13 | Causal diagnosis — limited by evidence | Descriptive predicates, accounting reconciliation and explicit caveats | New experimental/operational data and credible identification designs; extra agents alone cannot fill this gap |
| F14 | Durable preferences — implemented, limited | Explicit remember request and `memories` table | Review/edit/delete/expiry and distinction between personal conventions and official definitions |
| F15 | Conversation management — implemented | New/rename/delete, paginated history, retry; operations/app tests | Broader search beyond the current recent-title list; multi-user sharing is absent |
| F16 | Evidence and release provenance — implemented | SQL/E/D references, binding and exact release/skill/profile/source versions in Why this answer | Broader claim-to-evidence semantic grading |
| F17 | Analytical answer design — implemented | Three profiles, guided authoring, measured fixture preview, good/bad examples, preserved evidence and limitations | Richer layout customization with field/unit validation |
| F18 | Chart interaction/editor — partial | Nineteen designed visuals and seven generic query chart types | General chart editor and alternative visualization selection with field/unit validation |
| F19 | Exports — implemented subset | Analysis JSON, evidence CSV, browser-built conversation Markdown | General DOCX/PPTX/XLSX artifact service absent |
| F20 | Structured feedback — implemented | Issue categories/correction, original evidence/version snapshot, triage and reviewed regression draft conversion | Enterprise assignment, notifications and authenticated reviewer identity |
| F21 | Evaluation workbench — implemented with semantic limits | 76 bundled runtime cases, custom suites, frozen comparison, separate bounded jobs, review and promotion gates | Human-curated live benchmark and calibrated semantic/model judges; fixture authorship is not human benchmark approval |
| F22 | Job controls — implemented local | Two workers, deadlines, Stop/Retry, restart interruption; runtime/operations tests | Distributed queue, durable execution checkpoints and public-scale admission policies |
| F23 | Progress — implemented | Tool/job messages via polling | Token streaming absent; progress does not reveal private reasoning |
| F24 | Usage and evaluation budgets — implemented subset | Request/token accounting and conservative preflight reservations for explicit live evaluations | Dollar-price estimates, organization policy and global chat spend caps |
| F25 | Local service and health — implemented | LaunchAgent, liveness/readiness, bounded resources | Operational dashboards, alerting, retention, load targets and restore drills |
| F26 | Backup — implemented manual | Consistent SQLite backup API plus integrity check; operations tests | Scheduling, retention/encryption policy and rehearsed restore |
| F27 | Docker packaging — provided, unverified execution | Dockerfile/Compose with read-only root and warehouse mount | Build/run acceptance on Docker-capable host |
| F28 | Public enterprise deployment — missing | Current app trusts one local user | Identity, role/data authorization, tenancy, TLS, managed secrets and operational validation |
| F29 | Ingestion/connectors/uploads — missing | Fixed local warehouse and explicit context library | Governed connectors/import, schema reconciliation and source-specific access checks |
| F30 | Scheduled delivery, collaboration, voice, web browsing — missing | No active implementation | Separate product scope, tools, security and acceptance criteria |

## New improvement capabilities in release 2.1.0

| Capability | Delivered behavior | Verification |
|---|---|---|
| Registry and migration | 53 initial assets: 26 sources, 4 concepts, 19 skills, 3 profiles, 1 evaluation suite; optimistic drafts, immutable versions and releases | Registry migration/concurrency/immutability tests |
| Admin authoring | Five sections with guided forms, read-only built-ins, duplication, validation and preview | Frontend contracts plus browser acceptance in release notes |
| Candidate promotion | Complete deterministic foundation, exact snapshot/runtime fingerprints, operator review and stale-parent checks | Registry/evaluation gates and negative changed-code acceptance |
| Restoration | Restore previously published active pointer; keep old answers and audit | Rollback, restart and immutable snapshot tests |
| Evaluation isolation | Single worker separate from two interactive slots; context-local temporary conversations and memories | Parallel isolation, cancellation and restart tests |
| Chat transparency | Profile selection, exact source/asset versions, effective scope and structured feedback | Cross-component snapshot and frontend tests |
| Stable recipes | Explicit slug-to-chapter IDs replace positional pairing; calculations unchanged | Nineteen playbook/visual and stable-contract regressions |

## The nineteen solution playbooks

Each row has an executable all-business baseline. “Filtered adapter” means explicit support in `run_scoped_playbook`; it does not imply every advanced visual extension is present. Source specifications are in the [playbook library](../../../retail-data-analyst/references/playbooks.md), [visual specifications](../../../retail-data-analyst/references/visual-specs.md), and [existing output coverage](../OUTPUT_DESIGN.md).

| Slug | Business question and current output | Filtered adapter | Key interpretation limit |
|---|---|---|---|
| `trend` | Sales trend across current/comparison time | Yes | Partial weeks and unequal explicit periods must be visible |
| `pvm` | Price/volume/mix accounting bridge with Shapley allocation | No | Realized rate includes discount effects; attribution is not causal elasticity |
| `growth` | Contributions to sales change | Yes | Named baseline is division-based; reconciled accounting contributions are not independent mechanisms |
| `margin` | Sales-cohort revenue/cost/margin after linked returns | Yes | Merchandise margin excludes shipping, labor and operating costs |
| `seasonality` | Calendar/retail-week patterns | No | Two years, partial fiscal boundaries and week 53 constrain inference |
| `scorecard` | Multi-metric merchandise performance | Yes | Buyer/order reach overlaps across product groups |
| `channels` | Channel/store sales, growth and margin | No | Selling-store and digital market attribution are different concepts |
| `concentration` | Pareto concentration and exposure | Yes | Prior-period concentration change and broad drilldowns remain extensions |
| `pricing` | Actual versus regular price and markdown distributions | No | Current-window distribution is not automatically a prior-period comparison |
| `promotions` | Associated campaign sales and timeline | No | No randomized lift; leading campaign timeline may lack full before/after windows |
| `cohorts` | First-observed purchase cohorts and mature repeat cells | No | Observation starts in 2024; first observed is not true acquisition |
| `lapse` | Monthly active/lapsed/reactivated states | No | Illustrative global 90-day threshold, not a validated churn model |
| `segments` | Descriptive behavioral segment profiles | No | Rule-based thresholds are simulation choices |
| `affinity` | Basket co-occurrence and lift | No | Small bases need suppression/review; basket lift is not incremental impact |
| `loyalty` | Attached membership and mix | No | Member differences cannot identify program causality |
| `returns` | Cohort return rates, reasons and elapsed-return heatmap | No | Original sale cohort and return-date reason views must be distinguished |
| `velocity` | SKU selling velocity versus latest completed stock | No | High stock does not establish safe delisting or lost-demand causality |
| `inventory` | Completed weekly stock and flow history | No | Balances cannot be summed across snapshots; no daily lost demand |
| `fulfillment` | Completed order method mix | No | No actual-delivery events or fulfillment cost for reliability/profitability |

## Mapping the original C01–C48 proposal

The [earlier reference](../architecture-reference.txt) proposed a component backlog. This mapping preserves its intent without treating proposal text as delivered code.

| Original ID(s) | Proposal | Current status and explanation |
|---|---|---|
| C01 | Repository | Implemented local Git source and separate Milky Way working copy |
| C02, C47 | Docker runtime / Compose | Configuration provided; container acceptance unverified |
| C03 | FastAPI backend | Implemented, 65 OpenAPI operations including local admin/evaluation routes |
| C04 | React shell | Implemented chat and data workspace |
| C05 | Raw retail model | Missing separate raw-event ingestion tier; generated normalized facts/dimensions exist |
| C06 | Transformation pipelines | Partial: synthetic generator and analytical views; no enterprise orchestration/lineage scheduler |
| C07 | Curated analytical model | Implemented 23 tables and four analytical views |
| C08 | Scenario generator | Partial: deterministic configurable synthetic generator; no labeled causal incident authoring system |
| C09 | Ground truth | Partial: reproducibility, accounting rules and golden SQL; no broad causal incident truth set |
| C10 | Metadata catalog | Implemented catalog and dictionary |
| C11 | Dataset lineage | Partial: SQL/code and explicit join paths; no production lineage service |
| C12 | Human annotations | Implemented local ontology/knowledge authoring, ownership labels, revisions, preview and reviewed publication; authenticated enterprise stewardship absent |
| C13 | Code enrichment | Implemented bounded retrieval over selected source code; no external repository ingestion |
| C14 | Metric definitions | Implemented documents and scoped metric expressions |
| C15 | Retail knowledge base | Implemented local methods/reference corpus; enterprise event knowledge absent |
| C16 | Historical query examples | Implemented curated examples; no mined usage history |
| C17 | Context retrieval | Implemented lexical section index |
| C18 | Runtime inspection | Implemented schema, sample, count and profiles |
| C19 | Memory | Implemented bounded text plus durable scope/preferences/investigations |
| C20 | Context search tool | Implemented |
| C21 | Dataset inspection tool | Implemented |
| C22 | Read-only SQL tool | Implemented with bounded execution and selected semantic checks |
| C23 | Metric tool | Implemented definition retrieval and structured measure queries |
| C24 | Analytics tool | Implemented recipes, arithmetic and supported statistics |
| C25 | Visualization tool | Implemented measured chart specification and renderers |
| C26 | Memory tools | Implemented search and explicit save; lifecycle management partial |
| C27 | Agent state | Implemented graph state and persistent domain state; exact graph checkpointing absent |
| C28 | Primary Retail Agent | Implemented single agent |
| C29 | Self-correction | Implemented tool diagnostic/retry loop; no guarantee every error is corrected |
| C30 | Analysis validation | Partial: values, scope, grain checks, references and criteria; general semantic claim proof absent |
| C31 | Sales diagnosis | Implemented descriptive methods and persistent investigation |
| C32 | Margin diagnosis | Implemented merchandise basis; full operating profitability absent |
| C33 | Promotion analysis | Implemented associated sales; incremental causal design absent |
| C34 | Inventory analysis | Implemented weekly balances/flows; lost demand absent |
| C35 | Customer analysis | Implemented cohorts/segments/recency/loyalty; causal program evaluation absent |
| C36 | Category analysis | Implemented product hierarchy summaries; advanced lifecycle/assortment inputs absent |
| C37 | Weekly business review | Partial ingredients; no dedicated complete synthesis workflow |
| C38 | Conversational UI | Implemented |
| C39 | Analytical response cards | Implemented structured answer and measured cards |
| C40 | Evidence explorer | Implemented evidence/source access; deeper claim mapping is proposed |
| C41 | SQL/results viewer | Implemented |
| C42 | Analysis history | Implemented persistent local history |
| C43 | Golden questions | Partial: legacy five natural-language scenarios plus 76 developer-authored runtime cases; representative live semantic coverage remains a gap |
| C44 | Golden SQL | Implemented independent calculations for selected scenarios |
| C45 | Automated eval runner | Implemented legacy CLI plus bounded workbench with 76 foundation contracts, custom/live suites and review gates |
| C46 | Regression dashboard | Implemented baseline/candidate workbench with evidence, differences, coverage and review |
| C48 | Local deployment | Implemented startup and login service |

## Gaps grouped by the solution they require

| Gap | Proposed solution | Dependency / acceptance evidence |
|---|---|---|
| Runtime regressions do not establish broad live quality | Reviewed domain/live suites and failure-driven cases | Independent expected values, hidden goldens, human-calibrated semantic review |
| Citation existence does not prove support | Claim-level review over exact cited rows/definitions | Negative cases where a valid ID supports the wrong metric or scope |
| Filtered methods incomplete | Add one adapter at a time with grain-specific SQL | Agreement with independent queries; original filters and comparison basis retained |
| Missing business-event and incident labels | Versioned scenario controls and expected outcomes | Deterministic generator fixtures, documented assumptions, no unsupported causal claims |
| Missing traffic/delivery/lost-demand data | Extend the data model and event generator or governed real-source connector | Field contracts, temporal consistency, linkage and validation tests before new claims |
| No release/CI pipeline | Automated deterministic test/build/docs checks and versioned release receipts | Clean install and reproducible artifact checks on supported target platforms |
| Docker/platform and broader accessibility acceptance incomplete | Run dedicated platform checks and assistive-technology review | Current admin browser journey passed; container/startup and wider accessibility still require recorded results |
| No durable execution resume | Explicit checkpoint and worker design | Crash/restart correctness, idempotent side effects and obsolete-revision rejection |
| No managed operations | Measured load/cost budgets, monitoring, retention and restore runbook | Stress/failure tests, alert drills and successful isolated restore |
| No public identity/tenancy | Choose deployment/identity model then enforce data access everywhere | Cross-tenant denial, role boundaries, TLS and operational review |

The requested improvement workspace, scope/answer transparency and evaluation feedback loop are delivered. The next quality priority is domain-reviewed candidate-specific cases and representative live semantic review. Data acquisition, distributed execution and public deployment have separate dependencies and should not be represented as simple UI toggles.
