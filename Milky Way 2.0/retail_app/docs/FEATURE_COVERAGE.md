# Feature coverage: conversational retail analysis

This app implements a focused local retail analyst experience. “ChatGPT-style” describes its conversational interaction and reviewable analysis; it does not mean complete ChatGPT feature parity. Milky Way 2.0 uses one conversational Retail Agent with a shared analysis scope and persistent investigations. See the [implemented architecture](MILKY_WAY_2_ARCHITECTURE.md). The Milky Way deck informs terminology and analytical behavior only.

OpenAI's [dataset-analysis workflow](https://learn.chatgpt.com/use-cases/datasets-and-reports) describes exploring source data and producing reviewable findings with charts and caveats. Its [KPI root-cause workflow](https://learn.chatgpt.com/use-cases/kpi-root-cause-analysis) emphasizes metric definitions, useful breakdowns, source-backed findings and alternative explanations. These are comparison references, not an exhaustive ChatGPT product specification or a promise that this app implements their full tool ecosystem.

| Capability | Current app | Boundary |
|---|---|---|
| Open-ended questions and follow-ups | One agent chooses explanation, scoped analytics or investigation; session scope persists across turns and restarts | Needs configured API credentials/model; recent text context is bounded |
| ChatGPT-style visual experience | Black system text, neutral surfaces, responsive sidebar, central transcript/composer, Markdown tables | Real browser layout/click-through QA remains blocked |
| Saved chat management | New, search recent chats, rename, paginated messages and confirmed deletion | Local single-user SQLite; no shared workspaces or tenant separation |
| Stop and retry | Cooperative Stop and eligible retry of the unanswered question | In-flight provider calls can wait for their bounded timeout; no checkpoint resume |
| Progress updates | Visible tool/job progress | No token-by-token streaming |
| Retail playbooks | All 19 baseline recipes and visual designs; filtered adapters for trend, growth, margin, scorecard and concentration | Other filtered methods require an explicit adaptation or a precise limitation; larger A–I workflows remain partial |
| Answer structure | Headline, scope/metric, visible primary visual, supporting evidence, interpretation, limitations and next question | Single totals use metric cards; documentation/data-gap answers have no invented chart; fallback layouts are identified |
| Hypothesis work | 18 starting templates plus new data-grounded hypotheses; editable tree, revisions, falsifiers, declared criteria and immutable test evidence | Changed hypotheses and dependencies become stale; tests need an appropriate measured criterion |
| EDA and statistics | Schema/samples, column profiles and supported statistical tests over measured results | No arbitrary code notebook or unrestricted Python execution |
| Root-cause investigation | Agent selects investigation from intent, tests competing hypotheses and resumes saved progress; users can correct or exclude branches | The measured predicate determines the verdict; accounting contribution/correlation is not causal identification |
| Charts and tables | Dedicated visuals for all 19 playbooks, including reconciled waterfalls, heatmaps, scorecards, campaign timelines and inventory panels; evidence-bound query charts and visible tables | Only measured datasets are rendered; old reports may need rerunning; secondary workflow coverage varies; no general chart editor |
| Evidence and source inspection | SQL, parameters, evidence tables, document chunks, references, traces and limitations | ID existence checks do not prove semantic support for each claim |
| Analysis exports | JSON, evidence CSV and complete-conversation Markdown | Markdown includes narrative/SQL, not all rows; no general DOCX/PPTX/XLSX authoring service |
| Local context and memory | Domain retrieval, durable session scope/summary, saved investigations and explicit remembered conventions; history persists in SQLite | Historical examples and templates are not current findings; no unlimited verbatim model context, self-training or full historical-chat ingestion |
| Feedback and usage | Helpful/review flags plus model-call and token counters | No automatic learning, dollar-cost estimate or account-level spend cap |
| Dataset access | Configured Summit Field DuckDB opened read-only | No arbitrary file upload, remote warehouse connection or ingestion UI |
| Operations | Bounded jobs/SQL/results, deadlines, health checks, launch service and manual verified backup | Distributed execution, monitoring/alerts, backup retention and restore drills remain |
| Public/shared access | Not implemented | Requires identity, authorization, tenant isolation, TLS and deployment review |
| External apps and automation | Not implemented | No Drive/Slack connectors, scheduled reports/refresh, voice or web-browsing agent |

## Playbook-specific output coverage

The answer contract comes from the actual project playbooks and detailed visual specifications. `get_playbook_design` and `present_answer` stay inside the primary analyst's existing tool loop; they do not introduce a mandatory multi-agent pipeline. Baseline charts use the same measured outputs as the supporting tables, and narrower questions must preserve the requested filters in their own SQL and visuals.

New current-window datasets support monthly loyalty/fulfillment mix, return elapsed-day heatmaps, customer states and segment profiles, inventory stock/flows, and actual-versus-regular prices. Scorecards and channel/store growth metrics query both selected periods. A comparison shown in the date controls does not imply that every panel has a prior-period overlay. Promotion timelines are descriptive and may have incomplete before/after coverage; lapse states use an illustrative global 90-day rule.

[OUTPUT_DESIGN.md](OUTPUT_DESIGN.md) lists each primary visual and remaining boundaries. [DOMAIN_ASSETS.md](DOMAIN_ASSETS.md) records which project assets supply definitions, methods, hypotheses and provenance.

## Verification and release gates

Deterministic tests, representative live model checks and frontend rendering checks are separate forms of evidence; none establishes universal answer correctness. Consult [Milky Way 2.0 verification](MILKY_WAY_2_VERIFICATION.md) for current results; [TEST_REPORT.md](TEST_REPORT.md) preserves the inherited baseline record. The initial natural-language harness compares measured outputs with independent golden queries, retaining manual review criteria for scope, lineage and narrative claims. Wider regression datasets and claim-level review remain necessary; OpenAI's [agent-evaluation guide](https://developers.openai.com/api/docs/guides/agent-evals) describes how trace review and repeatable datasets can support that work.

Browser visual and interaction acceptance could not be completed because the administrator-enforced browser policy could not be verified. Docker build/run is unverified. Public production deployment remains outside the supported local single-user scope. [MISSING.md](MISSING.md) lists the concrete remaining evidence, product and operational gaps.
