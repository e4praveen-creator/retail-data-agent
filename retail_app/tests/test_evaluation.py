"""Offline regression checks for the manually invoked golden-question grader.

Uses an isolated tiny DuckDB fixture; no app state, credentials or model calls.
"""
import json
from pathlib import Path
import tempfile
import unittest

import duckdb

from retail_app.tests.evaluate_agent import (
    cited_references, grade, inspect_evidence, metric_match, parsed_source_tables,
)


class ParserConnection:
    """Simulate the known binder failure without blocking parser-only inspection."""
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.connection.close()

    def execute(self, *args):
        return self.connection.execute(*args)

    def get_table_names(self, sql):
        raise duckdb.BinderException('View metadata binding failed')


class FixtureData:
    def __init__(self, path):
        self.path = path
        self.replays = 0

    def connect(self):
        return ParserConnection(duckdb.connect(str(self.path), read_only=True,
                                             config={'enable_external_access': False}))

    def select_sql(self, sql, parameters=None, limit=500):
        self.replays += 1
        with self.connect() as connection:
            cursor = connection.execute(sql, parameters or [])
            names = [column[0] for column in cursor.description]
            rows = [dict(zip(names, row)) for row in cursor.fetchmany(limit + 1)]
        # App SQL evidence serializes Decimal values as strings.
        return json.loads(json.dumps({'rows': rows[:limit], 'truncated': len(rows) > limit}, default=str))


class EvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='retail-evaluation-test-')
        cls.path = Path(cls.temporary.name) / 'fixture.duckdb'
        with duckdb.connect(str(cls.path)) as connection:
            connection.execute('CREATE TABLE fact_sales_line(sku_key INTEGER, net_sales_cents BIGINT, quantity INTEGER)')
            connection.execute('INSERT INTO fact_sales_line VALUES(1,12000,2),(2,5000,1)')
            connection.execute('CREATE TABLE dim_sku(sku_key INTEGER, division_name VARCHAR)')
            connection.execute("INSERT INTO dim_sku VALUES(1,'Footwear'),(2,'Apparel')")
            connection.execute('CREATE VIEW v_product AS SELECT * FROM dim_sku')
            connection.execute('CREATE VIEW v_sales AS SELECT * FROM fact_sales_line')
        cls.sql = ("SELECT sum(s.net_sales_cents) AS net_sales_cents, sum(s.quantity) AS sold_units "
                   "FROM fact_sales_line s JOIN v_product p USING(sku_key) WHERE p.division_name='Footwear'")
        cls.case = {'metrics': {'sales_cents': 'money_cents', 'units': 'units'},
                    'manual_review': ['Check scope and narrative.']}
        cls.golden = {'sales_cents': 12000, 'units': 2}

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def setUp(self):
        self.data = FixtureData(self.path)

    def result(self, sql=None, answer='Measured totals [E1].'):
        sql = sql or self.sql
        output = self.data.select_sql(sql)
        return {'answer': answer, 'outputs': [{'name': 'custom_query', 'evidence_id': 'E1',
                                              'sql': sql, 'parameters': [], **output}], 'context': []}

    def sources(self, sql):
        with self.data.connect() as connection:
            return parsed_source_tables(connection, sql)

    def test_valid_product_view_join_uses_parser_without_binding(self):
        result = self.result()
        grading = grade(self.case, result, self.golden, self.data)
        self.assertTrue(grading['automated_checks_passed'])
        self.assertEqual(grading['evidence_replay'][0]['source_tables'], ['fact_sales_line', 'v_product'])

    def test_known_fact_view_and_used_cte_resolve(self):
        self.assertEqual(self.sources('WITH measured AS (SELECT * FROM v_sales) SELECT * FROM measured'), {'v_sales'})
        result = self.result('WITH measured AS (' + self.sql + ') SELECT * FROM measured')
        self.assertTrue(grade(self.case, result, self.golden, self.data)['automated_checks_passed'])

    def test_constant_magic_numbers_do_not_count_as_measured_evidence(self):
        result = self.result('SELECT 12000 AS net_sales_cents, 2 AS sold_units')
        self.assertFalse(grade(self.case, result, self.golden, self.data)['automated_checks_passed'])

    def test_cte_named_after_fact_cannot_fake_provenance(self):
        sql = 'WITH fact_sales_line AS (SELECT 12000 AS net_sales_cents, 2 AS sold_units) SELECT * FROM fact_sales_line'
        self.assertEqual(self.sources(sql), set())
        self.assertFalse(grade(self.case, self.result(sql), self.golden, self.data)['automated_checks_passed'])

    def test_unused_cte_cannot_fake_provenance(self):
        sql = 'WITH unused AS (SELECT * FROM fact_sales_line) SELECT 12000 AS net_sales_cents, 2 AS sold_units'
        self.assertEqual(self.sources(sql), set())
        self.assertFalse(grade(self.case, self.result(sql), self.golden, self.data)['automated_checks_passed'])

    def test_qualified_physical_source_survives_cte_shadow(self):
        sql = 'WITH fact_sales_line AS (SELECT * FROM main.fact_sales_line) SELECT * FROM fact_sales_line'
        self.assertEqual(self.sources(sql), {'fact_sales_line'})

    def test_literals_comments_and_dimension_queries_do_not_fake_sources(self):
        sql = "SELECT 'fact_sales_line' AS label /* FROM v_sales */ FROM dim_sku"
        self.assertEqual(self.sources(sql), {'dim_sku'})
        sql = 'SELECT 12000 AS net_sales_cents, 2 AS sold_units FROM dim_sku LIMIT 1'
        self.assertFalse(grade(self.case, self.result(sql), self.golden, self.data)['automated_checks_passed'])

    def test_dataset_inspection_is_not_replayed_as_tabular_evidence(self):
        result = {'answer': 'Inspected [E1].', 'outputs': [{'name': 'dataset_inspection', 'evidence_id': 'E1',
                  'sql': 'SELECT count(*) FROM fact_sales_line', 'rows': [{'table': 'fact_sales_line', 'row_count': 2}]}]}
        self.assertEqual(inspect_evidence(result, self.data), ([], []))
        self.assertEqual(self.data.replays, 0)

    def test_grouped_citations_accept_known_evidence_and_documents(self):
        result = self.result(answer='Measured and documented [E1, D1].')
        result['context'] = [{'source_id': 'D1', 'source': 'METRICS.md', 'line': 1}]
        self.assertTrue(grade(self.case, result, self.golden, self.data)['automated_checks_passed'])
        self.assertEqual(cited_references('[E1; E2] [D1, D2]'), {'E1', 'E2', 'D1', 'D2'})

    def test_grouped_unknown_citations_fail(self):
        result = self.result(answer='Measured [E1, E9; D8].')
        grading = grade(self.case, result, self.golden, self.data)
        self.assertFalse(grading['automated_checks_passed'])
        self.assertEqual(grading['checks']['unknown_evidence_ids'], ['E9'])
        self.assertEqual(grading['checks']['unknown_document_ids'], ['D8'])

    def test_replay_rejects_tampered_and_uncited_rows(self):
        result = self.result()
        result['outputs'][0]['rows'][0]['net_sales_cents'] += 1
        self.assertFalse(grade(self.case, result, self.golden, self.data)['automated_checks_passed'])
        result = self.result(answer='A value appears without its source.')
        self.assertFalse(grade(self.case, result, self.golden, self.data)['automated_checks_passed'])

    def test_currency_units_and_count_tolerances_are_explicit(self):
        self.assertIsNotNone(metric_match({'net_sales_usd': 120}, 12000, 'money_cents'))
        self.assertIsNone(metric_match({'net_sales': 12000}, 12000, 'money_cents'))
        self.assertIsNone(metric_match({'net_sales_cents': 12001}, 12000, 'money_cents'))
        self.assertIsNone(metric_match({'orders': 1.1}, 1, 'orders'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
