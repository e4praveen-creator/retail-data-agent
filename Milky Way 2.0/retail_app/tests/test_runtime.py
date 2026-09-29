"""Regression tests for provenance, bounded context, and cancellable reads."""
import json
import os
import threading
import time
import unittest
from unittest.mock import patch

import httpx
from retail_app.backend import agent, data
from retail_app.backend.evidence import comparison_from_evidence, bounded_history, register_sources, model_preview
from retail_app.backend.runtime import JobCancelled, JobControl
from retail_app.backend.analytics import profile_column, statistics_on_evidence

DATES=data.dates_for('2025-01-01','2025-01-31','2024-01-01','2024-01-31')


def tool(name,args,identity):
    return httpx.Response(200,json={'output':[{'type':'function_call','name':name,'arguments':json.dumps(args),'call_id':identity}]})


def answer(text):
    return httpx.Response(200,json={'output':[{'type':'message','content':[{'type':'output_text','text':text}]}]})


class ProvenanceTests(unittest.TestCase):
    def test_model_numbers_cannot_be_promoted_to_evidence(self):
        with self.assertRaisesRegex(ValueError,'Reference measured'):
            comparison_from_evidence({'current':100,'comparison':50},[])

    def test_operands_must_be_existing_numeric_cells(self):
        evidence=[{'evidence_id':'E8','rows':[{'now':10.15,'then':9.01,'name':'not a number'}]}]
        args={'current_evidence_id':'E8','current_column':'now','comparison_evidence_id':'E8','comparison_column':'then'}
        result=comparison_from_evidence(args,evidence)
        self.assertEqual(result['change'],1.14)
        self.assertEqual(result['source_evidence_ids'],['E8'])
        with self.assertRaises(ValueError):comparison_from_evidence({**args,'current_column':'name'},evidence)
        with self.assertRaises(ValueError):comparison_from_evidence({**args,'current_evidence_id':'E9'},evidence)
        with self.assertRaises(ValueError):comparison_from_evidence({**args,'current_row':-1},evidence)

    def test_rejected_legacy_specialist_does_not_duplicate_measured_evidence(self):
        replies=[tool('execute_sql',{'sql':'SELECT 11 AS current, 10 AS comparison'},'a'),
                 tool('eda_agent',{'question':'Calculate change using E1'},'b'),
                 tool('analyze_result',{'current_evidence_id':'E1','current_column':'current','comparison_evidence_id':'E1','comparison_column':'comparison'},'c'),
                 answer('Change is one [E2].')]
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test-only','OPENAI_MODEL':'test-model'}),patch.object(agent.MODEL_HTTP,'post',side_effect=replies):
            result=agent.run_agent('Calculate measured change with EDA',DATES)
        self.assertEqual([o['evidence_id'] for o in result['outputs']],['E1','E2'])
        self.assertEqual(result['outputs'][1]['source_evidence_ids'],['E1'])
        self.assertEqual(result['specialists'],[])
        self.assertEqual(result['trace'][1]['status'],'error')
        self.assertIn('approved tool registry',result['trace'][1]['detail'])

    def test_grouped_document_and_result_citations_checked(self):
        text,warnings=agent.check_citations('Valid [E1, D1]. Invalid [E1, E9].',[{'evidence_id':'E1'}],[{'source_id':'D1'}])
        self.assertIn('[E1, D1]',text)
        self.assertNotIn('[E1, E9]',text)
        self.assertTrue(warnings)

    def test_sources_receive_stable_ids(self):
        budget={};item={'source':'metrics.md','line':8,'text':'Definition'}
        first=register_sources(budget,[item]);second=register_sources(budget,[item])
        self.assertEqual(first,second);self.assertEqual(first[0]['source_id'],'D1')

    def test_latest_conversation_correction_survives_context_limit(self):
        prior={'messages':[{'role':'assistant','content':'old '*5000},{'role':'user','content':'Correction: use February 2025 Web only.'}], 'last_period':{'start':'2025-01-01'}}
        bounded=bounded_history(prior,1000)
        self.assertEqual(bounded['messages'][-1]['content'],prior['messages'][-1]['content'])
        self.assertTrue(bounded['earlier_messages_omitted'])

    def test_previews_remain_structured_and_labeled(self):
        source={'outputs':[{'rows':[{'x':i} for i in range(100)]}]}
        preview=model_preview(source)
        self.assertEqual(len(preview['outputs'][0]['rows']),20)
        self.assertTrue(preview['outputs'][0]['model_preview_truncated'])
        self.assertEqual(len(source['outputs'][0]['rows']),100)


class ProviderTests(unittest.TestCase):
    def test_incomplete_response_not_saved_as_success(self):
        reply=httpx.Response(200,json={'status':'incomplete','output':[], 'usage':{'input_tokens':12,'output_tokens':8,'total_tokens':20}})
        usage={}
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test-only'}),patch.object(agent.MODEL_HTTP,'post',return_value=reply):
            with self.assertRaisesRegex(ValueError,'did not finish'):agent.request_model({},lambda _:None,usage)
        self.assertEqual(usage['total_tokens'],20)

    def test_temporary_server_error_retries(self):
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test-only'}),patch.object(agent.MODEL_HTTP,'post',side_effect=[httpx.Response(503,json={}),answer('ready')]) as post,patch.object(agent.time,'sleep'):
            agent.request_model({},lambda _:None)
        self.assertEqual(post.call_count,2)

    def test_cancelled_model_call_never_reaches_provider(self):
        control=JobControl(lambda _:None);control.cancel()
        with patch.object(agent.MODEL_HTTP,'post') as post:
            with self.assertRaises(JobCancelled):agent.request_model({},control)
        post.assert_not_called()


class WarehouseBoundsTests(unittest.TestCase):
    def test_duplicate_column_names_rejected(self):
        with self.assertRaisesRegex(ValueError,'uniquely named'):
            data.select_sql('SELECT 1 AS value, 2 AS value')

    def test_large_cell_preview_is_flagged(self):
        result=data.select_sql("SELECT repeat('x',10000) AS long_text")
        self.assertTrue(result['truncated'])
        self.assertLess(len(result['rows'][0]['long_text']),8100)

    def test_sql_size_bound(self):
        with self.assertRaisesRegex(ValueError,'32,000'):
            data.select_sql('SELECT 1 /*'+'x'*33000+'*/')

    def test_warehouse_timeout_interrupts_work(self):
        with self.assertRaisesRegex(ValueError,'time limit'):
            with data.warehouse_session(timeout=.02) as con:
                con.execute('SELECT sum(sin(i)) FROM range(1000000000) t(i)').fetchone()

    def test_cancel_interrupts_read(self):
        control=JobControl(lambda _:None)
        timer=threading.Timer(.04,control.cancel);timer.start()
        try:
            with data.query_control(control),self.assertRaises(JobCancelled):
                data.select_sql('SELECT sum(sin(i)) FROM range(1000000000) t(i)')
        finally:timer.cancel()

    def test_cancelled_profile_uses_same_controls(self):
        control=JobControl(lambda _:None);control.cancel()
        with data.query_control(control),self.assertRaises(JobCancelled):
            profile_column('dim_date','day_index')

    def test_small_channel_dimension_includes_mobile_app(self):
        inspected=data.inspect_table('dim_channel')
        self.assertTrue(inspected['sample_complete'])
        self.assertEqual(len(inspected['sample']),inspected['row_count'])
        self.assertIn('Mobile app',{r['channel_name'] for r in inspected['sample']})
        self.assertIn('Mobile app',{r['channel_name'] for r in data.scope_values()['channels']})

    def test_kruskal_raw_variance_is_explicitly_labeled(self):
        out={'rows':[{'g':group,'x':n+shift} for group,shift in [('a',0),('b',1),('c',3)] for n in [1,2,4,8]],'truncated':False}
        result=statistics_on_evidence(out,'kruskal','x',group_column='g',independent_observations=True,design_note='One measurement for each independently sampled item.')
        self.assertNotIn('eta_squared',result)
        self.assertIn('descriptive_raw_value_eta_squared',result)


if __name__=='__main__':unittest.main()
