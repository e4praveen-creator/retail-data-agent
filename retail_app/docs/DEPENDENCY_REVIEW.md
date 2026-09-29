# Dependency review

Audit date: **2026-09-26 UTC**. Python tool: **pip-audit 2.10.1**, using the public PyPI vulnerability service. Frontend tool: **pnpm audit**, using npm advisories. The Python inventory was read from the **3.12.14** application environment; the frontend audit used its lockfile. Package names and versions were queried; application code, warehouse data, conversations and credentials were not uploaded.

## Results and limits

| Inventory | Packages | Known advisory records | Skipped packages | Verification |
|---|---:|---:|---:|---|
| Installed baseline before the coordinated upgrade | 39, including pip | 53 across 12 packages | 0 | Installed package metadata audited |
| Coherently resolved replacement libraries | 46 | 0 | 0 | Resolver succeeded; scanner exited 0 |
| Replacement installer, pip 26.2.1 | 1 | 0 | 0 | Independently scanned; scanner exited 0 |
| Application environment after installation | 48, including pip | 0 | 0 | Fresh installed inventory; scanner exited 0; `pip check` passed |
| Frontend lockfile, including development dependencies | 174 total dependency entries | 0 | Not reported by pnpm | `pnpm audit --json` exited 0; all severity counts zero |

The baseline's 53 records include duplicate vulnerability aliases and shared package mappings. They correspond to **29 distinct GHSA advisory families**, not 53 independently confirmed exploits. Static source review found that several advisories depend on features this application does not enable. That reduces the observed attack surface; it does not justify retaining flagged dependencies.

The precise claim supported by the Python scans is: **no known vulnerability advisories were reported for the 46 resolved library versions or the 48 actually installed packages on 2026-09-26, with no packages skipped**. The frontend scanner also reported zero known advisories. This is not proof that those packages or the application are free of vulnerabilities. Operating-system packages, container images, browser behavior and the entire deployment configuration were not evaluated by these scanners.

The installed inventory contains all 46 expected library versions plus pip 26.2.1 and the retained compatibility package exceptiongroup 1.3.1. No expected packages were missing, and both additional packages were included in the clean installed-environment scan. The frontend metadata lists 146 dependency entries, 28 development entries and 26 optional entries; optional entries overlap the other categories, so the reported total is 174.

The ignored local report, `retail_app/state/dependency-audit.json`, retains raw baseline, replacement, installed-environment and frontend scanner results, exact package versions, official advisory details and reachability notes. Reports are machine-local verification artifacts; they are not included in Git. The reproducible application dependency set is recorded in `retail_app/requirements.lock.txt`.

## Coordinated replacement set

The seven direct libraries resolved successfully together on Python 3.12.14/macOS arm64 using a clean `pip --dry-run --ignore-installed` resolution against public PyPI:

| Direct library | Installed exact version |
|---|---|
| FastAPI | 0.141.1 |
| Uvicorn | 0.54.0 |
| DuckDB | 1.5.5 |
| LangGraph | 1.2.12 |
| HTTPX | 0.28.1 |
| NumPy | 2.5.3 |
| SciPy | 1.18.1 |

The full resolution contains 46 libraries. Significant transitive upgrades include Starlette 1.7.0, LangChain Core 1.6.5, LangGraph Checkpoint 4.2.0, LangGraph SDK 0.4.5, LangSmith 0.14.1, AnyIO 4.15.1, orjson 3.12.0, Requests 2.34.2 and urllib3 2.8.0. The installer was separately upgraded to pip 26.2.1; it is not an application-library requirement.

These are dependency changes within the existing FastAPI → primary LangGraph agent/tool loop → read-only DuckDB architecture. They do not require a forced multi-agent sequence or the addition of checkpoint/cache backends. Resolver success alone does not establish runtime compatibility; application regressions and live evaluations remain necessary.

## Baseline findings and reachable surfaces

- **HTTP serving:** Starlette 0.49.3 was newer than the previously identified Range-header fix, and the application additionally rejects Range requests. It still had later advisories affecting malformed URL reconstruction, form parsing, class-based endpoints and Windows static-file handling. The application uses strict allowed hosts, JSON requests and function endpoints on macOS, reducing several documented prerequisites. The serving library is nevertheless directly used and should be upgraded. See the maintainer's [Host-header advisory](https://github.com/Kludex/starlette/security/advisories/GHSA-86qp-5c8j-p5mr), [form-parsing advisory](https://github.com/Kludex/starlette/security/advisories/GHSA-82w8-qh3p-5jfq), and [earlier Range advisory](https://github.com/Kludex/starlette/security/advisories/GHSA-7f5h-v6xp-fcq8).
- **Graph persistence and caching:** Old LangGraph/Checkpoint versions had unsafe deserialization paths. This application compiles its local graph without persistent checkpointers or cache backends; it stores plain application JSON in SQLite. It does not load attacker-supplied checkpoint bytes or call remote SDK resource APIs. Upgrade the package family before enabling those features. See the maintainers' [JSON checkpoint advisory](https://github.com/langchain-ai/langgraph/security/advisories/GHSA-wwqv-p2pp-99h5) and [cache advisory](https://github.com/langchain-ai/langgraph/security/advisories/GHSA-mhr3-j7m5-c7c9).
- **Prompt loading and tracing:** The application does not use legacy LangChain prompt loaders, public LangSmith prompt pulls, LangSmith tracing middleware, or `ChatOpenAI` image-token counting. The model endpoint is called directly with HTTPX. External tracing configuration was not inspected and could change exposure. See the [LangChain prompt-loader advisory](https://github.com/langchain-ai/langchain/security/advisories/GHSA-qh6h-p6c9-ff54) and [LangSmith tracing middleware advisory](https://github.com/langchain-ai/langsmith-sdk/security/advisories/GHSA-f4xh-w4cj-qxq8).
- **Supporting libraries:** AnyIO's documented non-ASCII TLS and process-worker conditions were not found in the fixed ASCII API endpoint/thread-worker paths. Requests/urllib3 are transitive rather than the application's direct networking layer. orjson is also transitive; indirect serialization was not exhaustively traced. Upgrade these packages instead of treating absent direct calls as a security guarantee. See the maintainers' [AnyIO TLS advisory](https://github.com/agronholm/anyio/security/advisories/GHSA-82r6-8w77-94w6) and [Requests utility advisory](https://github.com/psf/requests/security/advisories/GHSA-gc5v-m9x4-r6x2).
- **Installer and CLI:** The baseline pip had installer-time advisories, separate from normal HTTP request handling. Click is used for command-line startup and is not exposed as an arbitrary HTTP command runner. The Click advisory detail fetch was unavailable, so its baseline reachability remains untriaged beyond scanner data; the replacement version scans clean.

These assessments are based on source review and published advisory prerequisites, not exploit testing or exhaustive transitive call tracing.

## Integration and release checks

1. **Completed:** install the coherent pinned replacement set and update pip separately.
2. **Dependency check completed:** `pip check` reports no broken requirements. Run application regressions, warehouse integrity and golden-result comparisons after the upgrade; those outcomes are recorded separately from this dependency audit.
3. **Completed:** re-inventory and audit the installed environment, including pip. The extra exceptiongroup compatibility package was identified and scanned; it has no reported advisories in this run.
4. Run the manually authorized live question evaluations and complete their narrative/semantic review. Dependency scanning does not measure answer correctness.
5. Verify browser interactions and deployment/container behavior separately. This review does not approve shared or internet-facing deployment.

To repeat the Python package scan, install pip-audit in a separate temporary environment, export the application's installed package names/versions with `.venv-runtime/bin/python -m pip list --format=freeze`, then audit that pinned inventory with `pip-audit --requirement <inventory> --no-deps --disable-pip --format=json`. Repeat the frontend check with `pnpm audit --json` from `retail_app`. Do not install audit tooling into the application environment or include credentials in audit inputs.
