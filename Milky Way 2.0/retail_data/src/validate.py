"""Executable warehouse contract. Reports violations; exits nonzero on any failure."""
import argparse
import json
from pathlib import Path
import duckdb
from catalog import TABLES


def validate(c, expected_headers, stores):
    checks=[]
    def zero(name,sql):
        n=c.execute(sql).fetchone()[0]
        checks.append({'check':name,'violations':int(n),'passed':n==0})
    for table,spec in TABLES.items():
        pk=','.join(spec['pk'])
        zero(f'{table}: primary key uniqueness',f'SELECT count(*) FROM (SELECT {pk} FROM {table} GROUP BY {pk} HAVING count(*)>1)')
        cols=[r[0] for r in c.execute(f'DESCRIBE {table}').fetchall() if r[0] not in ('registered_date','enrollment_date')]
        zero(f'{table}: required columns',f'SELECT count(*) FROM {table} WHERE '+' OR '.join(f'{col} IS NULL' for col in cols))
        for col,target in spec.get('fk',{}).items():
            parent,key=target.split('.')
            zero(f'{table}.{col}: foreign key',f'SELECT count(*) FROM {table} t ANTI JOIN {parent} p ON t.{col}=p.{key}')
    zero('exact transaction headers',f'SELECT abs(count(*)-{expected_headers}) FROM fact_transaction')
    zero('sales line positions',"SELECT count(*) FROM (SELECT transaction_key FROM fact_sales_line GROUP BY 1 HAVING min(line_number)<>1 OR max(line_number)<>count(*) OR count(DISTINCT line_number)<>count(*))")
    zero('header versus line reconciliation',"""SELECT count(*) FROM fact_transaction h LEFT JOIN
        (SELECT transaction_key,count(*) line_count,sum(quantity) units,sum(net_sales_cents) net_sales_cents,sum(gross_sales_cents) gross_sales_cents,sum(markdown_cents) markdown_cents,sum(promotion_discount_cents) promotion_discount_cents,sum(tax_cents) tax_cents,sum(cost_of_goods_cents) cost_of_goods_cents FROM fact_sales_line GROUP BY 1) l USING(transaction_key)
        WHERE l.transaction_key IS NULL OR h.line_count<>l.line_count OR h.units<>l.units OR h.net_sales_cents<>l.net_sales_cents OR h.gross_sales_cents<>l.gross_sales_cents OR h.markdown_cents<>l.markdown_cents OR h.promotion_discount_cents<>l.promotion_discount_cents OR h.tax_cents<>l.tax_cents OR h.cost_of_goods_cents<>l.cost_of_goods_cents""")
    zero('sale arithmetic and positivity',"""SELECT count(*) FROM fact_sales_line WHERE quantity<1 OR quantity>2 OR selling_unit_price_cents<0 OR promotion_discount_cents<0 OR markdown_cents<0 OR unit_cost_cents<0 OR gross_sales_cents<>quantity*regular_unit_price_cents OR net_sales_cents<>quantity*selling_unit_price_cents OR gross_sales_cents-markdown_cents-promotion_discount_cents<>net_sales_cents OR cost_of_goods_cents<>quantity*unit_cost_cents OR tax_cents<>quantity*round(selling_unit_price_cents*0.07)""")
    zero('header totals and shipping',"""SELECT count(*) FROM fact_transaction WHERE total_paid_cents<>net_sales_cents+tax_cents+shipping_cents OR shipping_cents<>CASE WHEN fulfillment_method_key IN (3,4) AND net_sales_cents<7500 THEN 599 ELSE 0 END""")
    zero('sale/header dates and local timestamps',"SELECT count(*) FROM fact_sales_line l JOIN fact_transaction h USING(transaction_key) WHERE l.date_key<>h.date_key OR strftime(h.transaction_local_timestamp,'%Y%m%d')::INTEGER<>h.date_key OR hour(h.transaction_local_timestamp)*60+minute(h.transaction_local_timestamp)<>h.time_key")
    zero('loyalty ownership',"SELECT count(*) FROM fact_transaction h JOIN dim_loyalty l USING(loyalty_key) WHERE h.loyalty_key<>0 AND h.customer_key<>l.customer_key")
    zero('customer and loyalty active before sale',"SELECT count(*) FROM fact_transaction h JOIN dim_customer c USING(customer_key) JOIN dim_loyalty l USING(loyalty_key) JOIN dim_date d USING(date_key) WHERE (h.customer_key>0 AND c.registered_date>d.calendar_date) OR (h.loyalty_key>0 AND l.enrollment_date>d.calendar_date)")
    zero('fulfillment and channel consistency',"""SELECT count(*) FROM fact_sales_line l JOIN fact_transaction h USING(transaction_key) JOIN dim_location loc ON l.fulfillment_location_key=loc.location_key
        WHERE (h.channel_key=1 AND (h.selling_store_key=0 OR h.fulfillment_method_key<>1 OR loc.store_key<>h.selling_store_key)) OR (h.channel_key>1 AND (h.selling_store_key<>0 OR h.fulfillment_method_key=1)) OR (h.fulfillment_method_key=3 AND loc.location_type<>'DC') OR (h.fulfillment_method_key IN (1,2,4) AND loc.location_type<>'STORE')""")
    zero('price validity and SKU/channel alignment',"SELECT count(*) FROM fact_sales_line l JOIN fact_price_history p USING(price_key) JOIN fact_transaction h USING(transaction_key) JOIN dim_date d ON d.date_key=l.date_key WHERE l.sku_key<>p.sku_key OR h.channel_key<>p.channel_key OR d.calendar_date NOT BETWEEN p.valid_from AND p.valid_to OR l.regular_unit_price_cents<>p.regular_unit_price_cents OR l.markdown_cents<>l.quantity*round(p.regular_unit_price_cents*p.markdown_pct/100.0)")
    zero('price periods continuous and nonoverlapping',"SELECT count(*) FROM (SELECT *,lag(valid_to) OVER(PARTITION BY sku_key,channel_key ORDER BY valid_from) previous_value FROM fact_price_history) WHERE valid_to<valid_from OR (previous_value IS NOT NULL AND valid_from<>previous_value+1)")
    zero('price coverage',"SELECT count(*) FROM (SELECT sku_key,channel_key FROM fact_price_history GROUP BY 1,2 HAVING count(*)<>8 OR min(valid_from)<>DATE '2024-01-01' OR max(valid_to)<>DATE '2025-12-31')")
    zero('promotion eligibility and amount',"""SELECT count(*) FROM fact_sales_line l JOIN dim_promotion p USING(promotion_key) JOIN fact_transaction h USING(transaction_key) JOIN dim_date d ON d.date_key=l.date_key JOIN v_product s USING(sku_key)
        WHERE (l.promotion_key>0 AND (d.calendar_date NOT BETWEEN p.valid_from AND p.valid_to OR (p.channel_key<>0 AND p.channel_key<>h.channel_key) OR (p.loyalty_only AND h.loyalty_key=0) OR p.division_key<>s.division_key))
        OR l.promotion_discount_cents<>l.quantity*round((l.regular_unit_price_cents-l.markdown_cents/l.quantity)*p.discount_pct/100.0)""")
    zero('return linkage, limits and refunds',"""SELECT count(*) FROM fact_return_line r JOIN fact_sales_line l USING(sales_line_key) JOIN dim_date rd ON rd.date_key=r.return_date_key JOIN dim_date sd ON sd.date_key=l.date_key
        WHERE r.transaction_key<>l.transaction_key OR r.sku_key<>l.sku_key OR rd.calendar_date<=sd.calendar_date OR rd.calendar_date>sd.calendar_date+60 OR rd.calendar_date<l.promised_delivery_date OR r.returned_quantity<1 OR r.returned_quantity>l.quantity
        OR r.refund_net_cents<>r.returned_quantity*l.selling_unit_price_cents OR r.refund_tax_cents<>r.returned_quantity*round(l.selling_unit_price_cents*0.07) OR r.refund_total_cents<>r.refund_net_cents+r.refund_tax_cents OR r.recovered_cost_cents<>CASE WHEN r.is_restockable THEN l.unit_cost_cents*r.returned_quantity ELSE 0 END""")
    zero('total returns bounded by original sale',"SELECT count(*) FROM (SELECT sales_line_key,sum(returned_quantity) q,sum(refund_net_cents) amount FROM fact_return_line GROUP BY 1) r JOIN fact_sales_line l USING(sales_line_key) WHERE r.q>l.quantity OR r.amount>l.net_sales_cents")
    zero('inventory balance and nonnegative stock',"SELECT count(*) FROM fact_inventory_weekly WHERE closing_on_hand_units<>opening_on_hand_units+receipt_units+restocked_units-sold_units-shrink_units OR available_units<>closing_on_hand_units-reserved_units OR least(opening_on_hand_units,receipt_units,restocked_units,sold_units,shrink_units,closing_on_hand_units,reserved_units,available_units,in_transit_units)<0")
    zero('inventory continuity',"SELECT count(*) FROM (SELECT *,lag(closing_on_hand_units) OVER(PARTITION BY location_key,sku_key ORDER BY inventory_week_index) previous_value FROM fact_inventory_weekly) WHERE previous_value IS NOT NULL AND opening_on_hand_units<>previous_value")
    zero('inventory complete coverage',f"SELECT abs(count(*)-(SELECT count(DISTINCT inventory_week_index) FROM fact_inventory_weekly)*{stores+2}*2400) FROM fact_inventory_weekly")
    zero('inventory sales reconciliation',"""SELECT count(*) FROM (SELECT d.day_index//7 w,l.fulfillment_location_key location_key,l.sku_key,sum(quantity) q FROM fact_sales_line l JOIN dim_date d USING(date_key) GROUP BY 1,2,3) a
        FULL OUTER JOIN fact_inventory_weekly i ON i.inventory_week_index=a.w AND i.location_key=a.location_key AND i.sku_key=a.sku_key WHERE coalesce(a.q,0)<>coalesce(i.sold_units,0)""")
    zero('inventory return reconciliation',"""SELECT count(*) FROM (SELECT d.day_index//7 w,r.return_location_key location_key,r.sku_key,sum(returned_quantity) q FROM fact_return_line r JOIN dim_date d ON d.date_key=r.return_date_key WHERE is_restockable GROUP BY 1,2,3) a
        FULL OUTER JOIN fact_inventory_weekly i ON i.inventory_week_index=a.w AND i.location_key=a.location_key AND i.sku_key=a.sku_key WHERE coalesce(a.q,0)<>coalesce(i.restocked_units,0)""")
    zero('calendar continuous through return tail',"SELECT abs(count(*)-791)+abs(count(DISTINCT calendar_date)-791) FROM dim_date")
    return {'passed':all(x['passed'] for x in checks),'check_count':len(checks),'checks':checks}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data',type=Path,default=Path('data/full'))
    a=p.parse_args()
    manifest=json.loads((a.data/'manifest.json').read_text())
    c=duckdb.connect(str(a.data/'retail.duckdb'),read_only=True)
    c.execute("SET memory_limit='3GB'")
    c.execute('SET threads=4')
    report=validate(c,manifest['transaction_headers'],manifest['stores'])
    print(json.dumps(report,indent=2))
    raise SystemExit(0 if report['passed'] else 1)
