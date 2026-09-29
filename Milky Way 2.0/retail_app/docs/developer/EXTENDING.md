# Extending ontology, skills, evaluations and answer quality

[Handbook](README.md) · [Implementation status](UI_IMPROVEMENT_PLAN.md) · [Architecture](ARCHITECTURE.md)

## The supported admin workflow

Open **Improve workspace** from the chat sidebar. Author a draft, validate it, preview retrieval or an answer, create a release candidate, run and review evaluations against that candidate, and publish. Chat captures the active release when an answer starts. Publication changes future answers; an answer already running keeps its captured release.

All authoring data lives in the same local SQLite state database as the application. Built-in source documents are imported as immutable reference versions, and the nineteen skill manifests retain the existing executable recipes. The source files are packaged inside `Milky Way 2.0`; runtime edits belong in the registry, rather than editing copied documents and hoping a running index notices.

This release is a trusted local administrator workflow. The operator/reviewer name is an audit label, not authenticated identity. Independent approvers, tenant isolation and enterprise SSO are separate deployment work.

| Change | Admin UI | Developer boundary |
|---|---|---|
| Business meaning, caveat or source text | Knowledge & ontology → Source document | Reference content cannot create warehouse observations |
| Concept, alias, entity or relationship | Knowledge & ontology → Business concept | Conflicting aliases and missing concept references block publication |
| Existing metric under a business name | Metric concept → choose approved measure, units and basis | A new formula, field or event grain needs a reviewed query adapter |
| Method using existing tools | Skills → New skill or Duplicate built-in | Unknown executable handlers and tools cannot publish |
| Answer style and layout preference | Answer design & examples → Answer profile | Scope, citations, evidence and limitations remain available |
| Good or bad response example | Answer design & examples → Answer example | Historical/example values never become fresh query evidence |
| Regression contract | Evaluations → New suite or Duplicate built-in | Expected outcomes are excluded from model context |
| Weak real answer | Needs review → feedback → review → create regression | A correction is a review note; it does not silently become a golden answer |
| Promote or revert configuration | Feedback & releases | Immutable manifests and atomic active pointer; code/schema rollback is separate |
| New data, formula, callable operation or chart renderer | Source changes and tests | Use the implementation locations below |

## Asset and release model

`backend/workspace_assets.py` owns migrations, CRUD, validation, immutable versions, releases, frozen retrieval and feedback. `backend/workspace_api.py` exposes `/api/workspace`. Its module import performs no registry write; `ensure_initialized()` initializes the tables at service startup or first access. Existing chats, memories, investigations and analyses retain their original tables.

Asset IDs use 2–80 lowercase letters, numbers and hyphens, beginning with a letter. Kinds are `knowledge`, `ontology`, `skill`, `output_profile`, `example` and `evaluation_suite`. Each asset has stable identity and owner metadata. A draft has an integer revision. Every update supplies `expected_revision`; a stale editor receives HTTP 409 and must reload before saving.

A release contains the complete `asset_id → version_id` map, parent release, validation result, operator, rationale and hash. Version content is canonical JSON with a SHA-256 hash. SQLite triggers reject updates and deletions of stored versions and release manifests. A candidate freezes selected drafts and inherits unchanged active versions. Later draft edits do not mutate an existing candidate.

Publishing checks candidate validation, the exact completed deterministic evaluation run, all bundled core cases, operator review, source/data fingerprints and the expected active release ID. A candidate built from an older active release must be recreated. Rollback accepts a previously activated release and atomically changes the pointer; it does not rewrite previous answers or database schemas.

Important public service calls are:

```python
ensure_initialized()
active_snapshot()
candidate_snapshot(asset_ids=None)
get_snapshot(release_id)
create_asset(kind, name, content, id=None, owner="local-admin")
update_asset(asset_id, content, expected_revision, name=None)
validate_asset(asset_id)
validate_candidate(snapshot)
create_candidate_release(asset_ids=None, name="Workspace candidate", rationale="")
publish(release_id, expected_active_release_id, evaluation_run_id=run_id)
rollback(release_id, expected_active_release_id, rationale="Why revert")
search_snapshot(snapshot, query, limit=6)
snapshot_context(snapshot, question, output_profile_id=None)
```

A snapshot is a detached JSON value containing `release_id`, `parent_release_id`, `snapshot_hash`, `asset_versions` and all versioned assets. Full snapshots contain evaluator cases for reproducibility and must never be placed directly in model messages. Only `search_snapshot` and `snapshot_context` produce the bounded, filtered reference view. Runtime integration uses `workspace_runtime.capture`, `search`, `settings` and `attach`.

## Adding ontology context

Use a documentary concept when the data cannot support execution. Use a metric concept only when an approved existing measure represents the intended calculation. The UI distinguishes knowledge from executable mapping; writing a formula in a description does not create an executable formula.

A supported metric creation payload is:

```json
{
  "id": "merchandise-revenue-before-refunds",
  "kind": "ontology",
  "name": "Merchandise revenue before refunds",
  "content": {
    "concept_type": "metric",
    "description": "Completed merchandise sales after discounts, before refunds; excludes tax and shipping.",
    "aliases": ["merchandise revenue before refunds"],
    "measure": "sales_before_returns_cents",
    "units": "cents",
    "date_basis": "sale_date",
    "return_basis": "before_returns"
  }
}
```

The measure catalog comes from `scope.MEASURE_NAMES`; query dimensions and filter fields come from `scope.FIELDS`. Metrics require units, sale-date basis and a supported return basis. Approved currency measures use cents, AOV uses cents/order, average price uses cents/unit, rates use percent, and counts use their declared units. The display layer formats currency without changing stored measured values. Calendar return activity and inventory snapshots need their dedicated recipes; a sale-cohort mapping cannot relabel them.

An unavailable business concept can be saved with `concept_type: "concept"`. A metric without executable support can be explicitly marked `documentary: true`. It is then reference guidance with a visible documentary warning. An unknown `measure` or `field` remains a draft with a `needs_data_support` validation error.

Relationship concepts declare `from_id` and `to_id`; both must reference ontology assets present in the candidate. Alias validation normalizes case and whitespace and reports collisions. These ontology relationships are versioned semantic references; they are not a graph database or a SQL join compiler.

### Retrieval behavior

At initialization the registry freezes the existing allowlisted context documents, section boundaries, source roles, source locations and hashes. `search_snapshot` reconstructs the existing lexical ranking from those frozen sections. User-authored overlays receive at most half of the result slots, leaving room for physical schema and original metric contracts. Content is bounded to twelve results and eighteen thousand characters.

Built-in source references are read-only; duplicate one to add a workspace-specific document. A preview searches candidate content without changing the active release. Publication makes the new reference visible to subsequent answers. Citations use immutable `workspace/<asset_id>/<version_id>` source IDs. The source API returns the exact stored document body for original references, retaining original line numbers; `original_source` records the packaged source path.

Evaluation suites and their expected outputs never participate in retrieval. Runtime skill/profile views use explicit field allowlists and recursively omit evaluator fields. Reference material cannot increase tool permissions, change measured evidence or override the effective chat scope.

## Adding skills

The nineteen original manifests have stable IDs `skill-trend`, `skill-pvm`, `skill-growth`, `skill-margin`, `skill-seasonality`, `skill-scorecard`, `skill-channels`, `skill-concentration`, `skill-pricing`, `skill-promotions`, `skill-cohorts`, `skill-lapse`, `skill-segments`, `skill-affinity`, `skill-loyalty`, `skill-returns`, `skill-velocity`, `skill-inventory` and `skill-fulfillment`.

`load_builtin_contracts()` joins playbook and visual chapters by explicit numbered ID using `BUILTIN_SKILLS`. It rejects missing or mismatched IDs. Reordering chapters no longer changes which visual contract belongs to a skill. Recipes and numerical calculations remain in the existing runner and scope adapters.

A method skill declares:

```json
{
  "description": "Explain an assortment change using measured comparisons.",
  "trigger_examples": ["Which product groups account for the sales change?"],
  "method": "Compare identical scopes; reconcile disjoint contribution rows to the measured total; report overlap and uncertainty.",
  "required_concepts": ["metric-sales"],
  "approved_tools": ["query_retail", "reconcile_breakdown", "create_visualization", "present_answer"],
  "handler": "method_only",
  "allowed_filters": ["channel_name", "division_name"],
  "output_profile_id": "business-review",
  "caveats": ["Descriptive contribution does not establish a causal mechanism."]
}
```

`method_only` adds reasoning guidance using existing controlled tools. `playbook:<slug>` points to an existing allowlisted recipe and requires the `run_playbook` capability. An unsupported handler, unknown tool, missing concept, unsupported filter or missing profile blocks publication. The admin UI cannot upload executable Python, packages, browser code or a privileged SQL operation.

For a genuinely new executable capability, review these code locations together:

| Area | Files and required work |
|---|---|
| Formula, physical grain and metric semantics | `backend/scope.py` fields, measures, aliases and expressions; SQL/schema/catalog if needed |
| Baseline recipe | `retail-data-analyst/scripts/run_analysis.py` and `REPORTS` |
| Stable skill/visual wiring | `workspace_assets.BUILTIN_SKILLS`, numbered playbook/visual chapters, runner slug and title lists |
| Scoped recipe | `scope.run_scoped_playbook`; retain filters, dates, return treatment and denominator |
| Agent callable operation | `agent.py` declarations/dispatch or `conversation.py` tool definitions/handler |
| Measured visual data | `backend/visual_data.py` plus frontend chart renderer |
| Verification | Independent metric/query checks, schema/error cases, scope tests, presentation tests and targeted evaluation cases |

Updating packaged source documents after a workspace has been initialized does not silently replace its frozen release. New built-in content requires an explicit, reviewed registry migration or an administrator-authored replacement asset and release. This preserves answer provenance across application upgrades.

## Answer design and examples

The built-in profiles are Quick answer (`quick-answer`), Business review (`business-review`) and Analyst detail (`analyst-detail`). Profiles accept `detail` (`concise`, `standard`, `detailed`), required sections and chart preference. Advanced options include `max_table_rows`, `show_method` and tone. Required source, scope, evidence and limitation safeguards cannot be switched off.

The answer renderer applies display preferences to the existing measured payload. The underlying evidence rows are preserved. A profile controls the visible preview length and explanatory detail; it cannot fix an incorrect query or conceal a failed check.

Use **Preview answer** on a saved profile to query a fixed real warehouse fixture: monthly sales or channel sales for January–March 2025, before returns. `/api/workspace/output-preview` returns the measured rows, scope, presentation and profile version without creating a chat or publishing a draft. The preview is deterministic formatting over measured data; it does not claim to score a live model's prose.

Examples contain `question`, `answer`, `quality` (`good` or `bad`), notes and an optional output profile reference. Label historical or illustrative values clearly. An example is reference material, and every production numeric claim still needs current evidence. See [Answer examples](ANSWER_EXAMPLES.md) for the original documented patterns.

## Enterprise evaluations and release gates

The bundled `knowledge/enterprise_evaluations.json` suite contains 76 code-authored runtime contracts covering legacy skill designs, scope and return bases, retrieval, evidence references, measured values, charts, presentation and data/query behavior. It is an executable regression foundation, not a human-reviewed benchmark of narrative quality.

An evaluation case declares a stable ID, question, mode, category, runtime contract inputs, explicit expected checks, and whether human review is required. Supported deterministic checks compare values, required/forbidden text, collection lengths and source roles. Empty or unsupported checks fail closed. Optional live cases use a separate explicit call/token budget and require confirmation that they may call the configured model service.

The workbench runs baseline and candidate against immutable snapshots. It stores the suite version, code/context/warehouse fingerprints, grading version, actual outputs, hard failures, timing, limits and operator review. One evaluation worker has a bounded queue, separate from chat admission. Each live case uses temporary conversation/memory state and a read-only warehouse. Cancellation is cooperative; interrupted jobs are marked interrupted after a restart.

For publication, run the complete bundled deterministic suite, inspect failures and coverage, and record an operator decision with review notes. A small custom suite or partial case run cannot replace core checks. Custom suites can extend the bundled cases. A live run alone cannot authorize publication; once a live suite is run for the same candidate, its latest result must also pass and receive human review. No automated semantic grader or enterprise approval independence is claimed.

Author custom cases for each changed asset and set `asset_ids` or the contract's `profile_id`/`skill_id` so the workbench can show coverage. Declared coverage is a review aid; a case label cannot prove it tests the relevant behavior. The review screen makes uncovered changes visible.

## Feedback, memory and operational boundaries

**Needs review** captures issue types, correction, original question and answer, measured evidence and the original workspace release/profile/skill provenance. A reviewer marks the entry reviewed before converting it to a draft regression. The generated case deliberately has no expected answer; a developer or administrator must supply reviewed checks and evaluate it. Conversion never publishes a change.

Deleting a conversation removes its associated workspace feedback through the chat-owned cleanup path. An independently authored regression suite and its immutable release history remain separate authored workspace records. Do not place sensitive personal material into a reusable benchmark.

Personal remembered conventions retain their explicit-request behavior. Workspace publication controls official shared domain guidance and response profiles; the memory table is not an ontology registry. Long-term multi-user policy, SSO, external connectors, semantic-judge calibration and deployment approvals remain separate engineering work.

The new registry and API tests live in `tests/test_workspace_assets.py`; evaluation and integration tests sit alongside the existing test suite. Run the documented full backend/frontend checks before a code release. Back up the complete SQLite database with the existing maintenance backup operation; a workspace rollback only changes content selection, while a code/schema restoration uses the application release process.
