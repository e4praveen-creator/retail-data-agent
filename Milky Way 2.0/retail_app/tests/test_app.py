"""Real-warehouse regressions + independent golden SQL + API and agent-loop tests.
Run from project root: .venv/bin/python -m retail_app.tests.test_app
"""
import json
import os
import tempfile
import time
import unittest
import httpx
from pathlib import Path
from unittest.mock import patch
_tmp=tempfile.TemporaryDirectory()
os.environ['RETAIL_STATE_DIR']=_tmp.name
from fastapi.testclient import TestClient
from retail_app.backend import data, agent
from retail_app.backend.main import app
from retail_app.backend.context import INDEX

DATES=data.dates_for('2025-01-05','2025-12-27')
HEADERS={'X-Retail-App':'local'}
class ReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results={s:data.run_playbook(s,DATES) for s in data.SLUGS}
    def test_golden_trend_against_transaction_headers(self):
        """Line-based weekly sums must match independent order header totals."""
        with data.connect() as con:
            gold=con.execute('SELECT sum(net_sales_cents),sum(units),count(*) FROM fact_transaction WHERE date_key BETWEEN 20250105 AND 20251227').fetchone()
        rows=[r for r in self.results['trend']['outputs'][0]['rows'] if r['period']=='current']
        self.assertEqual(tuple(sum(r[k] for r in rows) for k in ['sales_before_returns_cents','sold_units','orders']),gold)
    def test_golden_growth_against_header_deltas(self):
        with data.connect() as con:
            gold=con.execute('SELECT sum(CASE WHEN date_key BETWEEN 20250105 AND 20251227 THEN net_sales_cents ELSE -net_sales_cents END) FROM fact_transaction WHERE date_key BETWEEN 20250105 AND 20251227 OR date_key BETWEEN 20240107 AND 20241228').fetchone()[0]
        self.assertEqual(sum(r['change_cents'] for r in self.results['growth']['outputs'][0]['rows']),gold)
        self.assertEqual(self.results['pvm']['outputs'][0]['rows'][0]['change_cents'],gold)
    def test_golden_margin_against_independent_facts(self):
        sql='''WITH s AS (SELECT sum(net_sales_cents-cost_of_goods_cents) margin FROM fact_sales_line WHERE date_key BETWEEN 20250105 AND 20251227),
         r AS (SELECT sum(r.refund_net_cents-r.recovered_cost_cents) deduction FROM fact_return_line r JOIN fact_sales_line l USING(sales_line_key) WHERE l.date_key BETWEEN 20250105 AND 20251227)
         SELECT s.margin-r.deduction FROM s,r'''
        with data.connect() as con: gold=con.execute(sql).fetchone()[0]
        rows=self.results['margin']['outputs'][0]['rows']
        self.assertEqual(sum(r['merchandise_margin_cents'] for r in rows if r['period']=='current'),gold)
    def test_golden_returns_from_original_cohort(self):
        with data.connect() as con:
            gold=con.execute('SELECT sum(r.returned_quantity) FROM fact_return_line r JOIN fact_sales_line s USING(sales_line_key) WHERE s.date_key BETWEEN 20250105 AND 20251227').fetchone()[0]
        self.assertEqual(sum(r['returned_units'] for r in self.results['returns']['outputs'][0]['rows']),gold)
    def test_golden_inventory_single_snapshot(self):
        with data.connect() as con:
            gold=con.execute('SELECT sum(closing_on_hand_units),max(week_end_date_key) FROM fact_inventory_weekly WHERE week_end_date_key=(SELECT max(week_end_date_key) FROM fact_inventory_weekly WHERE week_end_date_key<=20251227)').fetchone()
        rows=self.results['inventory']['outputs'][0]['rows']
        self.assertEqual(sum(r['closing_units'] for r in rows),gold[0])
        self.assertEqual({r['week_end_date_key'] for r in rows},{gold[1]})
    def test_anonymous_customer_excluded(self):
        with data.connect() as con:
            gold=con.execute('SELECT count(DISTINCT customer_key) FROM fact_transaction WHERE customer_key>0 AND date_key<=20251227').fetchone()[0]
        rows=self.results['lapse']['outputs'][0]['rows']
        self.assertEqual(sum(r['identified_buyers'] for r in rows),gold)

for slug in data.SLUGS:
    def test(self,slug=slug):
        r=self.results[slug]
        self.assertTrue(all(c['passed'] for c in r['checks']),r['checks'])
        self.assertTrue(all(o['rows'] and o['sql'] for o in r['outputs']))
        self.assertTrue(r['sources'])
    setattr(ReportTests,'test_playbook_'+slug,test)

class GuardTests(unittest.TestCase):
    def test_date_overlap_rejected(self):
        with self.assertRaises(ValueError):data.dates_for('2025-01-05','2025-12-27','2025-01-05','2025-12-27')
    def test_date_unequal_rejected(self):
        with self.assertRaises(ValueError):data.dates_for('2025-01-05','2025-12-27','2024-01-01','2024-12-28')
    def test_date_outside_coverage_rejected(self):
        with self.assertRaises(ValueError):data.dates_for('2026-01-01','2026-01-31')
    def test_write_rejected(self):
        with self.assertRaises(ValueError):data.select_sql('DELETE FROM dim_brand')
    def test_multiple_statements_rejected(self):
        with self.assertRaises(ValueError):data.select_sql('SELECT 1; SELECT 2')
    def test_external_read_blocked(self):
        with self.assertRaises(Exception):data.select_sql("SELECT * FROM read_csv_auto('/etc/passwd')")
    def test_copy_blocked(self):
        with self.assertRaises(ValueError):data.select_sql("COPY (SELECT 1) TO '/tmp/not-written.csv'")
    def test_extension_blocked(self):
        with self.assertRaises(ValueError):data.select_sql('INSTALL httpfs')
    def test_row_limit(self):
        r=data.select_sql('SELECT * FROM dim_date',limit=10)
        self.assertEqual(len(r['rows']),10);self.assertTrue(r['truncated'])
    def test_catalog_allowlist(self):
        with self.assertRaises(ValueError):data.inspect_table('dim_date; DROP TABLE dim_date')
    def test_document_traversal(self):
        with self.assertRaises(ValueError):INDEX.document('../../etc/passwd')
    def test_retrieval(self):
        hits=INDEX.search('anonymous customer_key repeat')
        self.assertTrue(hits);self.assertTrue(all(h['source'] and h['line']>0 for h in hits))

class ApiTests(unittest.TestCase):
    def setUp(self): self.client=TestClient(app)
    def test_home_and_assets(self):
        self.assertEqual(self.client.get('/').status_code,200)
        self.assertEqual(self.client.get('/static/app.js').status_code,200)
    def test_status(self):
        s=self.client.get('/api/status').json();self.assertEqual(s['orders'],5000000);self.assertEqual(len(s['playbooks']),19)
    def test_cross_origin_write_rejected(self):
        r=self.client.post('/api/memory',headers={**HEADERS,'Origin':'https://example.com'},json={'text':'abc','source':'reviewed'})
        self.assertEqual(r.status_code,403)
    def test_missing_app_header_rejected(self):
        self.assertEqual(self.client.post('/api/ask',json={'question':'sales'}).status_code,403)
    def test_missing_key_honest(self):
        with patch.dict(os.environ,{'OPENAI_API_KEY':''}):
            r=self.client.post('/api/ask',headers=HEADERS,json={'question':'Footwear sales last month'}).json()
        self.assertEqual(r['mode'],'suggestions');self.assertIn('not been applied',r['message'])
    def test_unsupported_question_not_proxied(self):
        with patch.dict(os.environ,{'OPENAI_API_KEY':''}):
            r=self.client.post('/api/ask',headers=HEADERS,json={'question':'How much incremental promotion revenue?'}).json()
        self.assertEqual(r['suggestions'],[]);self.assertTrue(r['gaps'])
    def test_analysis_persistence_export(self):
        r=self.client.post('/api/analyze',headers=HEADERS,json={'slug':'growth'});self.assertEqual(r.status_code,200)
        for _ in range(100):
            job=self.client.get('/api/jobs/'+r.json()['job_id']).json()
            if job['status']!='running':break
            time.sleep(.1)
        self.assertEqual(job['status'],'complete',job)
        identity=job['result']['id']
        self.assertEqual(self.client.get('/api/history/'+identity).status_code,200)
        self.assertIn('change_cents',self.client.get('/api/export/'+identity+'?format=csv').text)
        self.assertEqual(self.client.get('/api/export/'+identity).json()['id'],identity)
    def test_memory(self):
        r=self.client.post('/api/memory',headers=HEADERS,json={'text':'Use the metric contract','source':'User-reviewed test note'})
        self.assertEqual(r.status_code,200)
        self.assertTrue(self.client.get('/api/memory').json())

class AgentTests(unittest.TestCase):
    def test_nonexistent_evidence_citations_are_flagged(self):
        text,warnings=agent.check_citations('Measured [E1]. Unsupported [E2].',[{'evidence_id':'E1'}])
        self.assertIn('[E1]',text);self.assertNotIn('[E2]',text)
        self.assertIn('Unverified reference: E2',text);self.assertTrue(warnings)
        self.assertEqual(agent.check_citations('See METRICS.md line 10.',[])[1],[])
    def test_value_comparison_is_saved_as_citable_evidence(self):
        replies=[httpx.Response(200,json={'output':[{'type':'function_call','name':'analyze_result',
            'arguments':json.dumps({'current_evidence_id':'E1','current_column':'current','comparison_evidence_id':'E1','comparison_column':'comparison'}),'call_id':'1'}]}),
            httpx.Response(200,json={'output':[{'type':'message','content':[{'type':'output_text','text':'The measured increase is 1,208,099.26 [E1].'}]}]})]
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test-only','OPENAI_MODEL':'test-model'}),patch.object(agent.MODEL_HTTP,'post',side_effect=replies) as post:
            result=agent.run_agent('Compare the supplied measured totals',DATES,seed_evidence=[{'evidence_id':'E1','rows':[{'current':47454057.51,'comparison':46245958.25}], 'sql':'SELECT measured totals','truncated':False}],budget={'calls':0,'evidence_count':1})
        evidence=result['outputs'][1]
        self.assertEqual(evidence['evidence_id'],'E2')
        self.assertEqual(evidence['rows'][0]['change'],1208099.26)
        self.assertIn('E1',post.call_args_list[1].kwargs['json']['input'][-1]['output'])
    def test_rate_limit_recovers_without_exposing_key(self):
        limited=httpx.Response(429,json={'error':{'code':'rate_limit_exceeded'}},headers={'retry-after':'1','x-ratelimit-reset-tokens':'2s'})
        done=httpx.Response(200,json={'output':[]})
        notifications=[]
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test-only'}),patch.object(agent.MODEL_HTTP,'post',side_effect=[limited,done]) as post,patch.object(agent.time,'sleep') as sleep:
            self.assertEqual(agent.request_model({},notifications.append),[])
        self.assertEqual(post.call_count,2);sleep.assert_called_once()
        self.assertNotIn('test-only',str(notifications))
    def test_quota_failure_not_retried(self):
        limited=httpx.Response(429,json={'error':{'code':'insufficient_quota','message':'sensitive-provider-detail'}})
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test-only'}),patch.object(agent.MODEL_HTTP,'post',return_value=limited) as post,patch.object(agent.time,'sleep') as sleep:
            with self.assertRaisesRegex(ValueError,'quota is exhausted') as error:agent.request_model({},lambda _:None)
        self.assertEqual(post.call_count,1);sleep.assert_not_called();self.assertNotIn('sensitive-provider-detail',str(error.exception))
    def test_rate_retries_are_bounded(self):
        limited=httpx.Response(429,json={'error':{'code':'rate_limit_exceeded'}},headers={'retry-after':'120'})
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test-only'}),patch.object(agent.MODEL_HTTP,'post',return_value=limited) as post,patch.object(agent.time,'sleep') as sleep:
            with self.assertRaisesRegex(ValueError,'retries were exhausted'):agent.request_model({},lambda _:None)
        self.assertEqual(post.call_count,4);self.assertEqual(sleep.call_count,3)
        self.assertTrue(all(c.args[0]<=30 for c in sleep.call_args_list))
    def test_langgraph_self_correction_with_mock_model(self):
        # The model first returns invalid SQL, receives the error, then corrects it.
        class Reply:
            status_code=200
            def __init__(self,out):self.out=out
            def json(self):return {'output':self.out}
        replies=[Reply([{'type':'function_call','name':'execute_sql','arguments':json.dumps({'sql':'SELECT missing_column FROM dim_brand'}),'call_id':'1'}]),
                 Reply([{'type':'function_call','name':'execute_sql','arguments':json.dumps({'sql':'SELECT count(*) brands FROM dim_brand'}),'call_id':'2'}]),
                 Reply([{'type':'message','content':[{'type':'output_text','text':'There are 12 brand rows [E1].'}]}])]
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test-only','OPENAI_MODEL':'test-model'}),patch.object(agent.MODEL_HTTP,'post',side_effect=replies) as model:
            r=agent.run_agent('How many brands?',DATES)
        self.assertEqual(r['outputs'][0]['rows'][0]['brands'],12)
        self.assertEqual([t['status'] for t in r['trace']],['error','complete'])
        self.assertIn('error',model.call_args_list[1].kwargs['json']['input'][-1]['output'])
        self.assertNotIn('test-only',json.dumps(r))
    def test_missing_credentials(self):
        with patch.dict(os.environ,{'OPENAI_API_KEY':''}):
            with self.assertRaises(ValueError):agent.run_agent('sales',DATES)

class HypothesisAndStatsTests(unittest.TestCase):
    def test_all_retail_hypotheses_execute(self):
        from retail_app.backend.analytics import BANK
        from retail_app.backend.hypotheses import execute_hypothesis
        self.assertEqual(len(BANK),18)
        for h in BANK:
            with self.subTest(h=h['id']):
                self.assertTrue(set(h['required_tables']) <= set(data.CATALOG))
                r=execute_hypothesis(h['id'],DATES)
                self.assertTrue(r['report']['outputs'][0]['rows'])
                self.assertEqual(r['status'],'evidence_collected_not_automatically_confirmed')
                self.assertTrue(h['falsifier'] and h['metric_basis'] and h['scope'])
    def test_profile_live_column(self):
        from retail_app.backend.analytics import profile_column
        r=profile_column('dim_date','day_index')
        self.assertEqual(r['rows'],791);self.assertEqual(r['null_count'],0)
        self.assertEqual(r['minimum'],0);self.assertEqual(r['maximum'],790)
    def test_profile_invalid_column(self):
        from retail_app.backend.analytics import profile_column
        with self.assertRaises(ValueError):profile_column('dim_date','not_real')
    def test_welch_ci_and_effect_size(self):
        from retail_app.backend.analytics import statistics_on_evidence
        out={'rows':[{'group':g,'value':v} for g,values in [('a',[1,2,3,4,5]),('b',[4,5,6,7,8])] for v in values],'truncated':False,'evidence_id':'E1'}
        r=statistics_on_evidence(out,'welch_t','value',group_column='group',group_a='a',group_b='b',independent_observations=True,design_note='Separate independent sampled customers, one value per customer.')
        self.assertAlmostEqual(r['mean_difference'],-3)
        self.assertLess(r['mean_difference_ci95'][1],0);self.assertLess(r['p_value'],.05)
        self.assertLess(r['hedges_g'],0)
    def test_no_inference_without_design(self):
        from retail_app.backend.analytics import statistics_on_evidence
        with self.assertRaises(ValueError):statistics_on_evidence({'rows':[{'x':1},{'x':2},{'x':3}]},'welch_t','x')
    def test_no_inference_on_truncation(self):
        from retail_app.backend.analytics import statistics_on_evidence
        with self.assertRaises(ValueError):statistics_on_evidence({'rows':[{'x':1}],'truncated':True},'describe','x')
    def test_anova_and_spearman(self):
        from retail_app.backend.analytics import statistics_on_evidence
        out={'rows':[{'g':g,'x':v,'y':2*v} for g,vs in [('a',[1,2,3,4]),('b',[5,6,7,8]),('c',[9,10,11,12])] for v in vs]}
        kwargs={'independent_observations':True,'design_note':'Distinct independently sampled experimental units, comparable residuals.'}
        a=statistics_on_evidence(out,'anova','x',group_column='g',**kwargs)
        self.assertLess(a['p_value'],.01);self.assertGreater(a['eta_squared'],.8)
        r=statistics_on_evidence(out,'spearman','x',other_column='y',**kwargs)
        self.assertAlmostEqual(r['spearman_r'],1)

class ConversationTests(unittest.TestCase):
    def setUp(self):self.client=TestClient(app)
    def wait_job(self,job):
        for _ in range(150):
            j=self.client.get('/api/chat/jobs/'+job).json()
            if j['status']!='running':return j
            time.sleep(.05)
        self.fail('Chat job did not complete')
    def test_offline_chat_persists_and_renames(self):
        with patch.dict(os.environ,{'OPENAI_API_KEY':''}):
            r=self.client.post('/api/chat',headers=HEADERS,json={'question':'Compare Footwear with Apparel'}).json()
        c=r['conversation'];self.assertEqual(len(c['messages']),2)
        self.assertIn('not been applied',c['messages'][1]['text'])
        self.assertEqual(self.client.post('/api/conversations/'+c['id']+'/rename',headers=HEADERS,json={'title':'Footwear comparison'}).status_code,200)
        self.assertEqual(self.client.get('/api/conversations/'+c['id']).json()['title'],'Footwear comparison')
    def test_hypothesis_test_in_chat_no_key(self):
        r=self.client.post('/api/chat',headers=HEADERS,json={'question':'Test digital returns','hypothesis_id':'digital-softgoods-returns'}).json()
        self.assertEqual(self.wait_job(r['job_id'])['status'],'complete')
        c=self.client.get('/api/conversations/'+r['conversation_id']).json()
        a=c['messages'][-1]['analysis'];self.assertEqual(a['mode'],'hypothesis_test');self.assertEqual(len(a['outputs'][0]['rows']),6)
    def test_followup_carries_conversation(self):
        def fake(question,dates,prior,notify):
            return {'mode':'agent','question':question,'answer':'Scoped test answer','period':data.clean(dates),'outputs':[],'warnings':[],'context':[],'trace':[],'specialists':[]}
        with patch('retail_app.backend.main.configured',return_value=True),patch('retail_app.backend.main.run_agent',side_effect=fake) as fn:
            a=self.client.post('/api/chat',headers=HEADERS,json={'question':'Focus on Footwear Web sales'}).json();self.wait_job(a['job_id'])
            b=self.client.post('/api/chat',headers=HEADERS,json={'question':'Break that down by month','conversation_id':a['conversation_id']}).json();self.wait_job(b['job_id'])
            prior=fn.call_args.args[2]
            self.assertIn('Focus on Footwear Web sales',json.dumps(prior))
    def test_deep_investigation_uses_one_primary_agent(self):
        sentinel={'answer':'done'}
        with patch.object(agent,'run_agent',return_value=sentinel) as fn:
            r=agent.run_investigation('Why?',DATES)
        self.assertEqual(fn.call_count,1);self.assertFalse(fn.call_args.kwargs['enable_specialists']);self.assertEqual(r['investigation_mode'],'deep')
    def test_undeclared_specialist_cannot_bypass_approved_tools(self):
        class Reply:
            status_code=200
            def __init__(self,output):self.output=output
            def json(self):return {'output':self.output}
        def tool(name,args,identity):return Reply([{'type':'function_call','name':name,'arguments':json.dumps(args),'call_id':identity}])
        def text_reply(text):return Reply([{'type':'message','content':[{'type':'output_text','text':text}]}])
        replies=[tool('hypothesis_agent',{'question':'Check brand count'},'1'),tool('execute_sql',{'sql':'SELECT count(*) brands FROM dim_brand'},'2'),text_reply('There are 12 brands [E1]; a count alone is not a cause.')]
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test-only','OPENAI_MODEL':'test-model'}),patch.object(agent.MODEL_HTTP,'post',side_effect=replies):r=agent.run_agent('Check brand count',DATES)
        self.assertEqual(r['specialists'],[])
        self.assertEqual(r['trace'][0]['status'],'error')
        self.assertIn('approved tool registry',r['trace'][0]['detail'])
        self.assertEqual(r['outputs'][0]['evidence_id'],'E1');self.assertEqual(r['outputs'][0]['rows'][0]['brands'],12)

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromModule(__import__(__name__,fromlist=['*']))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    report={'total':result.testsRun,'passed':result.testsRun-len(result.failures)-len(result.errors),'failures':[str(t)+': '+e for t,e in result.failures+result.errors],
      'run_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'dataset':str(data.DB),'live_agent_tested':False,
      'coverage':'19 existing full-data playbook recipes; independent golden SQL for trend, growth/PVM, margin, returns, inventory and identified customers; API persistence/export; read-only guardrails; mocked LangGraph correction loop.'}
    (data.APP/'state/eval_report.json').write_text(json.dumps(report,indent=2))
    raise SystemExit(not result.wasSuccessful())
