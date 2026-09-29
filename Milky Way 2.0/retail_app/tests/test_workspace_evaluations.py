"""Evaluation isolation, honest grading, release pinning and bounded lifecycle."""
import copy
import json
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from retail_app.backend import storage, workspace_assets as assets
from retail_app.backend import workspace_evaluations as evaluations
from retail_app.backend import agent
from retail_app.backend.runtime import JobControl


class WorkspaceEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.state = storage.use_state(self.temporary.name)
        self.state.__enter__()
        self.snapshot = assets.active_snapshot()
        self.fingerprint = patch.object(evaluations, '_sources_fingerprint', return_value={'test': 'fixed-pinned-version'})
        self.fingerprint.start()

    def tearDown(self):
        self.fingerprint.stop()
        self.state.__exit__(None, None, None)
        self.temporary.cleanup()

    def run_core(self, **options):
        return evaluations.start_run('enterprise-core', background=False, **options)

    def test_bundled_cases_validate_and_exercise_real_runtime(self):
        suite = evaluations.seed_suite()
        self.assertGreaterEqual(len(suite['cases']), 60)
        self.assertEqual(evaluations.validate_suite(suite), [])
        run = self.run_core()
        self.assertEqual(run['status'], 'completed', run.get('error'))
        failures = [(r['case_id'], r['candidate']['failures']) for r in run['results'] if r['candidate']['status'] != 'passed']
        self.assertEqual(failures, [])
        self.assertEqual(run['completed_cases'], len(suite['cases']))
        self.assertEqual(run['summary']['semantic_review'], 'not_tested')
        self.assertNotIn('suite', run)
        self.assertNotIn('candidate_snapshot', run)
        self.assertEqual(run['provenance'], {'test': 'fixed-pinned-version'})

    def test_grader_rejects_missing_unimplemented_and_failed_checks(self):
        self.assertFalse(all(c['passed'] for c in evaluations.grade({}, {})))
        self.assertFalse(all(c['passed'] for c in evaluations.grade({'total': 2}, {'equals': {'total': 3}})))
        self.assertFalse(all(c['passed'] for c in evaluations.grade({}, {'equals': {'missing': 3}})))
        self.assertFalse(all(c['passed'] for c in evaluations.grade({}, {'equals': {'missing': None}})))
        self.assertFalse(all(c['passed'] for c in evaluations.grade({}, {'not_contains': {'missing': ['bad claim']}})))
        self.assertFalse(all(c['passed'] for c in evaluations.grade({}, {'error_contains': 'required denial'}, error='unexpected error')))
        self.assertTrue(all(c['passed'] for c in evaluations.grade({}, {'error_contains': 'denied'}, error='Operation denied')))
        invalid = {'cases': [{'id': 'x', 'question': 'Question', 'contract': {'type': 'scope'}, 'expected': {'equals': {}}}]}
        self.assertTrue(evaluations.validate_suite(invalid))
        invalid['cases'][0]['expected'] = {'min_length': {'answer': 'large'}}
        self.assertTrue(evaluations.validate_suite(invalid))

    def test_goldens_never_enter_live_prompt_snapshot_or_production_state(self):
        storage.save_memory('production memory', 'unit test')
        secret = 'HIDDEN_GOLDEN_SENTINEL_4921'
        snapshot = copy.deepcopy(self.snapshot)
        snapshot['assets'].append({'id': 'test-goldens', 'kind': 'evaluation_suite', 'content': {'expected': secret}})
        case = {'question': 'Explain revenue.', 'contract': {'type': 'live_answer', 'inputs': {}}, 'expected': {'contains': {'answer': secret}}}
        original_state = storage.STATE
        def fake_agent(question, dates, **kwargs):
            self.assertEqual(storage.memories(), [])
            self.assertNotIn(secret, json.dumps(kwargs['workspace_snapshot']))
            self.assertNotIn('expected', question)
            storage.save_memory('evaluation-only memory', 'test')
            return {'answer': 'Measured sample', 'workspace': {'snapshot_hash': snapshot['snapshot_hash']}, 'outputs': [], 'context': []}
        with patch('retail_app.backend.agent.run_agent', side_effect=fake_agent):
            evaluations.execute_contract(case, snapshot, JobControl(lambda _: None), {'calls': 0, 'max_model_calls': 2, 'max_total_tokens': 2000})
        self.assertIs(storage.STATE, original_state)
        self.assertEqual([m['text'] for m in storage.memories()], ['production memory'])
        self.assertEqual(storage.conversations(), [])

    def test_agent_sanitized_fabricated_citation_still_fails_live_grading(self):
        calls = [{'type': 'function_call', 'name': 'plan_turn', 'arguments': json.dumps({'response_type': 'explanation', 'scope_json': '{}'}), 'call_id': 'c1'},
                 {'type': 'function_call', 'name': 'answer_explanation', 'arguments': json.dumps({'answer': 'This claim cites unavailable evidence [E99].'}), 'call_id': 'c2'}]
        case = {'question': 'Explain this convention.', 'contract': {'type': 'live_answer', 'inputs': {}},
                'expected': {'min_length': {'answer': 1}}}
        with patch.dict('os.environ', {'OPENAI_MODEL': 'mocked-test', 'OPENAI_API_KEY': 'mocked-test'}), patch.object(agent, 'request_model', return_value=calls):
            result = evaluations._side(case, self.snapshot, JobControl(lambda _: None),
                                       {'calls': 0, 'evidence_count': 0, 'max_model_calls': 2, 'max_total_tokens': 100000})
        self.assertEqual(result['status'], 'failed')
        self.assertIn('[Unverified reference: E99]', result['output']['answer'])
        self.assertTrue(result['output']['evidence_checks']['citation_warnings'])
        self.assertFalse(next(check for check in result['checks'] if check['name'] == 'registered answer references')['passed'])

    def test_unverified_currency_and_legacy_sanitized_markers_fail_live_checks(self):
        case = {'question': 'Explain measured sales.', 'contract': {'type': 'live_answer', 'inputs': {}},
                'expected': {'min_length': {'answer': 1}}}
        for answer, warnings, flags, failed_name in [
            ('Sales $999.00 [unverified amount]', ['Currency check: these narrative amounts did not match measured evidence: $999.00.'], {}, 'measured monetary claims'),
            ('Sales $999.00', [], {'unverified_amounts': ['$999.00']}, 'measured monetary claims'),
            ('Claim [Unverified reference: E99]', [], {}, 'registered answer references')]:
            output = {'answer': answer, 'warnings': warnings, 'evidence_checks': flags,
                      'workspace': {'snapshot_hash': self.snapshot['snapshot_hash']}}
            with patch.object(evaluations, 'execute_contract', return_value=output):
                result = evaluations._side(case, self.snapshot, JobControl(lambda _: None), {})
            self.assertEqual(result['status'], 'failed')
            self.assertFalse(next(check for check in result['checks'] if check['name'] == failed_name)['passed'])

    def test_storage_context_isolation_across_concurrent_workers(self):
        original_state = storage.STATE
        seen = {}
        barrier = threading.Barrier(2)
        def worker(name):
            with tempfile.TemporaryDirectory() as path, storage.use_state(path):
                storage.save_memory(name, 'test')
                barrier.wait(timeout=2)
                seen[name] = [m['text'] for m in storage.memories()]
        threads = [threading.Thread(target=worker, args=(name,)) for name in ('left', 'right')]
        for thread in threads: thread.start()
        for thread in threads: thread.join(3)
        self.assertEqual(seen, {'left': ['left'], 'right': ['right']})
        self.assertIs(storage.STATE, original_state)
        self.assertEqual(storage.memories(), [])

    def test_complete_pinned_reviewed_core_required_for_publication(self):
        run = self.run_core()
        before_review = evaluations.publication_gate(run['id'], self.snapshot)
        self.assertFalse(before_review['passed'])
        self.assertIn('operator', ' '.join(before_review['errors']))
        evaluations.review_run(run['id'], 'Test operator', 'approved', 'Reviewed full contracts and scope applicability. Narrative quality remains untested.')
        self.assertTrue(evaluations.publication_gate(run['id'], self.snapshot)['passed'])
        altered = {**self.snapshot, 'snapshot_hash': 'changed'}
        self.assertFalse(evaluations.publication_gate(run['id'], altered)['passed'])
        partial = self.run_core(max_cases=1)
        evaluations.review_run(partial['id'], 'Test operator', 'approved', 'Only a smoke sample; not release approval.')
        gate = evaluations.publication_gate(partial['id'], self.snapshot)
        self.assertFalse(gate['passed'])
        self.assertIn('complete bundled', ' '.join(gate['errors']))

    def test_old_live_failure_remains_a_gate_after_recent_history_limit(self):
        run = self.run_core()
        evaluations.review_run(run['id'], 'Operator', 'approved', 'Reviewed complete core checks.')
        evaluations._store({'id': 'old-live-failure', 'status': 'completed', 'mode': 'live', 'suite_id': 'live-semantics',
                            'candidate': {'snapshot_hash': self.snapshot['snapshot_hash']},
                            'summary': {'hard_failures': 1}, 'review': {'status': 'pending'}})
        for index in range(100):
            evaluations._store({'id': 'unrelated-'+str(index), 'status': 'completed', 'mode': 'deterministic',
                                'candidate': {'snapshot_hash': 'other-candidate'}, 'results': []})
        self.assertNotIn('old-live-failure', [item['id'] for item in evaluations.list_runs()])
        gate = evaluations.publication_gate(run['id'], self.snapshot)
        self.assertFalse(gate['passed'])
        self.assertIn('live-semantics', ' '.join(gate['errors']))
        evaluations._store({'id': 'new-live-success', 'status': 'completed', 'mode': 'live', 'suite_id': 'live-semantics',
                            'candidate': {'snapshot_hash': self.snapshot['snapshot_hash']},
                            'summary': {'hard_failures': 0}, 'review': {'status': 'approved'}})
        self.assertTrue(evaluations.publication_gate(run['id'], self.snapshot)['passed'])

    def test_regression_and_provenance_diff_are_independent(self):
        base = {'status': 'passed', 'output_hash': 'a', 'sources': [{'source': 'old'}]}
        changed = {'status': 'failed', 'output_hash': 'b', 'sources': [{'source': 'new'}]}
        result = evaluations.compare_sides(base, changed)
        self.assertTrue(result['regression'])
        self.assertTrue(result['outcome_changed'])
        self.assertTrue(result['source_changed'])
        self.assertFalse(result['improvement'])
        result = evaluations.compare_sides(base, {**base, 'sources': [{'source': 'new'}]})
        self.assertFalse(result['output_changed'])
        self.assertTrue(result['source_changed'])

    def test_comparison_ignores_query_spelling_and_presentation_timestamps(self):
        baseline = {'answer': 'Sales are $1.00.', 'outputs': [{'rows': [{'sales_cents': 100}], 'sql': 'SELECT 100 AS sales_cents'}],
                    'presentation': {'generated_at': 'before', 'scope': 'Web'}, 'usage': {'total_tokens': 20}}
        candidate = copy.deepcopy(baseline)
        candidate['outputs'][0]['sql'] = 'select (50 + 50) as sales_cents'
        candidate['presentation']['generated_at'] = 'after'
        candidate['usage']['total_tokens'] = 40
        self.assertEqual(evaluations.semantic_output(baseline), evaluations.semantic_output(candidate))
        candidate['outputs'][0]['rows'][0]['sales_cents'] = 101
        self.assertNotEqual(evaluations.semantic_output(baseline), evaluations.semantic_output(candidate))

    def test_live_budget_reservations_carry_between_sides_and_cases(self):
        suite = {'cases': [{'id': 'live-'+str(i), 'question': 'Explain the revenue metric.', 'mode': 'live',
                           'contract': {'type': 'live_answer', 'inputs': {}}, 'expected': {'min_length': {'answer': 1}}}
                          for i in range(2)]}
        assets.create_asset('evaluation_suite', 'Budget propagation', suite, id='budget-propagation')
        candidate = assets.candidate_snapshot()
        observed = []
        def fake_side(case, snapshot, control, budget):
            observed.append((budget['requests'], budget['reserved_tokens']))
            budget['requests'] += 1
            budget['reserved_tokens'] += 700
            budget['total_tokens'] += 600
            return {'status': 'passed', 'output': {'answer': 'Explanation'}, 'output_hash': 'answer', 'checks': [],
                    'failures': [], 'sources': [], 'elapsed_ms': 0}
        with patch('retail_app.backend.agent.configured', return_value=True), patch.object(evaluations, '_side', side_effect=fake_side):
            run = evaluations.start_run('budget-propagation', candidate_version_ids=list(candidate['asset_versions'].values()),
                                        mode='live', confirm_billable=True, max_model_calls=4, max_tokens=5000, background=False)
        self.assertEqual(run['status'], 'completed', run.get('error'))
        self.assertEqual(observed, [(0, 0), (1, 700), (2, 1400), (3, 2100)])
        self.assertEqual(run['usage']['reserved_tokens'], 2800)
        self.assertEqual(run['review']['status'], 'pending')
        self.assertTrue(all(result['review_status'] == 'pending' for result in run['results']))

    def test_cancelled_live_side_retains_provider_usage_reservation(self):
        suite = {'cases': [{'id': 'live-cancel', 'question': 'Explain revenue.', 'mode': 'live',
                           'contract': {'type': 'live_answer', 'inputs': {}}, 'expected': {'min_length': {'answer': 1}}}]}
        assets.create_asset('evaluation_suite', 'Live cancellation', suite, id='live-cancellation')
        candidate = assets.candidate_snapshot()
        def cancel_side(case, snapshot, control, budget):
            budget.update(requests=1, reserved_tokens=900, total_tokens=700)
            control.cancel()
            control.check_cancelled()
        with patch('retail_app.backend.agent.configured', return_value=True), patch.object(evaluations, '_side', side_effect=cancel_side):
            run = evaluations.start_run('live-cancellation', candidate_version_ids=list(candidate['asset_versions'].values()),
                                        mode='live', confirm_billable=True, max_model_calls=2, max_tokens=5000, background=False)
        self.assertEqual(run['status'], 'cancelled')
        self.assertEqual(run['usage']['reserved_tokens'], 900)
        self.assertEqual(run['usage']['requests'], 1)

    def test_profile_check_exercises_display_without_deleting_evidence(self):
        case = {'question': 'Preview quick answer', 'contract': {'type': 'workspace_profile', 'inputs': {
            'profile_id': 'quick-answer', 'payload': {'answer': 'Measured value', 'outputs': [{'evidence_id': 'E1', 'rows': [{'sales_cents': 123}]}],
                                                    'warnings': ['Synthetic fixture; descriptive.']}}},
                'expected': {'equals': {'output_display.table_rows': 5, 'outputs.0.rows.0.sales_cents': 123},
                             'contains': {'presentation.limitations': ['Synthetic fixture']}}}
        result = evaluations._side(case, self.snapshot, JobControl(lambda _: None))
        self.assertEqual(result['status'], 'passed', result['failures'])

    def test_cancelled_job_keeps_its_completed_results(self):
        started = threading.Event()
        def slow_side(case, snapshot, control, live_budget=None):
            started.set()
            while True: control.wait(.01)
        with patch.object(evaluations, '_side', side_effect=slow_side):
            run = evaluations.start_run('enterprise-core', max_cases=2)
            self.assertTrue(started.wait(2))
            evaluations.cancel_run(run['id'])
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline and evaluations.get_run(run['id'])['status'] in evaluations.ACTIVE:
                time.sleep(.01)
            final = evaluations.get_run(run['id'])
        self.assertEqual(final['status'], 'cancelled')
        self.assertEqual(final['results'], [])
        self.assertFalse(evaluations.publication_gate(run['id'], self.snapshot)['passed'])

    def test_restart_recovery_preserves_completed_case_artifacts(self):
        run = self.run_core(max_cases=1)
        raw = evaluations._read(run['id'])
        raw['status'] = 'running'
        evaluations._store(raw)
        self.assertEqual(evaluations.recover_interrupted_runs(), 1)
        recovered = evaluations.get_run(run['id'])
        self.assertEqual(recovered['status'], 'interrupted')
        self.assertEqual(recovered['results'], run['results'])
        self.assertEqual(evaluations.recover_interrupted_runs(), 0)

    def test_live_requires_explicit_billable_budget_and_mode_cases(self):
        with self.assertRaisesRegex(ValueError, 'billable'):
            evaluations.start_run('enterprise-core', mode='live', background=False)
        with self.assertRaisesRegex(ValueError, 'at most'):
            evaluations.start_run('enterprise-core', max_model_calls=41, background=False)
        with patch('retail_app.backend.agent.configured', return_value=True):
            with self.assertRaisesRegex(ValueError, 'no live cases'):
                evaluations.start_run('enterprise-core', mode='live', max_model_calls=2, max_tokens=2000,
                                      confirm_billable=True, background=False)

    def test_candidate_behavior_and_coverage_are_distinct_from_baseline(self):
        assets.create_asset('knowledge', 'Fulfillment promise clarification',
                            {'text': 'Warehouse promise is an allocation convention; it is not actual delivery.', 'aliases': ['allocation promise']},
                            id='allocation-promise')
        candidate = assets.candidate_snapshot()
        case = {'id': 'new-knowledge', 'name': 'Candidate knowledge retrieval', 'question': 'allocation promise',
                'mode': 'deterministic', 'category': 'retrieval', 'asset_ids': ['allocation-promise'],
                'contract': {'type': 'retrieval', 'inputs': {'query': 'allocation promise'}},
                'expected': {'contains': {'sources': ['allocation-promise']}}}
        base = evaluations._side(case, self.snapshot, JobControl(lambda _: None))
        changed = evaluations._side(case, candidate, JobControl(lambda _: None))
        self.assertEqual(base['status'], 'failed')
        self.assertEqual(changed['status'], 'passed', changed['failures'])
        self.assertTrue(evaluations.compare_sides(base, changed)['improvement'])
        self.assertTrue(evaluations.compare_sides(base, changed)['source_changed'])
        self.assertNotEqual(candidate['snapshot_hash'], self.snapshot['snapshot_hash'])
        run = evaluations.start_run('enterprise-core', candidate_version_ids=list(candidate['asset_versions'].values()),
                                    max_cases=1, background=False)
        self.assertIn('allocation-promise', run['coverage']['uncovered_assets'])

    def test_duplicated_output_profile_requires_visible_coverage_review(self):
        profile = next(asset for asset in self.snapshot['assets'] if asset['id'] == 'quick-answer')
        assets.create_asset('output_profile', 'Custom quick response', {**profile['content'], 'max_table_rows': 7}, id='custom-quick-response')
        candidate = assets.candidate_snapshot()
        run = evaluations.start_run('enterprise-core', candidate_version_ids=list(candidate['asset_versions'].values()), max_cases=1, background=False)
        self.assertIn('custom-quick-response', run['coverage']['uncovered_assets'])
        self.assertIn('custom-quick-response', [asset['id'] for asset in run['coverage']['changed_assets']])

    def test_human_approval_cannot_override_failed_checks(self):
        run = self.run_core(max_cases=1)
        raw = evaluations._read(run['id']); raw['summary']['hard_failures'] = 1; evaluations._store(raw)
        with self.assertRaisesRegex(ValueError, 'cannot be overridden'):
            evaluations.review_run(run['id'], 'Operator', 'approved', 'Attempted override')
        reviewed = evaluations.review_run(run['id'], 'Operator', 'rejected', 'Wrong scope needs a correction.')
        self.assertEqual(reviewed['review']['status'], 'rejected')


if __name__ == '__main__':
    unittest.main()
