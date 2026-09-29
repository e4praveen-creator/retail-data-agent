"""Cross-component contracts: immutable answer versions, scope edits and budgets."""
import copy
import os
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from retail_app.backend import storage, main, agent, investigations, workspace_assets as assets
from retail_app.backend.presentation import apply_output_profile

HEADERS={'X-Retail-App':'local'}


class WorkspaceIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.default=patch.object(storage,'STATE',Path(self.tmp.name))
        self.default.start()
        with main.JOB_LOCK: main.JOBS.clear()
        self.client=TestClient(main.app)

    def tearDown(self):
        self.client.close()
        self.default.stop()
        self.tmp.cleanup()

    def test_state_override_is_nested_and_thread_local(self):
        storage.save_memory('normal workspace preference','test')
        with tempfile.TemporaryDirectory() as isolated:
            with storage.use_state(isolated):
                self.assertEqual(storage.memories(),[])
                storage.save_memory('evaluation only','test')
                observed=[]
                worker=threading.Thread(target=lambda:observed.extend(storage.memories()))
                worker.start();worker.join(2)
                self.assertEqual(observed[0]['text'],'normal workspace preference')
            self.assertEqual(storage.memories()[0]['text'],'normal workspace preference')

    def test_profile_changes_display_without_losing_evidence_or_limitations(self):
        payload={'answer':'Measured answer','outputs':[{'rows':[{'sales_cents':100}],'name':'total'}],
                 'warnings':['Descriptive evidence does not establish causation.']}
        quick=apply_output_profile(copy.deepcopy(payload),{'detail':'concise'})
        detail=apply_output_profile(copy.deepcopy(payload),{'detail':'detailed'})
        self.assertEqual(quick['outputs'],detail['outputs'])
        self.assertEqual(quick['presentation']['limitations'],detail['presentation']['limitations'])
        self.assertEqual(quick['output_display']['table_rows'],5)
        self.assertEqual(detail['output_display']['table_rows'],25)
        self.assertTrue(detail['output_display']['show_method'])

    def test_scope_update_rejects_stale_revision_and_keeps_other_filters(self):
        chat=storage.create_conversation('scope edit')['id']
        first=self.client.patch(f'/api/conversations/{chat}/scope',headers=HEADERS,json={
            'expected_revision':0,'scope':{'filters':[{'field':'channel','op':'eq','values':['Web']}]}})
        self.assertEqual(first.status_code,200,first.text)
        revision=first.json()['session']['revision']
        second=self.client.patch(f'/api/conversations/{chat}/scope',headers=HEADERS,json={
            'expected_revision':revision,'scope':{'filters':[{'field':'division','op':'eq','values':['Footwear']}]}})
        self.assertEqual(second.status_code,200,second.text)
        self.assertEqual(len(second.json()['session']['scope']['filters']),2)
        stale=self.client.patch(f'/api/conversations/{chat}/scope',headers=HEADERS,json={'expected_revision':revision,'scope':{'filters':[]}})
        self.assertEqual(stale.status_code,409)
        self.assertEqual(len(investigations.get_session(chat)['scope']['filters']),2)

    def test_chat_pins_snapshot_before_background_execution(self):
        original=assets.active_snapshot()
        started=threading.Event();finish=threading.Event();captured=[]
        def fake(question,dates,prior,notify,**kwargs):
            captured.append(copy.deepcopy(kwargs['workspace_snapshot']))
            started.set();finish.wait(3)
            return {'answer':'Pinned result','outputs':[],'context':[]}
        with patch.object(main,'configured',return_value=True),patch.object(main,'run_agent',side_effect=fake):
            admitted=self.client.post('/api/chat',headers=HEADERS,json={'question':'Describe sales','output_profile_id':'quick-answer'}).json()
            self.assertTrue(started.wait(3))
            with patch.object(assets,'active_snapshot',side_effect=AssertionError('Worker must not recapture active release')):
                finish.set()
                for _ in range(300):
                    job=self.client.get('/api/chat/jobs/'+admitted['job_id']).json()
                    if job['status'] not in main.ACTIVE_STATUSES: break
                    time.sleep(.01)
            self.assertEqual(job['status'],'complete',job)
        answer=storage.conversation(admitted['conversation_id'])['messages'][-1]['analysis']
        self.assertEqual(answer['workspace']['release_id'],original.get('release_id',original['id']))
        self.assertEqual(captured[0]['snapshot_hash'],original['snapshot_hash'])
        self.assertEqual(answer['output_display']['table_rows'],5)

    def test_scope_editor_rejects_dates_that_next_chat_cannot_use(self):
        identity=storage.create_conversation('invalid date controls')['id']
        result=self.client.patch(f'/api/conversations/{identity}/scope',headers=HEADERS,json={
            'expected_revision':0,'scope':{'dates':{'start':'2025-07-01','end':'2025-07-31',
                'compare_start':'2024-07-01','compare_end':'2024-07-30'}}})
        self.assertEqual(result.status_code,400)
        self.assertIn('equal',result.text)
        self.assertEqual(investigations.get_session(identity)['revision'],0)

    def test_scope_edit_cancels_answer_without_deadlocking_or_saving_stale_result(self):
        started=threading.Event()
        def waiting(question,dates,prior,notify,**kwargs):
            started.set();notify.wait(3)
            return {'answer':'Stale answer','outputs':[]}
        with patch.object(main,'configured',return_value=True),patch.object(main,'run_agent',side_effect=waiting):
            admitted=self.client.post('/api/chat',headers=HEADERS,json={'question':'Analyze this scope'}).json()
            self.assertTrue(started.wait(2))
            changed=self.client.patch('/api/conversations/'+admitted['conversation_id']+'/scope',headers=HEADERS,
                json={'expected_revision':0,'scope':{'filters':[{'field':'channel','op':'eq','values':['Web']}]}})
            self.assertEqual(changed.status_code,200,changed.text)
            for _ in range(200):
                job=self.client.get('/api/chat/jobs/'+admitted['job_id']).json()
                if job['status'] not in main.ACTIVE_STATUSES:break
                time.sleep(.01)
        self.assertEqual(job['status'],'cancelled')
        self.assertEqual([m['role'] for m in storage.conversation(admitted['conversation_id'])['messages']],['user'])

    def test_provider_budget_stops_before_any_request(self):
        with patch.object(agent.MODEL_HTTP,'post') as post:
            with self.assertRaisesRegex(ValueError,'model-call budget'):
                agent.request_model({'input':[]},lambda _:None,{'requests':1,'max_model_calls':1})
            with self.assertRaisesRegex(ValueError,'token budget'):
                agent.request_model({'input':'x'*2000},lambda _:None,{'max_total_tokens':100})
            post.assert_not_called()

    def test_delete_chat_removes_its_structured_feedback(self):
        identity=storage.create_conversation('feedback deletion')['id']
        answer=storage.finish_chat(identity,None,'test question',{'answer':'test answer','outputs':[]})
        assets.create_feedback(answer['id'],['definition'],'Please review this definition.')
        self.assertEqual(len(assets.list_feedback()),1)
        storage.delete_conversation(identity)
        self.assertEqual(assets.list_feedback(),[])

    def test_served_guide_links_open_only_documented_local_sources(self):
        guide=self.client.get('/guide')
        self.assertEqual(guide.status_code,200)
        self.assertIn('/api/guide-file?path=',guide.text)
        source=self.client.get('/api/guide-file',params={'path':'retail_app/backend/agent.py'})
        self.assertEqual(source.status_code,200)
        self.assertIn('def run_agent',source.text)
        for private in ('retail_app/.env','retail_app/state/app.sqlite3','../../.env'):
            self.assertEqual(self.client.get('/api/guide-file',params={'path':private}).status_code,404)

    def test_frozen_evaluation_snapshot_does_not_read_active_workspace(self):
        snapshot=assets.active_snapshot()
        observed=[]
        def model(payload,notify,usage):
            observed.append(payload)
            return [{'type':'message','content':[{'type':'output_text','text':'A documentation explanation.'}]}]
        with patch.dict(os.environ,{'OPENAI_API_KEY':'mock-only','OPENAI_MODEL':'mock-only'}), \
             patch.object(assets,'active_snapshot',side_effect=AssertionError('Active lookup during pinned run')), \
             patch.object(agent,'request_model',side_effect=model):
            result=agent.run_agent('Explain sales definitions',main.data.dates_for('2025-07-01','2025-07-31'),workspace_snapshot=snapshot,output_profile_id='analyst-detail')
        self.assertEqual(result['workspace']['snapshot_hash'],snapshot['snapshot_hash'])
        self.assertNotIn('published_workspace_methods',observed[0]['instructions'])
        self.assertIn('published_workspace_methods',observed[0]['input'][0]['content'])
        self.assertNotIn('golden_sql',json.dumps(observed[0]))


if __name__=='__main__': unittest.main()
