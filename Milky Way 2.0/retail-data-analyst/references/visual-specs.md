# Visual specifications and output standards

Use these specifications with the A–I recipe for the selected playbook. A chart is only useful if its denominator, metric basis, and comparison are visible. Export a chart with the same title and dates as the accompanying table; keep the underlying data available for audit.

## Shared visual grammar

- **Title:** business question answered, entity, metric basis, exact date range. Subtitle: comparison period and return treatment. Example: “Footwear sales before returns, 2025-04-06–2025-06-28 vs matched 2024 weeks.”
- **Units:** show USD, units, orders, customers, percentage, or percentage points on every axis/table. Express money after aggregating cents. Use `pp` for a difference between rates.
- **Colors:** current period deep green `#126B5A`; comparison gray `#7C8790`; favorable change teal `#178A7A`; unfavorable change vermilion `#C95145`; neutral/other slate `#8E9BA3`. The favorable/unfavorable mapping must follow the metric: fewer returns may be favorable. Do not rely on color alone; include labels or symbols.
- **Scales:** bars start at zero unless they depict signed contributions around zero. Lines may use a constrained y-axis when clearly labeled; never make a small change look large by hiding the scale. Use consistent scale across small multiples.
- **Ordering:** rank contribution charts by absolute dollars, then show sign. Rank rate charts only after applying minimum-base rules. State the base floor beside the chart; make it configurable and category-relative.
- **Dates:** align same weekdays or complete retail weeks for YoY trend comparisons. Note week 53, partial weeks, and the 2026 return-only tail. Distinguish weekly inventory buckets from retail weeks.
- **Uncertainty:** use a range band for forecasts or modeled estimates. For descriptive census-like synthetic data, show base size and historical variation rather than decorative p-values. Mark sparse cells “insufficient base.”
- **Interactions:** useful filters are division → department → category → style → SKU, channel, store/region, and date. Hover detail should show exact numerator, denominator, and metric definition. Keep a static table alternative for accessibility.
- **Reconciliation:** waterfalls end at the measured current total. A tooltip must show unrounded cents or a clearly labeled rounding adjustment if displayed dollar values do not visually sum.
- **Export:** chart caption should include source tables/views, run date, comparison basis, and one limitation. Never place a causal “lift” label on descriptive promotion or loyalty charts.

## Per-playbook chart recipe

### 1. YoY and Trend Analysis — aligned weekly lines

**Primary:** x = complete retail week ending date; y = net merchandise sales before returns, USD; current period solid green, matched prior period dashed gray. Direct-label the final points. Annotate any partial week or week 53, or exclude them from the comparable series. **Secondary:** diverging bars for L4, L13, and available long window growth; zero line; dollar and unit growth displayed as paired bars rather than dual axes. **Tooltip:** sales, units, orders, same-week prior-year sales, dollar difference, percentage difference. **Example read:** “The latest four complete weeks are below the corresponding 2024 weeks; units and dollars both fell.” **Do not:** use a monthly average line with unmarked incomplete months.

### 2. Price / Volume / Mix — reconciled waterfall

**Primary:** left bar = prior sales; middle signed bars = realized-rate, unit-volume, portfolio-mix if separately estimated, and item entry/exit; right bar = current sales. Each middle bar is labeled in dollars and as a percent of prior sales; tooltips show its SKU/channel base. **Secondary:** scatter of SKU unit change (x) versus realized-price change (y), point size = prior sales; four quadrants identify trade-offs. **Example read:** “The observed increase sits mostly in units, while realized rate offsets part of it.” **Do not:** add discount dollars to the waterfall if already embedded in realized-rate change; do not report a mix line unless the chosen identity reconciles.

### 3. Source of Growth — contribution bars

**Primary:** x = signed dollar contribution; y = mutually exclusive division/category/channel/store members, ranked by absolute contribution; green right, red left, zero line. Label top and bottom three, aggregate the long tail into “Other” only if it preserves total. **Secondary:** current sales share bar with the same members to separate size from growth. **Example read:** “Two divisions contain most of the company decline.” **Do not:** add a category breakdown to a channel breakdown as if they were different dollars.

### 4. Margin and Returns Bridge — two-level bridge

**Primary:** prior merchandise margin → change in original net sales → change in return deductions → change in net cost of goods → current merchandise margin. Show dollars, and separately show margin rate as a compact slope chart in percentage points. **Detail:** small table with original sales, refunds, original cost, recovered cost, and margin for each cohort. **Example read:** “Higher sales were outweighed by discount/return economics.” **Do not:** label merchandise margin as net profit or mix original-sale and return-date bases.

### 5. Seasonality and Calendar — seasonal overlay

**Primary:** x = comparable retail week; y = units or sales; 2024 gray and 2025 green, direct-labeled; shaded bands for the dataset’s synthetic seasonal events if included in the source. **Secondary:** a year-over-year weekly difference strip with a zero line. **Example read:** “The August peak appears in both years but is larger in 2025.” **Do not:** infer a stable seasonal model from only two years or silently fold week 53 into another week.

### 6. Category and Brand Scorecard — six metric tiles plus contribution

**Tiles:** realized sales, units, margin dollars, margin rate, unit return rate, identified-buyer reach; every tile shows current, prior, delta, base/coverage. **Primary detail:** diverging bars for category/style dollar contribution. **Example read:** “Sales improved, but margin rate and returns worsened.” **Do not:** show a green tile for growth without showing a material margin or return deterioration nearby.

### 7. Channel and Store Performance — growth versus margin scatter

**Primary:** x = YoY sales growth %, y = merchandise margin rate %, bubble area = current sales; point shape = channel or store format. Add median reference lines; display channel and store views separately. **Secondary:** sortable table with orders, AOV, sales change in dollars, return rate. **Example read:** “The web channel grew faster but had a different return profile.” **Do not:** interpret the between-channel difference as a channel effect or treat digital orders as sales of physical selling store 0.

### 8. Concentration and Pareto — cumulative contribution

**Primary:** entities sorted by sales descending; bars = entity sales, line = cumulative share; vertical marker at a stated entity percentile (for example top decile). **Secondary:** comparison of current and prior top-decile share. **Example read:** “The top tenth of styles account for a larger share than last year.” **Do not:** automatically call a category unhealthy because it approximates 80/20; show its change and business context.

### 9. Price Landscape and Markdown — weighted distribution

**Primary:** unit-weighted histogram of actual selling price in USD, fixed bin width appropriate to the category; overlay effective regular-price distribution with an outline or side-by-side facets. **Secondary:** box/dot plot by channel or category for realized price and markdown rate; table of discount dollars. **Example read:** “Q4 units shifted toward lower realized price bands because markdown and promotion amounts increased.” **Do not:** use SKU counts as a proxy for units sold, or join price history by SKU without the stored price key.

### 10. Promotion Performance — event timeline

**Primary:** weekly sales and units line for the affected division/channel with campaign-valid dates as a shaded band; below, separate bars for redeemed discount dollars and associated merchandise margin. **Card:** dates, eligibility, redeemed lines/units, associated sales, discount dollars, margin. **Example read:** “Redemption was concentrated in week two; associated margin was lower than surrounding weeks.” **Do not:** draw a “baseline” and shade “incremental lift” unless a causal design has been added.

### 11. Customer Cohort and Repeat — maturity-aware heatmap

**Primary:** rows = first observed purchase month; columns = months or 30/90/180 days since first order; cell = repeat share of *eligible* identified buyers; cell label = numerator/denominator. Unobserved cells are blank with hatch or muted fill, never zero. **Secondary:** cohort size bars. **Example read:** “The spring cohort’s 90-day repeat rate is lower than earlier mature cohorts.” **Do not:** compare a young cohort at 180 days when it has not had 180 days to repeat.

### 12. Customer Lapse and Reactivation — state transition

**Primary:** stacked counts of active, lapsed, and reactivated identified buyers by month using category-relative lapse rule; provide the rule in subtitle. **Secondary:** recency histogram by category, with threshold line. **Example read:** “More historically frequent buyers crossed the Footwear lapse threshold.” **Do not:** label an individual as definitively churned or forecast lost revenue from history alone.

### 13. Behavioral Segmentation — profile heatmap

**Primary:** rows = transparent behavior-defined segments; columns = recency, orders, spend, margin, category breadth, discount share, return rate; use standardized within-metric color, numeric labels, and segment size. **Secondary:** bubble scatter, x = buyer count, y = margin per buyer, size = sales. **Example read:** “A small frequent group contributes a disproportionate share of identified margin.” **Do not:** use demographic stereotypes or invented motivations as labels.

### 14. Basket Affinity — sparse pair matrix

**Primary:** category-pair matrix; cell hue = lift above/below 1, cell annotation = joint order count; hide cells under the stated minimum base. **Secondary:** ranked bars of joint baskets and lift for candidate pairs. **Example read:** “Golf and Apparel co-occur more often than their independent base rates suggest.” **Do not:** claim cross-selling one causes the other or show lift without support.

### 15. Loyalty Usage — share and cohort comparison

**Primary:** 100% bars by month for loyalty-attached versus nonattached merchandise sales; overlay order share only in a separate panel. **Secondary:** identified-customer repeat by enrollment cohort, with counts. **Example read:** “Most identified sales are attached to loyalty accounts.” **Do not:** call the member/nonmember gap a program impact; the synthetic enrollment process is selective.

### 16. Return Cohort and Reason — return heatmap

**Primary:** rows = original sale month; columns = elapsed days or return month; cell = returned units / original units for the same cohort, with numerator and denominator in tooltip. **Secondary:** ranked reasons as percent of returned units, faceted by category/channel. **Example read:** “Digital Footwear has a higher observed cohort return rate.” **Do not:** divide current-period returns by current-period sales or hide cohorts without full 60-day maturity.

### 17. Item Velocity and Sell-Through — stock versus sales scatter

**Primary:** x = units sold per observed week; y = weeks of supply using a documented recent-sales rate; bubble = latest available units; color = category-relative velocity percentile. Show threshold lines and the underlying numerator/denominator on hover. **Secondary:** ranked candidate table with SKU, recent units, available, margin, and return rate. **Example read:** “These SKUs have high available stock and low internal sales rate.” **Do not:** label the rate NIQ $/TDP or infer delisting safety from low sales alone.

### 18. Inventory Health and Reconciliation — stock/flow separation

**Primary:** line = ending on-hand by week; separate bars = receipts, sold units, restocks, and shrink. A compact reconciliation table shows opening + inflows − outflows = closing for each SKU/location/week. **Secondary:** heatmap of stock change by category and location. **Example read:** “Outdoor ending stock rose while recent sales were flat.” **Do not:** stack weekly ending balances or infer daily stockouts from the weekly series.

### 19. Fulfillment Method Mix — mix and outcome panels

**Primary:** 100% stacked bars of completed orders by carry-out, pickup, DC ship, and ship-from-store over time. **Secondary:** separate aligned dot plots for AOV, merchandise margin rate, and unit return rate by method; show order and sold-unit bases. **Example read:** “Pickup gained order share and has a different observed basket size.” **Do not:** show on-time delivery, delivery cost, or causal method benefit because actual delivery events and fulfillment costs are absent.
