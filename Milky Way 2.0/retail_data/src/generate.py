"""Deterministic synthetic retail warehouse. No downloads or personal data at runtime."""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import time
from pathlib import Path
import duckdb
from catalog import TABLES, describe_column
from validate import validate

VERSION = '1.0.0'
START = dt.date(2024, 1, 1)
END = dt.date(2025, 12, 31)
AS_OF = END + dt.timedelta(days=60)


def sqlstr(value):
    return "'" + str(value).replace("'", "''") + "'"


def fiscal_start(year):
    feb = dt.date(year, 2, 1)
    return feb + dt.timedelta(days=min(range(-3, 4), key=lambda n: abs(n) if (feb + dt.timedelta(days=n)).weekday() == 6 else 99))


def generate(out: Path, headers: int, seed: int, stores: int, customers: int, memory: str, threads: int):
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f'{out} is not empty. Choose a new --output directory; existing data is never overwritten.')
    out.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    con = duckdb.connect(str(out / 'retail.duckdb'))
    con.execute(f"SET memory_limit={sqlstr(memory)}")
    con.execute(f'SET threads={threads}')
    con.execute(f"SET temp_directory={sqlstr(out / '_spill')}")
    con.execute('SET preserve_insertion_order=false')
    con.execute(f'CREATE MACRO rnd(id, salt, n) AS (hash({seed}::BIGINT, id::BIGINT, salt::VARCHAR) % n)::BIGINT')
    def table(name, query):
        print(f'Building {name}', flush=True)
        con.execute(f'CREATE TABLE {name} AS {query}')
    def values(name, ddl, rows):
        con.execute(f'CREATE TABLE {name} ({ddl})')
        con.executemany(f'INSERT INTO {name} VALUES ({",".join("?" for _ in rows[0])})', rows)

    dates = []
    periods = [4,5,4]*4
    for offset in range((AS_OF-START).days+1):
        d = START + dt.timedelta(days=offset)
        fy = d.year if d >= fiscal_start(d.year) else d.year-1
        fw = (d-fiscal_start(fy)).days//7+1
        acc = 0
        fp = 12
        for p,w in enumerate(periods,1):
            acc += w
            if fw <= acc:
                fp = p
                break
        event = 'Holiday' if d.month == 12 else 'Back to school' if d.month == 8 else 'Summer' if d.month in (6,7) else 'Regular'
        # These are deliberately synthetic weights, not estimates of any real retailer.
        weight = (180 if d.month == 12 else 150 if d.month == 11 else 130 if d.month == 8 else 100)
        weight += 35 if d.weekday() in (5,6) else 0
        dates.append((int(d.strftime('%Y%m%d')),d,offset,d.year,d.month,d.day,d.weekday()+1,d.weekday() in (5,6),fy,fw,fp,(fp-1)//3+1,event,weight))
    values('dim_date','date_key INTEGER, calendar_date DATE, day_index INTEGER, calendar_year INTEGER, calendar_month INTEGER, day_of_month INTEGER, iso_day_of_week INTEGER, is_weekend BOOLEAN, retail_year INTEGER, retail_week INTEGER, retail_period INTEGER, retail_quarter INTEGER, seasonal_event VARCHAR, demand_weight INTEGER',dates)
    table('dim_time',"SELECT i::INTEGER time_key, (i//60)::INTEGER hour_of_day, (i%60)::INTEGER minute_of_hour, CASE WHEN i//60<12 THEN 'Morning' WHEN i//60<17 THEN 'Afternoon' ELSE 'Evening' END daypart FROM range(1440) t(i)")
    values('dim_channel','channel_key INTEGER, channel_name VARCHAR',[(0,'Not applicable / all channels'),(1,'Store POS'),(2,'Web'),(3,'Mobile app')])
    values('dim_fulfillment_method','fulfillment_method_key INTEGER, fulfillment_method VARCHAR',[(1,'Carry out'),(2,'Store pickup'),(3,'Ship from distribution center'),(4,'Ship from store')])
    table('dim_store',f"""SELECT i::INTEGER store_key, CASE WHEN i=0 THEN 'Digital / no selling store' ELSE 'Summit Field Store '||lpad(i::VARCHAR,3,'0') END store_name,
        CASE WHEN i=0 THEN 'Not applicable' ELSE ['Northeast','South','Midwest','West'][1+(i-1)%4] END region,
        CASE WHEN i=0 THEN 'Digital' WHEN i%10=0 THEN 'Experience' ELSE 'Standard' END store_format,
        DATE '2019-01-01' opened_date, CASE WHEN i=0 THEN 0 ELSE 30000+(i%5)*5000 END selling_area_sqft
        FROM range({stores+1}) t(i)""")
    table('dim_location',f"""SELECT store_key location_key, store_key, store_name location_name, 'STORE' location_type FROM dim_store WHERE store_key>0
        UNION ALL SELECT ({stores}+i)::INTEGER,0,'Summit Field DC '||i,'DC' FROM range(1,3) t(i)""")
    values('dim_division','division_key INTEGER, division_name VARCHAR',list(enumerate(['Apparel','Footwear','Team Sports','Outdoor','Golf','Fitness'],1)))
    depts=['Activewear','Outerwear','Athletic shoes','Specialty shoes','Ball sports','Training gear','Camp and hike','Outdoor recreation','Golf clubs','Golf essentials','Strength','Recovery']
    values('dim_department','department_key INTEGER, division_key INTEGER, department_name VARCHAR',[(i,(i-1)//2+1,n) for i,n in enumerate(depts,1)])
    cats=['Training tops','Training shorts','Fleece','Rain jackets','Running shoes','Training shoes','Hiking shoes','Cleats','Basketballs','Soccer balls','Baseball gloves','Sports bags','Tents','Daypacks','Bicycles','Hydration packs','Iron sets','Putters','Golf balls','Golf bags','Dumbbells','Kettlebells','Yoga mats','Foam rollers']
    values('dim_category','category_key INTEGER, department_key INTEGER, category_name VARCHAR',[(i,(i-1)//2+1,n) for i,n in enumerate(cats,1)])
    brands=['Cinder Peak','Northline Sport','Stridelark','Pine Arc','Court Finch','Trail Loom','Range Harbor','Forge Motion','Kestrel Run','Everpine Gear','Morrow Athletics','Summit Field']
    values('dim_brand','brand_key INTEGER, brand_name VARCHAR, is_private_label BOOLEAN',[(i,n,i==12) for i,n in enumerate(brands,1)])
    values('dim_color','color_key INTEGER, color_name VARCHAR',[(1,'Black'),(2,'Navy'),(3,'Red'),(4,'Gray')])
    size_labels = ['XS','S','M','L','XL','US 7','US 8','US 9','US 10','US 11','Variant A','Variant B','Variant C','Variant D','Variant E']
    values('dim_size','size_key INTEGER, size_system VARCHAR, size_label VARCHAR, size_sort INTEGER',[(i,['Apparel alpha','Footwear US unisex','Equipment configuration'][(i-1)//5],n,(i-1)%5+1) for i,n in enumerate(size_labels,1)])
    table('dim_style',"""SELECT i::INTEGER style_key, (1+(i-1)//5)::INTEGER category_key, (1+rnd(i,'brand',12))::INTEGER brand_key,
        'SF-'||lpad(i::VARCHAR,4,'0') style_code, 'Synthetic '||c.category_name||' model '||(1+(i-1)%5) style_name,
        CASE WHEN i<=40 THEN 'Unisex' ELSE 'Not applicable' END fit_group,
        CASE WHEN i%3=0 THEN 'Premium' WHEN i%3=1 THEN 'Value' ELSE 'Core' END price_tier
        FROM range(1,121) t(i) JOIN dim_category c ON c.category_key=1+(i-1)//5""")
    table('dim_sku',"""SELECT i::INTEGER sku_key, 'SKU-'||lpad(i::VARCHAR,6,'0') sku_code,
        (1+(i-1)//20)::INTEGER style_key, (1+((i-1)%20)//5)::INTEGER color_key,
        (1+(i-1)%5+CASE WHEN i<=400 THEN 0 WHEN i<=800 THEN 5 ELSE 10 END)::INTEGER size_key,
        ((CASE WHEN i<=400 THEN 2500 WHEN i<=800 THEN 6500 WHEN i<=1200 THEN 2000 WHEN i<=1600 THEN 5000 WHEN i<=2000 THEN 8000 ELSE 3000 END)
        +rnd(1+(i-1)//20,'price',12)*1000+99)::BIGINT msrp_cents,
        round(msrp_cents*(45+rnd(style_key,'cost',16))/100.0)::BIGINT unit_cost_cents,
        'USD' currency_code FROM range(1,2401) t(i)""")
    table('dim_customer',f"""SELECT i::INTEGER customer_key, CASE WHEN i=0 THEN 'ANONYMOUS' ELSE 'CUST-'||lpad(i::VARCHAR,7,'0') END customer_id,
        CASE WHEN i=0 THEN 0 ELSE 1+rnd(i,'home', {stores}) END::INTEGER home_store_key,
        CASE WHEN i=0 THEN 'Unknown' ELSE ['18-24','25-34','35-44','45-54','55-64','65+'][1+rnd(i,'age',6)] END age_band,
        CASE WHEN i=0 THEN 'Unknown' ELSE ['Occasional','Active','Enthusiast'][1+rnd(i,'segment',3)] END customer_segment,
        CASE WHEN i=0 THEN NULL ELSE DATE '2020-01-01'+rnd(i,'signup',1400)::INTEGER END registered_date
        FROM range({customers+1}) t(i)""")
    table('dim_loyalty',"""SELECT customer_key loyalty_key, customer_key, CASE WHEN customer_key=0 THEN 'NO-LOYALTY' ELSE 'LOY-'||lpad(customer_key::VARCHAR,7,'0') END loyalty_id,
        CASE WHEN customer_key=0 THEN 'None' WHEN customer_key%9=0 THEN 'Elite' WHEN customer_key%3=0 THEN 'Plus' ELSE 'Base' END loyalty_tier,
        registered_date enrollment_date FROM dim_customer WHERE customer_key=0 OR customer_key%5<>0""")
    table('_months',"SELECT (row_number() OVER (ORDER BY d)-1)::INTEGER month_index, d::DATE month_start, (d+INTERVAL '1 month'-INTERVAL '1 day')::DATE month_end FROM generate_series(DATE '2024-01-01',DATE '2025-12-01',INTERVAL '1 month') t(d)")
    table('dim_promotion',"""SELECT 0::INTEGER promotion_key,'No promotion' promotion_name,0::INTEGER division_key,0::INTEGER channel_key,DATE '2024-01-01' valid_from,DATE '2026-03-01' valid_to,0::INTEGER discount_pct,false loyalty_only
        UNION ALL SELECT 1+month_index*6+division_key-1,'Synthetic '||strftime(month_start,'%Y-%m')||' '||division_name||' event',division_key,
        CASE WHEN month_index%4=0 THEN 2 ELSE 0 END,month_start+9,month_start+23,
        CASE WHEN month_index%3=0 THEN 25 WHEN month_index%3=1 THEN 10 ELSE 20 END,month_index%5=0 FROM _months CROSS JOIN dim_division""")
    # Sentinel division for non-promotion rows; never used by the merchandise hierarchy.
    con.execute("INSERT INTO dim_division VALUES (0,'Not applicable')")
    table('fact_price_history',"""SELECT (((sku_key-1)*3+channel_key-1)*8+q)::INTEGER price_key,sku_key,channel_key,
        (DATE '2024-01-01'+((q-1)*3)*INTERVAL '1 month')::DATE valid_from,
        (DATE '2024-01-01'+q*3*INTERVAL '1 month'-INTERVAL '1 day')::DATE valid_to,
        (msrp_cents+CASE WHEN q>4 THEN 300 ELSE 0 END+CASE WHEN channel_key=3 THEN -100 ELSE 0 END)::BIGINT regular_unit_price_cents,
        CASE WHEN q IN (4,8) THEN 10 ELSE 0 END::INTEGER markdown_pct
        FROM dim_sku CROSS JOIN (SELECT channel_key FROM dim_channel WHERE channel_key>0) c CROSS JOIN range(1,9) t(q)""")
    table('dim_return_reason',"SELECT col0::INTEGER return_reason_key,col1 return_reason FROM (VALUES (1,'Fit / size'),(2,'Changed mind'),(3,'Damaged'),(4,'Performance'))")
    # Expanding small date weights makes seasonal date selection efficient and deterministic.
    table('_slots',"SELECT (row_number() OVER(ORDER BY date_key,j)-1)::BIGINT slot, date_key FROM dim_date,range(demand_weight) t(j) WHERE calendar_date<=DATE '2025-12-31'")
    slots=con.execute('SELECT count(*) FROM _slots').fetchone()[0]
    table('_headers',f"""WITH a AS (SELECT i transaction_key,1+rnd(i,'channel',100) ch,
        CASE WHEN rnd(i,'identify',100)<28 THEN 0 WHEN rnd(i,'repeat',100)<55 THEN 1+rnd(i,'customer',greatest(1,{customers}//5)) ELSE 1+rnd(i,'customer',{customers}) END::INTEGER customer_key,
        slot.date_key,1+rnd(i,'store',{stores})::INTEGER guest_store,
        rnd(i,'basket',100) basket FROM range(1,{headers+1}) t(i) JOIN _slots slot ON slot.slot=rnd(i,'date',{slots}))
        SELECT transaction_key,date_key,CASE WHEN ch<=66 THEN 1 WHEN ch<=89 THEN 2 ELSE 3 END::INTEGER channel_key,
        customer_key,CASE WHEN customer_key%5<>0 THEN customer_key ELSE 0 END::INTEGER loyalty_key,
        CASE WHEN customer_key=0 THEN guest_store ELSE c.home_store_key END::INTEGER market_store_key,
        CASE WHEN ch<=66 THEN market_store_key ELSE 0 END::INTEGER selling_store_key,
        CASE WHEN ch<=66 THEN 1 WHEN rnd(transaction_key,'fulfill',100)<30 THEN 2 WHEN rnd(transaction_key,'fulfill',100)<72 THEN 3 ELSE 4 END::INTEGER fulfillment_method_key,
        (CASE WHEN ch<=66 THEN 600+rnd(transaction_key,'time',660) ELSE rnd(transaction_key,'time',1440) END)::INTEGER time_key,
        (CASE WHEN basket<35 THEN 1 WHEN basket<65 THEN 2 WHEN basket<85 THEN 3 WHEN basket<95 THEN 4 ELSE 5 END)::INTEGER line_count
        FROM a JOIN dim_customer c USING(customer_key)""")
    table('_line_base',"""WITH a AS (SELECT h.*,n::INTEGER line_number,((transaction_key-1)*5+n)::BIGINT sales_line_key,
        d.calendar_date,d.calendar_month,d.calendar_year,
        CASE WHEN rnd(transaction_key,'mix',100)<35 THEN CASE WHEN d.calendar_month IN (6,7) THEN 4 WHEN d.calendar_month IN (8,9) THEN 2 WHEN d.calendar_month IN (11,12,1) THEN 1 ELSE 3 END ELSE 1+rnd(transaction_key,'division',6) END::INTEGER basket_division
        FROM _headers h JOIN dim_date d USING(date_key),range(1,h.line_count+1) t(n)), b AS (
        SELECT *,CASE WHEN rnd(sales_line_key,'cross_sell',100)<22 THEN 1+rnd(sales_line_key,'other_division',6) ELSE basket_division END::INTEGER division_key FROM a)
        SELECT *, ((division_key-1)*400+1+rnd(sales_line_key,'sku',400))::INTEGER sku_key,
        CASE WHEN rnd(sales_line_key,'quantity',100)<9 THEN 2 ELSE 1 END::INTEGER quantity,
        (((calendar_year-2024)*4+(calendar_month-1)//3)+1)::INTEGER price_quarter,
        (1+(calendar_year-2024)*72+(calendar_month-1)*6+division_key-1)::INTEGER candidate_promotion_key
        FROM b""")
    table('fact_sales_line',f"""WITH priced AS (
        SELECT b.*,p.price_key,p.regular_unit_price_cents,
        round(p.regular_unit_price_cents*p.markdown_pct/100.0)::BIGINT unit_markdown,
        CASE WHEN calendar_date BETWEEN pr.valid_from AND pr.valid_to AND (pr.channel_key=0 OR pr.channel_key=b.channel_key)
          AND (NOT pr.loyalty_only OR b.loyalty_key>0) AND rnd(sales_line_key,'redeem',100)<60 THEN pr.promotion_key ELSE 0 END::INTEGER applied_promotion_key,
        CASE WHEN applied_promotion_key>0 THEN pr.discount_pct ELSE 0 END::INTEGER applied_pct,s.unit_cost_cents
        FROM _line_base b JOIN fact_price_history p ON p.price_key=((b.sku_key-1)*3+b.channel_key-1)*8+b.price_quarter
        JOIN dim_sku s ON s.sku_key=b.sku_key JOIN dim_promotion pr ON pr.promotion_key=b.candidate_promotion_key)
        SELECT sales_line_key,transaction_key,line_number,date_key,sku_key,price_key,applied_promotion_key AS promotion_key,
        CASE WHEN fulfillment_method_key=3 THEN {stores}+1+rnd(sales_line_key,'dc',2) ELSE market_store_key END::INTEGER fulfillment_location_key,
        quantity,regular_unit_price_cents,
        (regular_unit_price_cents-unit_markdown-round((regular_unit_price_cents-unit_markdown)*applied_pct/100.0))::BIGINT selling_unit_price_cents,
        unit_cost_cents,(quantity*regular_unit_price_cents)::BIGINT gross_sales_cents,
        (quantity*unit_markdown)::BIGINT markdown_cents,
        (quantity*(regular_unit_price_cents-unit_markdown-selling_unit_price_cents))::BIGINT promotion_discount_cents,
        (quantity*selling_unit_price_cents)::BIGINT net_sales_cents,
        (quantity*round(selling_unit_price_cents*0.07))::BIGINT tax_cents,
        (quantity*unit_cost_cents)::BIGINT cost_of_goods_cents,
        CASE WHEN fulfillment_method_key IN (3,4) THEN (calendar_date+(2+rnd(sales_line_key,'delivery',5))::INTEGER) ELSE calendar_date END promised_delivery_date
        FROM priced""")
    table('fact_transaction',"""SELECT h.transaction_key,'TXN-'||lpad(h.transaction_key::VARCHAR,10,'0') transaction_id,h.date_key,h.time_key,h.customer_key,h.loyalty_key,h.channel_key,h.selling_store_key,h.market_store_key,h.fulfillment_method_key,
        (d.calendar_date+to_minutes(h.time_key))::TIMESTAMP transaction_local_timestamp,
        h.line_count,a.units,a.gross_sales_cents,a.markdown_cents,a.promotion_discount_cents,a.net_sales_cents,a.tax_cents,a.cost_of_goods_cents,
        CASE WHEN h.fulfillment_method_key IN (3,4) AND a.net_sales_cents<7500 THEN 599 ELSE 0 END::BIGINT shipping_cents,
        (a.net_sales_cents+a.tax_cents+shipping_cents)::BIGINT total_paid_cents,'COMPLETED' transaction_status,'USD' currency_code
        FROM _headers h JOIN (SELECT transaction_key,sum(quantity)::INTEGER units,sum(gross_sales_cents)::BIGINT gross_sales_cents,sum(markdown_cents)::BIGINT markdown_cents,
        sum(promotion_discount_cents)::BIGINT promotion_discount_cents,sum(net_sales_cents)::BIGINT net_sales_cents,sum(tax_cents)::BIGINT tax_cents,sum(cost_of_goods_cents)::BIGINT cost_of_goods_cents FROM fact_sales_line GROUP BY transaction_key) a USING(transaction_key)
        JOIN dim_date d USING(date_key)""")
    table('fact_return_line',f"""WITH a AS (SELECT l.*,h.channel_key,h.market_store_key,
        (d.calendar_date+(7+rnd(sales_line_key,'return_lag',54))::INTEGER)::DATE return_date,
        CASE WHEN rnd(sales_line_key,'reason',100)<45 AND l.sku_key<=800 THEN 1 ELSE 2+rnd(sales_line_key,'reason2',3) END::INTEGER return_reason_key
        FROM fact_sales_line l JOIN fact_transaction h USING(transaction_key) JOIN dim_date d ON d.date_key=l.date_key
        WHERE rnd(sales_line_key,'returned',1000)<CASE WHEN l.sku_key<=800 AND h.channel_key>1 THEN 170 WHEN l.sku_key<=800 THEN 90 ELSE 45 END)
        SELECT sales_line_key::BIGINT return_line_key,sales_line_key,transaction_key,sku_key,
        strftime(return_date,'%Y%m%d')::INTEGER return_date_key,return_reason_key,
        CASE WHEN channel_key=1 OR rnd(sales_line_key,'return_store',100)<65 THEN market_store_key ELSE {stores}+1+rnd(sales_line_key,'return_dc',2) END::INTEGER return_location_key,
        1::INTEGER returned_quantity,return_reason_key<>3 is_restockable,selling_unit_price_cents::BIGINT refund_net_cents,
        round(selling_unit_price_cents*0.07)::BIGINT refund_tax_cents,
        (selling_unit_price_cents+round(selling_unit_price_cents*0.07))::BIGINT refund_total_cents,
        CASE WHEN return_reason_key<>3 THEN unit_cost_cents ELSE 0 END::BIGINT recovered_cost_cents
        FROM a""")
    table('_weeks',f"SELECT i::INTEGER inventory_week_index,(DATE '2024-01-01'+(i*7)::INTEGER)::DATE week_start,least(DATE '2024-01-01'+(i*7+6)::INTEGER,DATE '{AS_OF}')::DATE week_end FROM range({((AS_OF-START).days//7)+1}) t(i)")
    table('_sold',"SELECT d.day_index//7 inventory_week_index,fulfillment_location_key location_key,sku_key,sum(quantity)::INTEGER sold_units FROM fact_sales_line l JOIN dim_date d USING(date_key) GROUP BY 1,2,3")
    table('_restocked',"SELECT d.day_index//7 inventory_week_index,return_location_key location_key,sku_key,sum(returned_quantity)::INTEGER restocked_units FROM fact_return_line r JOIN dim_date d ON d.date_key=r.return_date_key WHERE is_restockable GROUP BY 1,2,3")
    # Weekly receipts cover demand plus replenishment. No claim of daily stock availability.
    table('fact_inventory_weekly',"""WITH a AS (SELECT w.inventory_week_index,w.week_start,w.week_end,l.location_key,s.sku_key,
        coalesce(v.sold_units,0)::INTEGER sold_units,coalesce(r.restocked_units,0)::INTEGER restocked_units,
        (CASE WHEN l.location_type='DC' THEN 45 ELSE 8 END+rnd(l.location_key*2400+s.sku_key,'opening',8))::INTEGER initial_units,
        (2+rnd((w.inventory_week_index*1000+l.location_key)*2400+s.sku_key,'buffer',8))::INTEGER buffer_units,
        CASE WHEN rnd((w.inventory_week_index*1000+l.location_key)*2400+s.sku_key,'shrink',1000)<3 THEN 1 ELSE 0 END::INTEGER shrink_units
        FROM _weeks w CROSS JOIN dim_location l CROSS JOIN dim_sku s
        LEFT JOIN _sold v ON v.inventory_week_index=w.inventory_week_index AND v.location_key=l.location_key AND v.sku_key=s.sku_key
        LEFT JOIN _restocked r ON r.inventory_week_index=w.inventory_week_index AND r.location_key=l.location_key AND r.sku_key=s.sku_key), b AS (
        SELECT *, (initial_units+sum(restocked_units-shrink_units) OVER(PARTITION BY location_key,sku_key ORDER BY inventory_week_index ROWS UNBOUNDED PRECEDING))::INTEGER baseline
        FROM a), c AS (
        SELECT *, greatest(0,max(buffer_units-baseline) OVER(PARTITION BY location_key,sku_key ORDER BY inventory_week_index ROWS UNBOUNDED PRECEDING))::INTEGER topup_cumulative FROM b), e AS (
        SELECT *, (baseline+topup_cumulative)::INTEGER closing_on_hand_units,
        lag(baseline+topup_cumulative,1,initial_units) OVER(PARTITION BY location_key,sku_key ORDER BY inventory_week_index)::INTEGER opening_on_hand_units,
        (sold_units+topup_cumulative-lag(topup_cumulative,1,0) OVER(PARTITION BY location_key,sku_key ORDER BY inventory_week_index))::INTEGER receipt_units FROM c)
        SELECT inventory_week_index,location_key,sku_key,strftime(week_start,'%Y%m%d')::INTEGER week_start_date_key,strftime(week_end,'%Y%m%d')::INTEGER week_end_date_key,
        opening_on_hand_units,receipt_units,sold_units,restocked_units,shrink_units,closing_on_hand_units,
        least(closing_on_hand_units,rnd((inventory_week_index*1000+location_key)*2400+sku_key,'reserved',3))::INTEGER reserved_units,
        (closing_on_hand_units-reserved_units)::INTEGER available_units,
        rnd((inventory_week_index*1000+location_key)*2400+sku_key,'transit',12)::INTEGER in_transit_units FROM e""")
    # Helpers never exposed to agents or exported.
    for (name,) in con.execute("SELECT table_name FROM information_schema.tables WHERE table_name LIKE '\\_%' ESCAPE '\\'").fetchall():
        con.execute(f'DROP TABLE {name}')
    con.execute('DROP MACRO rnd')
    views=(Path(__file__).parent.parent/'sql'/'views.sql').read_text()
    con.execute(views)
    print('Validating all tables',flush=True)
    report=validate(con,headers,stores)
    (out/'validation_report.json').write_text(json.dumps(report,indent=2))
    if not report['passed']:
        raise RuntimeError('Validation failed; inspect validation_report.json')
    print('Exporting Parquet and schema',flush=True)
    export_root=out/'parquet'
    export_root.mkdir()
    ddl=['-- DuckDB physical schema. Foreign keys are validated in the generated warehouse.\n-- Execute in a fresh database; load referenced dimensions before facts.\n']
    dictionary=['# Data dictionary\n\nAll records are synthetic. Money is integer US cents. Date keys use YYYYMMDD.\n']
    catalog={}
    parquet_views=[]
    counts={}
    checksums={}
    for name,spec in TABLES.items():
        cols=con.execute(f'DESCRIBE {name}').fetchall()
        definitions=[]
        dictionary.append(f"\n## {name}\n\n{spec['grain']}\n\nPrimary key: `{', '.join(spec['pk'])}`.\n\n| Column | DuckDB type | Meaning / relationship |\n|---|---|---|\n")
        catalog[name]={'grain':spec['grain'],'primary_key':spec['pk'],'foreign_keys':spec.get('fk',{}),'columns':[]}
        for col,typ,*_ in cols:
            nullable=col in ('registered_date','enrollment_date')
            definitions.append(f'  {col} {typ}'+('' if nullable else ' NOT NULL'))
            desc=describe_column(name,col)
            dictionary.append(f'| {col} | {typ} | {desc} |\n')
            catalog[name]['columns'].append({'name':col,'type':typ,'description':desc,'nullable':nullable})
        definitions.append('  PRIMARY KEY ('+', '.join(spec['pk'])+')')
        for col,target in spec.get('fk',{}).items():
            target_table,target_col=target.split('.')
            definitions.append(f'  FOREIGN KEY ({col}) REFERENCES {target_table}({target_col})')
        ddl.append(f'CREATE TABLE {name} (\n'+',\n'.join(definitions)+'\n);\n')
        counts[name]=con.execute(f'SELECT count(*) FROM {name}').fetchone()[0]
        # Order-independent content fingerprint; portability is scoped to pinned DuckDB.
        checksums[name]=str(con.execute(f'SELECT bit_xor(hash(COLUMNS(*))) FROM {name}').fetchone())
        part='date_key' if name in ('fact_transaction','fact_sales_line') else 'return_date_key' if name=='fact_return_line' else 'week_end_date_key' if name=='fact_inventory_weekly' else None
        target=export_root/name
        if part:
            con.execute(f"COPY (SELECT *,({part}//100)::INTEGER partition_month FROM {name}) TO {sqlstr(target)} (FORMAT PARQUET,COMPRESSION ZSTD,PARTITION_BY(partition_month),ROW_GROUP_SIZE 122880)")
            glob=f'parquet/{name}/**/*.parquet'
        else:
            con.execute(f'COPY {name} TO {sqlstr(str(target)+".parquet")} (FORMAT PARQUET,COMPRESSION ZSTD)')
            glob=f'parquet/{name}.parquet'
        parquet_views.append(f"CREATE VIEW {name} AS SELECT *{' EXCLUDE (partition_month)' if part else ''} FROM read_parquet('{glob}',hive_partitioning=true);")
    docs=out/'metadata'
    docs.mkdir()
    (docs/'schema.sql').write_text('\n'.join(ddl))
    (docs/'data_dictionary.md').write_text(''.join(dictionary))
    (docs/'catalog.json').write_text(json.dumps(catalog,indent=2))
    (docs/'parquet_views.sql').write_text('-- Run with working directory set to this dataset output directory.\n'+'\n'.join(parquet_views)+'\n'+views)
    files={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(export_root.rglob('*.parquet'))}
    manifest={'generator_version':VERSION,'duckdb_version':duckdb.__version__,'seed':seed,'transaction_headers':headers,'stores':stores,'customers':customers,'sku_count':2400,'sales_start':str(START),'sales_end':str(END),'as_of_date':str(AS_OF),'inventory_frequency':'weekly Monday-Sunday; last week partial','row_counts':counts,'column_xor_fingerprints':checksums,'parquet_sha256':files,'elapsed_seconds':round(time.monotonic()-started,2),'reproducibility':'Same pinned DuckDB, configuration and seed reproduce table contents; Parquet byte layout may differ by threads/platform. Checksums attest this export only.'}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    con.execute('CHECKPOINT')
    con.close()
    print(json.dumps({'output':str(out),'rows':counts,'validation_passed':True,'seconds':manifest['elapsed_seconds']},indent=2),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=Path('data/full'))
    p.add_argument('--headers',type=int,default=5_000_000)
    p.add_argument('--seed',type=int,default=20250925)
    p.add_argument('--stores',type=int,default=60)
    p.add_argument('--customers',type=int,default=600_000)
    p.add_argument('--memory',default='3GB')
    p.add_argument('--threads',type=int,default=4)
    a=p.parse_args()
    if not (a.headers>0 and 1<=a.stores<=500 and a.customers>0 and a.threads>0):
        p.error('headers, customers, threads must be positive; stores must be 1..500')
    generate(a.output.resolve(),a.headers,a.seed,a.stores,a.customers,a.memory,a.threads)
