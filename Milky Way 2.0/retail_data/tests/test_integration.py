"""Run against a small generated sample and a second identical-seed replica.
Example: python tests/test_integration.py --data data/sample --replica data/replica
"""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import duckdb
from catalog import TABLES
from generate import fiscal_start


def test(data, replica):
    data,replica=data.resolve(),replica.resolve()
    os.environ['RETAIL_DATA_DIR']=str(data)
    from fastapi.testclient import TestClient
    from api import app
    from graph_demo import build_graph
    from reports import run_report
    checks=[]
    def ok(label,condition):
        if not condition:
            raise AssertionError(label)
        checks.append(label)
    con=duckdb.connect(str(data/'retail.duckdb'),read_only=True)
    con.execute("SET memory_limit='2GB'")
    def quote(path):
        return "'"+str(path).replace("'","''")+"'"
    con.execute(f'ATTACH {quote(replica/"retail.duckdb")} AS replica (READ_ONLY)')
    for table in TABLES:
        n=con.execute(f'SELECT count(*) FROM ((SELECT * FROM main.{table} EXCEPT ALL SELECT * FROM replica.{table}) UNION ALL (SELECT * FROM replica.{table} EXCEPT ALL SELECT * FROM main.{table}))').fetchone()[0]
        ok(f'{table}: exact same-seed reproduction',n==0)
    for table in TABLES:
        folder=data/'parquet'/table
        partitioned=folder.is_dir()
        path=folder/'**/*.parquet' if partitioned else data/'parquet'/f'{table}.parquet'
        select=f'SELECT *'+(' EXCLUDE(partition_month)' if partitioned else '')+f' FROM read_parquet({quote(path)},hive_partitioning=true)'
        n=con.execute(f'SELECT count(*) FROM ((SELECT * FROM main.{table} EXCEPT ALL {select}) UNION ALL ({select} EXCEPT ALL SELECT * FROM main.{table}))').fetchone()[0]
        ok(f'{table}: exact Parquet round trip',n==0)
    # Execute the published DDL and load every table in dependency order.
    with tempfile.TemporaryDirectory() as td:
        with duckdb.connect(str(Path(td)/'constrained.duckdb')) as target:
            target.execute("SET memory_limit='2GB'")
            target.execute((data/'metadata/schema.sql').read_text())
            target.execute(f'ATTACH {quote(data/"retail.duckdb")} AS source_db (READ_ONLY)')
            for table in TABLES:
                target.execute(f'INSERT INTO {table} SELECT * FROM source_db.{table}')
            ok('published constrained DDL loads all data',True)
    previous=Path.cwd()
    try:
        os.chdir(data)
        with duckdb.connect() as pq:
            pq.execute((data/'metadata/parquet_views.sql').read_text())
            ok('portable Parquet views',pq.execute('SELECT count(*) FROM v_sales').fetchone()==con.execute('SELECT count(*) FROM v_sales').fetchone())
    finally:
        os.chdir(previous)
    sql=(Path(__file__).resolve().parents[1]/'sql/example_queries.sql').read_text()
    statements=con.extract_statements(sql)
    for i,stmt in enumerate(statements,1):
        con.execute(stmt).fetchall()
        ok(f'example query {i}',True)
    client=TestClient(app)
    ok('API health',client.get('/health').status_code==200)
    ok('API catalog',len(client.get('/catalog').json())==len(TABLES))
    for name in ['division_sales','monthly_sales','channel_orders']:
        response=client.get('/reports/'+name)
        ok('API '+name,response.status_code==200 and len(response.json()['rows'])>0)
    ok('API rejects unknown report',client.get('/reports/unknown').status_code==400)
    ok('API rejects invalid date',client.get('/reports/monthly_sales?start_date=invalid').status_code==400)
    ok('API rejects reversed dates',client.get('/reports/monthly_sales?start_date=2025-12-31&end_date=2024-01-01').status_code==400)
    result=build_graph().invoke({'report':'division_sales'})['result']
    ok('LangGraph matches direct query',result==run_report('division_sales'))
    ok('4-5-4 year starts',[str(fiscal_start(y)) for y in [2023,2024,2025,2026]]==['2023-01-29','2024-02-04','2025-02-02','2026-02-01'])
    con.close()
    return {'passed':True,'check_count':len(checks),'checks':checks}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data',required=True,type=Path)
    p.add_argument('--replica',required=True,type=Path)
    p.add_argument('--report',type=Path)
    a=p.parse_args()
    report=test(a.data,a.replica)
    print(json.dumps(report,indent=2))
    if a.report:
        a.report.write_text(json.dumps(report,indent=2))
