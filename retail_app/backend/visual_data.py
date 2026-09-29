"""Additional read-only evidence required by the playbooks' visual specifications.

The original recipes remain unchanged. These small aggregated datasets preserve
header, sale-line, return-cohort, and weekly-inventory grains independently.
"""
from datetime import date

MAX_ROWS = 5000


def _output(con, name, sql, parameters):
    cursor = con.execute(sql, parameters)
    columns = [column[0] for column in cursor.description]
    values = cursor.fetchmany(MAX_ROWS + 1)
    return {'name': name, 'sql': sql.strip(),
            'parameters': [str(value) if isinstance(value, date) else value for value in parameters],
            'rows': [dict(zip(columns, row)) for row in values[:MAX_ROWS]],
            'row_count': len(values), 'truncated': len(values) > MAX_ROWS}


def _periods(dates):
    return [dates[key] for key in ('start', 'end', 'compare_start', 'compare_end', 'start', 'end')]


SCORECARD = """
SELECT CASE WHEN s.calendar_date BETWEEN ? AND ? THEN 'current' ELSE 'comparison' END period,
 sum(s.realized_net_sales_cents) realized_sales_cents, sum(s.quantity) sold_units,
 sum(s.merchandise_margin_cents) merchandise_margin_cents,
 100.0 * sum(s.merchandise_margin_cents) / nullif(sum(s.realized_net_sales_cents),0) margin_rate_pct,
 sum(s.returned_units) returned_units,
 100.0 * sum(s.returned_units) / nullif(sum(s.quantity),0) unit_return_rate_pct,
 count(DISTINCT CASE WHEN s.customer_key > 0 THEN s.customer_key END) identified_buyers,
 count(DISTINCT s.transaction_key) orders
FROM v_sales_after_returns s
WHERE s.calendar_date BETWEEN ? AND ? OR s.calendar_date BETWEEN ? AND ?
GROUP BY 1 ORDER BY 1
"""


def _channel_sql(store=False):
    # Aggregate sale lines to the same period/entity grain as header metrics first.
    key = 'selling_store_key' if store else 'channel_key'
    dimension = 'dim_store c ON h.entity_key=c.store_key' if store else 'dim_channel c ON h.entity_key=c.channel_key'
    labels = 'c.store_name,c.store_format,c.region' if store else 'c.channel_name'
    return f"""
WITH h AS (
 SELECT h.{key} entity_key,
 sum(h.net_sales_cents) FILTER (WHERE d.calendar_date BETWEEN ? AND ?) current_sales_cents,
 sum(h.net_sales_cents) FILTER (WHERE d.calendar_date BETWEEN ? AND ?) comparison_sales_cents,
 count(*) FILTER (WHERE d.calendar_date BETWEEN ? AND ?) orders,
 sum(h.units) FILTER (WHERE d.calendar_date BETWEEN ? AND ?) sold_units
 FROM fact_transaction h JOIN dim_date d USING(date_key)
 WHERE (d.calendar_date BETWEEN ? AND ? OR d.calendar_date BETWEEN ? AND ?) AND h.{key}>0 GROUP BY 1
), l AS (
 SELECT s.{key} entity_key,sum(s.merchandise_margin_cents) merchandise_margin_cents,
 sum(s.realized_net_sales_cents) realized_sales_cents,sum(s.returned_units) returned_units
 FROM v_sales_after_returns s WHERE s.calendar_date BETWEEN ? AND ? GROUP BY 1
)
SELECT {labels},h.current_sales_cents,h.comparison_sales_cents,
 100.0*(h.current_sales_cents-h.comparison_sales_cents)/nullif(h.comparison_sales_cents,0) sales_growth_pct,
 l.merchandise_margin_cents,l.realized_sales_cents,
 100.0*l.merchandise_margin_cents/nullif(l.realized_sales_cents,0) margin_rate_pct,
 h.orders,1.0*h.current_sales_cents/nullif(h.orders,0) aov_before_returns_cents,
 h.sold_units,l.returned_units,100.0*l.returned_units/nullif(h.sold_units,0) unit_return_rate_pct
FROM h LEFT JOIN l USING(entity_key) JOIN {dimension}
ORDER BY h.current_sales_cents DESC
"""

PROMOTION = """
WITH campaign AS (
 SELECT p.promotion_key,p.promotion_name,p.valid_from,p.valid_to,p.loyalty_only,
 p.channel_key,di.division_name,
 CASE WHEN p.channel_key=0 THEN 'All channels' ELSE c.channel_name END channel_name
 FROM dim_promotion p JOIN dim_division di USING(division_key)
 LEFT JOIN dim_channel c USING(channel_key) WHERE p.promotion_key=?
), weekly AS (
 SELECT CAST(date_trunc('week',s.calendar_date+INTERVAL 1 DAY)-INTERVAL 1 DAY AS DATE) week_start,
 sum(s.net_sales_cents) scope_sales_before_returns_cents,sum(s.quantity) scope_units,
 sum(CASE WHEN s.promotion_key=p.promotion_key THEN s.quantity ELSE 0 END) redeemed_units,
 sum(CASE WHEN s.promotion_key=p.promotion_key THEN s.promotion_discount_cents ELSE 0 END) promotion_discount_cents,
 sum(CASE WHEN s.promotion_key=p.promotion_key THEN s.merchandise_margin_cents ELSE 0 END) associated_cohort_merchandise_margin_cents
 FROM v_sales_after_returns s CROSS JOIN campaign p
 WHERE s.calendar_date BETWEEN ? AND ? AND s.division_name=p.division_name
 AND (p.channel_key=0 OR s.channel_key=p.channel_key)
 GROUP BY 1
)
SELECT w.*,p.promotion_key,p.promotion_name,p.valid_from,p.valid_to,p.division_name,p.channel_name,p.loyalty_only,
 (w.week_start<=p.valid_to AND w.week_start+INTERVAL 6 DAY>=p.valid_from) overlaps_campaign,
 (w.week_start<? OR w.week_start+INTERVAL 6 DAY>?) partial_week
FROM weekly w CROSS JOIN campaign p ORDER BY w.week_start
"""

LOYALTY = """
SELECT CAST(date_trunc('month',d.calendar_date) AS DATE) AS "month",
 CASE WHEN h.loyalty_key>0 THEN 'attached' ELSE 'not attached' END loyalty_usage,
 count(*) orders,sum(h.net_sales_cents) sales_before_returns_cents,sum(h.units) sold_units
FROM fact_transaction h JOIN dim_date d USING(date_key)
WHERE d.calendar_date BETWEEN ? AND ? GROUP BY 1,2 ORDER BY 1,2
"""

RETURN_COHORT = """
WITH sales AS (
 SELECT l.sales_line_key,d.calendar_date,l.quantity
 FROM fact_sales_line l JOIN dim_date d USING(date_key) WHERE d.calendar_date BETWEEN ? AND ?
), cohorts AS (
 SELECT CAST(date_trunc('month',calendar_date) AS DATE) sale_month,
 sum(quantity) original_units,max(calendar_date) latest_sale_date FROM sales GROUP BY 1
), observed AS (
 SELECT CAST(date_trunc('month',s.calendar_date) AS DATE) sale_month,
 CASE WHEN date_diff('day',s.calendar_date,d.calendar_date)<=30 THEN '0–30 days' ELSE '31–60 days' END elapsed_day_bin,
 sum(r.returned_quantity) returned_units
 FROM sales s JOIN fact_return_line r USING(sales_line_key) JOIN dim_date d ON r.return_date_key=d.date_key
 GROUP BY 1,2
), bins AS (SELECT * FROM (VALUES ('0–30 days'),('31–60 days')) t(elapsed_day_bin)),
 coverage AS (SELECT max(calendar_date) observed_through FROM dim_date)
SELECT c.sale_month,b.elapsed_day_bin,coalesce(o.returned_units,0) returned_units,c.original_units,
 100.0*coalesce(o.returned_units,0)/nullif(c.original_units,0) return_rate_pct,
 c.latest_sale_date,x.observed_through,(c.latest_sale_date+INTERVAL 60 DAY<=x.observed_through) fully_mature_60d
FROM cohorts c CROSS JOIN bins b CROSS JOIN coverage x
LEFT JOIN observed o ON o.sale_month=c.sale_month AND o.elapsed_day_bin=b.elapsed_day_bin
ORDER BY 1,2
"""

RETURN_REASONS = """
SELECT rr.return_reason,sum(r.returned_quantity) returned_units,
 sum(r.refund_net_cents) refund_merchandise_cents,
 100.0*sum(r.returned_quantity)/nullif(sum(sum(r.returned_quantity)) OVER (),0) returned_unit_share_pct
FROM fact_return_line r JOIN fact_sales_line l USING(sales_line_key)
JOIN dim_date d ON l.date_key=d.date_key JOIN dim_return_reason rr USING(return_reason_key)
WHERE d.calendar_date BETWEEN ? AND ? GROUP BY 1 ORDER BY returned_units DESC
"""

INVENTORY = """
SELECT ds.calendar_date week_start,de.calendar_date week_end,
 sum(i.opening_on_hand_units) opening_units,sum(i.receipt_units) receipt_units,
 sum(i.restocked_units) restocked_units,sum(i.sold_units) sold_units,
 sum(i.shrink_units) shrink_units,sum(i.closing_on_hand_units) closing_units,
 sum(i.available_units) available_units
FROM fact_inventory_weekly i JOIN dim_date ds ON i.week_start_date_key=ds.date_key
JOIN dim_date de ON i.week_end_date_key=de.date_key
WHERE ds.calendar_date>=? AND de.calendar_date<=? GROUP BY 1,2 ORDER BY 1
"""

FULFILLMENT_MONTH = """
SELECT CAST(date_trunc('month',d.calendar_date) AS DATE) AS "month",f.fulfillment_method,
 count(*) orders,sum(h.units) sold_units,sum(h.net_sales_cents) sales_before_returns_cents
FROM fact_transaction h JOIN dim_date d USING(date_key) JOIN dim_fulfillment_method f USING(fulfillment_method_key)
WHERE d.calendar_date BETWEEN ? AND ? GROUP BY 1,2 ORDER BY 1,2
"""

FULFILLMENT_OUTCOMES = """
WITH heads AS (
 SELECT h.fulfillment_method_key,count(*) orders,sum(h.net_sales_cents) sales_before_returns_cents,
 sum(h.units) sold_units FROM fact_transaction h JOIN dim_date d USING(date_key)
 WHERE d.calendar_date BETWEEN ? AND ? GROUP BY 1
), lines AS (
 SELECT s.fulfillment_method_key,sum(s.returned_units) returned_units,
 sum(s.realized_net_sales_cents) realized_sales_cents,sum(s.merchandise_margin_cents) merchandise_margin_cents
 FROM v_sales_after_returns s WHERE s.calendar_date BETWEEN ? AND ? GROUP BY 1
)
SELECT f.fulfillment_method,h.orders,h.sold_units,h.sales_before_returns_cents,
 1.0*h.sales_before_returns_cents/nullif(h.orders,0) aov_before_returns_cents,
 l.returned_units,l.realized_sales_cents,l.merchandise_margin_cents,
 100.0*l.merchandise_margin_cents/nullif(l.realized_sales_cents,0) margin_rate_pct,
 100.0*l.returned_units/nullif(h.sold_units,0) unit_return_rate_pct
FROM heads h JOIN lines l USING(fulfillment_method_key) JOIN dim_fulfillment_method f USING(fulfillment_method_key)
ORDER BY h.orders DESC
"""

SEGMENTS = """
WITH customers AS (
 SELECT h.customer_key,max(d.calendar_date) last_date,count(*) orders,
 sum(h.net_sales_cents) sales_cents,sum(h.gross_sales_cents) gross_sales_cents,
 sum(h.markdown_cents+h.promotion_discount_cents) discount_cents
 FROM fact_transaction h JOIN dim_date d USING(date_key)
 WHERE h.customer_key>0 AND d.calendar_date BETWEEN ? AND ? GROUP BY 1
), labels AS (
 SELECT *,date_diff('day',last_date,?) recency_days,
 CASE WHEN orders>=3 AND date_diff('day',last_date,?)<=90 THEN 'active frequent'
 WHEN orders>=3 THEN 'frequent lapsed'
 WHEN date_diff('day',last_date,?)<=90 THEN 'active occasional' ELSE 'occasional lapsed' END segment
 FROM customers
), lines AS (
 SELECT s.customer_key,sum(s.merchandise_margin_cents) merchandise_margin_cents,
 sum(s.quantity) sold_units,sum(s.returned_units) returned_units,
 count(DISTINCT s.category_name) category_breadth
 FROM v_sales_after_returns s WHERE s.customer_key>0 AND s.calendar_date BETWEEN ? AND ? GROUP BY 1
)
SELECT c.segment,count(*) identified_buyers,avg(c.recency_days) avg_recency_days,
 avg(c.orders) orders_per_buyer,avg(c.sales_cents) sales_per_buyer_cents,
 avg(l.merchandise_margin_cents) margin_per_buyer_cents,avg(l.category_breadth) categories_per_buyer,
 100.0*sum(c.discount_cents)/nullif(sum(c.gross_sales_cents),0) discount_share_pct,
 100.0*sum(l.returned_units)/nullif(sum(l.sold_units),0) unit_return_rate_pct,
 sum(c.sales_cents) sales_cents,sum(l.merchandise_margin_cents) merchandise_margin_cents,
 sum(c.orders) orders,sum(l.sold_units) sold_units,sum(l.returned_units) returned_units,
 sum(c.discount_cents) discount_cents,sum(c.gross_sales_cents) gross_sales_cents
FROM labels c JOIN lines l USING(customer_key) GROUP BY 1 ORDER BY sales_cents DESC
"""

LAPSE = """
WITH months AS (
 SELECT CAST(date_trunc('month',calendar_date) AS DATE) AS "month",max(calendar_date) observation_date
 FROM dim_date WHERE calendar_date BETWEEN ? AND ? GROUP BY 1
), orders AS (
 SELECT h.customer_key,h.transaction_key,d.calendar_date,
 lag(d.calendar_date) OVER (PARTITION BY h.customer_key ORDER BY d.calendar_date,h.transaction_key) previous_order_date
 FROM fact_transaction h JOIN dim_date d USING(date_key)
 WHERE h.customer_key>0 AND d.calendar_date<=?
), reactivated AS (
 SELECT DISTINCT customer_key,CAST(date_trunc('month',calendar_date) AS DATE) AS "month"
 FROM orders WHERE date_diff('day',previous_order_date,calendar_date)>90
), history AS (
 SELECT m.month,m.observation_date,o.customer_key,max(o.calendar_date) last_order_date
 FROM months m JOIN orders o ON o.calendar_date<=m.observation_date GROUP BY 1,2,3
)
SELECT h.month,h.observation_date,
 count(*) FILTER (WHERE date_diff('day',h.last_order_date,h.observation_date)<=90 AND r.customer_key IS NULL) active_buyers,
 count(*) FILTER (WHERE date_diff('day',h.last_order_date,h.observation_date)>90) lapsed_buyers,
 count(*) FILTER (WHERE r.customer_key IS NOT NULL) reactivated_buyers,
 count(*) identified_buyers,90 lapse_threshold_days
FROM history h LEFT JOIN reactivated r ON h.customer_key=r.customer_key AND h.month=r.month
GROUP BY 1,2 ORDER BY 1
"""

PRICING = """
WITH prices AS (
 SELECT s.division_name,'actual' price_basis,s.selling_unit_price_cents unit_price_cents,s.quantity
 FROM v_sales s WHERE s.calendar_date BETWEEN ? AND ?
 UNION ALL
 SELECT s.division_name,'regular' price_basis,s.regular_unit_price_cents unit_price_cents,s.quantity
 FROM v_sales s WHERE s.calendar_date BETWEEN ? AND ?
)
SELECT division_name,price_basis,CAST(floor(unit_price_cents/1000.0)*10 AS INTEGER) usd_bucket_start,
 10 bin_width_usd,sum(quantity) units FROM prices GROUP BY 1,2,3 ORDER BY 1,2,3
"""


def attach_visual_outputs(con, slug, dates, outputs):
    """Append chart evidence without mutating the supplied recipe output list."""
    result = list(outputs)
    current = [dates['start'], dates['end']]
    additions = []
    if slug == 'scorecard':
        additions.append(('scorecard_summary', SCORECARD, _periods(dates)))
    elif slug == 'channels':
        comparison = [dates['compare_start'], dates['compare_end']]
        parameters = current + comparison + current + current + comparison + current + current
        additions.extend([('channels_growth_margin', _channel_sql(), parameters),
                          ('stores_growth_margin', _channel_sql(store=True), parameters)])
    elif slug == 'promotions':
        campaigns = next((o['rows'] for o in outputs if o['name'] == 'campaign_associated_sales'), [])
        if campaigns:
            additions.append(('promotion_timeline', PROMOTION, [campaigns[0]['promotion_key']] + current + current))
    elif slug == 'loyalty':
        additions.append(('loyalty_monthly_mix', LOYALTY, current))
    elif slug == 'returns':
        additions.extend([('return_cohort_elapsed', RETURN_COHORT, current),
                          ('cohort_return_reasons', RETURN_REASONS, current)])
    elif slug == 'inventory':
        additions.append(('inventory_weekly', INVENTORY, current))
    elif slug == 'fulfillment':
        additions.extend([('fulfillment_monthly_mix', FULFILLMENT_MONTH, current),
                          ('fulfillment_outcome_metrics', FULFILLMENT_OUTCOMES, current + current)])
    elif slug == 'segments':
        additions.append(('segment_profiles', SEGMENTS, current + [dates['end']] * 3 + current))
    elif slug == 'lapse':
        additions.append(('lapse_monthly_states', LAPSE, current + [dates['end']]))
    elif slug == 'pricing':
        additions.append(('pricing_distribution', PRICING, current + current))
    existing = {o['name'] for o in result}
    result.extend(_output(con, name, sql, parameters) for name, sql, parameters in additions if name not in existing)
    return result
