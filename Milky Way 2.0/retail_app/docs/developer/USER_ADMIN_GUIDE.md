# User and administrator guide

[Handbook](README.md) · [Architecture](ARCHITECTURE.md) · [Technical improvement-workspace design](IMPROVEMENT_WORKSPACE_DESIGN.md) · [Release notes](RELEASE.md)

This guide covers the Milky Way 2.0 application, release 2.1.1. Everything described here belongs to the nested `Milky Way 2.0/` folder. Start the app with `Start Milky Way.command` or `./retail_app/start.sh`, then open [Milky Way](http://127.0.0.1:8766/). The sidebar's **Improve workspace** entry opens the administration interface. The guide is also served at `/guide`.

## 1. Who uses each part

| Person | Main activities | Entry point |
|---|---|---|
| Analyst or business user | Ask a question, refine scope, inspect evidence, report an answer issue | Chat |
| Domain administrator | Add definitions, aliases, approved metric mappings, methods and answer examples | Improve workspace → Knowledge & ontology / Skills / Answer design & examples |
| Quality reviewer | Examine expected checks and outputs, compare versions, approve or reject applicability | Improve workspace → Evaluations |
| Release operator | Freeze a candidate, select its reviewed evaluation, publish or restore a prior release | Improve workspace → Feedback & releases |
| Developer | Add a calculation/tool, support new data, change validation/rendering, run regressions, upgrade the application | Source files and development guide |

These are responsibilities, not enforced login roles. This release runs for a trusted local operator. Anyone with access to the local application has its administrator capabilities. Operator and reviewer names are audit labels, not authenticated identities. Use the localhost installation; enterprise authentication, tenant isolation and independent approval roles require a separate deployment implementation.

## 2. Ask and refine a question

1. Start a new chat. Select the date window and response profile.
2. Ask a specific question, such as “Show Web Footwear sales and units for July 2025 versus July 2024. Plot the comparison.” Explicit question dates can refine the saved scope.
3. Follow progress as the agent retrieves definitions and queries the warehouse. **Stop** requests cancellation; **Retry** resumes by retrying the last unanswered question without adding it twice.
4. Inspect the answer's scope, metric/return basis, chart, supporting values and limitations. Values come from the synthetic warehouse. Evidence references identify rows and reproducible queries for this answer.
5. Continue naturally: “Same for Mobile app”, “Group by category”, or “What drove that change? Test competing explanations.” Scope and investigation state persist.

**Scope chips and the scope editor.** Use the saved scope controls to change dates, filters, metric or return basis. Change grouping through a chat request such as “Group by category.” The editor saves the complete displayed filter list; removing a filter removes it from the next scope. A stale browser revision is rejected: reload the chat and reapply the intended correction. Editing scope stops an active answer and invalidates investigation findings that depend on the prior scope.

**Response profiles.** Quick answer uses a shorter initial table and concise writing instructions. Business review is the balanced default. Analyst detail exposes more initial rows and method details. Evidence, exact scope, units and material limitations remain available in every profile. Profiles influence model writing; they cannot guarantee identical wording across model runs or invent unavailable data.

**Why this answer?** Open the answer's provenance drawer to inspect its effective scope, release ID, selected skill and profile versions, retrieved sources and measured evidence. The release is captured before background execution. Publishing while an answer runs does not change that answer's snapshot. An old answer remains associated with its original release after rollback.

**Investigations.** The hypothesis panel records small, falsifiable statements, tests and verdicts. Edit or exclude a hypothesis and select **Continue / retest**. Changed branches become stale until retested. “Supported descriptively” means the declared measured predicate passed; it does not establish causation. An unresolved branch must stay visible.

**Memory.** Ask explicitly to remember a business preference. Ordinary chat scope, summary and investigation progress persist automatically; they do not require a remember command. Memories are reference content and cannot grant tool permissions. Workspace definitions are versioned separately from personal remembered conventions.

## 3. Understand drafts, candidates and releases

| State | Meaning | Changes normal answers? |
|---|---|---|
| Draft | An editable asset with a revision number | No |
| Candidate | An immutable collection of exact asset versions, frozen for evaluation | No |
| Published release | A candidate that passed promotion checks and was activated | Yes, for new answers |
| Previously published release | A historical, validated release available for restoration | Only if restored |
| Built-in | Imported read-only baseline content | Already in the initial release; duplicate to customize |

Saving a draft and publishing are different operations. Editing after creating a candidate does not change that candidate. Create another candidate to include later edits, then evaluate that new version. The active release pointer changes atomically. Revision conflicts prevent one browser from silently overwriting another browser's draft.

Built-in knowledge and the nineteen skill contracts are seeded into the local registry with source hashes. Their source files remain developer-maintained. Existing registry versions are historical records; changing a source file is not a silent hot edit of a published asset. To change business content in an existing workspace, use a custom draft and publish it. To change executable behavior, make a code change and release/test the application.

## 4. Add ontology or domain knowledge

Open **Improve workspace → Knowledge & ontology**. Choose the create type and create a source document or business concept.

### Source document

Enter a name, a short description under **What does this mean?**, the complete reference text under **Source content**, common terms/aliases and source references. Source references are provenance labels; this release does not crawl a URL or fetch an attachment. Paste the approved business context into **Source content**. Enter each alias on its own line and click outside that field to apply it before saving. Avoid copying evaluation expected answers into ordinary context.

Example:

> Name: Selling region and digital market region. Definition: Store region means the selling store's region. For a digital transaction, use market region to describe the attributed market. Do not describe this as the shopper's home region. Aliases: digital territory; attributed region.

Save the draft, validate it, and use **Preview saved draft** with “What region should I use for digital sales?” The preview shows the exact saved candidate source and version. Unsaved edits are not part of that preview.

### Business concept

Choose the capability that matches the concept:

| Concept type | Required intent | What it enables |
|---|---|---|
| Documentary concept | A definition, aliases, caveats and references | Retrieval and explanation |
| Metric | An existing approved measure mapping, units, date basis and return basis | A documented mapping to a supported calculation |
| Entity / dimension | An existing supported data field | A documented dimension/filter mapping |
| Relationship | Existing from/to concept IDs | Explicit domain relationship context |

Example metric: name “Merchandise sales before returns”, alias “till sales”, approved measure `sales_before_returns_cents`, units `cents`, **Original sale date** (`sale_date`), and **Before returns** (`before_returns`). These exact values pass the mapping and unit checks. The term can help the model resolve the user's language to the approved measure. It does not create a new arithmetic formula or physical column.

Use the exact unit expected by the selected measure: `cents` for monetary totals, `cents/order` for `aov_cents`, `cents/unit` for `avg_price_cents`, `percent` for percentage measures, `orders` for order counts, `customers` for identified buyers, and `units` for quantities. `USD cents` and `percentage` are not accepted unit names. Currency display conversion happens in the answer layer.

Validation checks ambiguous aliases, incompatible mappings and missing dependencies. Resolve reported conflicts before freezing a release. A concept requiring sessions, actual-delivery events, lost demand or an experimental control must remain documentary or require developer/data work; selecting a name cannot make those fields exist. Return-date activity has a different event grain and is not supported by the generic scoped retail query.

### Finish the change

1. Save and validate the draft.
2. Preview questions using the new term and confusing neighboring terms.
3. Add an evaluation case that requires the new source and checks the intended mapping/limitations.
4. Create a candidate release, run and review its evaluations, then publish it using the workflow in section 7.
5. Ask a new question. Inspect **Why this answer?** for the published asset version.

## 5. Add skills, answer profiles and examples

### Skills

In **Skills**, browse the built-in methods or select **Duplicate built-in**. A skill is a versioned method for the existing Retail Agent; creating one does not create a separately deployed autonomous agent.

Fill in its purpose, trigger questions, method, approved tools, required concept IDs, output profile, allowed filters and caveats. Choose a supported execution handler or an agent method using existing tools. For example, a “Digital category review” method can require an exact channel/date scope, scoped sales totals, a category breakdown, reconciliation to the total, a chart and a descriptive interpretation.

The method should say what evidence is required, how to compare it, and what cannot be concluded. Avoid instructions such as “always explain the drop by promotions.” A good method explicitly verifies the baseline and allows a conclusion that the premise is false or evidence is insufficient.

Unknown handlers, tools, dependencies and fields are validation errors. Arbitrary uploaded Python, new database write tools and new integrations are not supported through this UI. Those require a developer change in the allowlisted runtime plus tests. Duplicate a method to customize it; do not edit built-in source contracts in place through the admin UI.

### Answer design

In **Answer design & examples**, create or duplicate an answer profile. Choose detail and visual preference, describe the desired response, and name the required sections. Select **Preview saved draft** to see a real measured fixture rendered using the profile. The narrow-screen preview helps check readability. Fixture results are a demonstration of that fixture's dates and scope, not an answer to an unrelated user question.

Profiles retain the underlying answer evidence. The initial table size changes with detail; the reader can expand it. A preference for a table or chart is conditional on measured fields and a suitable visualization. Editing presentation cannot bypass chart validation or suppress a material limitation.

### Examples

Add a question, example answer, good/bad classification and the reason. Good examples teach structure and careful interpretation. Bad examples should explain the problem and correction. Examples are labeled reference material, never current measured findings. A model must query the user's actual scope before using numbers in a new answer. Expected outputs for grading belong in an evaluation suite, excluded from model context.

## 6. Turn weak answers into improvements

From an answer, select **Needs improvement**, choose issue categories and enter the correction or concern. Useful feedback identifies the specific error: “The answer used store region for a digital market question”, “The chart sums a rate”, or “This asserts causation without an experiment.”

Open **Feedback & releases** to inspect the original question, answer, saved evidence and workspace provenance. Save any correction text with **Save correction**, then set **Review status** to `reviewed`; this enables **Create regression draft**. That conversion creates a live-answer case without verified expected outcomes. It does not automatically train the model or publish a prompt change. Add concrete pass conditions in the case editor, mark those conditions reviewed, validate the suite, and link the relevant asset IDs where the case tests a draft. Review the failure before changing definitions or methods. A regression created from feedback needs a live evaluation budget unless you deliberately rewrite it as a supported deterministic contract.

Feedback states distinguish new, reviewed, resolved and dismissed items. Resolution should follow an evaluated fix or a documented conclusion that the concern does not require a change. A review label alone cannot override a failing hard release check.

## 7. Evaluate, review, publish and restore

### Create a candidate

In **Feedback & releases → Prepare a release candidate**, enter **Release name** and **What changes and why?**, select the saved drafts to include, then select **Create candidate**. Include any new concept, profile or suite required by another selected draft. Inspect the candidate's immutable version map and validation results. If validation fails, return to the reported asset, correct the draft, and create a fresh candidate. The operator label is entered later under **Version history** when publishing or restoring.

### Run a comparison

In **Evaluations**, choose the suite, baseline release and candidate release. The active release is the usual baseline. Use deterministic mode first. The bundled Enterprise runtime contracts suite exercises scope, evidence, retrieval, chart, presentation and legacy playbook contracts without making model calls. The release gate requires its complete core contracts; a sampled or one-case suite is useful during editing but cannot replace the foundation.

Add candidate-specific cases to a duplicated suite while retaining the bundled cases. Include that suite draft in the candidate and select it for the comparison. Set **Maximum cases** high enough to include every applicable case; the bundled suite alone contains 76 deterministic cases and the current limit is 120. The workbench records changed assets and case coverage. Check uncovered custom assets before approving applicability. A general foundation suite does not demonstrate that every newly authored business meaning is correct.

Inspect baseline and candidate outputs side by side, failures, source versions, status and review requirements. Cancellation keeps completed case evidence and prevents a partial run from being used for publication. A process restart marks unfinished jobs interrupted; start a new run after restart. Evaluation conversations and memories use isolated temporary storage.

### Live evaluations

Live mode uses the configured model and is billable. It requires an explicit confirmation and bounded case, model-call and token budgets. The controls enforce request admission, including retries; conservative token estimates can stop a run before reaching its nominal budget. They are not a currency price quote. A model failure, cancellation, budget exhaustion or missing required output is recorded honestly.

The initial fixture suite is a developer-authored runtime regression pack. It is not a completed human-reviewed enterprise narrative benchmark. Add explicit `live_answer` cases for model answer checks; consult the [technical design](IMPROVEMENT_WORKSPACE_DESIGN.md) for schemas. Deterministic passes do not establish claim-to-evidence semantics or live answer quality. Human review is required; no automatic model judge certifies the narratives in this release.

### Review and publish

1. Complete the full deterministic run for the exact candidate.
2. Read failures and the changed-asset coverage. Review the outputs and test applicability. Record a reviewer label, decision and rationale.
3. Resolve hard failures with a new draft/candidate and rerun. Approval cannot erase a failed deterministic check.
4. Return to **Feedback & releases**, select the qualifying evaluation run and publish the reviewed candidate.
5. Verify that the active release label changed. New answers capture that release. Old saved answers keep their original provenance.

Publication rejects stale active-release expectations, a different candidate hash, changed runtime/data provenance, incomplete runs, failed checks or missing review. If a live suite has been run against that same candidate, its latest run must also be complete, passing and explicitly approved; a passing deterministic run cannot hide a failed or unreviewed live result. A review changed during publication is rejected as stale evaluation state. If another operator/tab changed the active release, reload and review what changed before retrying.

### Restore a previous release

Choose a previously published release, enter the operator and reason, and select **Restore this release**. This changes the active content pointer for future answers. It preserves the intervening releases, activation history and existing answers. An unevaluated candidate is not a rollback target. Content rollback does not undo executable code changes or SQLite schema migrations.

## 8. Where to update each thing

| Change | Preferred location | Persists in |
|---|---|---|
| Definition, alias, relationship, mapped concept | Knowledge & ontology | Workspace drafts, versions and releases in SQLite |
| Existing-tool analytical method | Skills | Versioned skill assets |
| Detail profile or writing example | Answer design & examples | Versioned profile/example assets |
| Regression expectations | Evaluations | Evaluation suite asset, frozen run inputs and outputs |
| Answer issue and triage | Answer feedback / Feedback & releases | Structured feedback with original provenance |
| Active business content | Publish / restore release | Atomic active pointer and activation audit |
| New measure, dimension or calculation | `backend/scope.py`, data layer and executable recipe sources | Application source and tests |
| New tool or handler | `backend/agent.py`, validation allowlists and tool implementation | Application source and tests |
| Built-in stable skill mapping | `BUILTIN_SKILLS` in `backend/workspace_assets.py` | Explicit source constant and initial registry import |
| Default enterprise test fixture | `knowledge/enterprise_evaluations.json` | Source-controlled fixture; existing versions remain immutable |
| UI interactions | `frontend/chat.jsx`, `frontend/improve-workspace.jsx`, `frontend/answer-report.jsx`, `static/improve.css` | Source and rebuilt `static/app.js` |
| Model connection | Local `retail_app/.env` | Private local file, followed by service restart |
| Warehouse generation and schema | `retail_data/` | Generator, data contract and generated warehouse |

The local default database is `retail_app/state/app.sqlite3`; `RETAIL_STATE_DIR` can change its directory. A workspace release is not an export of that database. Store backups separately and protect them as business content because they include chats, feedback and expected evaluations.

## 9. Back up and operate the app

From the Milky Way 2.0 folder, create a consistent SQLite backup:

```sh
.venv-runtime/bin/python -m retail_app.maintenance backup
```

This includes conversations, evidence, investigations, workspace versions, feedback and evaluation records in the same database. The backup utility uses SQLite's backup API and verifies integrity. It does not include the API key, source code, Python runtime or the DuckDB warehouse; preserve those separately through the release/delivery process.

Check or restart the installed Mac service:

```sh
.venv-runtime/bin/python retail_app/service.py status
.venv-runtime/bin/python retail_app/service.py restart
```

Restart after rebuilding/deploying Python code or changing credentials. Business drafts and published registry content do not require a restart. `/health/ready` checks local storage and data availability; it does not certify model answer quality. Rebuild the browser bundle after changing frontend source. See [Testing](TESTING.md) for the complete verification commands and [Release](RELEASE.md) for the actual delivered test results.

## 10. Common problems

| Message or symptom | What to do |
|---|---|
| Draft saved, normal chat unchanged | Validate, freeze, evaluate, review and publish; draft preview is intentionally separate |
| Built-in fields cannot be edited | Duplicate the built-in and edit the custom draft |
| Alias or definition conflict | Remove the ambiguous alias or clarify which approved mapping the term means |
| Missing concept/profile/tool/handler | Add the dependency to the candidate, select a supported option, or request developer implementation |
| No retrieval result for a new concept | Save first; preview its exact term and aliases; check the release includes its version |
| Profile unavailable after restore | Choose a profile present in the restored active release |
| Stale revision / active release changed | Reload, inspect current values, and reapply the intended edit |
| Candidate evaluation differs from release | Evaluate the exact frozen candidate; draft changes require a new candidate |
| Evaluation passed but publish is blocked | Check complete bundled coverage, review approval, matching hashes, code/data changes and live-run failures |
| Agent unavailable | Check local model settings and API access; deterministic playbooks and admin checks remain available |
| Token/call budget exhausted | Inspect completed results, reduce the case subset for diagnosis, or deliberately choose a larger allowed budget |
| Answer has wrong scope | Correct scope, report the answer and add a scope regression; saved prior evidence does not become valid for new filters |
| Question needs absent business data | Document the limitation and required dataset; do not rename an available proxy as the missing measure |

## 11. Suggested first admin session

Create a documentary definition for a business term, preview it, duplicate the enterprise suite and add a retrieval case for that term, freeze a candidate, run the full deterministic suite, review the results and publish. Ask a new explanation question and inspect its release/source versions. Then restore the initial release and confirm the new term no longer appears as published context. This exercises the full content lifecycle without requiring a new calculation or a live evaluation batch.
