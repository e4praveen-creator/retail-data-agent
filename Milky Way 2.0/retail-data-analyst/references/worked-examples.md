# Worked examples from the full synthetic database

These examples were computed with `scripts/run_analysis.py` against `retail_data/data/full/retail.duckdb`. They illustrate answer shape and arithmetic. They are **fictional dataset findings**, not industry benchmarks or claims about a real retailer. The two comparable windows are **2025-01-05–2025-12-27** and **2024-01-07–2024-12-28**, each 51 complete Sunday–Saturday weeks. Rerun the query for any other dates or scope.

## Example 1 — “Are sales growing, and is it more demand?”

**Route:** 1 → 2. **Computed answer:** Net merchandise sales before returns were **$576.53 million**, up **$14.45 million (+2.57%)** from $562.09 million in the matched 2024 weeks. Original sold units fell from 5,840,052 to 5,824,619 (**−0.26%**). The dollar/unit divergence calls for the price–volume–mix bridge; it should not be labeled price growth from the trend alone.

**Visual:** aligned weekly sales lines for both 51-week windows, followed by paired dollar- and unit-growth bars. Show the two date ranges and “before returns” in the subtitle.

**SQL evidence:** `trend.weekly_sales` in the runner; summed weekly rows for each period. **Do not say:** “Demand grew 2.57%.”

## Example 2 — “How much was price, volume, or mix?”

**Route:** 2. **Computed answer:** The **$14.45 million** sales increase reconciles to approximately **+$15.94 million realized-rate**, **−$1.51 million total-unit volume**, **+$0.01 million SKU/channel mix**, and **$0 entry/exit**. The helper uses a symmetric three-factor Shapley allocation on continuing SKU/channel cells, then a separate entry/exit line; displayed effects reconcile after cent rounding.

**Visual:** prior sales → rate +$15.94m → volume −$1.51m → mix +$0.01m → current sales waterfall. Provide the exact dollar values in a table because rounded millions can appear not to sum.

**SQL evidence:** `pvm.sku_channel_periods` plus `shapley_pvm`. **Do not say:** “The higher price caused the lower unit sales.” The synthetic generation rules do not establish learned elasticity.

## Example 3 — “Why is merchandise margin different?”

**Route:** 4. **Computed answer:** Sale-cohort merchandise margin was **$238.80 million** for the 2025 window, versus **$224.54 million** in the matched 2024 window. Realized sales after all observed linked returns were **$537.33 million** versus **$523.93 million**. Merchandise margin rate rose from **42.86% to 44.44%**, or **+1.59 percentage points** after rounding. This measure excludes fulfillment and operating costs.

**Visual:** prior and current merchandise margin bars with a component table: original net sales, returned revenue, original COGS, recovered cost, realized sales, and margin. The table is needed before interpreting any single component as the explanation.

**SQL evidence:** `margin.division_margin_components`, summed across divisions. **Do not say:** “Company profit rose by $14.26 million.”

## Example 4 — “Which promotion had the most associated sales?”

**Route:** 10. **Computed answer:** In the selected 2025 window, the **Synthetic 2025-08 Footwear event** has the highest associated sales among redeemed lines: **$8.00 million** before returns across **66,320 units**, with **$0.89 million** in promotion discounts. Its linked sale-cohort merchandise margin was **$3.01 million**. The event ran **2025-08-10–2025-08-24** with a 10% discount.

**Visual:** event card and weekly timeline with the campaign window shaded; separate panels for associated sales, discount dollars, and margin. **Do not say:** “The campaign generated $8.00 million of incremental sales” or calculate ROI without a causal comparison and funding/cost data.

## Example 5 — “Are digital Footwear returns higher?”

**Route:** 16. **Computed answer:** For original Footwear sale cohorts in the 2025 window, Web returned **34,346 of 220,653 units (15.57%)**; Store POS returned **53,910 of 647,877 units (8.32%)**. Both rates use original sold units from the same sales cohort and all observed linked returns. The descriptive difference is **7.25 percentage points**.

**Visual:** channel-aligned return-rate dots with labels showing the exact returned/original unit counts. **Do not say:** “Web fulfillment caused higher returns.” Channel shoppers and baskets differ.

## Example 6 — “Where is inventory now?”

**Route:** 18 → 17. **Computed answer:** At the latest weekly snapshot on or before the requested end date (**2025-12-21**), Apparel had **492,168 on-hand units** and **467,451 available units**. The difference, **24,717 units**, is reserved. Its weekly flow reconciles: 487,912 opening + 69,388 receipts + 4,321 restocks − 69,388 sold − 65 shrink = 492,168 closing.

**Visual:** latest-snapshot inventory table by division, then a separate stock-flow view for Apparel. **Do not say:** “Apparel was out of stock on a particular day” or sum the weekly balances across time.

## Example 7 — “Are new identified buyers repeating?”

**Route:** 11. **Computed answer:** Among the **10,228** identified customers whose first *observed* purchase was in January 2025, **2,574 (25.17%)** placed another order within 90 days and **4,547 (44.46%)** within 180 days. These customers have full observation windows through the selected period end.

**Visual:** cohort heatmap with numerator/denominator in each cell and blank cells for cohorts without enough time. **Do not say:** “These are all new customers.” Their first-ever purchase is unknown before the dataset begins.
