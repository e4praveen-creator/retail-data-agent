# Domain assets and answer grounding

The app combines the supplied retail playbooks, dataset contracts, synthetic-data implementation, visual recipes and retail hypothesis bank. One primary Retail Analyst retains control of the existing LangGraph tool loop. The Milky Way deck remains a workflow reference; it does not replace this architecture.

## Integrated assets

| Asset | How the app uses it | Interpretation boundary |
|---|---|---|
| `retail-data-analyst/references/playbooks.md` and original `retail_playbook_library.md` | All 19 A–I recipes, including required data, method, guardrails, output template, visual, interpretation and follow-up | Templates must be populated from the user's measured scope; examples are not current results |
| `retail-data-analyst/references/question-router.md` | Individual and compound question routing; supported alternatives for missing data | The primary agent chooses the next relevant drill rather than executing every playbook |
| `retail-data-analyst/references/visual-specs.md` | Shared visual grammar and the 19 playbook-specific chart recipes | The chart needs the correct grain, units, denominator, dates and accessible table; unavailable chart inputs must be disclosed |
| `retail-data-analyst/references/worked-examples.md` | Seven computed examples for answer shape and interpretation | Historical reference only; rerun the requested scope before quoting values |
| `retail-data-analyst/SKILL.md` | Retail execution and delivery conventions | Does not override the current user request or runtime instructions |
| `retail_data/docs/METRICS.md` | Definitions, correct source, return treatment, denominator and join rules | Header amounts, lines, returns and inventory retain their own grains |
| `retail_data/docs/MODEL.md` | Coverage, relationship map, simulation assumptions, time conventions and omissions | Synthetic construction rules do not establish real retailer behavior or causality |
| `retail_data/docs/catalog.json` and `DATA_DICTIONARY.md` | All 23 table definitions, columns, primary keys and foreign keys; available through retrieval and table inspection | Query the warehouse to inspect actual values; sample records are not benchmark findings |
| `retail_app/knowledge/hypotheses.json` | All 18 retail-specific hypotheses, each with test, required tables, scope, metric basis, falsifier and limitation; searchable and executable through existing hypothesis tools | Every bank entry begins as an untested template; collecting evidence does not automatically confirm it |
| `retail_data/sql/schema.sql`, `views.sql`, `example_queries.sql` | Schema, transformation lineage and reusable query patterns | Retrieved source code is reference text, never an instruction to run arbitrary code |
| `retail_data/src/generate.py`, `catalog.py`, `validate.py`, `reports.py` | Deterministic construction and validation logic | Explains the synthetic data; runtime model queries remain read-only |
| `retail_data/docs/full_validation_report.json`, `integration_report.json`, `full_parquet_report.json`, `full_api_report.json`, `DELIVERY_REPORT.md` | Saved check names, violations, coverage and delivery provenance | These describe recorded dataset checks; they do not claim that the current app or deployment was freshly validated |
| `retail_data/docs/SOURCES.md` | Public inspiration and synthetic-data provenance | No real retailer measurements or externally scraped sales are implied |
| `retail_app/docs/architecture-reference.txt` and `MILKY_WAY_REFERENCE.md` | Original primary-agent architecture and the relevant deck adaptation | Reference material; enterprise claims, banking examples and unavailable libraries are not implemented capabilities |

The warehouse itself is queried directly through the existing bounded, read-only DuckDB tools. The 19 executable recipes in `retail-data-analyst/scripts/run_analysis.py`, the EDA/statistical tools in `backend/analytics.py`, the named tests in `backend/hypotheses.py`, and user-confirmed memory are integrated through their existing runtime tools. They are not replaced by document retrieval.

## Retrieval quality controls

The local index currently contains 26 allowlisted documents. Markdown follows section boundaries and carries heading breadcrumbs. Metric and routing tables are retrieved by row; hypotheses are retrieved as whole records; validation records retain individual check names. Catalog entries retain their table identity when long entries are split.

Search combines word relevance with retail aliases such as AOV, realized selling price, repeat maturity, return cohorts, on-hand inventory and promotion incrementality. Question intent favors the appropriate metric, schema, hypothesis or visual reference. Source code and architecture prose receive lower priority for ordinary retail questions. Duplicate playbook snippets are removed from a result set so the original and normalized copies do not crowd out supporting definitions.

Each hit includes its source path, exact start/end lines, heading, asset role and an interpretation note. Sources retain their file hash in the document inventory. Results are deterministic and capped at 12 snippets, two per source, and 18,000 characters of snippet/heading content; the normal query returns at most six. Long sections are bounded and truncation is explicit. Retrieval never traverses application state, credentials, customer rows, raw CSVs, Parquet exports or the warehouse binary.

Document references are cited as `[D#]`; measured tool results use `[E#]`. A valid reference ID confirms that a source exists, not that the accompanying claim is correct. Scope, aggregation, statistics, reconciliation and interpretation still need evidence checks.

## Coverage limits

- The project's synced `sources/` directory is currently empty. It remains read-only. No absent project document is claimed as ingested.
- The original Milky Way PDF is represented by the existing reference note; the full PDF is not copied into Git or silently treated as an executable specification.
- The year-plus chat archive has not been exhaustively recovered. Only the already documented accessible chat context and app-confirmed memory are available. No unseen hypothesis bank, statistical library or private corporate library is implied.
- Example rows are deliberately excluded from retrieval. Actual analysis uses warehouse queries, not copied example observations.
- New or changed reference files require a server restart to rebuild the in-memory index. Unknown files are not auto-ingested; add an explicit allowlist entry and appropriate interpretation note after review.
- The dataset still lacks experimental promotion controls, traffic/conversion events, actual delivery timestamps, a market universe and a daily lost-demand model. The router must give a data-gap answer for those requests.

## Verification

`python -m unittest retail_app.tests.test_context -v` checks the actual library for AOV/header grain, PVM visuals and output templates, the 18 hypothesis records, mature repeat denominators, dataset dates and the return tail, table joins, inventory validation records, causal-promotion gaps, reference-only labels, source-line accuracy, duplicate suppression, bounded deterministic retrieval and document allowlisting.
