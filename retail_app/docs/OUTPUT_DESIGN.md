# Playbook output design

The app uses the project's existing output convention: **headline; scope and metric definition; primary visual; supporting values; interpretation; limitations; next question**. The evidence table is visible in the answer, with a selector when several supporting datasets are available. Full SQL, source rows, checks and specialist findings remain inspectable.

This design is grounded in the 19 normalized [A–I playbooks](../../retail-data-analyst/references/playbooks.md), their [detailed visual specifications](../../retail-data-analyst/references/visual-specs.md), and the [metric contract](../../retail_data/docs/METRICS.md). Historical worked examples guide answer shape only. The [domain asset inventory](DOMAIN_ASSETS.md) explains how definitions, hypotheses, schema, validation and design references are integrated.

## How the answer is assembled

The primary Retail Analyst reads the narrowest matching output design with `get_playbook_design`, gathers measured evidence, creates or reuses its visual, and supplies its narrative through `present_answer`. These are tools in the original LangGraph loop; Hypothesis, EDA and RCA remain optional callable specialists within that architecture.

The presentation contract supplies exact scope, metric basis and return treatment, supporting evidence IDs, interpretation, limitations and the next useful drill. References point to measured results (`E#`) or source documents (`D#`). ID validation and supported chart fields do not independently prove that every narrative claim is correct.

A single measured row is displayed as metric cards, without inventing a time series or comparison. Documentation-only answers and data-gap explanations need no chart. If the structured presentation is unavailable, the app identifies its fallback layout; it may use a simple chart from actual rows when the fields support one. This does not establish that the full playbook method was executed.

## Per-playbook coverage

All original executable recipes remain unchanged. Additional parameterized queries provide the datasets required by the new primary visuals. Named runs are all-business baselines using the selected dates; narrower questions require SQL and chart data for the user's exact slice.

| Playbook | Primary visual in the app | Important boundary or supporting evidence |
|---|---|---|
| 1. YoY and Trend | Aligned current/comparison weekly sales lines | Exact windows and partial weeks are disclosed; L4/L13/L52 growth panels are not a separate baseline output |
| 2. Price / Volume / Mix | Reconciling waterfall with rate, unit volume, mix, entry/exit and rounding | Uses the existing exact SKU × channel Shapley bridge; does not identify elasticity or add discount dollars twice |
| 3. Source of Growth | Signed division contribution bars ordered by absolute dollars | One mutually exclusive partition; other dimensions need a separately scoped query |
| 4. Margin and Returns | Cohort merchandise-margin waterfall and margin-rate change | Original sales, refunds, COGS and recovered cost remain separate; excludes operating/fulfillment costs |
| 5. Seasonality | Retail-year overlay by retail week | Missing/partial fiscal boundaries and week 53 stay visible; no robust seasonal forecast is implied |
| 6. Category and Brand Scorecard | Six measured tiles plus division contributions | Sales, units, margin dollars/rate, unit-return rate and deduplicated identified-buyer reach; both periods are queried |
| 7. Channel and Store | Channel growth-versus-margin scatter with sales-sized points | POS-store growth/margin is also queried and selectable as a table; a separate store scatter is not rendered |
| 8. Concentration and Pareto | Style sales bars and cumulative share | Top-decile marker refers to the displayed set; no automatic prior-period concentration-change panel |
| 9. Price Landscape and Markdown | Unit-weighted actual and effective regular-price distributions | Added query uses fixed $10 bins and the same selected sales window; division detail stays in evidence; show a regular-price comparison only when measured rows exist |
| 10. Promotion Performance | Selected campaign's affected-scope weekly sales/units and redemption-economics panels | Highest associated-sales campaign in scope; campaign dates are shown; no incremental baseline or automatic date-window extension |
| 11. Customer Cohort and Repeat | 90/180-day repeat heatmap with numerator/eligible denominator | Immature cells remain unobserved; first observed purchase is not proven acquisition; not a full cohort-age matrix |
| 12. Customer Lapse and Reactivation | Monthly active, lapsed and reactivated counts | Transparent illustrative 90-day rule and observation cutoff; full prior history is used; no category-specific churn model |
| 13. Behavioral Segmentation | Seven-metric segment profile heatmap | Per-buyer recency/orders/sales/margin/category breadth plus discount and unit-return rates; transparent existing membership rules |
| 14. Basket Affinity | Category-pair lift matrix with joint-order counts and configurable support floor | Low-base cells are muted; only returned pairs are shown; co-occurrence does not establish causal cross-selling |
| 15. Loyalty Usage | Monthly 100% sales-mix bars by attachment | Order/unit bases remain in evidence; attachment is not enrollment or program impact; enrollment-cohort repeat is a further drill |
| 16. Return Cohort and Reason | Original sale month × 0–30/31–60-day return heatmap | Same original-unit denominator per cohort and 60-day maturity; added cohort-reason evidence is distinct from the original return-date reason table |
| 17. Item Velocity and Sell-Through | Sales-per-observed-week versus weeks-of-supply scatter | Bubble size is latest available units; zero-sale ratios are undefined and remain in the table; no lost-demand or delisting claim |
| 18. Inventory Health and Reconciliation | Weekly ending/available stock lines and separate receipt/restock/sales/shrink panels | Complete current-window Monday–Sunday buckets; latest-snapshot headline retained; stock balances are never added across weeks |
| 19. Fulfillment Method Mix | Monthly completed-order share by method | Method AOV, margin rate and unit-return metrics are also queried for tables; separate outcome dot plots remain an extension; delivery events/costs are absent |

## Scope and visual safeguards

- **Data basis:** charts and cards convert aggregate cents to USD. Evidence tables keep the actual named source units. Rates retain their numerator and denominator; rate changes use percentage points when comparing rates.
- **Current/comparison:** both windows are shown in the answer scope, but only datasets that query both support a period comparison. Actual-versus-regular price is a price-basis comparison within the same selected sales window. Monthly mix, profile, return and stock/flow panels are current-window views unless an additional comparison is measured.
- **Promotion timing:** the affected-scope line includes observed sales in the campaign's division/channel, not only redeemed sales. Separate redeemed discount and associated margin measures retain their own basis. A campaign-valid date band is descriptive; a selected window may omit before/after observations or contain partial weeks.
- **Customer states:** monthly states count identified buyers observed by each cutoff. Reactivation means a purchase after a gap greater than 90 days. Active excludes reactivated buyers, making displayed states mutually exclusive; the rule is an illustrative global threshold.
- **Inventory timing:** the latest completed snapshot answers the as-of question. Historical panels include complete buckets within the chosen start/end dates. The inventory calendar is Monday–Sunday, separate from Sunday-start retail reporting weeks.
- **Missing evidence:** nulls and immature cells are not zeros. A chart that requires absent data asks for a rerun or shows the available measured table. It must not infer a causal effect, prior-period series or regular-price distribution from another measure.
- **Fallback charts:** general query charts validate output indices and field types; numeric keys are not chosen as measures by the automatic fallback. Rendering may cap displayed rows, with truncation disclosed. A generic cumulative or signed-contribution chart is not automatically a complete-population Pareto or reconciled business bridge.
- **History:** new chart datasets are collected when an analysis runs. Old saved reports are preserved and may require rerunning for the new visuals.

The source color grammar applies to chart marks; interface text remains simple black system typography. Captions identify metric basis, source context and limitations, and supporting tables provide an accessible exact-value alternative. Browser appearance and interactions still require real-browser acceptance testing when the desktop policy permits it; recorded verification is in [TEST_REPORT.md](TEST_REPORT.md).

The primary analyst reserves the closing step for `present_answer`; structured presentation ends the same tool loop without an extra prose-generation pass. Chart tools accept evidence IDs directly and normalize the documented horizontal contribution axes. Numeric SQL Decimal values remain numbers in JSON. Monetary prose is checked against labeled USD/cents cells and complete-column totals with rounding tolerance; unmatched claims are rejected for correction or visibly flagged in fallback text. This catches transcription errors, not aggregation-grain or semantic errors, and does not turn descriptive evidence into causal proof.
