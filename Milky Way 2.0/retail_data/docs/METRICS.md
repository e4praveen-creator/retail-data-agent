# Metric contract for the Retail Data Agent

Use this file as retrieved context when answering retail questions. State the period, grain, channel definition, and return treatment in every answer. Money is US cents in storage; divide the **aggregate** by 100 for dollars. Never treat a currency amount as unit count.

| Metric | Definition | Correct source |
|---|---|---|
| Orders/transactions | Count of completed headers | `fact_transaction` |
| Units sold | Sum of original sold quantities | `fact_sales_line.quantity` |
| Gross merchandise sales | Effective regular price × quantity | `gross_sales_cents`, not MSRP |
| Merchandise discounts | Markdown + promotion discount | Two separate line/header fields |
| Net sales before returns | Gross − markdown − promotion | `net_sales_cents` |
| Tax / shipping | Separate amounts excluded from merchandise sales | Header totals; tax also on lines |
| Total collected at sale | Net merchandise + tax + shipping | `fact_transaction.total_paid_cents` |
| Return revenue deduction | Original discounted amount of returned units, positive | `fact_return_line.refund_net_cents` |
| Period net revenue | Sales on sale date less returns on return date | `v_merchandise_activity.merchandise_revenue_cents` |
| Sales-cohort realized revenue | Original sales less all observed linked returns | `v_sales_after_returns.realized_net_sales_cents` |
| Merchandise margin | Cohort realized revenue − original COGS + restockable returned cost | `v_sales_after_returns.merchandise_margin_cents`; excludes shipping/operating costs |
| AOV before returns | Sum header net sales / count headers | `fact_transaction`; no header-to-line fan-out |
| Unit return rate | Returned units / original units in the same sales cohort | `v_sales_after_returns`; not returns-period/sales-period mixture |
| Loyalty sales share | Sales on headers with loyalty_key > 0 / all sales | Specify before/after returns |
| Repeat-customer rate | Identified purchasing customers with >1 order / identified purchasing customers | Exclude customer_key 0; do not use all registered customers as denominator |
| Ending inventory | Closing on-hand at one period end | `fact_inventory_weekly`; additive over SKU/location, not time |
| Available inventory | Closing on-hand − reserved units | Same snapshot; excludes inbound transit |
| Inventory turnover | Period COGS / average comparable snapshots at cost | Explicitly state period and return treatment; example uses 2025 sale cohorts |

## Join rules

- Header → line is one-to-many. **Do not sum header amounts after joining lines.** Count distinct transaction keys only when necessary, or aggregate lines and headers separately.
- Join line → SKU → style → category → department → division. Brand is attached to style; color and size are attached to SKU. `v_product` provides one row per SKU.
- Line → price uses `price_key`, which already resolves SKU, channel and inclusive date interval. Do not join solely on SKU to all price history.
- Returns → original line uses `sales_line_key`. Aggregate returns first when combining sales and returns; the provided cohort view does this even though v1 has at most one return per sale line.
- Inventory → sales is many-to-many unless both are aggregated to SKU/location/week. Never join raw inventory snapshots to raw sales and sum either measure.
- `selling_store_key=0` means a digital order; physical source is `fulfillment_location_key`. A returned online sale may arrive at a different physical location.
- `customer_key=0` pools anonymous transactions and is not one real customer. `loyalty_key=0` means no loyalty usage; it does not imply that every identified customer is enrolled.

## Time and interpretation

Sales stop December 31, 2025. Returns continue through March 1, 2026, so 2026 return-tail revenue is negative without 2026 sales. All original sales have a complete 60-day return window in this frozen extract. Retail fiscal years crossing the sales boundaries are partial; use common complete weeks for comparisons. Week 53 is not silently restated. Inventory weeks start Monday; retail weeks start Sunday: use calendar dates to align them rather than joining on week number alone.

There are demand weights for weekends, holiday shopping and back-to-school, a seasonal division preference, and a small repeat-customer concentration. These are deliberate simulation rules. Price changes and markdowns are known inputs; no claim of learned price elasticity is justified. Promotional sales are associated sales, not incremental sales. Weekly inventory cannot prove daily stockouts, traffic/conversion, or lost demand. Do not invent causal explanations unsupported by the data.
