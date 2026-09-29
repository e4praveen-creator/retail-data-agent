# Answer examples and output review

[Handbook](README.md) · [Output implementation](LOW_LEVEL_DESIGN.md) · [Proposed answer-design UI](UI_IMPROVEMENT_PLAN.md)

These are developer reference examples, not additional model-visible benchmark answers. Numerical values below were freshly measured with deterministic scoped queries for this documentation baseline. They are not a newly generated live-model response. The exact SQL, bound parameters, scope and rows are in [answer-example-evidence.json](reference/answer-example-evidence.json). Do not copy these numbers into answers for other dates or filters.

## 1. Definition answer

**Question:** “What does customer_key mean, and why is zero special?”

**Desired response:**

> `customer_key` links a transaction to its customer record. Key `0` means the purchase is anonymous. Exclude it when counting identified buyers; otherwise all anonymous purchases would appear to belong to one customer. See the customer definition and metric contract for the relevant field and counting rule.

The actual app should attach the real retrieved `D#` reference. This documentation sample does not invent a runtime source ID. No sales chart is needed. A good answer explains the operational consequence of the definition without claiming a new measured customer count.

## 2. Scoped comparison with measured evidence

**Question:** “Show Web Footwear sales and units for July 2025 versus July 2024.”

**Headline:** Web Footwear merchandise sales rose **3.70% to $1,520,528.53**; sold units rose **1.25% to 12,222**.

**Scope and basis:** July 1–31, 2025 versus July 1–31, 2024, inclusive. Channel = Web; division = Footwear. Merchandise sales after markdown/promotion discounts and before returns, tax and shipping. Original sale dates; USD display from integer cents.

| Measure | July 2024 | July 2025 | Change |
|---|---:|---:|---:|
| Merchandise sales before returns | $1,466,257.79 | $1,520,528.53 | +$54,270.74 / +3.70% |
| Sold units | 12,071 | 12,222 | +151 / +1.25% |
| Matching orders | 7,231 | 7,366 | +135 |

**Primary visual:** two aligned comparison panels, one for sales in USD and one for units. Separate units avoid a shared axis that conflates money and quantities. Both panels use the same two measured period rows.

**Interpretation:** Sales grew faster than units. Average realized selling price is a plausible next measured comparison; this table alone does not establish why customer behavior changed.

**Limitations:** Fictional synthetic retailer. This is a descriptive period comparison. Matching orders are orders containing selected Footwear lines, not all Web orders. Return deductions are excluded from this metric.

**Next question:** “Break down the Web Footwear sales change by category, keeping these dates.”

In the running app, bind headline values to actual evidence cells and use `analyze_result` or measured SQL for changes. The renderer supplies seven sections in order. This example's evidence fixture includes all underlying totals; arithmetic above is reproduced from those totals.

## 3. Follow-up retains intent

**Follow-up:** “Same for Mobile app.”

The agent should replace the channel filter while preserving Footwear, July dates, comparison dates and the before-returns metric basis. The measured outcome is:

| Measure | July 2024 | July 2025 |
|---|---:|---:|
| Merchandise sales before returns | $761,124.42 | $794,889.77 |
| Sold units | 6,308 | 6,423 |
| Matching orders | 3,711 | 3,764 |

A suitable headline is “Mobile app Footwear sales rose 4.44% to $794,889.77.” The answer must visibly confirm the retained dates and Footwear filter. A result for all Mobile app products is a scope failure even if its SQL is valid.

## 4. Investigation and correction

**Question:** “Did sold units decline for Web Footwear in July 2025 versus July 2024?”

Declare a hypothesis with statement “Sold units declined”, a prespecified criterion `units_change < 0`, and a query that returns that delta from the exact scoped current/comparison rows. The measured delta is **+151**; the criterion is **contradicted**.

**Desired response:**

> Sold units increased by 151, from 12,071 to 12,222. The declared “units declined” hypothesis is contradicted for this scope. This result checks the measured direction of change; it does not explain a causal mechanism.

The saved test should include statement, criterion, query, parameters, scope, observed value, verdict, hypothesis revision and test ID. If the user edits a previously supported statement into its opposite, preserve the node ID, invalidate the old conclusion, declare a fresh criterion and record a new test. The previous test remains in history.

**Bad output to reject:** “The decline is caused by lower demand.” There was no measured decline, and demand causality is not established by these observations.

## 5. Unavailable causal effect

**Question:** “How much incremental revenue did loyalty membership cause?”

**Desired response:**

> The available data cannot identify that causal effect. Membership was not randomized, and the dataset supplies no validated holdout or quasi-experimental design. I can compare member-associated and nonmember sales descriptively, but that difference is not incremental lift. A causal estimate would need an appropriate experiment or a defensible identification design with supporting data.

Attach the actual retrieved model/metric references. Do not invent a percentage, relabel descriptive differences as incrementality or run unrelated period totals to make the answer look more substantial.

## 6. Clarification and invalid entity

**Question:** “Show sales for the Enterprise Wholesale channel.”

If that channel is not in the warehouse, name the mismatch and show valid channel choices obtained from the complete reference lookup. Do not silently choose Web. A user decision is appropriate when the available labels do not identify the requested entity.

**Question:** “Show net sales.”

Use the documented/default basis and state it clearly, or clarify when context indicates conflicting business definitions. Do not ask for routine missing filters when documented defaults suffice. The proposed ontology UI should make ambiguous official definitions visible before runtime.

## 7. No-data and partial-output states

An empty result should show the exact scope and whether there are genuinely no matching rows, an unavailable observation or a query error that needs correction. A misspelled result alias is not a missing business fact. A truncated result cannot be summed to produce a headline total. A zero comparison denominator should display percentage change as unavailable rather than infinity or an invented zero.

If only a table is available, show it and explain the visual limitation. If a deadline leaves hypotheses untested, preserve the investigation and label unfinished branches. A saved partial answer must not claim the whole requested investigation is complete.

## Review rubric

| Check | Pass condition | Hard failure example |
|---|---|---|
| Question answered | Requested measures and comparisons are present | Offers to calculate requested totals after already finishing |
| Effective scope | Dates, filters and return basis match request/corrections | All-business substitution under a product filter |
| Numerical accuracy | Display values and derived changes match measured cells | Invented amount or cents treated as dollars |
| Grain/denominator | Correct order/customer/cohort/snapshot basis | Header fan-out; summed distinct buyers; immature repeat denominator |
| Evidence | Every material numerical claim maps to the relevant measured output | Valid reference ID attached to unrelated evidence |
| Source meaning | Historical examples and proposals are labeled as such | Repeats a sample as a fresh finding |
| Hypotheses | Criteria precede tests and narrative agrees with saved verdict | Model overrules a contradicted predicate |
| Causality | Claim strength matches available design | Correlation or accounting contribution called causal lift |
| Chart/table consistency | Same data, scope, units and missing-value meaning | Separate charts imply a comparison that was never queried |
| Readability | Clear headline, visible scope, usable evidence and specific caveats | Dense generic prose with buried result and repeated sections |
| Interaction | Useful next drill retains scope; edits mark results stale | Old answer presented as current after a scope change |

Deterministic checks should cover values, IDs, units, scopes and contract fields. Human or calibrated semantic review covers whether a claim is actually supported and whether the response is useful. A single high style score cannot compensate for a hard correctness failure.
