"""Registry publication, migration and isolation contracts using temporary state."""
import copy
import json
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from retail_app.backend import storage, workspace_assets as registry
from retail_app.backend.workspace_api import router


class WorkspaceFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = patch.object(storage, 'STATE', Path(self.tmp.name))
        self.state.start()
        registry.ensure_initialized()

    def tearDown(self):
        self.state.stop()
        self.tmp.cleanup()

    def concept(self, id='custom-concept', name='Weather adjusted demand', **content):
        return registry.create_asset('ontology', name, {
            'concept_type': 'concept', 'description': 'A documentary weather planning concept; observations are unavailable.',
            'aliases': ['weather planning'], **content,
        }, id=id)

    def activate(self, release):
        with patch('retail_app.backend.workspace_evaluations.publication_gate', return_value={'passed': True}):
            return registry.publish(release['id'], registry.active_snapshot()['release_id'], evaluation_run_id='checked-run')


class WorkspaceRegistryTests(WorkspaceFixture):
    def test_seed_is_idempotent_and_preserves_original_chats(self):
        conversation = storage.create_conversation('Existing conversation')
        storage.add_message(conversation['id'], 'user', 'Retain my existing chat.')
        before = registry.active_snapshot()
        registry.ensure_initialized()
        after = registry.active_snapshot()
        self.assertEqual(before, after)
        self.assertEqual(len(storage.conversation(conversation['id'])['messages']), 1)
        self.assertEqual(len([a for a in after['assets'] if a['kind'] == 'skill']), 19)
        self.assertTrue(any(a['id'] == 'enterprise-core' for a in after['assets']))
        self.assertEqual(len(registry.list_releases()), 1)

    def test_skill_contracts_join_stable_numbered_sections(self):
        contracts = registry.load_builtin_contracts()
        self.assertEqual(set(contracts), set(registry.BUILTIN_SKILLS))
        for slug, number in registry.BUILTIN_SKILLS.items():
            self.assertEqual(contracts[slug]['number'], number)
            self.assertTrue(contracts[slug]['method'])
            self.assertTrue(contracts[slug]['visual_spec'])
        self.assertIn('symmetric identity', contracts['pvm']['method'])

    def test_draft_never_changes_active_snapshot_or_answer_capture(self):
        before = registry.active_snapshot()
        asset = self.concept()
        candidate = registry.candidate_snapshot([asset['id']])
        self.assertNotIn(asset['id'], before['asset_versions'])
        self.assertEqual(before, registry.active_snapshot())
        self.assertIn(asset['id'], candidate['asset_versions'])
        registry.update_asset(asset['id'], {**asset['content'], 'description': 'A revised documentary definition.'}, 1)
        frozen = next(a for a in candidate['assets'] if a['id'] == asset['id'])
        self.assertNotEqual(frozen['content']['description'], registry.get_asset(asset['id'])['content']['description'])

    def test_optimistic_revision_rejects_stale_edit(self):
        asset = self.concept()
        registry.update_asset(asset['id'], asset['content'], 1)
        with self.assertRaises(registry.WorkspaceError) as caught:
            registry.update_asset(asset['id'], {'description': 'Stale overwrite'}, 1)
        self.assertEqual(caught.exception.code, 'stale_revision')

    def test_concurrent_updates_have_one_winner(self):
        asset = self.concept()
        def update(value):
            try:
                return registry.update_asset(asset['id'], {**asset['content'], 'description': value}, 1)['draft_revision']
            except registry.WorkspaceError as exc:
                return exc.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(update, ['First editor', 'Second editor']))
        self.assertCountEqual(results, [2, 'stale_revision'])

    def test_duplicate_id_and_path_identifier_rejected(self):
        self.concept()
        with self.assertRaises(registry.WorkspaceError) as caught: self.concept()
        self.assertEqual(caught.exception.code, 'asset_id_conflict')
        with self.assertRaises(registry.WorkspaceError): self.concept(id='../../secrets')

    def test_alias_conflict_ignores_case_and_duplicate_whitespace(self):
        self.concept(aliases=['AOV'])
        validation = registry.validate_candidate()
        self.assertFalse(validation['valid'])
        self.assertTrue(any(e['code'] == 'alias_conflict' for e in validation['errors']))

    def test_unsupported_metric_mapping_can_save_but_cannot_validate(self):
        asset = self.concept(concept_type='metric', measure='actual_delivery_days', units='days', date_basis='sale_date', return_basis='before_returns')
        self.assertEqual(asset['status'], 'draft')
        self.assertTrue(any(e['code'] == 'needs_data_support' for e in registry.validate_asset(asset['id'])['errors']))

    def test_metric_units_and_malformed_fields_fail_as_validation_errors(self):
        asset = self.concept(concept_type='metric', measure='sales_cents', units='USD', date_basis='sale_date', return_basis='before_returns')
        self.assertIn('unit_mapping_mismatch', {e['code'] for e in registry.validate_asset(asset['id'])['errors']})
        registry.update_asset(asset['id'], {'description': 'Invalid type', 'from_id': {}, 'aliases': [42]}, 1)
        self.assertIn('invalid_text_list', {e['code'] for e in registry.validate_asset(asset['id'])['errors']})
        preview = registry.preview('Invalid type', [asset['id']])
        self.assertFalse(preview['validation']['valid'])
        self.assertIn(asset['id'], preview['excluded_asset_ids'])
        self.assertFalse(any(source.get('asset_id') == asset['id'] for source in preview['results']))

    def test_documentary_metric_explicitly_has_no_execution(self):
        asset = self.concept(concept_type='metric', documentary=True)
        validation = registry.validate_asset(asset['id'])
        self.assertTrue(validation['valid'])
        self.assertEqual(validation['warnings'][0]['code'], 'documentary_only')

    def test_missing_relationship_and_skill_dependencies_block_release(self):
        self.concept(concept_type='relationship', from_id='missing', to_id='metric-aov')
        registry.create_asset('skill', 'Unsupported skill', {'description': 'Test', 'method': 'Test',
            'handler': 'python:uploaded-code', 'approved_tools': ['run_shell'], 'required_concepts': ['missing'], 'output_profile_id': 'missing-profile'}, id='invalid-skill')
        codes = {e['code'] for e in registry.validate_candidate()['errors']}
        self.assertTrue({'missing_reference', 'unknown_handler', 'unsupported_tool', 'missing_dependency', 'missing_profile'} <= codes)

    def test_profile_cannot_hide_scope_evidence_or_caveats(self):
        profile = registry.create_asset('output_profile', 'Bad display', {'detail': 'concise', 'show_evidence': False,
            'show_scope': False, 'show_limitations': False}, id='bad-display')
        self.assertEqual(len([e for e in registry.validate_asset(profile['id'])['errors'] if e['code'] == 'required_safeguard']), 3)

    def test_reference_baseline_read_only_and_immutable_versions(self):
        original = next(a for a in registry.list_assets('knowledge') if a['built_in'])
        with self.assertRaises(registry.WorkspaceError) as caught:
            registry.update_asset(original['id'], {'description': 'Replace built-in'}, 0)
        self.assertEqual(caught.exception.code, 'baseline_read_only')
        with storage.connection() as con:
            with self.assertRaises(sqlite3.IntegrityError): con.execute("UPDATE workspace_versions SET content='{}'")
            with self.assertRaises(sqlite3.IntegrityError): con.execute('DELETE FROM workspace_releases')

    def test_publish_requires_validation_and_successful_evaluation(self):
        self.concept()
        release = registry.create_candidate_release()
        with self.assertRaises(registry.WorkspaceError) as caught:
            registry.publish(release['id'], 'release-baseline')
        self.assertEqual(caught.exception.code, 'evaluation_required')
        with patch('retail_app.backend.workspace_evaluations.publication_gate', return_value={'passed': False, 'errors': ['wrong scope']}):
            with self.assertRaises(registry.WorkspaceError) as caught:
                registry.publish(release['id'], 'release-baseline', evaluation_run_id='failed-run')
        self.assertEqual(caught.exception.code, 'evaluation_gate_failed')
        self.assertEqual(registry.active_snapshot()['release_id'], 'release-baseline')

    def test_publish_atomically_switches_release_and_rollback_restores(self):
        captured = registry.active_snapshot()
        self.concept()
        release = registry.create_candidate_release(name='Reviewed weather context')
        self.activate(release)
        self.assertEqual(registry.active_snapshot()['release_id'], release['id'])
        self.assertNotIn('custom-concept', captured['asset_versions'])
        self.assertIn('custom-concept', registry.active_snapshot()['asset_versions'])
        registry.rollback('release-baseline', release['id'], rationale='Revert review')
        self.assertEqual(registry.active_snapshot()['asset_versions'], captured['asset_versions'])
        self.assertEqual(registry.get_release(release['id'])['status'], 'published')

    def test_stale_active_pointer_and_stale_candidate_rejected(self):
        self.concept()
        first, stale = registry.create_candidate_release(), registry.create_candidate_release()
        self.activate(first)
        with patch('retail_app.backend.workspace_evaluations.publication_gate', return_value={'passed': True}):
            with self.assertRaises(registry.WorkspaceError) as caught:
                registry.publish(stale['id'], 'release-baseline', evaluation_run_id='pass')
            self.assertEqual(caught.exception.code, 'stale_active_release')
            with self.assertRaises(registry.WorkspaceError) as caught:
                registry.publish(stale['id'], first['id'], evaluation_run_id='pass')
            self.assertEqual(caught.exception.code, 'stale_candidate')

    def test_concurrent_review_change_prevents_publication(self):
        release = registry.create_candidate_release()
        payload = {'candidate': {'snapshot_hash': release['snapshot_hash']}, 'review': {'status': 'approved'}, 'summary': {'hard_failures': 0}, 'completed_cases': 76, 'total_cases': 76}
        with storage.connection() as con:
            con.execute('CREATE TABLE workspace_evaluation_runs(id TEXT PRIMARY KEY,status TEXT,updated TEXT,payload TEXT)')
            con.execute('INSERT INTO workspace_evaluation_runs VALUES(?,?,?,?)', ('reviewed-run', 'completed', 'now', json.dumps(payload)))
        def reject_during_gate(*args):
            payload['review']['status'] = 'rejected'
            with storage.connection() as con:
                con.execute('UPDATE workspace_evaluation_runs SET payload=? WHERE id=?', (json.dumps(payload), 'reviewed-run'))
            return {'passed': True}
        with patch('retail_app.backend.workspace_evaluations.publication_gate', side_effect=reject_during_gate):
            with self.assertRaises(registry.WorkspaceError) as caught:
                registry.publish(release['id'], 'release-baseline', evaluation_run_id='reviewed-run')
        self.assertEqual(caught.exception.code, 'stale_evaluation')
        self.assertEqual(registry.active_snapshot()['release_id'], 'release-baseline')

    def test_cannot_rollback_to_never_published_candidate(self):
        release = registry.create_candidate_release()
        with self.assertRaises(registry.WorkspaceError) as caught:
            registry.rollback(release['id'], 'release-baseline')
        self.assertEqual(caught.exception.code, 'unpublished_rollback')

    def test_candidate_preview_isolated_then_published_context_available(self):
        asset = self.concept(aliases=['winter-weather-specialist'])
        self.assertFalse(any(s.get('asset_id') == asset['id'] for s in registry.search_snapshot(registry.active_snapshot(), 'winter-weather-specialist')))
        preview = registry.preview('winter-weather-specialist', [asset['id']])
        self.assertTrue(any(s.get('asset_id') == asset['id'] for s in preview['results']))
        release = registry.create_candidate_release([asset['id']]); self.activate(release)
        source = next(s for s in registry.search_snapshot(registry.active_snapshot(), 'winter-weather-specialist') if s['asset_id'] == asset['id'])
        self.assertEqual(registry.read_version_source(source['source'])['version_id'], source['version_id'])

    def test_original_retrieval_roles_and_exact_frozen_source_survive(self):
        snapshot = registry.active_snapshot()
        result = registry.search_snapshot(snapshot, 'promotion incremental lift')[0]
        self.assertEqual(result['role'], 'question_router')
        self.assertTrue(result['source'].startswith('workspace/'))
        original = registry.read_version_source(result['source'])['text']
        self.assertIn('Randomized holdout', original)
        with patch('retail_app.backend.context.INDEX.search', return_value=[]):
            self.assertEqual(result, registry.search_snapshot(snapshot, 'promotion incremental lift')[0])

    def test_expected_values_never_enter_retrieval_or_runtime_settings(self):
        secret = 'GOLDEN_NEVER_SEND_9381'
        profile = registry.create_asset('output_profile', 'Reference display', {'detail': 'standard',
            'expected': secret, 'nested': {'cases': [secret]}}, id='reference-display')
        registry.create_asset('skill', 'Weather planning specialist', {'description': 'Weather planning', 'method': 'Use approved evidence.',
            'approved_tools': ['query_retail'], 'expected_answer': secret, 'handler': 'method_only', 'output_profile_id': profile['id'],
            'trigger_examples': ['weather planning'], 'source_refs': [{'expected': secret}]}, id='weather-specialist')
        snapshot = registry.candidate_snapshot()
        settings = registry.snapshot_context(snapshot, 'weather planning', output_profile_id=profile['id'])
        self.assertNotIn(secret, json.dumps(settings))
        self.assertFalse(any(source['asset_id'] == 'enterprise-core' for source in registry.search_snapshot(snapshot, 'expected cases validation scope')))
        core = next(a for a in snapshot['assets'] if a['id'] == 'enterprise-core')
        with self.assertRaises(registry.WorkspaceError): registry.read_version_source('workspace/enterprise-core/' + core['version_id'])

    def test_feedback_captures_original_answer_provenance_and_review_required(self):
        with storage.connection() as con:
            con.execute('INSERT INTO analyses(id,question,payload) VALUES(?,?,?)', ('test-answer', 'Why did returns rise?', json.dumps({
                'answer': 'Original answer', 'workspace': {'release_id': 'release-baseline'}, 'outputs': [{'evidence_id': 'E1', 'rows': [{'units': 2}]}]})))
        item = registry.create_feedback('test-answer', ['definition'], 'Use the mature sales-cohort denominator.')
        self.assertEqual(item['provenance']['release_id'], 'release-baseline')
        with self.assertRaises(registry.WorkspaceError): registry.convert_feedback(item['id'], 1)
        item = registry.update_feedback(item['id'], 1, 'reviewed')
        converted = registry.convert_feedback(item['id'], item['revision'])
        case = converted['asset']['content']['cases'][0]
        self.assertNotIn('expected', case)
        self.assertEqual(case['contract']['type'], 'live_answer')
        self.assertTrue(case['requires_human_review'])
        self.assertEqual(converted['feedback']['original_answer'], 'Original answer')
        self.assertFalse(registry.validate_asset(converted['asset']['id'])['valid'])
        self.assertNotIn(converted['asset']['id'], registry.active_snapshot()['asset_versions'])

    def test_context_local_state_isolation(self):
        before = registry.active_snapshot()
        with tempfile.TemporaryDirectory() as isolated:
            with storage.use_state(isolated):
                registry.ensure_initialized(); self.concept()
                self.assertEqual(len(registry.list_assets('ontology')), 5)
        self.assertEqual(registry.active_snapshot(), before)
        self.assertEqual(len(registry.list_assets('ontology')), 4)


class WorkspaceApiTests(WorkspaceFixture):
    def setUp(self):
        super().setUp()
        app = FastAPI(); app.include_router(router)
        self.client = TestClient(app)

    def test_api_roundtrip_conflicts_and_structured_errors(self):
        response = self.client.post('/api/workspace/assets', json={'id': 'ui-definition', 'kind': 'ontology', 'name': 'UI definition',
            'content': {'description': 'A UI-authored documentary concept.', 'concept_type': 'concept'}})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['draft_revision'], 1)
        body = {'content': {'description': 'Edited UI concept'}, 'expected_revision': 1}
        self.assertEqual(self.client.put('/api/workspace/assets/ui-definition', json=body).status_code, 200)
        conflict = self.client.put('/api/workspace/assets/ui-definition', json=body)
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.json()['detail']['code'], 'stale_revision')
        self.assertTrue(self.client.post('/api/workspace/assets/ui-definition/validate').json()['valid'])

    def test_api_requires_typed_revision_and_lists_custom_profiles(self):
        self.assertEqual(self.client.put('/api/workspace/assets/quick-answer', json={'content': {}, 'expected_revision': True}).status_code, 422)
        registry.create_asset('output_profile', 'New audience', {'detail': 'standard'}, id='new-audience')
        self.assertIn('new-audience', self.client.get('/api/workspace/capabilities').json()['profiles'])

    def test_api_builtins_require_duplication_for_every_asset_kind(self):
        for asset_id in ('quick-answer', 'skill-trend', 'metric-sales', 'enterprise-core'):
            original = registry.get_asset(asset_id)
            rejected = self.client.put('/api/workspace/assets/' + asset_id, json={'content': original['content'], 'expected_revision': 0})
            self.assertEqual(rejected.status_code, 409)
            self.assertEqual(rejected.json()['detail']['code'], 'baseline_read_only')
        profile = registry.get_asset('quick-answer')
        copied = self.client.post('/api/workspace/assets', json={'kind': 'output_profile', 'name': 'Custom quick answer', 'content': profile['content']})
        self.assertEqual(copied.status_code, 201)
        edited = self.client.put('/api/workspace/assets/' + copied.json()['id'], json={'content': {**profile['content'], 'detail': 'detailed'}, 'expected_revision': 1})
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(edited.json()['content']['detail'], 'detailed')


if __name__ == '__main__':
    unittest.main()
