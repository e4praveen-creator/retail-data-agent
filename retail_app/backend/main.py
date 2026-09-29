import csv
import io
import json
import logging
import os
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Optional
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.responses import FileResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field
from . import data, storage
from .context import INDEX
from .agent import configured, run_agent
from .runtime import JobControl, JobCancelled

@asynccontextmanager
async def lifespan(application):
    global POOL, STOPPING
    with JOB_LOCK:
        if STOPPING:POOL=ThreadPoolExecutor(max_workers=2)
        STOPPING=False
    storage.recover_interrupted_jobs()
    try:
        yield
    finally:
        with JOB_LOCK:
            STOPPING=True
            for job in JOBS.values():
                if job['status'] in ACTIVE_STATUSES and job.get('control'):
                    job['control'].cancel()
        # In-flight HTTP requests finish at their bounded timeout. The shared
        # provider client is closed at process exit, after worker completion.
        POOL.shutdown(wait=False,cancel_futures=True)

app=FastAPI(title='Summit Field · Retail Data Agent',version='0.2.0',lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware,allowed_hosts=['localhost','127.0.0.1','testserver'])
POOL=ThreadPoolExecutor(max_workers=2)
STOPPING=False
JOBS={}; JOB_LOCK=threading.RLock()
LOG=logging.getLogger('retail_app')
ACTIVE_STATUSES={'running','cancelling'}
MAX_JOB_RECORDS=50
MAX_REQUEST_BYTES=64*1024
SECURITY_HEADERS={
    'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'none'; form-action 'self'",
    'X-Content-Type-Options':'nosniff', 'X-Frame-Options':'DENY',
    'Referrer-Policy':'no-referrer', 'Permissions-Policy':'camera=(), microphone=(), geolocation=()',
}

@app.middleware('http')
async def local_origin(request:Request,call_next):
    request_id=str(uuid.uuid4())
    response=None
    # Range requests are unnecessary for bundled app assets; reject them before
    # StaticFiles/FileResponse parses potentially pathological range sets.
    if request.headers.get('range'):
        response=Response('Range requests are not supported',status_code=400)
    if response is None and request.method not in ('GET','HEAD','OPTIONS'):
        origin=request.headers.get('origin')
        if origin and origin not in ('http://localhost:8765','http://127.0.0.1:8765'):
            response=Response('Local app origin required',status_code=403)
        elif request.headers.get('x-retail-app')!='local':
            response=Response('App request header required',status_code=403)
    if response is None:
        try:
            declared=int(request.headers.get('content-length','0'))
            if declared < 0: raise ValueError()
        except ValueError:
            response=Response('Invalid content length',status_code=400)
        else:
            if declared>MAX_REQUEST_BYTES:
                response=Response('Request body is too large',status_code=413)
            elif request.method not in ('GET','HEAD','OPTIONS'):
                chunks=[]; size=0
                async for chunk in request.stream():
                    size+=len(chunk)
                    if size>MAX_REQUEST_BYTES:
                        response=Response('Request body is too large',status_code=413);break
                    chunks.append(chunk)
                if response is None:
                    request._body=b''.join(chunks)
    if response is None:
        try:
            response=await call_next(request)
        except Exception as exc:
            # Log category and correlation ID only. Do not log question bodies,
            # provider details, paths or credentials through raw exception text.
            LOG.error('Request failed id=%s category=%s',request_id,type(exc).__name__)
            response=Response(json.dumps({'detail':'The request could not be completed. Try again or check the local service.','request_id':request_id}),status_code=500,media_type='application/json')
    for key,value in SECURITY_HEADERS.items():response.headers[key]=value
    response.headers['X-Request-ID']=request_id
    if request.url.path.startswith('/api/') or request.url.path=='/':
        response.headers['Cache-Control']='no-store'
    return response

@app.exception_handler(ValueError)
async def invalid(request,exc):
    detail=str(exc)
    code=404 if detail in ('Conversation not found.','Analysis not found.','Job not found.') else 400
    return Response(json.dumps({'detail':detail[:1000]}),status_code=code,media_type='application/json')

@app.get('/health/live')
def health_live():return {'status':'ok'}

@app.get('/health/ready')
def health_ready():
    try:
        if not data.DB.is_file():raise OSError()
        with data.connect() as con:con.execute('SELECT 1')
        with storage.connection() as con:con.execute('SELECT 1')
        return {'status':'ready','agent_ready':configured(),'mode':'local_single_user'}
    except Exception:
        raise HTTPException(503,'Local data or conversation storage is unavailable.')

class Scope(BaseModel):
    start:str=Field(default='2025-01-05',pattern=r'^\d{4}-\d{2}-\d{2}$',max_length=10)
    end:str=Field(default='2025-12-27',pattern=r'^\d{4}-\d{2}-\d{2}$',max_length=10)
    compare_start:Optional[str]=Field(default=None,pattern=r'^\d{4}-\d{2}-\d{2}$',max_length=10)
    compare_end:Optional[str]=Field(default=None,pattern=r'^\d{4}-\d{2}-\d{2}$',max_length=10)
    def dates(self): return data.dates_for(self.start,self.end,self.compare_start,self.compare_end)
class Analysis(Scope):
    slug:str
class CleanTextModel(BaseModel):
    model_config={"str_strip_whitespace":True}

class Question(Scope,CleanTextModel):
    question:str=Field(min_length=1,max_length=4000)
    previous_id:Optional[str]=None
class Memory(CleanTextModel):
    text:str=Field(min_length=3,max_length=2000)
    source:str=Field(min_length=3,max_length=500)

GAPS=[
 {'priority':'Next','title':'Connect the reasoning model','detail':'Set OPENAI_API_KEY and OPENAI_MODEL on the server. The single-agent LangGraph loop is implemented; live model execution is unverified until credentials and model access are supplied.'},
 {'priority':'Data','title':'Scenario ground truth','detail':'Existing data contains generation assumptions, not labeled causal incidents. Add scenario controls, expected findings, and a wider question / golden-SQL evaluation set.'},
 {'priority':'Data','title':'Raw-to-curated enterprise context','detail':'Generation code, DDL and analytical views are indexed. Separate raw ingestion tables, transformation jobs, operational lineage, usage telemetry and SME business-event annotations are not present.'},
 {'priority':'Coverage','title':'Deeper playbook implementations','detail':'All 19 existing baseline recipes run. Full A–I coverage still needs filtered offline reports, weekly business review synthesis, reactivation transitions, full promotion timelines and advanced visual diagnostics.'},
 {'priority':'Data','title':'Evidence for causal and operational questions','detail':'Add experiments for promotion incrementality and price elasticity; sessions/carts for conversion; daily inventory and demand for lost sales; actual delivery events and costs for service and profitability.'},
 {'priority':'Quality','title':'Broader agent evaluation','detail':'Local report regressions and selected independent golden SQL checks are included. Broader live-model regression, claim-to-evidence grading, retrieval relevance and adversarial questions still need reviewed expected answers.'},
 {'priority':'Later','title':'Production operations','detail':'This is a local single-user app with bounded jobs, cancellation and durable history. Authentication, access roles, managed secrets, scheduled refresh, durable job resumption and external monitoring require a managed deployment.'}
]

@app.get('/api/status')
def status():
    manifest=json.loads((data.DB.parent/'manifest.json').read_text())
    return {'ready':data.DB.is_file(),'dataset':'Synthetic Summit Field','orders':manifest['transaction_headers'],'skus':manifest['sku_count'],'stores':manifest['stores'],
      'sales_start':manifest['sales_start'],'sales_end':manifest['sales_end'],'returns_through':manifest['as_of_date'],
      'agent_ready':configured(),'model':os.getenv('OPENAI_MODEL'),'documents':len(INDEX.documents),'chunks':len(INDEX.chunks),'specialists':['Hypothesis Agent','EDA Agent','RCA Agent'],'chat_ready':True,'hypothesis_count':18,
      'playbooks':[{'slug':s,'title':data.TITLES[i],'number':i+1,'note':data.NOTES.get(s,'All-business baseline; before returns.')} for i,s in enumerate(data.SLUGS)],'gaps':GAPS[1:] if configured() else GAPS}

@lru_cache(maxsize=16)
def cached_overview(start,end,compare_start,compare_end):
    dates=data.dates_for(start,end,compare_start,compare_end)
    return {'kpis':data.overview(dates),'trend':data.run_playbook('trend',dates),'growth':data.run_playbook('growth',dates)}

@app.get('/api/overview')
def overview(start='2025-01-05',end='2025-12-27',compare_start:Optional[str]=None,compare_end:Optional[str]=None):
    return cached_overview(start,end,compare_start,compare_end)


def _reserve_job(identity=None):
    """Caller holds JOB_LOCK so capacity check and admission cannot race."""
    if STOPPING:raise HTTPException(503,'The app is restarting; retry in a moment.')
    completed=sorted((key for key,j in JOBS.items() if j['status'] not in ACTIVE_STATUSES),key=lambda key:JOBS[key]['started'])
    for key in completed:
        if len(JOBS)>=MAX_JOB_RECORDS or time.time()-JOBS[key]['started']>3600:
            del JOBS[key]
    if sum(j['status'] in ACTIVE_STATUSES for j in JOBS.values())>=2:
        raise HTTPException(429,'Two analyses are already running. Wait for one to finish.')
    identity=identity or str(uuid.uuid4())
    JOBS[identity]={'status':'running','message':'Loading context and querying the warehouse','started':time.time()}
    return identity


def _public_error(exc):
    # ValueErrors raised by our validation/agent boundary contain curated user
    # guidance. Database/provider/internal exceptions are never copied to clients.
    if isinstance(exc,ValueError):return str(exc)[:1000]
    LOG.error('Background analysis failed category=%s',type(exc).__name__)
    return 'The analysis could not finish. Retry with a narrower question or restart the local service.'


def submit(work):
    with JOB_LOCK:identity=_reserve_job()
    def notify(message):
        with JOB_LOCK:JOBS[identity]['message']=str(message)[:500]
    control=JobControl(notify)
    with JOB_LOCK:JOBS[identity]['control']=control
    def execute():
        try:
            control.check_cancelled()
            with data.query_control(control):result=work(control)
            control.check_cancelled()
            with JOB_LOCK:JOBS[identity].update(status='complete',result=result)
        except Exception as exc:
            with JOB_LOCK:JOBS[identity].update(status='cancelled' if isinstance(exc,JobCancelled) else 'error',error=_public_error(exc))
    try:POOL.submit(execute)
    except RuntimeError:
        with JOB_LOCK:JOBS.pop(identity,None)
        raise HTTPException(503,'The app is restarting; retry in a moment.')
    return {'job_id':identity}

@app.post('/api/analyze')
def analyze(req:Analysis):
    dates=req.dates()
    if req.slug not in data.SLUGS: raise ValueError('Unknown playbook.')
    def work(notify):
        report=data.run_playbook(req.slug,dates)
        payload={'mode':'playbook','question':report['title'],'answer':report['summary'],'report':report,'period':report['period'],
          'outputs':report['outputs'],'warnings':report['warnings'],'context':INDEX.search(report['title']),
          'trace':[{'tool':'run_playbook','status':'complete','detail':{'slug':req.slug,'scope':report['scope']}}]}
        return storage.save_analysis(report['title'],payload)
    return submit(work)

ROUTES={'trend':['sales','trend','growing','growth','doing'],'pvm':['price volume','mix','revenue gap'],'growth':['contribution','drivers','decline'],'margin':['margin','profit'],'seasonality':['season','holiday'], 'scorecard':['scorecard','brand','category'],'channels':['channel','store','region'],'concentration':['pareto','concentration','dependent'], 'pricing':['pricing','markdown','price'],'promotions':['promotion','campaign'],'cohorts':['cohort','repeat','retention'],'lapse':['lapse','quiet','win back'],'segments':['segment'],'affinity':['affinity','together','cross-sell'],'loyalty':['loyalty'],'returns':['return','refund'],'velocity':['velocity','slow mover'],'inventory':['inventory','stock'],'fulfillment':['fulfillment','pickup','shipping']}

@app.post('/api/ask')
def ask(req:Question):
    dates=req.dates()
    if not configured():
        q=req.question.lower()
        ranked=sorted(((sum(t in q for t in terms),slug) for slug,terms in ROUTES.items()),reverse=True)
        slugs=[s for score,s in ranked if score][:3]
        unsupported=any(x in q for x in ['market share','incremental','elasticity','conversion','abandon','lost sales','on time','on-time'])
        return {'mode':'suggestions','message':('This question needs evidence absent from the current dataset. See the data gaps below.' if unsupported else 'Local mode can run the playbooks below. These are all-business baselines using the date controls; your free-text filters have not been applied. Enable the reasoning model for open-ended questions and scoped SQL.'),'suggestions':[] if unsupported else slugs,'context':INDEX.search(req.question),'gaps':GAPS if unsupported else []}
    prior=storage.get_analysis(req.previous_id) if req.previous_id else None
    return submit(lambda notify:storage.save_analysis(req.question,run_agent(req.question,dates,prior,notify)))

@app.get('/api/jobs/{identity}')
def job(identity:str):
    with JOB_LOCK:
        if identity not in JOBS: raise HTTPException(404,'Job not found; interrupted jobs do not survive a server restart.')
        return {key:value for key,value in JOBS[identity].items() if key!='control'}
@app.get('/api/history')
def history(): return storage.history()
@app.get('/api/history/{identity}')
def history_item(identity:str): return storage.get_analysis(identity)
@app.get('/api/context')
def context(q:str=''): return {'documents':INDEX.documents,'matches':INDEX.search(q) if q else []}
@app.get('/api/document')
def document(path:str): return PlainTextResponse(INDEX.document(path))
@app.get('/api/catalog')
def catalog(): return data.CATALOG
@app.get('/api/inspect/{table}')
def inspect(table:str): return data.inspect_table(table)
@app.get('/api/memory')
def memory(): return storage.memories()
@app.post('/api/memory')
def memory_add(req:Memory): return storage.save_memory(req.text,req.source)
@app.get('/api/quality')
def quality():
    path=data.APP/'state/eval_report.json'
    existing=json.loads((data.ROOT/'retail_data/docs/full_validation_report.json').read_text())
    live_path=data.APP/'state/live_smoke/summary.json'
    live=json.loads(live_path.read_text()) if live_path.exists() else None
    return {'app_evals':json.loads(path.read_text()) if path.exists() else None,'dataset_validation':existing,
      'live_agent_tested':bool(live and live.get('passed') and live.get('model')==os.getenv('OPENAI_MODEL')),
      'live_agent_evaluation':live}

@app.get('/api/export/{identity}')
def export(identity:str,format:str='json',output:int=0):
    result=storage.get_analysis(identity)
    if format=='json': return Response(json.dumps(result,indent=2),media_type='application/json',headers={'Content-Disposition':f'attachment; filename="analysis-{identity}.json"'})
    if format!='csv': raise ValueError('Export format must be json or csv.')
    outputs=result.get('outputs',[])
    if output<0 or output>=len(outputs): raise ValueError('Unknown output table.')
    rows=outputs[output]['rows']; stream=io.StringIO()
    def safe(v):
        if isinstance(v,str) and v[:1] in '=+-@\t\r': return "'"+v
        return v
    if rows:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader()
        for row in rows: writer.writerow({k:safe(v) for k,v in row.items()})
    filename=re.sub(r'[^a-zA-Z0-9_.-]','_',str(outputs[output]['name']))[:100] or 'evidence'
    return Response(stream.getvalue(),media_type='text/csv',headers={'Content-Disposition':f'attachment; filename="{filename}.csv"'})

app.mount('/static',StaticFiles(directory=str(data.APP/'static')),name='static')
@app.get('/')
def home(): return FileResponse(data.APP/'static/index.html')

# Chat-first API. Completed conversations survive reloads and process restarts.
from .agent import run_investigation
CHAT_LOCK=threading.Lock()

class ChatMessage(Scope,CleanTextModel):
    conversation_id:Optional[str]=None
    question:str=Field(min_length=1,max_length=8000)
    mode:str='auto'
    playbook:Optional[str]=None
    hypothesis_id:Optional[str]=None
    retry:bool=False
class ConversationTitle(CleanTextModel):
    title:str=Field(min_length=1,max_length=100)

@app.get('/api/conversations')
def list_conversations(): return storage.conversations()
@app.post('/api/conversations')
def new_conversation(req:ConversationTitle): return storage.create_conversation(req.title)
@app.get('/api/conversations/{identity}')
def get_conversation(identity:str,before:Optional[int]=Query(default=None,ge=1),limit:int=Query(default=50,ge=1,le=100)): return storage.conversation(identity,before,limit)
@app.post('/api/conversations/{identity}/rename')
def rename_chat(identity:str,req:ConversationTitle): return storage.rename_conversation(identity,req.title)
@app.get('/api/chat/jobs/{identity}')
def chat_job_status(identity:str):
    with JOB_LOCK:
        job=storage.get_chat_job(identity)
        live=JOBS.get(identity)
        # A transient disk/SQLite failure can prevent the terminal write after
        # a worker has stopped. Reconcile once storage is available again, so
        # polling cannot leave the chat permanently marked as running.
        if live and live['status'] not in ACTIVE_STATUSES and job['status'] in ACTIVE_STATUSES:
            storage.chat_job(identity,job['conversation_id'],live['status'],live.get('message','Answer ended'),live.get('error',''))
            job=storage.get_chat_job(identity)
        return job

@app.post('/api/chat/jobs/{identity}/cancel')
def cancel_chat_job(identity:str):
    with CHAT_LOCK,JOB_LOCK:
        job=storage.get_chat_job(identity)
        if job['status'] not in ACTIVE_STATUSES:return job
        live=JOBS.get(identity)
        if not live or not live.get('control'):
            storage.chat_job(identity,job['conversation_id'],'interrupted','The server restarted. Retry your question.')
        else:
            live['control'].cancel()
            live.update(status='cancelling',message='Stopping the current step…')
            storage.chat_job(identity,job['conversation_id'],'cancelling','Stopping the current step…')
        return storage.get_chat_job(identity)

@app.delete('/api/conversations/{identity}')
def delete_chat(identity:str):
    with CHAT_LOCK,JOB_LOCK:
        if storage.conversation(identity)['active_job']:
            raise HTTPException(409,'Stop the active answer and wait for it to finish before deleting this chat.')
        return storage.delete_conversation(identity)

@app.post('/api/chat')
def chat(req:ChatMessage):
    dates=req.dates()
    if req.mode not in ('auto','deep'):raise ValueError('Choose auto or deep investigation mode.')
    if req.playbook and req.playbook not in data.SLUGS:raise ValueError('Unknown playbook.')
    if req.playbook and req.hypothesis_id:raise ValueError('Choose one playbook or hypothesis test at a time.')
    if req.hypothesis_id:
        from .analytics import BANK
        if req.hypothesis_id not in {h['id'] for h in BANK}:raise ValueError('Unknown hypothesis.')
    offline=not configured() and not req.playbook and not req.hypothesis_id
    with CHAT_LOCK,JOB_LOCK:
        # Admission happens before writing the prompt; rejected requests cannot
        # leave an orphan user message or consume an unbounded executor queue.
        if STOPPING:raise HTTPException(503,'The app is restarting; retry in a moment.')
        if sum(j['status'] in ACTIVE_STATUSES for j in JOBS.values())>=2:
            raise HTTPException(429,'Two analyses are already running. Wait for one to finish.')
        identity=req.conversation_id or storage.create_conversation(req.question[:80])['id']
        conv=storage.conversation(identity)
        if conv['active_job']:raise HTTPException(409,'This conversation already has an answer in progress.')
        last=conv['messages'][-1] if conv['messages'] else None
        if req.retry and (not last or last['role']!='user' or last['text']!=req.question):
            raise ValueError('Retry requires the last unanswered question in this chat.')
        prior_messages=conv['messages'][:-1] if req.retry else conv['messages']
        prior={'messages':[{'role':m['role'],'content':m['text']} for m in prior_messages[-12:]],'last_period':next((m['analysis']['period'] for m in reversed(prior_messages) if m.get('analysis')),None)}
        if not req.retry:storage.add_message(identity,'user',req.question)
        if offline:
            suggested=ask(Question(question=req.question[:4000],start=req.start,end=req.end,compare_start=req.compare_start,compare_end=req.compare_end))
            payload={'mode':'suggestions','question':req.question,'answer':suggested['message'],'suggestions':suggested.get('suggestions',[]),'period':data.clean(dates),'outputs':[],'warnings':['The reasoning model is not configured. No open-ended investigation has been run.'],'context':suggested.get('context',[]),'trace':[],'specialists':[]}
            storage.finish_chat(identity,None,req.question,payload)
            return {'conversation_id':identity,'conversation':storage.conversation(identity)}
        job_id=_reserve_job()
        try:
            storage.chat_job(job_id,identity,'running','Retrieving relevant context')
        except Exception:
            # No worker exists yet; failure to persist admission must not leak
            # one of the two running slots. The saved question can be retried.
            JOBS.pop(job_id,None)
            raise
        def notify(message):
            with JOB_LOCK:
                if JOBS[job_id]['status']!='running':return
                storage.chat_job(job_id,identity,'running',str(message)[:500])
                JOBS[job_id]['message']=str(message)[:500]
        control=JobControl(notify)
        JOBS[job_id]['control']=control
    def do_work():
        try:
            control.check_cancelled()
            if req.hypothesis_id:
                from .hypotheses import execute_hypothesis
                tested=execute_hypothesis(req.hypothesis_id,dates);report=tested['report']
                payload={'mode':'hypothesis_test','question':req.question,'answer':report['summary']+'\n\nTest criterion: '+tested['hypothesis']['falsifier'],'report':report,'period':report['period'],'outputs':report['outputs'],'warnings':report['warnings'],'context':INDEX.search(tested['hypothesis']['hypothesis']),'trace':[{'tool':'execute_hypothesis','status':'complete','detail':req.hypothesis_id}],'specialists':[],'hypothesis':tested['hypothesis']}
            elif req.playbook:
                report=data.run_playbook(req.playbook,dates)
                payload={'mode':'playbook','question':req.question,'answer':report['summary'],'report':report,'period':report['period'],'outputs':report['outputs'],'warnings':report['warnings'],'context':INDEX.search(report['title']),'trace':[{'tool':'run_playbook','status':'complete','detail':req.playbook}],'specialists':[]}
            else:
                fn=run_investigation if req.mode=='deep' else run_agent
                payload=fn(req.question,dates,prior,control)
            with JOB_LOCK:
                control.check_cancelled()
                payload=storage.finish_chat(identity,job_id,req.question,payload)
                # Durable payload is fetched through the conversation. Keeping
                # another full copy per completed chat would grow process memory.
                JOBS[job_id].update(status='complete',message='Answer ready')
        except Exception as exc:
            cancelled=isinstance(exc,JobCancelled)
            message='Answer stopped. You can retry your question.' if cancelled else _public_error(exc)
            with JOB_LOCK:
                terminal='cancelled' if cancelled else 'error'
                try:
                    storage.chat_job(job_id,identity,terminal,message if cancelled else 'Could not complete this answer','' if cancelled else message)
                finally:
                    JOBS[job_id].update(status=terminal,message=message,error='' if cancelled else message)
    def work():
        with data.query_control(control):do_work()
    try:POOL.submit(work)
    except RuntimeError:
        with JOB_LOCK:
            JOBS[job_id].update(status='error')
            storage.chat_job(job_id,identity,'error','The app is restarting; retry in a moment.')
        raise HTTPException(503,'The app is restarting; retry in a moment.')
    return {'conversation_id':identity,'job_id':job_id}

from .analytics import hypothesis_bank,profile_column
@app.get('/api/hypotheses')
def hypotheses(q:str=''): return hypothesis_bank(q)
@app.get('/api/profile/{table}/{column}')
def profile(table:str,column:str): return profile_column(table,column)

class Feedback(BaseModel):
    analysis_id:str
    rating:str
    comment:str=Field(default='',max_length=2000)
@app.post('/api/feedback')
def feedback(req:Feedback):
    storage.get_analysis(req.analysis_id)
    if req.rating not in ('helpful','needs_review'): raise ValueError('Unknown feedback rating.')
    with storage.connection() as con:
        con.execute('CREATE TABLE IF NOT EXISTS feedback(id TEXT PRIMARY KEY,analysis_id TEXT,rating TEXT,comment TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP)')
        con.execute('INSERT INTO feedback(id,analysis_id,rating,comment) VALUES(?,?,?,?)',(str(uuid.uuid4()),req.analysis_id,req.rating,req.comment))
    return {'saved':True,'note':'Feedback saved for human review; no automatic prompt changes or training performed.'}
