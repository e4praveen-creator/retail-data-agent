# Production readiness for a trusted local installation

[Handbook](README.md) · [Architecture](ARCHITECTURE.md) · [Release evidence](RELEASE.md) · [Maintenance](REPOSITORY_MAINTENANCE.md)

## Supported target

The requested target is one trusted developer or administrator on one machine. Run the supplied loopback launcher or Compose configuration with one application worker. This chapter records engineering controls and their verification; it is not a security certification or a guarantee of model answer quality.

All development belongs under `Milky Way 2.0/`. The original sibling application and synced `sources/` are separate. Private credentials, conversations, backups, the generated warehouse and installed dependencies are preserved outside source control.

## How OpenAI guidance is applied

OpenAI publishes several applicable guides, rather than one universal “data agent compliance” specification. The following mapping is this project's engineering interpretation, reviewed September 26, 2026. Product/API capabilities can evolve; recheck the linked primary sources when changing model or provider behavior.

| Official guidance | Milky Way implementation | Practical limit |
|---|---|---|
| Separate untrusted content from developer instructions and constrain data crossing agent boundaries. [Agent safety](https://developers.openai.com/api/docs/guides/agent-builder-safety) | Static application rules remain in instructions. Retrieved sources, saved memory, conversation text and editable workspace assets enter reference input. Tools are selected from the server's registry and validated before execution. | Prompt separation reduces injection opportunities; it cannot prove model immunity. Documents remain data and cannot grant permissions. |
| Use strict function schemas and validate function arguments. [Function calling](https://developers.openai.com/api/docs/guides/function-calling) | Strict provider schemas, explicit nullable optional fields and local type/shape checks precede semantic handlers. Unknown tools fail closed. Scope, SQL and evidence checks remain necessary. | Structural correctness does not establish that a query answers the business question. JSON-string payloads also need domain validation. |
| Develop scoped evaluations, include typical/edge/adversarial cases, and combine automation with human review. [Evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices) | Offline regression suite, 76 runtime contracts, candidate/baseline comparisons, fixed provenance, injection/invalid-tool cases and reviewed publication gates. Live model checks are explicit opt-in. | The bundled suite is developer-authored. Passing it does not establish enterprise semantic quality or cover every custom asset. |
| Protect keys, isolate environments, bound resource use and monitor operational behavior. [Production best practices](https://developers.openai.com/api/docs/guides/production-best-practices) | Server-only environment settings; private state excluded from Git; isolated test memory; bounded worker queues, query deadlines and model budgets; health endpoints and sanitized correlated errors. | Local secrets are not a managed vault. External monitoring, distributed execution and public authentication are not installed. |
| Keep reusable context stable and measure cache behavior for the actual model. [Prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching) | Application instructions are separated from changing reference input. Existing model selection and API settings are preserved. | No cache-hit, token-cost or latency improvement is claimed without a measured live run; no model-specific caching parameters were added. |

## Implemented controls and ownership

| Boundary | Owner | Verification |
|---|---|---|
| Model instructions, reference input and callable tool contracts | [agent.py](../../backend/agent.py), [tool_contracts.py](../../backend/tool_contracts.py) | Tool/input regression cases in the [test inventory](reference/TEST_INVENTORY.md) |
| Read-only warehouse, query size/rows/deadline, no file/network SQL access | [data.py](../../backend/data.py), [sql_checks.py](../../backend/sql_checks.py), [scope.py](../../backend/scope.py) | SQL, scope, runtime and independent metric reconciliations |
| Immutable release captured at job admission | [workspace_runtime.py](../../backend/workspace_runtime.py), [workspace_assets.py](../../backend/workspace_assets.py) | Publication, rollback, concurrency and in-flight snapshot tests |
| Expected answers excluded from evaluation context; test state isolated | [workspace_evaluations.py](../../backend/workspace_evaluations.py) | Evaluation suite, budgets, release gate and memory-isolation checks |
| Bounded HTTP body bytes and receive time, response headers, safe caching | [http_boundary.py](../../backend/http_boundary.py) | [HTTP boundary tests](../../tests/test_http_boundary.py) and operations suite |
| Documentation references cannot expose private files | [guide_api.py](../../backend/guide_api.py) | Linked private files, symlinks, missing reference and cache invalidation tests |
| Atomic final answer persistence and stale-result prevention | [storage.py](../../backend/storage.py), [main.py](../../backend/main.py) | Cancellation, scope revision, persistence and rollback tests |
| Reproducible browser build and deferred administration UI | [package.json](../../package.json), [chat entry](../../frontend/chat.jsx) | Rendering suites, build/import checks and local browser smoke |
| Safe regenerable-file cleanup and verified SQLite backup | [maintenance.py](../../maintenance.py) | Path/symlink/retention tests and verified backup receipt |

## Release acceptance workflow

1. Back up the current SQLite state before applying application changes. Never copy only a live WAL database file.
2. Install from the existing dependency locks. Run the unified offline checks described in [maintenance](REPOSITORY_MAINTENANCE.md).
3. Regenerate public contract references after intentional source changes; review the changed schemas, hashes and test outcomes. Rebuild and validate the handbook.
4. Run browser smoke checks for chat, deferred workspace loading, admin navigation and reload. A production bundle must include its hashed chunks.
5. Restart the local service. Confirm `/health/ready`, the application version, preserved records and guide access. A configured key is not evidence of a successful provider request.
6. For content changes, use draft → preview → candidate → compare → review → publish. A code change invalidates prior evaluation provenance; rerun the relevant comparison before publishing.
7. For a model or prompt change, add representative reviewed live cases and run them with an explicit budget. Check tool choice, filters, arithmetic, claims, citations and limitations against measured evidence. Offline mocked tests cannot replace this step.

Current execution counts, actual browser checks, cleanup totals and unperformed checks are recorded in [release notes](RELEASE.md). Historical receipts retain their original versions and dates.

## Operations and remaining limits

- Keep the launcher on `127.0.0.1:8766`. Local origin and application-header checks are browser protections, not sign-in or tenant isolation.
- Keep one Uvicorn worker. Chat admission, cancellation and the evaluation executor are process-local. Job metadata persists, but interrupted model execution does not resume automatically.
- Keep backups outside any cleanup target. Verify a restore in a separate state directory before replacing a working installation.
- Keep the configured model until reviewed comparisons justify changing it. Context, skill or prompt changes can alter answer behavior even without a model change.
- No fresh paid model-quality benchmark, container run, broad load test or external dependency-advisory/security audit is claimed by this cleanup release.
- Public hosting or shared users require a separately designed identity/authorization layer, tenant-aware data access, managed secrets, durable scheduling and operational acceptance. They are outside the confirmed local deployment target.
- Data limitations remain: synthetic observations do not establish causal effects; missing traffic, delivery-event, cost and experiment data cannot be repaired through prompting or ontology additions.
