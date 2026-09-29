"""Investigation persistence and decision checks; no model or network requests."""
from concurrent.futures import ThreadPoolExecutor
import importlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

_import_state = tempfile.TemporaryDirectory()
with patch.dict(os.environ, {'RETAIL_STATE_DIR': _import_state.name}):
    from retail_app.backend import storage, investigations as inv


SCOPE = {'start_date': '2025-01-01', 'end_date': '2025-01-31', 'channel': 'Web'}


def evidence(value=-12, **changes):
    return {'evidence_id': 'E1', 'sql': 'SELECT -12 AS sales_change', 'parameters': [],
            'rows': [{'sales_change': value}], 'row_count': 1, 'truncated': False,
            'scope': dict(SCOPE), **changes}


def node(identity='H1', **changes):
    return {'id': identity, 'statement': 'Web sales fell in the selected comparison.',
            'test': 'Compare the selected period sales change with zero.',
            'falsifier': 'Sales change is zero or positive.',
            'criterion': {'column': 'sales_change', 'operator': 'lt', 'threshold': 0}, **changes}


class InvestigationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state_patch = patch.object(storage, 'STATE', Path(self.tmp.name))
        self.state_patch.start()
        self.chat = storage.create_conversation('Retail investigation')['id']
        self.investigation = inv.create_investigation(self.chat, 'Why did sales fall?', dict(SCOPE))

    def tearDown(self):
        self.state_patch.stop()
        self.tmp.cleanup()

    def add(self, identity='H1', **changes):
        self.investigation = inv.upsert_hypothesis(self.investigation['id'], node(identity, **changes), self.investigation['revision'])
        return self.investigation

    def test_session_remembers_scope_summary_and_interface_dates_after_reload(self):
        inv.update_session(self.chat, {'summary': 'The user prefers gross margin.',
                                      'preferences': {'metric': 'gross_margin'}, 'ui_dates': {'start': '2025-01-01'}})
        importlib.reload(inv)
        session = inv.get_session(self.chat)
        self.assertEqual(session['scope'], SCOPE)
        self.assertIn('gross margin', session['summary'])
        self.assertEqual(session['ui_dates']['start'], '2025-01-01')
        self.assertEqual(inv.current_investigation(self.chat)['id'], self.investigation['id'])

    def test_scope_change_invalidates_evidence_and_clears_baseline(self):
        self.add()
        recorded = inv.record_test(self.investigation['id'], 'H1', evidence(), 'supported_descriptively', 'The measured change is negative.')
        inv.update_session(self.chat, {'scope': {**SCOPE, 'channel': 'Mobile App'}})
        current = inv.current_investigation(self.chat)
        self.assertGreater(current['revision'], recorded['revision'])
        self.assertEqual(current['hypotheses'][0]['status'], 'stale')
        self.assertEqual(current['hypotheses'][0]['evidence'], [])
        self.assertIsNone(current['baseline'])
        self.assertTrue(current['hypotheses'][0]['test_history'][0]['superseded'])
        with self.assertRaisesRegex(ValueError, 'scope differs'):
            inv.record_test(current['id'], 'H1', evidence(), 'supported_descriptively', 'Old scope cannot apply.')

    def test_scope_noop_keeps_investigation_revision(self):
        inv.update_session(self.chat, {'scope': dict(SCOPE)})
        self.assertEqual(inv.current_investigation(self.chat)['revision'], 1)

    def test_declared_criterion_computes_verdict(self):
        self.add()
        result = inv.record_test(self.investigation['id'], 'H1', evidence(), 'supported_descriptively', 'Negative measured change.', self.investigation['revision'])
        tested = result['hypotheses'][0]
        self.assertEqual(tested['verdict'], 'supported_descriptively')
        self.assertEqual(tested['status'], 'tested')
        self.assertEqual(tested['test_history'][0]['evaluation']['observed'], -12)
        self.assertIn('not causal', tested['test_history'][0]['evaluation']['reason'])

    def test_model_proposed_verdict_cannot_override_measurement(self):
        self.add()
        before = inv.get_investigation(self.investigation['id'])
        with self.assertRaisesRegex(ValueError, 'disagrees'):
            inv.record_test(before['id'], 'H1', evidence(10), 'supported_descriptively', 'Pretend it supports the theory.')
        self.assertEqual(inv.get_investigation(before['id']), before)

    def test_numeric_evaluator_covers_operators_null_and_invalid_cells(self):
        for op, threshold, verdict in [('gt', -20, 'supported_descriptively'), ('gte', -12, 'supported_descriptively'),
                                       ('lt', -20, 'contradicted'), ('lte', -12, 'supported_descriptively'),
                                       ('eq', -12, 'supported_descriptively'), ('ne', -12, 'contradicted')]:
            result = inv.evaluate_criterion(evidence(), {'column': 'sales_change', 'operator': op, 'threshold': threshold})
            self.assertEqual(result['verdict'], verdict)
        self.assertEqual(inv.evaluate_criterion(evidence(None), node()['criterion'])['verdict'], 'data_missing')
        for value in ('-12', True, float('nan')):
            with self.assertRaises(ValueError):
                inv.evaluate_criterion(evidence(value), node()['criterion'])

    def test_no_criterion_remains_inconclusive(self):
        self.add(criterion=None)
        with self.assertRaisesRegex(ValueError, 'Declare a measurable'):
            inv.record_test(self.investigation['id'], 'H1', evidence(), 'supported_descriptively', 'It looks persuasive.')
        result = inv.record_test(self.investigation['id'], 'H1', evidence(), 'inconclusive', 'Further controlled comparison is needed.')
        self.assertEqual(result['hypotheses'][0]['verdict'], 'inconclusive')

    def test_missing_data_verdict_is_explicit_and_durable(self):
        self.add()
        result = inv.record_test(self.investigation['id'], 'H1', None, 'data_missing', 'No campaign randomization field exists.')
        self.assertEqual(result['hypotheses'][0]['evidence'], [])
        self.assertEqual(result['hypotheses'][0]['verdict'], 'data_missing')
        with self.assertRaisesRegex(ValueError, 'Missing evidence'):
            inv.record_test(self.investigation['id'], 'H1', None, 'inconclusive', 'No result.')

    def test_query_provenance_and_complete_rows_required(self):
        self.add()
        for result in [evidence(truncated=True), evidence(model_preview_truncated=True), evidence(row_count=20),
                       evidence(sql=''), {'rows': [{'sales_change': -12}]}]:
            with self.assertRaises(ValueError):
                inv.record_test(self.investigation['id'], 'H1', result, 'supported_descriptively', 'Unsupported evidence input.')

    def test_tree_rejects_cycles_orphan_parents_and_untestable_statements(self):
        self.add()
        self.add('H2', parent_id='H1')
        with self.assertRaisesRegex(ValueError, 'cycle'):
            inv.edit_hypothesis(self.investigation['id'], 'H1', {'parent_id': 'H2'})
        with self.assertRaisesRegex(ValueError, 'parent hypothesis'):
            inv.upsert_hypothesis(self.investigation['id'], node('H3', parent_id='missing'))
        for field in ('statement', 'test', 'falsifier'):
            with self.assertRaises(ValueError):
                inv.upsert_hypothesis(self.investigation['id'], node('H3', **{field: ''}))
        with self.assertRaisesRegex(ValueError, 'Only record_test'):
            inv.edit_hypothesis(self.investigation['id'], 'H1', {'status': 'tested'})

    def test_edit_stales_descendants_but_preserves_history_and_siblings(self):
        self.add()
        self.add('H2', parent_id='H1')
        self.add('H3')
        for identity in ('H2', 'H3'):
            inv.record_test(self.investigation['id'], identity, evidence(), 'supported_descriptively', 'Measured negative change.')
        edited = inv.edit_hypothesis(self.investigation['id'], 'H1', {'statement': 'Investigate product mix instead.'})
        nodes = {n['id']: n for n in edited['hypotheses']}
        self.assertEqual(nodes['H1']['status'], 'stale')
        self.assertEqual(nodes['H2']['status'], 'stale')
        self.assertEqual(nodes['H3']['status'], 'tested')
        self.assertEqual(nodes['H2']['test_history'][0]['statement'], node()['statement'])
        self.assertTrue(nodes['H2']['test_history'][0]['superseded'])

    def test_edit_stales_parent_synthesis(self):
        self.add()
        self.add('H2', parent_id='H1')
        inv.record_test(self.investigation['id'], 'H1', evidence(), 'supported_descriptively', 'Older parent synthesis.')
        edited = inv.edit_hypothesis(self.investigation['id'], 'H2', {'statement': 'A corrected child explanation.'})
        self.assertEqual(edited['hypotheses'][0]['status'], 'stale')

    def test_user_semantic_edit_clears_old_decision_rule(self):
        self.add()
        edited = inv.edit_hypothesis(self.investigation['id'], 'H1', {'statement': 'Sales increased instead.'})
        self.assertIsNone(edited['hypotheses'][0]['criterion'])
        with self.assertRaisesRegex(ValueError, 'Declare a measurable'):
            inv.record_test(edited['id'], 'H1', evidence(), 'supported_descriptively', 'Do not reuse an old rule.')
        corrected = inv.edit_hypothesis(edited['id'], 'H1', {'criterion': {'column': 'sales_change', 'operator': 'gt', 'threshold': 0}})
        result = inv.record_test(corrected['id'], 'H1', evidence(), 'contradicted', 'The revised criterion does not hold.')
        self.assertEqual(result['hypotheses'][0]['verdict'], 'contradicted')

    def test_exclusion_preserves_tree_history_and_requires_restore(self):
        self.add()
        self.add('H2', parent_id='H1')
        excluded = inv.edit_hypothesis(self.investigation['id'], 'H1', {'excluded': True})
        self.assertEqual([n['status'] for n in excluded['hypotheses']], ['excluded', 'excluded'])
        with self.assertRaisesRegex(ValueError, 'excluded hypothesis'):
            inv.record_test(excluded['id'], 'H2', evidence(), 'supported_descriptively', 'No longer authorized branch.')
        with self.assertRaisesRegex(ValueError, 'Reactivate the parent'):
            inv.edit_hypothesis(excluded['id'], 'H2', {'status': 'planned'})
        restored = inv.edit_hypothesis(excluded['id'], 'H1', {'excluded': False})
        self.assertEqual(restored['hypotheses'][0]['status'], 'planned')
        self.assertEqual(restored['hypotheses'][1]['status'], 'excluded')

    def test_old_completion_rejected_after_user_edit(self):
        self.add()
        old_revision = self.investigation['revision']
        inv.edit_hypothesis(self.investigation['id'], 'H1', {'statement': 'User corrected explanation.'}, old_revision)
        with self.assertRaises(inv.RevisionConflict):
            inv.record_test(self.investigation['id'], 'H1', evidence(), 'supported_descriptively', 'Old worker response.', old_revision)
        with self.assertRaises(inv.RevisionConflict):
            inv.finish_investigation(self.investigation['id'], 'Old worker conclusion.', 'incomplete', old_revision)

    def test_concurrent_updates_only_one_revision_wins(self):
        self.add()
        identity, revision = self.investigation['id'], self.investigation['revision']
        def edit(number):
            try:
                inv.edit_hypothesis(identity, 'H1', {'statement': 'Correction ' + str(number)}, revision)
                return 'saved'
            except inv.RevisionConflict:
                return 'conflict'
        with ThreadPoolExecutor(max_workers=2) as callers:
            results = list(callers.map(edit, (1, 2)))
        self.assertEqual(sorted(results), ['conflict', 'saved'])
        self.assertEqual(inv.get_investigation(identity)['revision'], revision + 1)

    def test_finish_requires_leaves_but_allows_unmeasured_parent(self):
        self.add()
        self.add('H2', parent_id='H1')
        with self.assertRaisesRegex(ValueError, 'Unfinished'):
            inv.finish_investigation(self.investigation['id'], 'Premature conclusion.')
        inv.record_test(self.investigation['id'], 'H2', evidence(), 'supported_descriptively', 'Leaf tested.')
        finished = inv.finish_investigation(self.investigation['id'], 'Leaf evidence summarized; no causal claim.')
        self.assertEqual(finished['status'], 'complete')
        self.assertEqual(finished['hypotheses'][0]['status'], 'planned')

    def test_partial_completion_keeps_unfinished_work_visible(self):
        self.add()
        result = inv.finish_investigation(self.investigation['id'], 'The next test remains unfinished.', status='partial')
        self.assertEqual(result['status'], 'incomplete')
        self.assertEqual(result['hypotheses'][0]['status'], 'planned')

    def test_new_investigation_supersedes_old_worker(self):
        previous = self.investigation
        new = inv.create_investigation(self.chat, 'Why did units rise?', SCOPE)
        self.assertEqual(inv.current_investigation(self.chat)['id'], new['id'])
        self.assertEqual(inv.get_investigation(previous['id'])['status'], 'superseded')
        with self.assertRaises(inv.RevisionConflict):
            inv.upsert_hypothesis(previous['id'], node())

    def test_input_and_return_mutation_cannot_rewrite_saved_evidence(self):
        self.add()
        measured = evidence()
        result = inv.record_test(self.investigation['id'], 'H1', measured, 'supported_descriptively', 'Measured decline.')
        measured['rows'][0]['sales_change'] = 999
        result['hypotheses'][0]['test_history'][0]['evidence']['rows'][0]['sales_change'] = 888
        saved = inv.get_investigation(self.investigation['id'])
        self.assertEqual(saved['hypotheses'][0]['test_history'][0]['evidence']['rows'][0]['sales_change'], -12)
        self.assertEqual([e['revision'] for e in inv.revision_history(saved['id'])], [1, 2, 3])

    def test_session_cannot_adopt_another_chats_investigation(self):
        other_chat = storage.create_conversation()['id']
        with self.assertRaisesRegex(ValueError, 'another conversation'):
            inv.update_session(other_chat, {'investigation_id': self.investigation['id']})
        with self.assertRaisesRegex(ValueError, 'Conversation not found'):
            inv.get_session('missing')

    def test_partition_reconciliation_checks_totals_and_unique_keys(self):
        parts = evidence(rows=[{'channel': 'Web', 'value': 4}, {'channel': 'Store', 'value': 6}], row_count=2)
        total = {'evidence': evidence(10), 'column': 'sales_change'}
        result = inv.reconcile_partition(parts, 'value', total, ['channel'])
        self.assertTrue(result['reconciled'])
        self.assertTrue(result['total_evidence_verified'])
        self.assertFalse(result['membership_disjoint_verified'])
        self.assertFalse(inv.reconcile_partition(parts, 'value', 11, ['channel'])['reconciled'])
        duplicate = evidence(rows=[{'channel': 'Web', 'value': 4}, {'channel': 'Web', 'value': 6}], row_count=2)
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            inv.reconcile_partition(duplicate, 'value', 10, ['channel'])

    def test_partition_membership_detects_overlapping_observations(self):
        parts = evidence(rows=[{'channel': 'Web', 'value': 4, 'orders': ['a']},
                               {'channel': 'Store', 'value': 6, 'orders': ['a', 'b']}], row_count=2)
        with self.assertRaisesRegex(ValueError, 'overlaps'):
            inv.reconcile_partition(parts, 'value', 10, ['channel'], member_ids_column='orders')
        parts['rows'][1]['orders'] = ['b']
        self.assertTrue(inv.reconcile_partition(parts, 'value', 10, ['channel'], member_ids_column='orders')['membership_disjoint_verified'])


if __name__ == '__main__':
    unittest.main()
