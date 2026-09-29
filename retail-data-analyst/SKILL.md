---
name: retail-data-analyst
description: Answer sales, margin, pricing, promotion, customer, returns, inventory, and fulfillment questions using the Summit Field synthetic retail DuckDB dataset and its validated playbook recipes. Use for analyses of this project's data, not for external market-share or web-funnel claims.
---

# Retail Data Analyst

Use this skill when a user asks a retail business question about the Summit Field dataset or asks to apply one of its playbooks. The dataset is fictional. Give computed findings only after querying it; never present a worked example as a result.

## Route and execute

1. Read [question routing](references/question-router.md) to select the narrowest playbook and any necessary follow-up. For a broad “how are we doing?” request, start with Playbook 1, then run Playbooks 2–4 only where the observed result points.
2. Read the selected A–I recipe in [playbooks](references/playbooks.md) and its exact [visual specification](references/visual-specs.md). Read only the relevant headings, not the entire catalogue, during routine use.
   For answer shape, consult the matching section of [computed worked examples](references/worked-examples.md); rerun the data for the user's requested scope.
3. Read the project's `retail_data/docs/METRICS.md` and `retail_data/docs/MODEL.md` before writing a new query or interpreting a result. Use `retail_data/docs/DATA_DICTIONARY.md` when a column or join is uncertain. Locate these under the active Retail Data Agent project, regardless of where this skill is installed.
4. Run the read-only helper for a baseline result: `python3 scripts/run_analysis.py --list`, then `python3 scripts/run_analysis.py --playbook <slug> --data <path-to-retail.duckdb> --start YYYY-MM-DD --end YYYY-MM-DD`. The helper returns SQL evidence and machine-readable rows. Use `--compare-start` and `--compare-end` to control comparison dates. If `duckdb` is unavailable, use the project's pinned dependency instructions; do not silently replace missing query results with estimates.
5. Validate denominators, bridge reconciliation, date coverage, and sample sizes. For a user-requested slice not handled by the helper, adapt the recipe's source tables and joins, query the read-only database, and keep the SQL and filters with the answer.
6. Deliver a concise business answer: headline, exact scope and metric, primary visual, supporting values, uncertainty or limitations, and the next useful drill. Use the recipe's output template and visual spec. If a visualization is requested or materially helps, render the specified chart using available plotting tools and inspect it before delivering.

## Binding data limits

- Sales: 2024-01-01 to 2025-12-31. Returns: through 2026-03-01. Money: integer US cents. Merchandise sales exclude tax and shipping.
- Say whether returns are excluded, linked to their original sales cohort, or recognized on return date. Never mix these bases.
- `customer_key=0` is all anonymous orders pooled; `loyalty_key=0` means no attached account. Exclude anonymous key 0 from customer counts and repeat calculations.
- Aggregate headers, lines, returns, and inventory at their own grains before joining. Inventory is a weekly snapshot and is not additive through time. Retail weeks start Sunday; inventory weeks start Monday.
- Decompositions locate a change; they do not prove causes. Promotion sales are associated, not incremental. No market universe, web funnel, causal price experiment, actual delivery event, genuine launch/delist, or lost-demand simulator exists here. Route such questions to a data-gap response using [question routing](references/question-router.md).
- The project data is synthetic. Do not describe its values as real retailer benchmarks or infer actual customer preferences from generation assumptions.
