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
from . import data, storage, investigations, scope as scoped
from .context import INDEX
from .agent import configured, run_agent
from .runtime import JobControl, JobCancelled
from . import workspace_runtime as workspace

@asynccontextmanager
async def lifespan(application):
    global POOL, STOPPING
    with JOB_LOCK:
        if STOPPING:POOL=ThreadPoolExecutor(max_workers=2)
        STOPPING=False
    storage.recover_interrupted_jobs()
    from .workspace_assets import ensure_initialized
    from .workspace_evaluations import recover_interrupted_runs
    ensure_initialized()
    recover_interrupted_runs()
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
        from .workspace_evaluations import shutdown
        shutdown()

app=FastAPI(title='Milky Way 2.0 · Retail Agent',version='2.1.1',lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware,allowed_hosts=['localhost','127.0.0.1','testserver'])
POOL=ThreadPoolExecutor(max_workers=2)
STOPPING=False
JOBS={}; JOB_LOCK=threading.RLock()
LOG=logging.getLogger('retail_app')
ACTIVE_STATUSES={'running','cancelling'}
MAX_JOB_RECORDS=50
# Keep HTTP boundaries and documentation serving separate from job orchestration.
from .http_boundary import local_origin, MAX_REQUEST_BYTES, MAX_WORKSPACE_REQUEST_BYTES
from .guide_api import router as guide_router

app.middleware('http')(local_origin)
app.include_router(guide_router)

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
      'agent_ready':configured(),'model':os.getenv('OPENAI_MODEL'),'documents':len(INDEX.documents),'chunks':len(INDEX.chunks),'specialists':[],'product':'Milky Way 2.0','capabilities':['Conversation','Analytics','Charts','Playbooks','Hypotheses','EDA','RCA','Session memory'],'chat_ready':True,'hypothesis_count':18,
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
    snapshot=workspace.capture()
    def work(notify):
        report=data.run_playbook(req.slug,dates)
        payload={'mode':'playbook','question':report['title'],'answer':report['summary'],'report':report,'period':report['period'],
          'outputs':report['outputs'],'warnings':report['warnings'],'context':workspace.search(snapshot,report['title']),
          'trace':[{'tool':'run_playbook','status':'complete','detail':{'slug':req.slug,'scope':report['scope']}}]}
        return storage.save_analysis(report['title'],workspace.attach(payload,snapshot,report['title']))
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
    snapshot=workspace.capture()
    return submit(lambda notify:storage.save_analysis(req.question,run_agent(req.question,dates,prior,notify,workspace_snapshot=snapshot)))

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
def document(path:str):
    if path.startswith('workspace/'):
        from .workspace_assets import read_version_source
        return PlainTextResponse(read_version_source(path)['text'])
    return PlainTextResponse(INDEX.document(path))
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
CHAT_LOCK=threading.RLock()

class ChatMessage(Scope,CleanTextModel):
    conversation_id:Optional[str]=None
    question:str=Field(min_length=1,max_length=8000)
    mode:str='auto'
    playbook:Optional[str]=None
    hypothesis_id:Optional[str]=None
    retry:bool=False
    output_profile_id:Optional[str]=Field(default=None,max_length=100)
class ConversationTitle(CleanTextModel):
    title:str=Field(min_length=1,max_length=100)

@app.get('/api/conversations')
def list_conversations(): return storage.conversations()
@app.post('/api/conversations')
def new_conversation(req:ConversationTitle): return storage.create_conversation(req.title)
@app.get('/api/conversations/{identity}')
def get_conversation(identity:str,before:Optional[int]=Query(default=None,ge=1),limit:int=Query(default=50,ge=1,le=100)):
    result=storage.conversation(identity,before,limit)
    result['session']=investigations.get_session(identity)
    result['investigation']=investigations.current_investigation(identity)
    return result
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
    snapshot=workspace.capture()
    profile_id=req.output_profile_id
    if req.conversation_id and profile_id is None:
        profile_id=investigations.get_session(req.conversation_id).get('preferences',{}).get('output_profile_id')
    selected=workspace.settings(snapshot,req.question,profile_id)
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
        if req.output_profile_id:
            preferences=investigations.get_session(identity).get('preferences',{})
            investigations.update_session(identity,{'preferences':{**preferences,'output_profile_id':req.output_profile_id}})
        prior_messages=conv['messages'][:-1] if req.retry else conv['messages']
        prior={'messages':[{'role':m['role'],'content':m['text']} for m in prior_messages[-12:]],'last_period':next((m['analysis']['period'] for m in reversed(prior_messages) if m.get('analysis')),None)}
        if not req.retry:storage.add_message(identity,'user',req.question)
        if offline:
            suggested=ask(Question(question=req.question[:4000],start=req.start,end=req.end,compare_start=req.compare_start,compare_end=req.compare_end))
            payload={'mode':'suggestions','question':req.question,'answer':suggested['message'],'suggestions':suggested.get('suggestions',[]),'period':data.clean(dates),'outputs':[],'warnings':['The reasoning model is not configured. No open-ended investigation has been run.'],'context':suggested.get('context',[]),'trace':[],'specialists':[]}
            payload['context']=workspace.search(snapshot,req.question)
            storage.finish_chat(identity,None,req.question,workspace.attach(payload,snapshot,req.question,profile_id,resolved=selected))
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
                if (investigations.get_session(identity).get('scope') or {}).get('filters'):
                    raise ValueError('Ask the Retail Agent to test this hypothesis in your active scope; the fixed bank recipe is an all-business baseline.')
                from .hypotheses import execute_hypothesis
                tested=execute_hypothesis(req.hypothesis_id,dates);report=tested['report']
                payload={'mode':'hypothesis_test','question':req.question,'answer':report['summary']+'\n\nTest criterion: '+tested['hypothesis']['falsifier'],'report':report,'period':report['period'],'outputs':report['outputs'],'warnings':report['warnings'],'context':INDEX.search(tested['hypothesis']['hypothesis']),'trace':[{'tool':'execute_hypothesis','status':'complete','detail':req.hypothesis_id}],'specialists':[],'hypothesis':tested['hypothesis']}
            elif req.playbook:
                session=investigations.get_session(identity)
                from .conversation import prepare_turn
                active_scope=prepare_turn(req.question,dates,prior,identity)['scope']
                report=scoped.run_scoped_playbook(req.playbook,dates,active_scope)
                payload={'mode':'playbook','question':req.question,'answer':report['summary'],'report':report,'period':report['period'],'outputs':report['outputs'],'warnings':report['warnings'],'context':INDEX.search(report['title']),'trace':[{'tool':'run_playbook','status':'complete','detail':req.playbook}],'specialists':[]}
            else:
                payload=run_agent(req.question,dates,prior,control,conversation_id=identity,workspace_snapshot=snapshot,output_profile_id=profile_id)
            if not payload.get('workspace'):
                payload['context']=workspace.search(snapshot,req.question)
                payload=workspace.attach(payload,snapshot,req.question,profile_id,resolved=selected)
            with JOB_LOCK:
                control.check_cancelled()
                if payload.get('investigation') and payload.get('investigation_revision') is not None:
                    current=investigations.get_investigation(payload['investigation']['id'])
                    if current['revision']!=payload['investigation_revision']:
                        raise ValueError('The investigation changed. Continue from the updated hypotheses.')
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


# Milky Way 2.0: durable session context and editable investigations.
@app.get('/api/conversations/{identity}/session')
def session_state(identity:str):
    storage.conversation(identity)
    return investigations.get_session(identity)


@app.get('/api/scope/capabilities')
def scope_capabilities():
    return scoped.query_capabilities()


class ScopeEdit(BaseModel):
    scope:dict
    expected_revision:int=Field(ge=0)


@app.patch('/api/conversations/{identity}/scope')
def edit_scope(identity:str,req:ScopeEdit):
    with CHAT_LOCK,JOB_LOCK:
        storage.conversation(identity)
        session=investigations.get_session(identity)
        if session['revision']!=req.expected_revision:
            raise HTTPException(409,'This chat scope changed. Reload it before saving your edits.')
        normalized=scoped.normalize_scope(req.scope,previous=session.get('scope'))
        edited_dates=normalized.get('dates') or {}
        if edited_dates.get('start') and edited_dates.get('end'):
            # This editor feeds the top-level chat date controls. Validate the
            # same contract now, rather than accepting an unusable next turn.
            data.dates_for(**edited_dates)
        result=investigations.update_session(identity,{'scope':normalized})
        _stop_superseded(identity)
        return {'session':result,'investigation':investigations.current_investigation(identity)}

@app.get('/api/conversations/{identity}/investigation')
def investigation_state(identity:str):
    storage.conversation(identity)
    return investigations.current_investigation(identity)

class HypothesisEdit(CleanTextModel):
    expected_revision:int=Field(ge=1)
    statement:Optional[str]=Field(default=None,max_length=2000)
    test:Optional[str]=Field(default=None,max_length=4000)
    falsifier:Optional[str]=Field(default=None,max_length=2000)
    parent_id:Optional[str]=None
    excluded:Optional[bool]=None


def _stop_superseded(conversation_id):
    active=storage.conversation(conversation_id)['active_job']
    if active:cancel_chat_job(active['id'])

@app.patch('/api/investigations/{identity}/hypotheses/{node_id}')
def edit_hypothesis(identity:str,node_id:str,req:HypothesisEdit):
    with CHAT_LOCK,JOB_LOCK:
        patch=req.model_dump(exclude_unset=True);revision=patch.pop('expected_revision')
        result=investigations.edit_hypothesis(identity,node_id,patch,expected_revision=revision)
        _stop_superseded(result['conversation_id'])
        return result

@app.post('/api/investigations/{identity}/hypotheses')
def add_hypothesis(identity:str,req:HypothesisEdit):
    with CHAT_LOCK,JOB_LOCK:
        node=req.model_dump(exclude_none=True);revision=node.pop('expected_revision')
        node.setdefault('kind','mechanism')
        current=investigations.get_investigation(identity)
        used={n['id'] for n in current['hypotheses']};number=len(used)+1
        while 'H'+str(number) in used:number+=1
        node['id']='H'+str(number)
        result=investigations.upsert_hypothesis(identity,node,expected_revision=revision)
        _stop_superseded(result['conversation_id'])
        return result

@app.post('/api/investigations/{identity}/continue')
def continue_investigation(identity:str):
    investigation=investigations.get_investigation(identity)
    session=investigations.get_session(investigation['conversation_id'])
    dates=session.get('ui_dates') or {}
    question='Continue the current investigation. Keep user edits and exclusions. Test or retest the planned/stale leaf hypotheses, reuse valid evidence, and summarize supported, contradicted, unresolved and data-missing findings.'
    return chat(ChatMessage(conversation_id=investigation['conversation_id'],question=question,**{k:v for k,v in dates.items() if v}))


from .workspace_api import router as workspace_router
from .evaluation_api import router as evaluation_router
app.include_router(workspace_router)
app.include_router(evaluation_router)
