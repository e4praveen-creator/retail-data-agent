"""Read-only warehouse access and the existing, versioned playbook recipes."""
from . import config
from .sql_checks import validate_model_sql
from .visual_data import attach_visual_outputs
import datetime as dt
import importlib.util
import json
import os
import re
import threading
import time
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from decimal import Decimal
import duckdb

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / 'retail_app'
DB = Path(os.getenv('RETAIL_DB', str(ROOT / 'retail_data/data/full/retail.duckdb')))
spec = importlib.util.spec_from_file_location('playbook_runner', ROOT / 'retail-data-analyst/scripts/run_analysis.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
SLUGS = list(runner.REPORTS)
TITLES = ['Sales trend','Price, volume & mix','Sources of growth','Margin & returns','Seasonality','Merchandise scorecard','Channels & stores','Sales concentration','Pricing & markdown','Promotion performance','Customer cohorts','Customer recency','Behavioral segments','Basket affinity','Loyalty usage','Returns & reasons','Item velocity','Inventory health','Fulfillment mix']
NOTES = {
 'pvm': 'Three-factor Shapley allocation at SKU × channel grain; realized rate includes discount effects. This locates change, not causality.',
 'margin':'Sales cohorts include all linked returns through 2026-03-01. Merchandise margin excludes shipping, labor and operating expenses.',
 'scorecard':'Sales-cohort revenue and merchandise margin after observed returns. Buyer counts exclude anonymous customers; counts across divisions overlap.',
 'promotions':'Redeemed promotion-associated sales, not incremental lift. Campaigns may only partly overlap the selected period.',
 'cohorts':'First observed purchase, not true acquisition. History starts in 2024. Only customers with a complete observation window enter each repeat-rate denominator.',
 'lapse':'Historical customers through each cutoff. Monthly transitions use an illustrative global 90-day lapse rule, not a category-relative threshold. Recency and reactivation are descriptive, not permanent churn.',
 'segments':'Behavioral groups use the existing recipe: at least 3 orders for frequent and 90 days for active. Thresholds are illustrative.',
 'affinity':'Lift is basket co-occurrence, not causal incremental sales. Small basket-pair bases should be reviewed before acting.',
 'loyalty':'Loyalty is attached when loyalty_key > 0. Member differences do not measure program impact.',
 'returns':'Unit rates and the elapsed-return heatmap use original sales cohorts and linked returns; eligible bases and 60-day maturity are shown. The original reason table uses return dates; the added cohort reason table uses original-sale dates. Keep these bases separate.',
 'velocity':'Latest complete inventory snapshot on or before the end date; observed sales over the selected period. High stock is not proof of lost demand or delisting safety.',
 'inventory':'The baseline selects the latest completed Monday–Sunday snapshot; the stock/flow series shows separate weekly snapshots. Ending balances are never summed across weeks.',
 'fulfillment':'Completed orders by fulfillment method. No actual delivery dates or fulfillment costs exist.',
 'seasonality':'Two years support descriptive patterns only. Retail week 53 and partial fiscal years are explicitly visible.',
 'channels':'POS stores use selling_store_key; digital selling_store_key is 0. Header AOV avoids line fan-out.',
}
CATALOG = json.loads((ROOT / 'retail_data/docs/catalog.json').read_text())
LOCK = threading.Semaphore(2)
QUERY_CONTROL = ContextVar('retail_query_control', default=None)


@contextmanager
def query_control(control):
    token = QUERY_CONTROL.set(control)
    try:
        yield
    finally:
        QUERY_CONTROL.reset(token)


@contextmanager
def warehouse_session(timeout=30):
    """Bound queueing, query runtime, and cooperative cancellation for every read."""
    control = QUERY_CONTROL.get()
    check = getattr(control, 'check_cancelled', lambda: None)
    waiting = time.monotonic()
    while not LOCK.acquire(timeout=.1):
        check()
        if time.monotonic() - waiting >= 5:
            raise ValueError('The warehouse is busy. Please wait for the current analyses to finish.')
    con = None
    done = threading.Event()
    failures = []
    monitor = None
    try:
        check()
        con = connect()
        deadline = time.monotonic() + timeout
        def interrupt_if_needed():
            while not done.wait(.1):
                try:
                    check()
                    if time.monotonic() >= deadline:
                        raise ValueError('The warehouse query exceeded its time limit. Narrow the question and retry.')
                except Exception as error:
                    failures.append(error)
                    con.interrupt()
                    return
        monitor = threading.Thread(target=interrupt_if_needed, daemon=True)
        monitor.start()
        try:
            yield con
        except Exception:
            if failures:
                raise failures[0]
            check()
            raise
        check()
        if failures:
            raise failures[0]
    finally:
        done.set()
        if monitor:
            monitor.join(timeout=1)
        if con:
            con.close()
        LOCK.release()


def clean(obj):
    return json.loads(json.dumps(obj, default=lambda value: (int(value) if value==value.to_integral_value() else float(value)) if isinstance(value,Decimal) else str(value), allow_nan=False))


def connect():
    con = duckdb.connect(str(DB), read_only=True, config={'enable_external_access':False, 'threads':2, 'memory_limit':'1GB'})
    return con


def dates_for(start, end, compare_start=None, compare_end=None):
    start, end = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    cs = dt.date.fromisoformat(compare_start) if compare_start else start-dt.timedelta(days=364)
    ce = dt.date.fromisoformat(compare_end) if compare_end else end-dt.timedelta(days=364)
    if start > end or cs > ce:
        raise ValueError('Period starts must be before their ends.')
    if end-start != ce-cs:
        raise ValueError('Comparison periods must have equal numbers of days.')
    if min(start,cs) < dt.date(2024,1,1) or max(end,ce) > dt.date(2025,12,31):
        raise ValueError('Sales and comparison dates must be within 2024-01-01 to 2025-12-31.')
    if ce >= start:
        raise ValueError('Comparison must end before the current period begins.')
    return {'start':start,'end':end,'compare_start':cs,'compare_end':ce}


def select_sql(sql, parameters=None, limit=500):
    """Parser-enforced single SELECT; disabled file/network access; bounded result/time."""
    if not isinstance(sql, str) or not sql.strip() or len(sql) > 32000:
        raise ValueError('Provide one SQL query of at most 32,000 characters.')
    if not isinstance(limit, int) or not 1 <= limit <= 500:
        raise ValueError('Query previews must contain between 1 and 500 rows.')
    with warehouse_session() as con:
        statements = con.extract_statements(sql)
        if len(statements) != 1 or statements[0].type != duckdb.StatementType.SELECT:
            raise ValueError('Only one read-only SELECT statement is allowed.')
        validate_model_sql(sql, con)
        cursor = con.execute(sql, parameters or [])
        names = [c[0] for c in cursor.description]
        if len(names) > 100 or len(set(names)) != len(names):
            raise ValueError('Use at most 100 uniquely named result columns; alias duplicate columns explicitly.')
        rows = []; size = 0; truncated = False
        for i in range(limit + 1):
            values = cursor.fetchone()
            if values is None:
                break
            if i == limit:
                truncated = True
                break
            row = clean(dict(zip(names, values)))
            for key, value in row.items():
                if isinstance(value, str) and len(value) > 8000:
                    row[key] = value[:8000] + ' [truncated]'
                    truncated = True
            row_size = len(json.dumps(row).encode('utf-8'))
            if size + row_size > 1024 * 1024:
                truncated = True
                break
            rows.append(row); size += row_size
        return {'name':'custom_query','rows':rows,'row_count':len(rows), 'truncated':truncated,
                'sql':sql,'parameters':clean(parameters or []),
                'limits':{'max_rows':limit,'max_bytes':1024 * 1024,'max_cell_characters':8000}}


def inspect_table(table):
    if table not in set(CATALOG) | {'v_product','v_sales','v_sales_after_returns','v_merchandise_activity'}:
        raise ValueError('Choose a table or view from the catalog.')
    with warehouse_session() as con:
        columns = runner.fetch(con, 'DESCRIBE SELECT * FROM "'+table+'"', [])
        count = con.execute('SELECT count(*) FROM "'+table+'"').fetchone()[0]
        sample_limit = 20 if table.startswith('dim_') else 3
        sample = runner.fetch(con, 'SELECT * FROM "'+table+'" LIMIT '+str(sample_limit), [])
    return clean({'table':table,'row_count':count,'columns':columns,'sample':sample,
                  'sample_complete':count<=sample_limit,'sample_limit':sample_limit,'metadata':CATALOG.get(table,{})})


def scope_values():
    """Complete, bounded reference labels for the two common retail filters."""
    with warehouse_session() as con:
        return {name: runner.fetch(con, sql, []) for name, sql in {
            'channels': 'SELECT channel_key, channel_name FROM dim_channel ORDER BY channel_key LIMIT 50',
            'divisions': 'SELECT division_key, division_name FROM dim_division ORDER BY division_key LIMIT 50',
        }.items()}


def checks(slug, outputs):
    out = [{'name':'Validated date coverage and nonoverlapping equal-length comparison','passed':True},
           {'name':'Read-only warehouse and parameterized playbook SQL','passed':True}]
    rows = outputs[0]['rows']
    out.append({'name':'Result contains rows','passed':bool(rows)})
    if slug == 'pvm':
        out.append({'name':'Price / volume / mix bridge reconciles to the cent','passed':bool(rows and rows[0]['reconciles'])})
    if slug == 'inventory':
        out.append({'name':'Opening + receipts + restocks − sales − shrink = closing','passed':all(r['opening_units']+r['receipt_units']+r['restocked_units']-r['sold_units']-r['shrink_units']==r['closing_units'] for r in rows)})
    if slug == 'margin':
        out.append({'name':'Cohort margin reconciles to revenue and recovered cost','passed':all(r['original_net_sales_cents']-r['returned_revenue_cents']-r['original_cogs_cents']+r['recovered_cost_cents']==r['merchandise_margin_cents'] for r in rows)})
    if slug == 'cohorts':
        out.append({'name':'Repeat buyers do not exceed mature eligible customers','passed':all(0<=r['repeat_buyers_90']<=r['eligible_90']<=r['identified_buyers'] and 0<=r['repeat_buyers_180']<=r['eligible_180']<=r['identified_buyers'] for r in rows)})
    return out


def money(cents):
    return '${:,.0f}'.format(cents/100)


def summarize(slug, results):
    rows = results[0]['rows']
    if not rows: return 'No matching rows were found for this period.'
    if slug == 'trend':
        totals = {p:sum(r['sales_before_returns_cents'] for r in rows if r['period']==p) for p in ['current','comparison']}
        c,b=totals['current'],totals['comparison']
        return f"Sales before returns were {money(c)}, {((c-b)/b*100):+.1f}% versus the comparison period." if b else f"Sales before returns were {money(c)}; the comparison has no sales."
    if slug == 'pvm':
        r=rows[0]
        return f"Sales changed by {money(r['change_cents'])}: realized rate {money(r['realized_rate_cents'])}, volume {money(r['volume_cents'])}, mix {money(r['mix_cents'])}, and entry/exit {money(r['entry_exit_cents'])}."
    if slug == 'growth':
        r=rows[0]
        return f"{r['division_name']} had the largest absolute contribution to the sales change ({money(r['change_cents'])}). Division contributions total {money(sum(x['change_cents'] for x in rows))}."
    if slug == 'inventory':
        return f"Ending on-hand was {sum(r['closing_units'] for r in rows):,} units, with {sum(r['available_units'] for r in rows):,} available. Snapshot: {rows[0]['week_end_date_key']}."
    if slug == 'returns':
        units=sum(r['original_units'] for r in rows); ret=sum(r['returned_units'] for r in rows)
        return f"{ret:,} of {units:,} original units were returned ({ret/units*100:.2f}%). All cohorts have a full 60-day return window."
    if slug == 'promotions':
        r=rows[0]
        return f"{r['promotion_name']} had the most associated sales in this period: {money(r['associated_sales_before_returns_cents'])}. This is not incremental lift."
    if slug == 'margin':
        c=sum(r['merchandise_margin_cents'] for r in rows if r['period']=='current'); b=sum(r['merchandise_margin_cents'] for r in rows if r['period']=='comparison')
        return f"Sales-cohort merchandise margin was {money(c)}, a change of {money(c-b)}. It excludes fulfillment and operating expenses."
    return f"{TITLES[SLUGS.index(slug)]}: {results[0]['row_count']:,} result groups computed from the selected scope. Review the chart and evidence for the measured values."


def run_playbook(slug, dates):
    if slug not in runner.REPORTS: raise ValueError('Unknown playbook.')
    with warehouse_session(timeout=60) as con:
        outputs=runner.run_one(con,slug,dates,5000)
        outputs=attach_visual_outputs(con,slug,dates,outputs)
    for i,output in enumerate(outputs):output['evidence_id']='E'+str(i+1)
    warnings=['Synthetic Summit Field data; descriptive findings do not establish causes.',NOTES.get(slug,'Original merchandise sales before returns, excluding tax and shipping. All-business baseline.')]
    if dates['start'].weekday()!=6 or dates['end'].weekday()!=5 or dates['compare_start'].weekday()!=6 or dates['compare_end'].weekday()!=5:
        warnings.append('Selected periods include partial retail weeks. These are shown; weekly values should not be treated as complete-week comparisons.')
    if slug=='seasonality': warnings.append('Fiscal-year boundaries are partial. Week 53 is not restated.')
    report=clean({'slug':slug,'title':TITLES[SLUGS.index(slug)],'summary':summarize(slug,outputs),'period':dates,'scope':'All business; no product, channel or store filters','basis':warnings[1],'warnings':warnings,'outputs':outputs,'checks':checks(slug,outputs),'sources':sorted(set(re.findall(r'\b(?:fact_\w+|dim_\w+|v_\w+)\b',' '.join(x['sql'] for x in outputs))))})
    from .presentation import report_headline,get_contract
    report['summary']=report_headline(report)
    report['output_design']=get_contract(slug)
    return report


def overview(dates):
    sql='''SELECT CASE WHEN d.calendar_date BETWEEN ? AND ? THEN 'current' ELSE 'comparison' END period,
      sum(h.net_sales_cents) sales_cents, sum(h.units) units, count(*) orders,
      count(DISTINCT CASE WHEN h.customer_key>0 THEN h.customer_key END) identified_buyers
      FROM fact_transaction h JOIN dim_date d USING(date_key)
      WHERE d.calendar_date BETWEEN ? AND ? OR d.calendar_date BETWEEN ? AND ? GROUP BY 1'''
    vals=[dates[k] for k in ['start','end','start','end','compare_start','compare_end']]
    return select_sql(sql,vals)
