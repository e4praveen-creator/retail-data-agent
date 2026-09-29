"""Summit Field-specific hypothesis tests, grounded in existing synthetic fields."""
from .data import select_sql, run_playbook, clean

QUERIES={
 'q4-markdown':'''SELECT s.calendar_year,s.calendar_month,sum(s.quantity) sold_units,
 sum(s.gross_sales_cents) regular_sales_cents,sum(s.markdown_cents) markdown_cents,
 100.0*sum(s.markdown_cents)/nullif(sum(s.gross_sales_cents),0) markdown_pct
 FROM v_sales s WHERE s.calendar_date BETWEEN ? AND ? GROUP BY 1,2 ORDER BY 1,2''',
 'app-price-book':'''SELECT c.channel_name,count(*) price_intervals,avg(p.regular_unit_price_cents) average_regular_price_cents
 FROM fact_price_history p JOIN dim_channel c USING(channel_key)
 WHERE p.valid_from<=? AND p.valid_to>=? GROUP BY 1 ORDER BY 1''',
 'digital-softgoods-returns':'''SELECT s.division_name,c.channel_name,sum(s.quantity) original_units,
 sum(s.returned_units) returned_units,100.0*sum(s.returned_units)/nullif(sum(s.quantity),0) unit_return_rate_pct,
 sum(s.refund_net_cents) refund_cents FROM v_sales_after_returns s JOIN dim_channel c USING(channel_key)
 WHERE s.calendar_date BETWEEN ? AND ? AND s.division_name IN ('Apparel','Footwear') GROUP BY 1,2 ORDER BY 1,2''',
 'damaged-recovery':'''SELECT rr.return_reason,sum(r.returned_quantity) returned_units,
 sum(r.refund_net_cents) refunded_sales_cents,sum(r.recovered_cost_cents) recovered_cost_cents
 FROM fact_return_line r JOIN dim_return_reason rr USING(return_reason_key)
 JOIN fact_sales_line s USING(sales_line_key) JOIN dim_date d ON s.date_key=d.date_key
 WHERE d.calendar_date BETWEEN ? AND ? GROUP BY 1 ORDER BY 1''',
 'anonymous-orders':'''SELECT CASE WHEN h.customer_key=0 THEN 'Anonymous key 0' ELSE 'Identified customer' END identification,
 count(*) orders,sum(h.units) sold_units,sum(h.net_sales_cents) sales_before_returns_cents,
 count(DISTINCT CASE WHEN h.customer_key>0 THEN h.customer_key END) identified_buyers
 FROM fact_transaction h JOIN dim_date d USING(date_key) WHERE d.calendar_date BETWEEN ? AND ? GROUP BY 1''',
 'seasonal-divisions':'''SELECT s.calendar_year,s.calendar_month,s.division_name,sum(s.quantity) sold_units,
 sum(s.net_sales_cents) sales_before_returns_cents
 FROM v_sales s WHERE s.calendar_date BETWEEN ? AND ? GROUP BY 1,2,3 ORDER BY 1,2,3''',
 'private-label-mix':'''SELECT CASE WHEN p.is_private_label THEN 'Private label' ELSE 'Other brands' END brand_type,
 sum(s.quantity) units,sum(s.net_sales_cents) sales_before_returns_cents,
 sum(s.realized_net_sales_cents) cohort_realized_sales_cents,sum(s.merchandise_margin_cents) cohort_margin_cents,
 sum(s.returned_units) returned_units FROM v_sales_after_returns s JOIN v_product p USING(sku_key)
 WHERE s.calendar_date BETWEEN ? AND ? GROUP BY 1''',
 'promotion-eligibility':'''SELECT p.loyalty_only,c.channel_name,count(*) redeemed_lines,sum(s.quantity) redeemed_units,
 sum(s.net_sales_cents) associated_sales_before_returns_cents,sum(s.promotion_discount_cents) discount_cents
 FROM v_sales s JOIN dim_promotion p USING(promotion_key) JOIN dim_channel c ON s.channel_key=c.channel_key
 WHERE s.calendar_date BETWEEN ? AND ? AND s.promotion_key>0 GROUP BY 1,2 ORDER BY 1,2''',
 'weekend-concentration':'''SELECT d.is_weekend,count(DISTINCT d.calendar_date) observed_days,count(*) orders,
 sum(h.net_sales_cents) sales_before_returns_cents,1.0*count(*)/nullif(count(DISTINCT d.calendar_date),0) orders_per_observed_day
 FROM fact_transaction h JOIN dim_date d USING(date_key) WHERE d.calendar_date BETWEEN ? AND ? GROUP BY 1''',
}

def execute_hypothesis(identity,dates):
    from .analytics import BANK
    item=next((h for h in BANK if h['id']==identity),None)
    if not item:raise ValueError('Unknown retail hypothesis.')
    if item.get('test_recipe') in QUERIES:
        recipe=item['test_recipe'];values=[dates['end'],dates['start']] if recipe=='app-price-book' else [dates['start'],dates['end']]
        output=select_sql(QUERIES[recipe],values,500)
        output['name']=recipe.replace('-','_')
        report={'slug':'hypothesis','title':item['hypothesis'],'summary':'Measured evidence for: '+item['hypothesis'],'outputs':[output],
          'period':clean(dates),'scope':item['scope'],'basis':item['metric_basis'],'warnings':[item['limitation'],'Candidate hypothesis: assess the measured result against the falsifier before marking it supported.'],
          'checks':[{'name':'Named read-only test executed on the actual warehouse','passed':True}], 'sources':item['required_tables']}
    else:
        report=run_playbook(item['test_recipe'],dates)
    return {'hypothesis':item,'report':report,'status':'evidence_collected_not_automatically_confirmed'}
