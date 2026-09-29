# Retail Data Agent — Playbook Library

The executable skill version is in [retail-data-analyst](retail-data-analyst/SKILL.md). It adds [common question routing](retail-data-analyst/references/question-router.md), [detailed visual specifications](retail-data-analyst/references/visual-specs.md), [computed synthetic examples](retail-data-analyst/references/worked-examples.md), and a read-only analysis runner. The A–I recipes below are also packaged with that skill.

This library follows the tiered index and nine-section (A–I) format in the supplied images. It is scoped to the fictional Summit Field dataset, not to syndicated NielsenIQ or Circana data. These are analytical playbooks for an agent or analyst to implement; the worked examples are question-and-answer *templates*, not computed findings.

## How to read this library

Each playbook specifies **A. Summary; B. Required Input Data; C. Method; D. Accuracy Guardrails; E. Output Template; F. Visual Spec; G. Worked Example; H. How to Interpret; I. Follow-Up Deep Dives**. The quoted question in A or G is a routing trigger. Run the narrowest playbook that answers the question, then follow the listed deep dives when the evidence warrants it.

### Dataset contract and binding conventions

- Sales cover **2024-01-01 through 2025-12-31**. Returns are observed through **2026-03-01**, giving every sale a complete 60-day return window. No sales occur in the 2026 return tail.
- Money is stored in **US cents**. Divide the final aggregate by 100. Merchandise sales exclude tax and shipping. Say whether the answer is **before returns**, **sale-cohort after returns**, or **period revenue** with returns booked on return date.
- Sales lines, transactions, returns, and weekly inventory have different grains. Aggregate each fact to the intended grain before joining. Never sum header money after joining to lines, or inventory balances over weeks.
- Use the same dates, SKU universe, channel mapping, and 4-5-4 retail weeks in comparisons. State exact start and end dates. Flag partial periods and week 53. Inventory weeks start Monday; retail weeks start Sunday, so align them by dates.
- Show base size, comparison period, and ordinary week-to-week variation before calling a change meaningful. A single exceptional week is not a trend. Small cells should be combined or labeled unstable. Thresholds should be relative to category or historical behavior and stated explicitly.
- A decomposition is an accounting allocation: it locates the change but does not establish its cause. Use one documented interaction convention throughout a bridge, either a separate interaction line or a symmetric split. The bridge must reconcile to the headline at the cent level before display rounding.
- Every output uses the same decision structure: **headline; scope and metric definition; primary visual; supporting table; interpretation; uncertainty or limitation; suggested next question**. Visuals need units, date range, legend, denominator, and accessible colors. Do not draw a causal arrow where only association is known.
- The dataset is simulated. Promotions have no treatment/control design; prices are constructed inputs; inventory receipts cover observed demand; all stock-holding locations carry every SKU. Do not infer promotional incrementality, learned price elasticity, genuine lost sales, market share, competitive distribution, or launch success. The `dim_customer.customer_segment` label is synthetic metadata, not a behavior-derived segment.

See [metric definitions](retail_data/docs/METRICS.md), [model boundaries](retail_data/docs/MODEL.md), and the [field dictionary](retail_data/docs/DATA_DICTIONARY.md) for the authoritative data contract.

## Playbook index

The order follows the images' sales-driver spine, adapted to what this retailer's data can support.

| Tier | # | Playbook | Typical trigger |
|---|---:|---|---|
| 1 — Headline and economic drivers | 1 | YoY and Trend Analysis | “Are sales improving?” |
| 1 | 2 | Price / Volume / Mix Bridge | “Is growth price, units, or product mix?” |
| 1 | 3 | Source of Growth | “Which categories, brands, stores, or channels account for the change?” |
| 1 | 4 | Margin and Returns Bridge | “Why did merchandise margin move?” |
| 1 | 5 | Seasonality and Calendar | “Is this dip seasonal?” |
| 2 — Merchandise and commercial context | 6 | Category and Brand Scorecard | “Which part of the assortment is healthy?” |
| 2 | 7 | Channel and Store Performance | “Where are we winning or losing?” |
| 2 | 8 | Concentration and Pareto | “How dependent are we on a few SKUs or buyers?” |
| 2 | 9 | Price Landscape and Markdown | “How are realized prices and markdowns changing?” |
| 2 | 10 | Promotion Performance — Descriptive | “What sold during the campaign?” |
| 3 — Customers and baskets | 11 | Customer Cohort and Repeat | “Are new customers coming back?” |
| 3 | 12 | Customer Lapse and Reactivation | “Which identified customers have stopped buying?” |
| 3 | 13 | Behavioral Segmentation | “What distinct shopping patterns exist?” |
| 3 | 14 | Basket Affinity | “Which categories are bought together?” |
| 3 | 15 | Loyalty Usage | “How much sales and repeat behavior involve loyalty?” |
| 4 — Returns, stock, and execution | 16 | Return Cohort and Reason | “What is driving returns?” |
| 4 | 17 | Item Velocity and Sell-Through | “Which items move efficiently?” |
| 4 | 18 | Inventory Health and Reconciliation | “Where is stock building up?” |
| 4 | 19 | Fulfillment Method Mix | “How do pickup, shipping, and carry-out differ?” |

---

## Tier 1 — Headline and economic drivers

### Playbook 1 — YoY and Trend Analysis

**A. Summary.** Entry point for “How did sales do?” Establish direction, scale, and momentum before seeking causes.

**B. Required Input Data.** `fact_transaction` for orders, header merchandise sales, and channel; `fact_sales_line` or `v_sales` for product units and sales; `dim_date` for aligned calendar/retail weeks. Grain: complete week × requested entity, with current and comparable prior-year dates. Returns require an explicitly selected view.

**C. Method.** Calculate sales, units, orders, average selling price (`sales / units`), and YoY dollar/percentage changes for comparable 4-, 13-, and 52-week windows where coverage permits. Compare L4W to L13W before describing acceleration. Rank the largest absolute contributors only after the headline is established.

**D. Accuracy Guardrails.** Exclude or flag partial weeks; state exact dates; never silently compare 53 and 52 weeks. Dollar growth above unit growth is a *rate or mix* signal, not proof of a list-price rise. AOV uses headers without line fan-out.

**E. Output Template.** “For [dates], [scope] net merchandise sales before returns were [$], [±$ / ±%] versus comparable dates; units were [±%]. L4W versus L13W suggests [momentum read].” Include period table and one limitation.

**F. Visual Spec.** Weekly sales line: current period solid green, comparable prior period dashed gray, same axis. A small labeled bar chart shows L4/L13/L52 growth. Zero line for growth rates.

**G. Worked Example.** Q: “How did Footwear do in the last four complete weeks of 2025?” A: Return its four-week sales, units, comparable 2024 change, exact dates, and route any dollar/unit divergence to Playbook 2.

**H. How to Interpret.** Sales and units rising together indicate broader observed sales growth; sales rising with flat units calls for price/mix analysis; a L4 reversal needs confirmation against weekly variation.

**I. Follow-Up Deep Dives.** Playbook 2 for rate versus quantity; 3 for location of the change; 5 for calendar effects; 16 if returns alter the picture.

### Playbook 2 — Price / Volume / Mix Bridge

**A. Summary.** Answer “How much of the sales change is price, how much is quantity, and how much is assortment mix?”

**B. Required Input Data.** `fact_sales_line`, `v_product`, `fact_price_history` via the stored `price_key`, and `dim_date`. Grain: SKU × channel × matched period. Use merchandise sales before returns unless the question specifies otherwise.

**C. Method.** For continuing SKU/channel cells calculate unit quantity `q` and realized average selling price `p = net_sales / q`. Use the symmetric identity: price effect `Δp × (q0+q1)/2`; quantity effect `Δq × (p0+p1)/2`. Sum at cell level; separate new, discontinued, and zero-quantity cells as entry/exit. If a portfolio “mix” line is needed, further split quantity into total-unit change and SKU share movement using a documented, reconciling convention. Show regular-price, markdown, and promotion changes as *sub-analysis*, not extra lines added to the same total.

**D. Accuracy Guardrails.** Do not calculate from brand-level average prices. Keep the same SKU and channel definitions. Do not label all realized-price movement “list price”; promotions and markdowns affect it. The synthetic assortment has no true launches or delistings, so entry/exit is likely uninformative.

**E. Output Template.** “Sales changed by [$]: [price/rate $], [unit $], [mix $ if used], and [entry/exit $]. The displayed terms reconcile to [$].” Add the top contributing SKUs/categories.

**F. Visual Spec.** Reconciling waterfall from prior to current sales; positive green, negative red, neutral gray. Detail table reports units, realized price, and each effect.

**G. Worked Example.** Q: “Was Apparel’s 2025 growth from prices or more units?” A: Compute the SKU/channel bridge for comparable 2024 and 2025 periods; explicitly distinguish realized price from regular price.

**H. How to Interpret.** A rate contribution with flat units may reflect price-book change, fewer discounts, or richer mix; it does not identify shopper price response.

**I. Follow-Up Deep Dives.** Playbook 9 for markdown/price mechanics; 10 for promotion association; 3 for which categories contribute.

### Playbook 3 — Source of Growth

**A. Summary.** Locate the segments of the business in which an observed sales movement sits.

**B. Required Input Data.** `v_sales`/`fact_sales_line`, `v_product`, `fact_transaction` for channel and store attribution, `dim_date`. Grain: one mutually exclusive dimension value × period.

**C. Method.** For each chosen partition (division, category, brand, channel, or market store), calculate `current − prior` and contribution to total change. Reconcile the partition to the headline. Use one partition at a time; a channel and a category breakdown are alternative views of the same dollars.

**D. Accuracy Guardrails.** Do not add contributions from overlapping dimensions. Digital orders have `selling_store_key=0`; use `market_store_key` for home-market analysis and `fulfillment_location_key` for stock source, labeling the choice. Do not say a segment “caused” the change.

**E. Output Template.** Headline change, top three positive and negative contributors, complete reconciled table, and next diagnostic question.

**F. Visual Spec.** Horizontal diverging bars of dollar contribution with a zero line; optional treemap for current size, never as a substitute for change.

**G. Worked Example.** Q: “Which divisions account for our sales decline?” A: Show each division’s dollar contribution summing to the company decline and then drill into the largest one.

**H. How to Interpret.** Large contributions indicate where to investigate. A small segment with a large percentage change may have little total impact.

**I. Follow-Up Deep Dives.** Playbook 2 for price/units; 6 for merchandise health; 7 for geographic/channel concentration.

### Playbook 4 — Margin and Returns Bridge

**A. Summary.** Explain movement in merchandise margin from sales, discounts, returned revenue, and net product cost.

**B. Required Input Data.** `v_sales_after_returns`, `fact_sales_line`, `fact_return_line`, and `dim_date`. Grain: original sales cohort × product or channel. Use complete 60-day return observation for both cohorts.

**C. Method.** Reconcile cohort realized net sales to original net sales less returned merchandise. Reconcile margin to realized net sales minus original COGS plus recovered cost on restockable returns. Compare margin dollars and margin rate across matched cohorts; display sales and cost components separately.

**D. Accuracy Guardrails.** This is **merchandise margin**, excluding shipping, handling, labor, and operating expenses. Never mix return-date deductions with sale-date cohort margin in one bridge. Avoid comparing an immature cohort with a fully matured one.

**E. Output Template.** “Cohort merchandise margin changed by [$]; the largest accounting movements were [items]. Margin rate moved [percentage points].” Include reconciliation and exclusions.

**F. Visual Spec.** Prior-to-current margin waterfall plus a two-point margin-rate comparison; label dollars and percentage points distinctly.

**G. Worked Example.** Q: “Why did Footwear margin fall in Q4?” A: Compare fully observed Q4 sale cohorts, disaggregating discounts, returned revenue, and recovered product cost.

**H. How to Interpret.** Higher sales can coexist with lower margin if discount or return effects outweigh the revenue gain.

**I. Follow-Up Deep Dives.** Playbook 9 for discount detail; 10 for promotion-associated margin; 16 for return reasons.

### Playbook 5 — Seasonality and Calendar

**A. Summary.** Test whether a trough or peak is consistent with the dataset’s recurring calendar pattern.

**B. Required Input Data.** `v_sales` or `fact_transaction`, `dim_date` with Gregorian and 4-5-4 fields; weekly product/category history for 2024–2025.

**C. Method.** Plot weekly sales and units by aligned retail week, compare each week with its prior-year match, and inspect category-level patterns. Explain holiday, back-to-school, and weekend concentration as dataset construction rules only when relevant.

**D. Accuracy Guardrails.** Two years support a descriptive seasonal comparison, not a robust multi-year seasonal forecast. Flag partial fiscal years and week 53; do not silently restate it. Calendar association is not a causal estimate.

**E. Output Template.** Current observation, comparable prior-year week, category pattern, and whether the difference exceeds normal week-to-week variation.

**F. Visual Spec.** Overlay of 2024 and 2025 weekly values with aligned week labels; annotate holidays or period boundaries.

**G. Worked Example.** Q: “Is the August Footwear spike unusual?” A: Compare aligned August weeks and the surrounding weeks, then state whether the spike also appears in the prior year.

**H. How to Interpret.** A repeating pattern suggests a seasonal component; a one-year difference needs a commercial drill-down.

**I. Follow-Up Deep Dives.** Playbooks 1, 3, 9, and 10.

## Tier 2 — Merchandise and commercial context

### Playbook 6 — Category and Brand Scorecard

**A. Summary.** Give a compact health view for a division, category, or brand.

**B. Required Input Data.** `v_sales_after_returns`, `v_product`, `fact_transaction`, and `dim_date`. Grain: chosen merchandise level × matched period.

**C. Method.** Report six tiles: realized sales, units, margin dollars, margin rate, return rate, and buyer/order reach where identity allows. Compare with prior year and with the parent category. Rank subcategories or styles by contribution, not just percentage growth.

**D. Accuracy Guardrails.** Brand is attached to style; aggregate through the documented hierarchy. Buyer reach excludes anonymous key 0 and is not household penetration. Parent category comparison is internal, not market share.

**E. Output Template.** Six-tile scorecard, one-sentence health read, three largest positive/negative components, and a limitation.

**F. Visual Spec.** Six aligned KPI tiles plus ranked diverging bars; consistent green/red semantics and explicit period labels.

**G. Worked Example.** Q: “Give me a one-page scorecard for our private label.” A: Report its six metrics against the matching prior period and company/category context.

**H. How to Interpret.** Sales growth paired with margin or return deterioration is mixed performance, not an unqualified win.

**I. Follow-Up Deep Dives.** Playbooks 2, 3, 10, and 16.

### Playbook 7 — Channel and Store Performance

**A. Summary.** Compare POS, web, app, stores, and home markets on consistent commercial measures.

**B. Required Input Data.** `fact_transaction`, `fact_sales_line`, `v_sales_after_returns`, `dim_channel`, `dim_store`, `dim_fulfillment_method`, and `dim_date`. Grain: channel or store/market × period.

**C. Method.** Calculate sales, orders, units, AOV, margin, return rate, and YoY change; compare like-for-like stores or a fixed store universe. Keep selling store, market store, and fulfillment source as separate geographic concepts.

**D. Accuracy Guardrails.** Online orders have selling store 0; do not allocate them to a physical selling store. AOV comes from transaction headers. Differences across channels reflect different customers and baskets, not channel treatment effects.

**E. Output Template.** Channel/store ranking, largest changes in dollars, comparison basis, and the first segment to inspect.

**F. Visual Spec.** Scatterplot of growth versus margin with bubble size as sales; filterable table. A map is optional only if a valid store geography exists.

**G. Worked Example.** Q: “Which stores are lagging in 2025?” A: Rank comparable POS stores by contribution and show each store’s category mix and return rate.

**H. How to Interpret.** A weak store may have a category-specific issue; a weak channel may reflect its order mix or promotion exposure.

**I. Follow-Up Deep Dives.** Playbooks 3, 6, 10, and 16.

### Playbook 8 — Concentration and Pareto

**A. Summary.** Show dependence on a small set of SKUs, styles, categories, or identified buyers.

**B. Required Input Data.** `fact_sales_line`, `v_product`, `fact_transaction`, and `dim_date`. Grain: entity × period. Customer calculations exclude `customer_key=0`.

**C. Method.** Sort entities by sales or margin, calculate cumulative contribution and top-decile share, and compare periods. For customers, report identified-sales coverage so the excluded anonymous portion remains visible.

**D. Accuracy Guardrails.** Do not treat pooled anonymous key 0 as one buyer. Thresholds such as “top 20%” should be labeled, not assumed to prove an 80/20 law. SKU count and dollar concentration measure different things.

**E. Output Template.** “The top [n / %] entities account for [%] of [metric] in [period], versus [%] previously.” Add the denominator and coverage.

**F. Visual Spec.** Pareto bars and cumulative line; optional Lorenz curve for customer concentration.

**G. Worked Example.** Q: “How dependent is Golf on its top styles?” A: Show cumulative sales and margin by style and how this changed year over year.

**H. How to Interpret.** Concentration increases exposure to a few items or buyers, but may be appropriate for a focused category.

**I. Follow-Up Deep Dives.** Playbooks 6, 13, and 17.

### Playbook 9 — Price Landscape and Markdown

**A. Summary.** Describe price architecture and discount realization across products and channels.

**B. Required Input Data.** `fact_price_history`, `fact_sales_line`, `v_product`, `dim_channel`, and `dim_date`. Grain: SKU × channel × valid price interval or sold line.

**C. Method.** Compare effective regular price, realized selling price, markdown cents, and promotion cents. Use unit-weighted price histograms and price bands by category. Calculate markdown rate on the defined regular-sales base and show margin by price band.

**D. Accuracy Guardrails.** Use the line’s `price_key` to identify its valid price record; do not join a SKU to every price-history row. MSRP is absent. There is no learned elasticity, competitor price, or genuine clearance optimization in this simulation.

**E. Output Template.** Price distribution, realized-to-regular price gap, markdown dollars/rate, margin implications, and affected SKUs.

**F. Visual Spec.** Unit-weighted price histogram with clearly labeled bins; regular versus realized price dot plot; avoid dual axes.

**G. Worked Example.** Q: “Did Q4 markdowns change the price ladder in Apparel?” A: Compare Q4 unit-weighted regular and selling prices with Q3 and identify the categories contributing most to markdown dollars.

**H. How to Interpret.** A lower selling price can reflect markdowns, promotion redemption, or mix toward cheaper items; distinguish them before recommending a change.

**I. Follow-Up Deep Dives.** Playbooks 2, 4, and 10.

### Playbook 10 — Promotion Performance, Descriptive

**A. Summary.** Answer what happened on promotion-associated lines and around each campaign; do not estimate incrementality.

**B. Required Input Data.** `dim_promotion`, `fact_sales_line`, `fact_transaction`, `v_product`, and `dim_date`. Grain: campaign × SKU/category × date/channel, with comparable noncampaign context.

**C. Method.** Measure redeemed units, associated net sales, discount dollars, associated merchandise margin, buyer reach, and sales trend before/during/after valid dates. Separate eligibility from redemption because not every eligible line redeems. Compare campaigns by depth and channel with context for seasonality.

**D. Accuracy Guardrails.** Do not call associated sales “incremental,” “lift,” or “ROI.” Campaign dates, prices, and seasons overlap by design. There is no randomized holdout or trade funding ledger. State whether loyalty-only and channel restrictions apply.

**E. Output Template.** Campaign card: dates/eligibility, associated sales and units, discount dollars, observed margin, and pre/during/post pattern, followed by a causal-evidence warning.

**F. Visual Spec.** Weekly event timeline with campaign band, separate sales/units and margin panels; no unlabelled causal uplift bar.

**G. Worked Example.** Q: “How did the December Outdoor promotion perform?” A: Report redeemed lines and dollars, margin, and surrounding weeks; say that incremental effect is unavailable.

**H. How to Interpret.** High campaign sales may include purchases that would have happened anyway. Low margin during a campaign deserves review but is not proof the campaign reduced total profit.

**I. Follow-Up Deep Dives.** Playbooks 4 and 9; add a randomized or credible quasi-experimental design before building an incrementality playbook.

## Tier 3 — Customers and baskets

### Playbook 11 — Customer Cohort and Repeat

**A. Summary.** Follow identified shoppers from their first observed order to later orders.

**B. Required Input Data.** `fact_transaction`, `dim_date`, and optionally `v_sales_after_returns`. Grain: identified `customer_key` × order date; acquisition cohort × elapsed month.

**C. Method.** Assign first **observed** purchase month, count eligible buyers and repeat buyers at fixed elapsed horizons, and report orders and sales per buyer. Compare only cohorts with equal observation time.

**D. Accuracy Guardrails.** Exclude anonymous key 0. First observed purchase in 2024 may not be true first-ever purchase because history begins then. Late-2025 cohorts are right-censored for repeat behavior. Registration date is not purchase acquisition.

**E. Output Template.** Cohort retention table, eligible denominators, repeat rate by elapsed month, and a comparison of matured cohorts.

**F. Visual Spec.** Cohort heatmap with acquisition month rows and elapsed-month columns; fade unavailable cells rather than plotting zeros.

**G. Worked Example.** Q: “Did shoppers first seen in spring 2025 come back?” A: Show their three- and six-month repeat rates only where the full horizon is observed.

**H. How to Interpret.** A low short-term repeat rate may reflect a long purchase cycle rather than poor retention.

**I. Follow-Up Deep Dives.** Playbooks 12, 13, 15, and 16.

### Playbook 12 — Customer Lapse and Reactivation

**A. Summary.** Identify historical buyers who have not purchased again within an explicitly chosen window.

**B. Required Input Data.** `fact_transaction`, `dim_date`, and `v_product` for category-specific cadence. Grain: identified customer × analysis date.

**C. Method.** Measure days since last purchase and historical order interval by customer/category. Define lapse using a category-relative threshold; count customers and historical sales at risk. Track return to purchase after lapse as reactivation.

**D. Accuracy Guardrails.** Do not label every infrequent shopper “churned.” The observation window ends with 2025 sales, so no 2026 purchasing can be observed. “Sales at risk” is historical exposure, not a forecast or realized loss.

**E. Output Template.** Lapsed buyer count, threshold, prior activity, category mix, and reactivation history.

**F. Visual Spec.** Recency distribution and transition matrix (active → lapsed → reactivated), with explicit window boundaries.

**G. Worked Example.** Q: “Which repeat Footwear buyers went quiet in the second half of 2025?” A: Apply the Footwear cadence threshold to identified buyers and list aggregate segment counts, not individual personal records.

**H. How to Interpret.** Lapse is a prioritization signal whose usefulness depends on the expected buying cycle.

**I. Follow-Up Deep Dives.** Playbooks 11, 13, and 15.

### Playbook 13 — Behavioral Segmentation

**A. Summary.** Create transparent groups from observed shopping behavior to guide analysis and testing.

**B. Required Input Data.** `fact_transaction`, `fact_sales_line`, `v_product`, and `dim_date`. Grain: identified customer over a fixed lookback. Exclude customer key 0.

**C. Method.** Compute recency, order frequency, realized spend or margin, discount share, category breadth, channel preference, and return rate. Start with interpretable rules or RFM quantiles; describe group size, sales share, and stability across periods.

**D. Accuracy Guardrails.** The provided `dim_customer.customer_segment` is a synthetic label and must not be passed off as a discovered segment. Avoid demographic or psychological claims. State that anonymous buyers are outside the analysis; choose relative thresholds and report them.

**E. Output Template.** Segment definition table, buyer count, share of identified sales, distinctive behavior, and a testable action for each group.

**F. Visual Spec.** Segment profile heatmap using standardized measures, plus a size-versus-margin scatterplot; no fabricated persona portraits.

**G. Worked Example.** Q: “Group our customers by actual shopping behavior.” A: Produce a small, named set of behavior-defined groups with clear rules and coverage.

**H. How to Interpret.** A useful segment suggests different decisions and is stable enough to find again, not merely a cluster with a catchy name.

**I. Follow-Up Deep Dives.** Playbooks 11, 12, 14, and 15.

### Playbook 14 — Basket Affinity

**A. Summary.** Find product or category combinations observed in the same completed order.

**B. Required Input Data.** `fact_sales_line`, `fact_transaction`, and `v_product`. Grain: unique transaction × category/style; deduplicate repeated lines of the same entity in a basket.

**C. Method.** For candidate pairs calculate joint-basket count, support, confidence, and lift versus the base rate. Show pair margin and reach; filter to a configurable minimum basket base.

**D. Accuracy Guardrails.** Do not infer causation, cross-sell incrementality, or sequence from same-basket co-occurrence. Very popular categories appear in many pairs by chance; lift and base count must accompany raw pair counts.

**E. Output Template.** Pair table with joint baskets, support, confidence, lift, sales/margin context, and an activation hypothesis.

**F. Visual Spec.** Sparse affinity matrix or ranked pair bars. Scale color by lift and annotate joint-basket count so small cells do not look decisive.

**G. Worked Example.** Q: “What tends to be bought with Golf?” A: Show category pairs with sufficient joint baskets and above-baseline co-occurrence, not a claim that one item causes the other.

**H. How to Interpret.** A strong pair is a candidate for merchandising or a controlled cross-sell test.

**I. Follow-Up Deep Dives.** Playbooks 6, 13, and 10; validate an offer through an experiment before claiming halo.

### Playbook 15 — Loyalty Usage

**A. Summary.** Describe how much commerce is attached to a loyalty account and how those identified buyers behave.

**B. Required Input Data.** `fact_transaction`, `dim_loyalty`, `dim_customer`, `dim_date`, and optionally `v_sales_after_returns`. Grain: transaction or identified customer × period.

**C. Method.** Measure loyalty-attached sales share, orders, AOV, repeat, and margin. Compare enrollment cohorts and tiers descriptively; distinguish account enrollment from use on a specific order.

**D. Accuracy Guardrails.** `loyalty_key=0` means no attached account, not necessarily an anonymous buyer. Enrolled identified shoppers always attach loyalty in this simulation, creating selection by construction. Do not claim loyalty enrollment caused higher spending or retention.

**E. Output Template.** Loyalty share and behavior table, identified-customer coverage, and a clear descriptive interpretation.

**F. Visual Spec.** Share bars over time and aligned cohort retention curves; label different denominators.

**G. Worked Example.** Q: “What share of 2025 sales came from loyalty members?” A: Report the header-based share and specify before/after-return treatment.

**H. How to Interpret.** A high loyalty sales share shows attachment and concentration, not program effectiveness.

**I. Follow-Up Deep Dives.** Playbooks 11, 12, and 13; a program impact study would require an appropriate comparison design.

## Tier 4 — Returns, stock, and execution

### Playbook 16 — Return Cohort and Reason

**A. Summary.** Diagnose return incidence, revenue deduction, recovered cost, and reasons by original sales cohort.

**B. Required Input Data.** `v_sales_after_returns`, `fact_return_line`, `fact_sales_line`, `dim_return_reason`, `v_product`, `dim_channel`, and `dim_date`. Grain: original sale line/cohort × product/channel.

**C. Method.** Calculate returned units divided by original units for the same fully observed sale cohort. Measure refund merchandise, restockable share, and reason mix; compare product and channel cohorts. Separately report return-date revenue deductions if the user asks about period revenue.

**D. Accuracy Guardrails.** Never divide returns in one calendar period by sales in that same period and call it a cohort rate. At most one unit returns per selected line in this simulation; reason distribution and return probabilities are constructed, not benchmarks.

**E. Output Template.** Cohort unit return rate, returned-revenue share, top contributing products/channels, reason mix, and recovered-cost context.

**F. Visual Spec.** Cohort heatmap by sale month and return lag; ranked reason bars; rate axis starts at zero.

**G. Worked Example.** Q: “Are digital Footwear returns higher than store returns?” A: Compare matched Footwear sale cohorts by channel and report rates, counts, and amount; avoid inferring the channel caused the difference.

**H. How to Interpret.** A high rate warrants an item, size, fulfillment, or customer-mix review, but the dataset does not identify an operational root cause by itself.

**I. Follow-Up Deep Dives.** Playbooks 4, 6, 7, and 19.

### Playbook 17 — Item Velocity and Sell-Through

**A. Summary.** Find SKUs whose observed sales rate or stock movement differs from category peers.

**B. Required Input Data.** `fact_sales_line`, `fact_inventory_weekly`, `v_product`, `dim_location`, and dates. Grain: SKU × physical location × aligned week; aggregate sales and inventory separately before joining.

**C. Method.** Calculate units per selling week and per stocked location, plus a clearly defined period sell-through using starting stock and receipts. Compare SKU percentiles within category/size configuration. Report current available units and weeks of supply as descriptive ratios.

**D. Accuracy Guardrails.** This is **internal velocity**, not NIQ $/TDP or market distribution. All locations carry all SKUs; distribution reach has no meaningful variation. Weekly balances cannot identify intraday stockouts or lost demand. A low-sales SKU is not automatically safe to delist.

**E. Output Template.** SKU peer rank, sales rate, available units, weeks of supply, and category-relative flag with a stated threshold.

**F. Visual Spec.** Scatterplot of units per week versus weeks of supply; bubble size as margin dollars; category percentile reference lines.

**G. Worked Example.** Q: “Which Apparel SKUs are slow movers with high stock?” A: Rank within Apparel using category-relative thresholds and show the underlying sales and stock values.

**H. How to Interpret.** High stock and low observed velocity is an inventory-review candidate, not evidence that the item lacks customer value.

**I. Follow-Up Deep Dives.** Playbooks 8, 9, 18, and 6.

### Playbook 18 — Inventory Health and Reconciliation

**A. Summary.** Examine closing inventory, available stock, stock build, and ledger consistency.

**B. Required Input Data.** `fact_inventory_weekly`, `fact_sales_line`, `fact_return_line`, `v_product`, `dim_location`, and date dimension. Grain: SKU × location × Monday-start week.

**C. Method.** Verify `closing = opening + receipts + restocked returns − sold − shrink` and `available = closing − reserved`. Use the **last** snapshot for ending inventory. Compare current stock with recent observed demand and identify the largest stock-build contributors.

**D. Accuracy Guardrails.** Never sum weekly balances across time. Do not join inventory week number to Sunday-start retail week number. Receipts and in-transit units are illustrative and lack purchase-order links; replenishment was constructed to cover demand. No daily stockout, service-level, or lost-sales conclusion is supported.

**E. Output Template.** Ending on-hand and available units, stock-build locations/items, reconciliation exceptions, and turnover or supply metric with its exact period and denominator.

**F. Visual Spec.** Ending-stock trend as a line, flows as separate bars, and SKU/location exception heatmap. Do not stack snapshots as if they were flows.

**G. Worked Example.** Q: “Where is Outdoor stock accumulating?” A: Compare ending snapshots, rank SKU/location increases, then show whether recent unit sales kept pace.

**H. How to Interpret.** Stock build is observable; excess, shortage, and replenishment causality require a service target and real demand/lead-time data.

**I. Follow-Up Deep Dives.** Playbooks 17, 5, and 9.

### Playbook 19 — Fulfillment Method Mix

**A. Summary.** Compare completed orders by carry-out, pickup, DC shipping, and ship-from-store.

**B. Required Input Data.** `fact_transaction`, `dim_fulfillment_method`, `fact_sales_line`, `v_sales_after_returns`, `dim_channel`, and dates. Grain: completed order × fulfillment method; returns can be linked back to the sale.

**C. Method.** Report orders, sales, AOV, units/order, merchandise margin, and sale-cohort return rate by method and channel. Describe promise days using `promised_delivery_date` for lines, keeping an order-level rollup separate.

**D. Accuracy Guardrails.** The dataset contains a delivery *promise*, not actual shipment or delivery. Shipping expense and handling cost are absent. Do not report on-time rate, delivery quality, fulfillment profitability, or causal method effects.

**E. Output Template.** Method mix and metrics table, largest YoY shift, basket/return context, and operational data needed to answer any service-quality follow-up.

**F. Visual Spec.** 100% stacked method-mix bars over time and a separate margin/return-rate comparison; avoid combining unlike units on one axis.

**G. Worked Example.** Q: “Did pickup grow in 2025, and how do its orders compare?” A: Show order share and observed basket/margin/return differences, without claiming pickup caused those outcomes.

**H. How to Interpret.** A shift in method mix is a channel and operations signal; it does not measure service success.

**I. Follow-Up Deep Dives.** Playbooks 7, 16, and 4; add actual fulfillment events and costs for service and profitability analysis.

## Requests to route to a data-gap answer

The agent should say what is missing, offer the closest descriptive analysis, and specify the next dataset or test. Do not simulate a conclusion from the synthetic warehouse.

| User request | Why this dataset cannot answer it | Needed to enable it |
|---|---|---|
| “What is our market share or %ACV?” | Only one fictional retailer; no competitive market universe | Syndicated market POS, outlet universe, and coverage definitions |
| “Did this promotion cause incremental sales?” | No randomized or credible untreated comparison | Holdout or defensible quasi-experiment and cost/funding ledger |
| “What is price elasticity?” | Price and demand are generated from assumptions; no exogenous variation | Rich price history, competitor/context controls, and identification design |
| “How many sales did stockouts cost?” | Weekly stock, no lost-demand or daily availability events | Daily/intraday availability and demand/traffic evidence |
| “What is web conversion or cart abandonment?” | No sessions, views, or carts | Digital event stream and identity/session rules |
| “Which new launch succeeded?” | Fixed assortment, no genuine launch events | Item introduction dates, distribution ramp, and mature repeat window |
| “Are deliveries on time?” | Promise date only, no actual delivery event | Shipment and delivery timestamps |
| “Which supplier should we reorder from?” | No suppliers, POs, or lead times | Procurement and vendor data |
