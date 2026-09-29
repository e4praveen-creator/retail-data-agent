"""Compare exported Parquet with DuckDB exactly, in bounded monthly batches."""
import argparse
import json
from pathlib import Path
import duckdb
from catalog import TABLES


def verify(data):
    data=data.resolve()
    con=duckdb.connect(str(data/'retail.duckdb'),read_only=True)
    con.execute("SET memory_limit='2GB'")
    con.execute('SET threads=2')
    con.execute('SET preserve_insertion_order=false')
    checks=[]
    for table in TABLES:
        folder=data/'parquet'/table
        partitioned=folder.is_dir()
        path=folder/'**/*.parquet' if partitioned else data/'parquet'/f'{table}.parquet'
        quoted="'"+str(path).replace("'","''")+"'"
        source=f'read_parquet({quoted},hive_partitioning=true)'
        select='SELECT *'+(' EXCLUDE(partition_month)' if partitioned else '')+' FROM '+source
        different=0
        if partitioned:
            key={'fact_transaction':'date_key','fact_sales_line':'date_key','fact_return_line':'return_date_key','fact_inventory_weekly':'week_end_date_key'}[table]
            months=con.execute(f'SELECT DISTINCT {key}//100 FROM {table} UNION SELECT DISTINCT partition_month FROM {source}').fetchall()
            batches=[(f'SELECT * FROM {table} WHERE {key}//100={m[0]}',select+f' WHERE partition_month={m[0]}') for m in months]
        else:
            batches=[(f'SELECT * FROM {table}',select)]
        for a,b in batches:
            different+=con.execute(f'SELECT count(*) FROM (({a} EXCEPT ALL {b}) UNION ALL ({b} EXCEPT ALL {a}))').fetchone()[0]
        checks.append({'table':table,'different_rows':different,'passed':different==0})
        print(f'{table}: {different} differences',flush=True)
    con.close()
    return {'passed':all(x['passed'] for x in checks),'check_count':len(checks),'method':'Exact bidirectional EXCEPT ALL in monthly batches','checks':checks}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data',type=Path,default=Path('data/full'))
    p.add_argument('--report',type=Path)
    a=p.parse_args()
    result=verify(a.data)
    if a.report:
        a.report.write_text(json.dumps(result,indent=2))
    print(json.dumps({'passed':result['passed'],'check_count':result['check_count']}))
    raise SystemExit(0 if result['passed'] else 1)
