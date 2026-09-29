"""Operational API checks against isolated state, with no provider requests."""
import os
import asyncio
import sqlite3
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
# Isolate state before importing application modules. Running this file alone
# must never touch the user's live conversation database.
_import_state=tempfile.TemporaryDirectory()
with patch.dict(os.environ,{'RETAIL_STATE_DIR':_import_state.name}):
    from retail_app.backend import main, storage
from retail_app.backend.runtime import JobControl, JobCancelled

HEADERS={'X-Retail-App':'local'}


def wait_job(client, identity, status=None):
    for _ in range(200):
        job=client.get('/api/chat/jobs/'+identity).json()
        if (status and job['status']==status) or (not status and job['status'] not in main.ACTIVE_STATUSES):
            return job
        time.sleep(.01)
    raise AssertionError('Job did not finish in time: '+str(job))


class OperationsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.state=patch.object(storage,'STATE',Path(self.tmp.name))
        self.state.start()
        with main.JOB_LOCK:main.JOBS.clear()
        self.client=TestClient(main.app)

    def tearDown(self):
        self.client.close()
        self.state.stop()
        self.tmp.cleanup()

    def test_health_and_security_headers(self):
        response=self.client.get('/health/ready')
        self.assertEqual(response.status_code,200)
        self.assertIn('frame-ancestors',response.headers['content-security-policy'])
        self.assertEqual(response.headers['x-content-type-options'],'nosniff')
        self.assertEqual(self.client.get('/health/live').json()['status'],'ok')
        self.assertEqual(self.client.get('/api/status').headers['cache-control'],'no-store')

    def test_host_origin_and_range_guard(self):
        self.assertEqual(self.client.get('/',headers={'Host':'evil.example'}).status_code,400)
        r=self.client.post('/api/conversations',headers={**HEADERS,'Origin':'https://evil.example'},json={'title':'no'})
        self.assertEqual(r.status_code,403)
        self.assertEqual(self.client.get('/static/app.js',headers={'Range':'bytes=0-1,2-3'}).status_code,400)

    def test_large_request_and_blank_question_rejected(self):
        r=self.client.post('/api/chat',headers=HEADERS,content=b'x'*(main.MAX_REQUEST_BYTES+1))
        self.assertEqual(r.status_code,413)
        r=self.client.post('/api/chat',headers=HEADERS,json={'question':'   '})
        self.assertEqual(r.status_code,422)
        self.assertEqual(storage.conversations(),[])

    def test_no_raw_unhandled_error(self):
        with patch.object(main.data,'inspect_table',side_effect=RuntimeError('provider-secret-must-not-leak')):
            r=self.client.get('/api/inspect/dim_brand')
        self.assertEqual(r.status_code,500)
        self.assertNotIn('provider-secret',r.text)
        self.assertIn('request_id',r.json())

    def test_cancel_preserves_question_and_retry_does_not_duplicate(self):
        started=threading.Event()
        def slow(question,dates,prior,notify):
            started.set()
            notify.wait(10)
            return {'answer':'should never save','outputs':[]}
        with patch.object(main,'configured',return_value=True),patch.object(main,'run_agent',side_effect=slow):
            accepted=self.client.post('/api/chat',headers=HEADERS,json={'question':'Inspect retail sales'}).json()
            self.assertTrue(started.wait(2))
            blocked=self.client.delete('/api/conversations/'+accepted['conversation_id'],headers=HEADERS)
            self.assertEqual(blocked.status_code,409)
            stopped=self.client.post('/api/chat/jobs/'+accepted['job_id']+'/cancel',headers=HEADERS)
            self.assertIn(stopped.json()['status'],('cancelling','cancelled'))
            self.assertEqual(wait_job(self.client,accepted['job_id'])['status'],'cancelled')
        conv=storage.conversation(accepted['conversation_id'])
        self.assertEqual([m['role'] for m in conv['messages']],['user'])
        with patch.object(main,'configured',return_value=False):
            retry=self.client.post('/api/chat',headers=HEADERS,json={'conversation_id':accepted['conversation_id'],'question':'Inspect retail sales','retry':True})
        self.assertEqual(retry.status_code,200)
        conv=storage.conversation(accepted['conversation_id'])
        self.assertEqual([m['role'] for m in conv['messages']],['user','assistant'])
        deleted=self.client.delete('/api/conversations/'+accepted['conversation_id'],headers=HEADERS)
        self.assertEqual(deleted.status_code,200)
        self.assertEqual(storage.history(),[])

    def test_concurrent_admission_never_exceeds_two_or_saves_rejected_prompt(self):
        release=threading.Event()
        def work(question,dates,prior,notify):
            release.wait(3)
            return {'answer':'Measured answer','outputs':[]}
        with patch.object(main,'configured',return_value=True),patch.object(main,'run_agent',side_effect=work):
            with ThreadPoolExecutor(max_workers=8) as callers:
                responses=list(callers.map(lambda i:self.client.post('/api/chat',headers=HEADERS,json={'question':'Sales '+str(i)}),range(8)))
            try:
                self.assertEqual(sum(r.status_code==200 for r in responses),2)
                self.assertEqual(sum(r.status_code==429 for r in responses),6)
                self.assertEqual(len(storage.conversations()),2)
            finally:release.set()
            for response in responses:
                if response.status_code==200:self.assertEqual(wait_job(self.client,response.json()['job_id'])['status'],'complete')

    def test_atomic_completion_rolls_back_analysis_and_message(self):
        conv=storage.create_conversation()
        storage.add_message(conv['id'],'user','question')
        storage.chat_job('test-job',conv['id'],'cancelled')
        with self.assertRaises(ValueError):
            storage.finish_chat(conv['id'],'test-job','question',{'answer':'must roll back'})
        self.assertEqual(storage.history(),[])
        self.assertEqual(len(storage.conversation(conv['id'])['messages']),1)

    def test_restart_recovers_running_and_cancelling(self):
        conv=storage.create_conversation()
        storage.chat_job('one',conv['id'],'running')
        storage.chat_job('two',conv['id'],'cancelling')
        storage.recover_interrupted_jobs()
        self.assertEqual(storage.get_chat_job('one')['status'],'interrupted')
        self.assertEqual(storage.get_chat_job('two')['status'],'interrupted')
        self.assertIsNone(storage.conversation(conv['id'])['active_job'])

    def test_job_memory_bounded_and_control_not_serialized(self):
        with main.JOB_LOCK:
            for i in range(80):
                main.JOBS[str(i)]={'status':'complete','started':time.time()}
            identity=main._reserve_job()
        self.assertLessEqual(len(main.JOBS),main.MAX_JOB_RECORDS)
        main.JOBS[identity]['control']=JobControl(lambda _:None)
        self.assertNotIn('control',self.client.get('/api/jobs/'+identity).json())
        main.JOBS[identity]['status']='complete'

    def test_cancel_deadline_and_unknown_records(self):
        control=JobControl(lambda _:None)
        control.cancel()
        with self.assertRaises(JobCancelled):control.wait(0)
        with self.assertRaisesRegex(ValueError,'time limit'):JobControl(lambda _:None,timeout=0).check_cancelled()
        self.assertEqual(self.client.get('/api/conversations/missing').status_code,404)
        self.assertEqual(self.client.post('/api/chat/jobs/missing/cancel',headers=HEADERS).status_code,404)

    def test_conversation_pagination_has_no_gaps_or_duplicates(self):
        conv=storage.create_conversation()
        for i in range(75):storage.add_message(conv['id'],'user','Question '+str(i))
        first=self.client.get('/api/conversations/'+conv['id']).json()
        self.assertEqual(len(first['messages']),50)
        self.assertEqual(first['total_messages'],75)
        self.assertTrue(first['has_older'])
        second=self.client.get('/api/conversations/'+conv['id']+'?before='+str(first['older_cursor'])).json()
        self.assertEqual(len(second['messages']),25)
        self.assertFalse(second['has_older'])
        self.assertEqual([m['text'] for m in second['messages']+first['messages']],['Question '+str(i) for i in range(75)])

    def test_cancelling_keeps_capacity_until_worker_acknowledges(self):
        release=threading.Event()
        def work(question,dates,prior,notify):
            release.wait(3)
            return {'answer':'Should not publish after cancelled','outputs':[]}
        with patch.object(main,'configured',return_value=True),patch.object(main,'run_agent',side_effect=work):
            first=self.client.post('/api/chat',headers=HEADERS,json={'question':'one'}).json()
            second=self.client.post('/api/chat',headers=HEADERS,json={'question':'two'}).json()
            try:
                response=self.client.post('/api/chat/jobs/'+first['job_id']+'/cancel',headers=HEADERS)
                self.assertEqual(response.json()['status'],'cancelling')
                self.assertEqual(self.client.post('/api/chat',headers=HEADERS,json={'question':'three'}).status_code,429)
            finally:release.set()
            self.assertEqual(wait_job(self.client,first['job_id'])['status'],'cancelled')
            self.assertEqual(wait_job(self.client,second['job_id'])['status'],'complete')
            self.assertEqual(len(storage.conversation(first['conversation_id'])['messages']),1)

    def test_consistent_backup_includes_wal_and_refuses_overwrite(self):
        from retail_app.maintenance import backup_state
        path=Path(self.tmp.name)
        with storage.connection() as live:
            live.execute('INSERT INTO memories(id,text,source) VALUES(?,?,?)',('wal-note','Saved while app running','test'))
            live.commit()
            output=backup_state(path,path/'backups'/'verified.sqlite3')
            backup=sqlite3.connect(str(output))
            try:
                self.assertEqual(backup.execute('PRAGMA integrity_check').fetchone()[0],'ok')
                self.assertEqual(backup.execute('SELECT text FROM memories').fetchone()[0],'Saved while app running')
            finally:backup.close()
            self.assertEqual(output.stat().st_mode & 0o777,0o600)
            with self.assertRaises(FileExistsError):backup_state(path,output)
            with self.assertRaises(ValueError):backup_state(path,path/'app.sqlite3')

    def test_shutdown_requests_cancellation_without_closing_live_provider_client(self):
        control=JobControl(lambda _:None)
        fake_pool=MagicMock()
        async def run_lifespan():
            async with main.lifespan(main.app):
                with main.JOB_LOCK:
                    main.JOBS['shutdown-test']={'status':'running','started':time.time(),'control':control}
        with patch.object(main,'POOL',fake_pool),patch.object(main,'STOPPING',False):
            asyncio.run(run_lifespan())
            fake_pool.shutdown.assert_called_once_with(wait=False,cancel_futures=True)
            with self.assertRaises(JobCancelled):control.check_cancelled()

    def test_failed_job_registration_releases_capacity_without_starting_worker(self):
        with patch.object(main,'configured',return_value=True),patch.object(storage,'chat_job',side_effect=sqlite3.OperationalError('private disk details')),patch.object(main,'run_agent') as agent:
            for _ in range(3):
                result=self.client.post('/api/chat',headers=HEADERS,json={'question':'Check sales'})
                self.assertEqual(result.status_code,500)
                self.assertNotIn('private disk',result.text)
                self.assertEqual(sum(j['status'] in main.ACTIVE_STATUSES for j in main.JOBS.values()),0)
            agent.assert_not_called()

    def test_poll_recovers_terminal_state_after_transient_storage_failure(self):
        def complete(question,dates,prior,notify):return {'answer':'Measured result','outputs':[]}
        original=storage.chat_job
        def fail_terminal(identity,conversation_id,status,message='',error=''):
            if status=='error':raise sqlite3.OperationalError('private terminal write failure')
            return original(identity,conversation_id,status,message,error)
        with patch.object(main,'configured',return_value=True),patch.object(main,'run_agent',side_effect=complete),patch.object(storage,'finish_chat',side_effect=sqlite3.OperationalError('private completion failure')),patch.object(storage,'chat_job',side_effect=fail_terminal):
            result=self.client.post('/api/chat',headers=HEADERS,json={'question':'Check sales'}).json()
            for _ in range(200):
                with main.JOB_LOCK:state=main.JOBS[result['job_id']]['status']
                if state=='error':break
                time.sleep(.01)
            self.assertEqual(state,'error')
            self.assertEqual(storage.get_chat_job(result['job_id'])['status'],'running')
        repaired=self.client.get('/api/chat/jobs/'+result['job_id'])
        self.assertEqual(repaired.status_code,200)
        self.assertEqual(repaired.json()['status'],'error')
        self.assertNotIn('private',repaired.text)
        self.assertEqual(storage.get_chat_job(result['job_id'])['status'],'error')
        self.assertIsNone(storage.conversation(result['conversation_id'])['active_job'])
        self.assertEqual(storage.history(),[])

    def test_sqlite_wal(self):
        with storage.connection() as con:
            self.assertEqual(con.execute('PRAGMA journal_mode').fetchone()[0],'wal')
            self.assertGreaterEqual(con.execute('PRAGMA busy_timeout').fetchone()[0],20000)


if __name__=='__main__':unittest.main(verbosity=2)
