# Milky Way 2.0 — delivery verification

Verified on September 26, 2026 against the included Summit Field synthetic warehouse.

## Delivered and running

- Separate application folder, warehouse, installed local runtime and SQLite state; original app remains unchanged.
- Local service: http://127.0.0.1:8766/ (`com.milkyway.retailagent.v2`).
- One conversational Retail Agent chooses explanation, measured analysis, playbooks and investigation capabilities. No user-selected specialist mode is required.
- Conversation messages, charts, evidence, active scope, concise summaries, explicitly saved preferences and versioned investigations persist locally.
- User edits invalidate affected test findings and obsolete workers. Continued investigations retain node IDs and immutable prior tests.
- Source, prebuilt frontend, dependency locks, generator, warehouse and domain references are included locally. Generated/private/installed files are excluded from Git; the warehouse checksum is in `DELIVERY_MANIFEST.json`.

## Deterministic verification

**232 backend tests passed**, with no skipped tests. These cover the 19 baseline recipes, hypothesis templates, independent financial reconciliations, scoped queries, provenance, numeric bindings, hypothesis revision and testing rules, conversation persistence, API validation, cancellation and fault recovery.

**Four frontend suites passed**: conversation rendering and network errors; all 19 playbook visual designs; structured analytical answers; Milky Way explanations, grouped comparison charts and editable investigation rendering. The production frontend build succeeded.

Commands are in the root README. Test receipts are local in `retail_app/state/eval_report.json` and `mw-tests.log`.

## Live model verification

Live Responses API checks used temporary, isolated conversation state and the full included warehouse. The configured key remained server-side and was not written to test output.

| Scenario | Observed result |
|---|---|
| Data definition | Explained `customer_key` and anonymous key 0 conversationally, without inventing an analytical chart. |
| Scoped analysis | Web × Footwear July 2025 sales were $1,520,528.53 and 12,222 units; July 2024 was $1,466,257.79 and 12,071 units. The answer retained the requested scope and supplied comparison visuals. |
| Follow-up | “Same for Mobile app” retained Footwear and July comparison: $794,889.77 / 6,423 units versus $761,124.42 / 6,308 units. |
| RCA | Saved two hypotheses and executed measured tests: average selling price increased by 309.6594927 cents per unit; sold units increased by 115. Both declared directional predicates were supported descriptively. |
| User correction | Edited the first existing hypothesis to “Sold units declined.” The app cleared its obsolete criterion, saved a fresh `units_change < 0` criterion, retested, and recorded **contradicted**. The other hypothesis remained intact. |

The final RCA used 10 model calls and its correction used 5. One rate-limit retry was handled. Query-column and monetary-validation errors were surfaced to the model and corrected during execution. Earlier failed receipts remain available rather than being overwritten. A final deterministic formatting fix prevents duplicated percent signs and “USD cents” labels after measured-value substitution.

Live receipts are under `retail_app/state/live_v2_final/` and `retail_app/state/rca_verified/`; they are excluded from Git. Successful examples establish these scenarios, not universal answer accuracy.

## Boundaries and remaining acceptance

- This is a trusted local, single-user app. Public deployment still needs identity/access control, tenancy separation, managed secrets, backup policy, load testing and operational monitoring.
- Browser automation was blocked by the desktop policy verifier in this session. Rendering, API and build checks passed, but manual browser layout and click-through acceptance remain unverified.
- Docker configuration is included but a Docker build/run was not verified here. Its root build context excludes private credentials, state and generated data.
- All 19 original baseline playbooks are available. Validated filtered adapters cover trend, growth, margin, scorecard and concentration. Other filtered requests require the agent to adapt the documented method using scoped data or state the exact limitation.
- `query_retail` and `scoped_sales` bind filters and dates. Unfiltered legacy read-only SQL remains available for data outside sales and still requires correct date predicates and grain selection. Arbitrary formulas and joins are not a semantic guarantee.
- A saved verdict validates the declared numeric predicate. It does not prove a broad hypothesis's wording or establish causality. Mechanisms may overlap; reconciled accounting partitions and causal identification are separate questions.
- The data cannot establish missing traffic, lost demand, actual-delivery events or randomized causal effects. The agent must explain these gaps.
- Chat context is bounded, with durable scope/summary and investigation state retained separately. It is not unlimited verbatim recall. Provider outages, limits and model mistakes remain possible; incomplete work is preserved for continuation.
- The included Python environment is usable on this Mac and relies on its installed runtime. Another machine must recreate it from the lockfile. The login service operates while this Mac is awake and logged in.
