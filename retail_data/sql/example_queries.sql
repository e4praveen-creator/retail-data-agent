-- 1. Calendar-month revenue, returns recognized on return date (USD).
SELECT d.calendar_year,d.calendar_month,
 round(sum(a.merchandise_revenue_cents)/100.0,2) net_revenue_usd
FROM v_merchandise_activity a JOIN dim_date d USING(date_key)
GROUP BY 1,2 ORDER BY 1,2;

-- 2. Sales-cohort division margin after every observed return through March 1, 2026.
SELECT division_name,round(sum(realized_net_sales_cents)/100.0,2) revenue_usd,
 round(sum(merchandise_margin_cents)/100.0,2) merchandise_margin_usd
FROM v_sales_after_returns GROUP BY 1 ORDER BY 2 DESC;

-- 3. Average order value from headers, never from joined lines. Excludes returns/tax/shipping.
SELECT c.channel_name,count(*) orders,round(avg(h.net_sales_cents)/100.0,2) aov_usd
FROM fact_transaction h JOIN dim_channel c USING(channel_key) GROUP BY 1;

-- 4. Identified-customer repeat purchase rate. Anonymous key 0 is not a person.
WITH frequency AS (SELECT customer_key,count(*) n FROM fact_transaction
 WHERE customer_key>0 GROUP BY 1)
SELECT count(*) purchasing_customers,avg(CASE WHEN n>1 THEN 1.0 ELSE 0 END) repeat_rate FROM frequency;

-- 5. Unit return rates for original sales cohorts, by channel and division.
SELECT c.channel_name,s.division_name,sum(s.returned_units)::DOUBLE/sum(s.quantity) unit_return_rate
FROM v_sales_after_returns s JOIN dim_channel c USING(channel_key) GROUP BY 1,2;

-- 6. Inventory on one snapshot date. Never sum closing inventory across weeks.
SELECT p.division_name,sum(i.closing_on_hand_units) on_hand,sum(i.available_units) available
FROM fact_inventory_weekly i JOIN v_product p USING(sku_key)
WHERE i.week_end_date_key=20251228 GROUP BY 1;

-- 7. Inventory turnover: net COGS / average weekly inventory valued at static cost.
WITH inventory AS (
 SELECT i.week_end_date_key,sum(i.closing_on_hand_units*s.unit_cost_cents) inventory_cost
 FROM fact_inventory_weekly i JOIN dim_sku s USING(sku_key)
 WHERE week_end_date_key BETWEEN 20250101 AND 20251231 GROUP BY 1),
 cogs AS (SELECT sum(net_cost_of_goods_cents) c FROM v_sales_after_returns WHERE calendar_year=2025)
SELECT c/(SELECT avg(inventory_cost) FROM inventory) annual_turnover_cohort_basis FROM cogs;

-- 8. Promotion-associated sales, NOT causal incrementality.
SELECT p.promotion_name,count(*) lines,sum(l.quantity) units,
 round(sum(l.net_sales_cents)/100.0,2) promoted_revenue_usd
FROM fact_sales_line l JOIN dim_promotion p USING(promotion_key)
WHERE l.promotion_key>0 GROUP BY 1 ORDER BY 4 DESC LIMIT 20;

-- 9. Ordering channel versus physical fulfillment source.
SELECT c.channel_name,f.fulfillment_method,loc.location_type,sum(l.quantity) units
FROM fact_sales_line l JOIN fact_transaction h USING(transaction_key)
JOIN dim_channel c USING(channel_key) JOIN dim_fulfillment_method f USING(fulfillment_method_key)
JOIN dim_location loc ON loc.location_key=l.fulfillment_location_key GROUP BY 1,2,3;

-- 10. Retail-week comparable sales: only weeks with seven covered days in BOTH years.
-- Week 53 is excluded; no restatement is applied.
WITH complete_weeks AS (
 SELECT retail_year,retail_week FROM dim_date
 WHERE calendar_date BETWEEN DATE '2024-01-01' AND DATE '2025-12-31'
 AND retail_year IN (2024,2025) AND retail_week<=52
 GROUP BY 1,2 HAVING count(*)=7
), common_weeks AS (
 SELECT retail_week FROM complete_weeks GROUP BY 1 HAVING count(DISTINCT retail_year)=2
)
SELECT d.retail_week,
 sum(CASE WHEN d.retail_year=2024 THEN l.net_sales_cents ELSE 0 END)/100.0 sales_2024,
 sum(CASE WHEN d.retail_year=2025 THEN l.net_sales_cents ELSE 0 END)/100.0 sales_2025
FROM fact_sales_line l JOIN dim_date d USING(date_key)
JOIN common_weeks w USING(retail_week)
WHERE d.retail_year IN (2024,2025)
GROUP BY 1 ORDER BY 1;
