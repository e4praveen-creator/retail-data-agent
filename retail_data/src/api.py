"""Local, read-only report API. Start: uvicorn api:app --app-dir src"""
import json
from fastapi import FastAPI, HTTPException
from reports import DATA_DIR, REPORTS, run_report

app=FastAPI(title='Synthetic Retail Dataset',version='1.0.0',description='Fictional Summit Field retail data. No model key required. Read-only named reports.')

@app.get('/health')
def health():
    ready=(DATA_DIR/'manifest.json').is_file() and (DATA_DIR/'retail.duckdb').is_file()
    if not ready:
        raise HTTPException(503,'Dataset not ready; generate it first.')
    manifest=json.loads((DATA_DIR/'manifest.json').read_text())
    return {'status':'ready','transactions':manifest['transaction_headers'],'reports':list(REPORTS)}

@app.get('/catalog')
def catalog():
    path=DATA_DIR/'metadata'/'catalog.json'
    if not path.exists():
        raise HTTPException(503,'Dataset not ready.')
    return json.loads(path.read_text())

@app.get('/reports/{report}')
def report(report: str,start_date: str='2024-01-01',end_date: str='2025-12-31'):
    try:
        return run_report(report,start_date,end_date)
    except ValueError as e:
        raise HTTPException(400,str(e)) from e
    except FileNotFoundError as e:
        raise HTTPException(503,str(e)) from e
