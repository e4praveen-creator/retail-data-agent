# Question Router

Select by the *decision the user wants*, not only by keywords. When the user asks “why,” first quantify the change with Playbook 1, locate it with 3, and then run the relevant diagnostic. If the user asks for a specific period, category, channel, store, or brand, retain that scope through all follow-ups. The runner gives an all-business baseline; adapt its SQL with the documented keys for narrower slices.

## Common questions and primary route

| Playbook / CLI slug | Typical user questions | Useful follow-up |
|---|---|---|
| **1 `trend`** | How are sales doing? How was last week/month/quarter? Are we growing YoY? Is growth accelerating? What happened to orders and units? | 2 if dollars and units diverge; 3 for location; 5 for seasonal context |
| **2 `pvm`** | Was growth price or volume? Did product mix change? Are we selling more units or getting a higher rate? What explains the revenue gap? | 9 for regular price/markdown; 10 for promo-associated discounts |
| **3 `growth`** | Which division, category, brand, channel, or store accounted for the decline? What were the biggest positive and negative contributors? What is the source of growth? | 6 or 7 to inspect a contributor |
| **4 `margin`** | Why did margin fall? Did discounting or returns offset revenue growth? Is our merchandise margin improving? Which category diluted margin? | 9, 10, or 16 |
| **5 `seasonality`** | Is this a normal seasonal dip? Is back-to-school stronger this year? Is the holiday peak moving? Was a short-term jump just a calendar effect? | 1 for trend; 3 for categories |
| **6 `scorecard`** | How is Apparel/Footwear/private label performing? Give me a brand/category scorecard. Which categories are healthy on sales, margin, and returns? | 2, 4, 16 |
| **7 `channels`** | Which channel is growing? Which store is lagging? How do app, web, and POS baskets compare? Are some regions weak? | 3 for contribution; 19 for fulfillment |
| **8 `concentration`** | What percent of sales comes from our top SKUs/styles/customers? Are we dependent on a few products? How long is the tail? | 6, 13, 17 |
| **9 `pricing`** | What is our price ladder? How much markdown did we give? Did realized selling price change? Which categories are most discounted? | 2, 4, 10 |
| **10 `promotions`** | What sold on promotion? Which campaign had most redeemed sales? How much did we discount? What happened before, during, and after the campaign? | 9, 4; require a new design for causal lift |
| **11 `cohorts`** | Are new customers returning? What is the repeat rate? How did the spring cohort perform? What percent bought again within 90 days? | 12, 13, 15 |
| **12 `lapse`** | Which customers have gone quiet? How many prior buyers stopped purchasing? Are lapsed buyers reactivating? | 11, 13 |
| **13 `segments`** | Segment our customers. Who are frequent/high-value/discount-heavy buyers? What behavioral groups should we target? | 11, 12, 14 |
| **14 `affinity`** | What gets bought with Golf? Which categories co-occur in orders? What cross-sell should we test? | 13, then controlled test for incremental cross-sell |
| **15 `loyalty`** | What share of sales uses loyalty? Do loyalty members buy more often? How do tiers differ? | 11, 13; do not infer program impact |
| **16 `returns`** | Why are returns high? Which SKUs or channels have the highest return rate? What reasons dominate? Are digital returns different? | 4, 6, 19 |
| **17 `velocity`** | Which items are slow movers? What has high stock but low observed unit sales? Which SKUs turn quickly? | 18, 9 |
| **18 `inventory`** | What is ending inventory? Where is stock building? Does inventory reconcile? How many units are available? | 17, 5 |
| **19 `fulfillment`** | How much is pickup versus shipping? Do pickup orders have a different basket? What are return rates by fulfillment method? | 7, 16 |

## Compound questions

| User wording | Route in order | Decision rule |
|---|---|---|
| “Why are sales down?” | 1 → 3 → 2, 5, 7, or 10 | Choose the last drill from the observed concentration; do not run everything by default. |
| “Sales are up; why is profit down?” | 1 → 4 → 9/10/16 | Use merchandise margin terminology and show its exclusions. |
| “What should we mark down?” | 17 → 18 → 9 → 4 | Present candidates and margin/stock trade-offs; this data cannot optimize true demand response. |
| “Which customers should we win back?” | 12 → 13 → 11 | Use aggregate behavior and category-relative lapse windows. |
| “What is wrong with this promotion?” | 10 → 9 → 4 | Diagnose observed economics; explain that incrementality cannot be measured here. |
| “Which stores should carry more of this item?” | 7 → 17 → 18 | Current stock and sales can prioritize review, but every simulated store already carries every SKU. |
| “Are online orders less profitable?” | 7 → 19 → 4 → 16 | Compare *merchandise* margin and returns; fulfillment expense is missing. |

## Questions the data cannot fully answer

Do not route these to a misleading proxy. State the missing evidence and offer the nearest supported analysis.

| Question | Closest supported answer | Needed for the requested answer |
|---|---|---|
| “What is our market share, %ACV, TDP, or competitive velocity?” | Internal category sales and SKU/location sales rate | External retailer/market universe and distribution data |
| “How much incremental revenue did the promotion cause?” | Promotion-associated sales, discount, margin, and timing | Randomized holdout or defensible quasi-experiment |
| “What is price elasticity?” | Price realization and sales movements | Exogenous variation or credible causal modeling context |
| “Did we lose sales from stockouts?” | Weekly ending availability and observed sales | Daily/intraday availability plus demand evidence |
| “What is web conversion or cart abandonment?” | Completed online orders and AOV | Sessions, product views, carts, checkout events |
| “Did pickup improve retention?” | Descriptive repeat by past fulfillment method | Controlled or credible matched comparison |
| “Were deliveries on time?” | Promise-date distribution only | Actual shipment and delivery timestamps |
| “Which launch should we scale?” | Existing item sales/returns | True launch dates, distribution ramp, mature trial/repeat history |

