"""Milky Way 2.0 conversational workflow boundaries with isolated session state."""
import json, os, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import closing
import httpx
from fastapi.testclient import TestClient
from retail_app.backend.evidence import bind_measured_values, comparison_from_evidence
from retail_app.backend.presentation import unmatched_money
from retail_app.backend import agent, conversation as flow, data, storage, investigations as inv, scope as scopes, main

DATES=data.dates_for('2025-01-01','2025-01-31','2024-01-01','2024-01-31')
HEADERS={'X-Retail-App':'local'}

def call(name,args,identity):
    return httpx.Response(200,json={'output':[{'type':'function_call','name':name,'arguments':json.dumps(args),'call_id':str(identity)}]})

class ConversationV2Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.state=patch.object(storage,'STATE',Path(self.tmp.name));self.state.start()
        self.cid=storage.create_conversation('Retail questions')['id']
        self.turn=flow.prepare_turn('Why did sales change?',DATES,None,self.cid)
        self.evidence=[]
    def tearDown(self):self.state.stop();self.tmp.cleanup()
    def add(self,output):
        output={**data.clean(output),'scope':self.turn['scope'],'evidence_id':'E'+str(len(self.evidence)+1)}
        self.evidence.append(output);return output
    def tool(self,name,args):return flow.handle_tool(name,args,self.turn,self.evidence,self.add)[1]
    def begin(self):
        self.tool('plan_turn',{'response_type':'investigation','scope_json':json.dumps({'filters':[{'field':'channel','op':'eq','values':['Web']}]}),'summary':'Investigate Web sales.'})
        baseline=self.tool('query_retail',{'measures':['sales','units'],'dimensions':[],'compare':True})
        self.tool('start_investigation',{'question':'What drove the change?','baseline_evidence_id':baseline['evidence_id']})
        self.tool('save_hypothesis',{'id':'H1','statement':'Sold units declined.','test':'Compare units between the selected periods.','falsifier':'Units increased or stayed constant.','kind':'mechanism','criterion_json':json.dumps({'column':'unit_change','operator':'lt','threshold':0,'row':0})})
    def test_definition_is_conversational_and_uses_one_agent(self):
        replies=[call('plan_turn',{'response_type':'explanation','scope_json':'{}','summary':'Explained customer identity.'},1),call('answer_explanation',{'answer':'customer_key identifies a customer; key 0 pools anonymous orders.'},2)]
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test','OPENAI_MODEL':'test'}),patch.object(agent.MODEL_HTTP,'post',side_effect=replies) as post:
            result=agent.run_agent('What does customer_key mean?',DATES,conversation_id=self.cid)
        self.assertEqual(result['response_type'],'explanation');self.assertNotIn('presentation',result)
        self.assertEqual(result['outputs'],[])
        names={x['name'] for x in post.call_args.kwargs['json']['tools']}
        self.assertIn('test_hypothesis',names);self.assertNotIn('rca_agent',names)
        self.assertEqual(inv.get_session(self.cid)['summary'],'Explained customer identity.')
    def test_followup_preserves_filters_and_dates_across_new_turn(self):
        self.tool('plan_turn',{'response_type':'analysis','scope_json':json.dumps({'filters':[{'field':'channel','op':'eq','values':['Web']},{'field':'division','op':'eq','values':['Footwear']}]}),'summary':'Web Footwear.'})
        newer=flow.prepare_turn('Same for Mobile app',DATES,None,self.cid)
        self.assertEqual(newer['scope'],self.turn['scope'])
        flow.handle_tool('plan_turn',{'response_type':'analysis','scope_json':json.dumps({'filters':[{'field':'channel','op':'eq','values':['Mobile app']}]})},newer,[],lambda x:x)
        filters={f['field']:f['values'] for f in inv.get_session(self.cid)['scope']['filters']}
        self.assertEqual(filters['division_name'],['Footwear']);self.assertEqual(filters['channel_name'],['Mobile app'])
    def test_filtered_custom_sql_cannot_drop_scope(self):
        self.tool('plan_turn',{'response_type':'analysis','scope_json':json.dumps({'filters':[{'field':'channel','op':'eq','values':['Web']}]})})
        with self.assertRaises(ValueError):flow.execute_model_sql('SELECT sum(net_sales_cents) sales FROM fact_transaction',self.turn)
        output=flow.execute_model_sql("SELECT period,sum(net_sales_cents) sales_cents FROM scoped_sales GROUP BY period",self.turn)
        expected=scopes.query_retail(self.turn['scope'],['sales'],[],True)
        self.assertEqual(sorted(r['sales_cents'] for r in output['rows']),sorted(r['sales_cents'] for r in expected['rows']))
    def test_investigation_runs_declared_test_and_can_resume(self):
        self.begin()
        result=self.tool('test_hypothesis',{'hypothesis_id':'H1','sql':"SELECT sum(CASE WHEN period='current' THEN quantity ELSE -quantity END) unit_change FROM scoped_sales",'interpretation':'Observed unit change tests the proposed decline; it does not establish a cause.'})
        node=result['investigation']['hypotheses'][0]
        self.assertEqual(node['status'],'tested');self.assertIn(node['verdict'],('supported_descriptively','contradicted'))
        self.tool('finish_investigation',{'summary':'The unit-change hypothesis was tested descriptively.','status':'complete'})
        resumed=flow.prepare_turn('Explain this finding',DATES,None,self.cid)
        loaded=[]
        def save(o):o={**o,'evidence_id':'E'+str(len(loaded)+1)};loaded.append(o);return o
        flow.handle_tool('load_investigation_evidence',{},resumed,loaded,save)
        self.assertGreaterEqual(len(loaded),2);self.assertTrue(all(o.get('saved_origin') for o in loaded))
    def test_user_edit_rejects_old_worker_before_context_refresh(self):
        self.begin();snapshot=self.turn['investigation']
        inv.edit_hypothesis(snapshot['id'],'H1',{'statement':'Unit growth was positive.'},snapshot['revision'])
        with self.assertRaisesRegex(ValueError,'edited'):
            self.tool('plan_turn',{'response_type':'investigation','scope_json':'{}'})
    def test_scope_change_cannot_relabel_old_evidence(self):
        self.begin();old=self.evidence[0]
        self.tool('plan_turn',{'response_type':'investigation','scope_json':json.dumps({'filters':[{'field':'channel','op':'eq','values':['Mobile app']}]})})
        with self.assertRaisesRegex(ValueError,'another scope'):
            self.tool('assess_hypothesis',{'hypothesis_id':'H1','evidence_id':old['evidence_id'],'interpretation':'Invalid reuse.','data_missing':False})
    def test_measurements_cannot_hide_in_explanation(self):
        self.add({'rows':[{'units':10}],'name':'custom_query'})
        with self.assertRaisesRegex(ValueError,'present_answer'):
            self.tool('answer_explanation',{'answer':'Ten units.'})
    def test_preference_write_requires_explicit_user_request(self):
        with self.assertRaises(ValueError):self.tool('remember_preference',{'text':'Show dollars.'})
        self.turn['question']='Remember to show money in USD.'
        self.tool('remember_preference',{'text':'Show money in USD.'})
        self.assertIn('USD',storage.memories()[0]['text'])
    def test_edit_api_marks_stale_and_does_not_change_old_evidence(self):
        self.begin();self.tool('test_hypothesis',{'hypothesis_id':'H1','sql':"SELECT sum(quantity) unit_change FROM scoped_sales WHERE period='current'",'interpretation':'Measured units.'})
        snapshot=self.turn['investigation']
        with closing(TestClient(main.app)) as client:
            response=client.patch('/api/investigations/'+snapshot['id']+'/hypotheses/H1',headers=HEADERS,json={'expected_revision':snapshot['revision'],'statement':'Investigate price changes instead.'})
            self.assertEqual(response.status_code,200,response.text)
            node=response.json()['hypotheses'][0]
            self.assertEqual(node['status'],'stale');self.assertIsNone(node['criterion']);self.assertTrue(node['test_history'])
            self.assertEqual(client.get('/api/conversations/'+self.cid).json()['investigation']['revision'],response.json()['revision'])
    def test_exact_value_bindings_and_money_comparison_are_validated(self):
        evidence=[{'evidence_id':'E1','rows':[{'sales_cents':79488977},{'sales_cents':76112442}]}]
        delta=comparison_from_evidence({'current_evidence_id':'E1','current_column':'sales_cents','current_row':0,'comparison_evidence_id':'E1','comparison_column':'sales_cents','comparison_row':1},evidence)
        evidence.append({'evidence_id':'E2','rows':[delta]})
        answer=bind_measured_values('Sales {{E1:0:sales_cents}}; change {{E2:0:change_cents}}.',evidence)
        self.assertEqual(answer,'Sales $794,889.77; change $33,765.35.')
        self.assertEqual(unmatched_money(answer,evidence),[])
        evidence.append({'evidence_id':'E3','rows':[{'avg_price_change_cents':309.65949,'change_pct':4.4362}]})
        self.assertEqual(bind_measured_values('Price {{E3:0:avg_price_change_cents}} cents; {{E3:0:change_pct}}%.',evidence),'Price $3.10; 4.44%.')
        with self.assertRaises(ValueError):bind_measured_values('{{E9:0:missing}}',evidence)
    def test_batch_saves_prespecified_hypotheses_and_records_real_queries(self):
        self.tool('plan_turn',{'response_type':'investigation','scope_json':'{}'})
        self.assertIsNotNone(self.turn['investigation'])
        result=self.tool('investigate_hypotheses',{'hypotheses_json':json.dumps([{'id':'H1','statement':'The selected period has sales.','test':'Aggregate observed sales.','falsifier':'The total is zero.','criterion':{'column':'sales_cents','operator':'gt','threshold':0},'sql':"SELECT sum(net_sales_cents) sales_cents FROM scoped_sales WHERE period='current'"}])})
        self.assertEqual(result['investigation']['hypotheses'][0]['status'],'tested')
        self.assertEqual(result['investigation']['hypotheses'][0]['verdict'],'supported_descriptively')

    def test_a_nonzero_count_cannot_validate_a_growth_or_primary_driver_claim(self):
        with self.assertRaisesRegex(ValueError,'nonzero level'):
            flow.validate_atomic_hypothesis({'statement':'Orders increased.','criterion':{'column':'orders','operator':'ne','threshold':0}})
        with self.assertRaisesRegex(ValueError,'primary-driver'):
            flow.validate_atomic_hypothesis({'statement':'Orders primarily explain sales growth.','criterion':{'column':'orders_change','operator':'gt','threshold':0}})
        flow.validate_atomic_hypothesis({'statement':'Orders increased.','criterion':{'column':'orders_change','operator':'gt','threshold':0}})

    def test_edited_hypothesis_requires_a_new_prespecified_criterion(self):
        self.begin()
        snap=self.turn['investigation']
        updated=inv.edit_hypothesis(snap['id'],'H1',{'statement':'Units increased.'},snap['revision'])
        self.turn['investigation']=updated;self.turn['investigation_revision']=updated['revision']
        with self.assertRaisesRegex(ValueError,'no prespecified criterion'):
            self.tool('test_hypothesis',{'hypothesis_id':'H1','sql':"SELECT sum(quantity) units FROM scoped_sales",'interpretation':'Test units.'})
        self.assertEqual(inv.get_investigation(snap['id'])['hypotheses'][0]['status'],'stale')

    def test_bad_query_alias_does_not_become_missing_business_data(self):
        self.begin()
        with self.assertRaisesRegex(ValueError,'schema mismatch'):
            self.tool('test_hypothesis',{'hypothesis_id':'H1','sql':"SELECT sum(quantity) units FROM scoped_sales",'interpretation':'Test units.'})
        self.assertEqual(inv.get_investigation(self.turn['investigation']['id'])['hypotheses'][0]['status'],'planned')

    def test_delete_chat_cleans_investigation_records(self):
        self.begin();identity=self.turn['investigation']['id']
        storage.delete_conversation(self.cid)
        with self.assertRaises(ValueError):inv.get_investigation(identity)

if __name__=='__main__':unittest.main()
