"""Small parameterized report tools shared by FastAPI and the LangGraph example."""
import datetime as dt
import os
from pathlib import Path
import duckdb

DATA_DIR = Path(os.environ.get('RETAIL_DATA_DIR','data/full'))
REPORTS = {
    'monthly_sales': """SELECT d.calendar_year,d.calendar_month,
        CAST(sum(a.merchandise_revenue_cents)/100.0 AS DECIMAL(18,2)) net_revenue_usd,
        sum(a.net_units) net_units FROM v_merchandise_activity a JOIN dim_date d USING(date_key)
        WHERE d.calendar_date BETWEEN ? AND ? GROUP BY 1,2 ORDER BY 1,2""",
    'division_sales': """SELECT p.division_name,
        CAST(sum(a.merchandise_revenue_cents)/100.0 AS DECIMAL(18,2)) net_revenue_usd,
        sum(a.net_units) net_units FROM v_merchandise_activity a JOIN dim_date d USING(date_key)
        JOIN v_product p USING(sku_key) WHERE d.calendar_date BETWEEN ? AND ? GROUP BY 1 ORDER BY 2 DESC""",
    'channel_orders': """SELECT c.channel_name,count(*) orders,sum(h.units) sold_units,
        CAST(sum(h.net_sales_cents)/100.0 AS DECIMAL(18,2)) sales_before_returns_usd,
        CAST(avg(h.net_sales_cents)/100.0 AS DECIMAL(18,2)) aov_before_returns_usd
        FROM fact_transaction h JOIN dim_channel c USING(channel_key) JOIN dim_date d USING(date_key)
        WHERE d.calendar_date BETWEEN ? AND ? GROUP BY 1 ORDER BY 2 DESC""",
}


def run_report(report: str, start_date: str='2024-01-01', end_date: str='2025-12-31'):
    if report not in REPORTS:
        raise ValueError('Unknown report: '+report)
    start,end=dt.date.fromisoformat(start_date),dt.date.fromisoformat(end_date)
    if start>end:
        raise ValueError('start_date must be on or before end_date')
    if not (DATA_DIR/'retail.duckdb').is_file():
        raise FileNotFoundError('Generate the dataset first, or set RETAIL_DATA_DIR to its folder.')
    with duckdb.connect(str(DATA_DIR/'retail.duckdb'),read_only=True) as con:
        con.execute("SET memory_limit='2GB'")
        con.execute('SET threads=2')
        result=con.execute(REPORTS[report],[start,end])
        cols=[x[0] for x in result.description]
        rows=[dict(zip(cols,row)) for row in result.fetchall()]
    return {'report':report,'start_date':str(start),'end_date':str(end),'rows':rows,
            'evidence':{'sql':REPORTS[report],'parameters':[str(start),str(end)],'dataset':'synthetic Summit Field v1'}}
