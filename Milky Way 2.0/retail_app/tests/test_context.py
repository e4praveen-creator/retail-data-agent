"""Domain retrieval regression tests over the actual, allowlisted project assets."""
import json
import unittest
from collections import Counter
from retail_app.backend.context import INDEX, ROOT, MAX_CHUNK_CHARS, MAX_SEARCH_CHARS


class DomainContextTests(unittest.TestCase):
    def find(self, query, role, text):
        matches = INDEX.search(query)
        self.assertTrue(any(h['role'] == role and text.lower() in (h['heading'] + '\n' + h['text']).lower() for h in matches), query)
        return matches

    def test_aov_uses_header_metric_contract(self):
        hits = self.find('AOV metric definition', 'metric_contract', 'no header-to-line fan-out')
        self.assertIn('AOV before returns', hits[0]['heading'])

    def test_pvm_visual_and_answer_template(self):
        hits = self.find('visual price volume mix waterfall', 'visual_specification', 'reconciled waterfall')
        self.assertEqual(hits[0]['role'], 'visual_specification')
        self.assertTrue(any(h['role'] == 'playbook' and 'E. Output Template' in h['text'] for h in hits))
        self.assertEqual(len({h['text'].strip() for h in hits}), len(hits))

    def test_retail_hypothesis_keeps_test_falsifier_and_limitation(self):
        hits = self.find('hypotheses digital softgoods returns Footwear', 'hypothesis_template', 'digital-softgoods-returns')
        first = hits[0]
        self.assertIn('"falsifier"', first['text'])
        self.assertIn('"limitation"', first['text'])
        self.assertIn('untested_template', first['text'])
        self.assertIn('Untested candidate', first['source_note'])

    def test_repeat_uses_mature_denominators(self):
        hits = self.find('customer repeat 90 day maturity denominator', 'hypothesis_template', 'mature-repeat')
        self.assertTrue(any(h['role'] == 'visual_specification' and 'eligible' in h['text'] for h in hits))

    def test_dates_preserve_return_only_tail(self):
        hits = self.find('sales date range returns tail', 'metric_contract', 'March 1, 2026')
        self.assertIn('December 31, 2025', hits[0]['text'])
        self.assertIn('60-day', hits[0]['text'])

    def test_catalog_and_join_grains_retrieved(self):
        hits = self.find('channel_key grain join fact_sales_line', 'schema', 'fact_sales_line')
        self.assertTrue(any(h['source'].endswith('catalog.json') for h in hits))
        self.assertTrue(any(h['role'] == 'metric_contract' and 'Join rules' in h['heading'] for h in hits))

    def test_inventory_validation_has_saved_artifact_label(self):
        hits = self.find('inventory reconciliation validation checks', 'validation_record', 'inventory sales reconciliation')
        self.assertTrue(any(h['source'].endswith('full_validation_report.json') and 'not a fresh validation' in h['source_note'] for h in hits))

    def test_causal_question_routes_to_data_gap(self):
        hits = self.find('promotion incremental lift', 'question_router', 'Randomized holdout')
        self.assertIn('Questions the data cannot fully answer', hits[0]['heading'])

    def test_worked_examples_are_not_current_evidence(self):
        hits = INDEX.search('worked example price volume mix')
        examples = [h for h in hits if h['role'] == 'worked_example']
        self.assertTrue(examples)
        self.assertTrue(all('rerun the requested scope' in h['source_note'] for h in examples))

    def test_architecture_is_explicitly_reference_only(self):
        hits = self.find('Milky Way architecture', 'design_reference', 'architecture preserved')
        self.assertTrue(all('does not override' in h['source_note'] for h in hits if h['role'] == 'design_reference'))

    def test_all_hypotheses_and_catalog_tables_are_indexed(self):
        bank = json.loads((ROOT / 'retail_app/knowledge/hypotheses.json').read_text())
        indexed = [c for c in INDEX.chunks if c['role'] == 'hypothesis_template']
        self.assertEqual(len(indexed), len(bank)); self.assertEqual(len(bank), 18)
        for item in bank:
            self.assertTrue(any(c['heading'].startswith(item['id'] + ' —') for c in indexed))
        catalog = json.loads((ROOT / 'retail_data/docs/catalog.json').read_text())
        self.assertEqual(len(catalog), 23)
        for table in catalog:
            self.assertTrue(any(c['source'].endswith('catalog.json') and c['heading'] == table for c in INDEX.chunks))

    def test_source_locations_reproduce_original_text(self):
        documents = {d['path']: INDEX.document(d['path']).splitlines() for d in INDEX.documents}
        for chunk in INDEX.chunks:
            lines = documents[chunk['source']]
            self.assertTrue(1 <= chunk['line'] <= chunk['line_end'] <= len(lines))
            expected = '\n'.join(lines[chunk['line'] - 1:chunk['line_end']])
            if not chunk['truncated']:
                self.assertEqual(chunk['text'], expected)
            self.assertLessEqual(len(chunk['text']), MAX_CHUNK_CHARS + 100)

    def test_bounded_reproducible_diverse_results(self):
        query = 'sales units inventory returns customer hypothesis metric visual ' * 1000
        first = INDEX.search(query, 12)
        self.assertEqual(first, INDEX.search(query, 12))
        self.assertLessEqual(len(first), 12)
        self.assertLessEqual(sum(len(h['text']) + len(h['heading']) for h in first), MAX_SEARCH_CHARS)
        self.assertLessEqual(max(Counter(h['source'] for h in first).values()), 2)
        self.assertEqual(INDEX.search(''), [])
        for limit in (0, -1, 13, True, '6'):
            with self.assertRaises(ValueError): INDEX.search('sales', limit)

    def test_only_curated_reference_assets_can_be_opened(self):
        for path in ('../../etc/passwd', 'retail_app/.env', 'retail_app/state/chat.sqlite3', 'retail_data/docs/SAMPLE_ROWS.json'):
            with self.assertRaises(ValueError): INDEX.document(path)
        paths = [d['path'] for d in INDEX.documents]
        self.assertFalse(any('/state/' in path or path.endswith(('.csv', '.duckdb', '.env')) for path in paths))


if __name__ == '__main__': unittest.main()
