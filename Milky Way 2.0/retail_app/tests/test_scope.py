"""Independent fact-grain checks for conversational scope and filtered recipes."""
import copy
import datetime as dt
import unittest
from unittest.mock import patch

from retail_app.backend import scope as sc
from retail_app.backend.data import warehouse_session

DATES = {'start':'2025-01-01','end':'2025-01-31','compare_start':'2024-01-01','compare_end':'2024-01-31'}


def scoped(**changes):
    return sc.normalize_scope(changes, dates=DATES)


class ScopeContractTests(unittest.TestCase):
    def test_explanations_have_no_invented_dates_or_comparison(self):
        result = sc.normalize_scope({})
        self.assertTrue(all(v is None for v in result['dates'].values()))
        current = sc.normalize_scope({'dates':{'start':'2024-01-01','end':'2024-01-15'}})
        self.assertIsNone(current['dates']['compare_start'])
        with self.assertRaisesRegex(ValueError, 'explicit compare'):
            sc.query_retail(current, compare=True)

    def test_followups_merge_remove_and_clear_filters_without_mutating_previous(self):
        initial = scoped(filters=[{'field':'division','values':['footwear']},{'field':'channel','values':['Web']}])
        snapshot = copy.deepcopy(initial)
        next_scope = sc.normalize_scope({'filters':[{'field':'channel','values':['App']}], 'dimensions':['month']}, initial)
        self.assertEqual({f['field']:f['values'] for f in next_scope['filters']}, {'channel_name':['Mobile app'],'division_name':['Footwear']})
        self.assertEqual(initial, snapshot)
        removed = sc.normalize_scope({'remove_filters':['division']}, next_scope)
        self.assertEqual(len(removed['filters']), 1)
        self.assertEqual(sc.normalize_scope({'filters':[]}, removed)['filters'], [])
        self.assertEqual(sc.normalize_scope({}, next_scope), next_scope)

    def test_current_period_change_invalidates_old_comparison(self):
        result = sc.normalize_scope({'dates':{'start':'2025-02-01','end':'2025-02-28'}}, scoped())
        self.assertIsNone(result['dates']['compare_start'])
        self.assertIsNone(result['dates']['compare_end'])
        explicit = sc.normalize_scope({'dates':{'start':'2025-02-01','end':'2025-02-28','compare_start':'2024-02-01','compare_end':'2024-02-29'}}, scoped())
        self.assertEqual(explicit['dates']['compare_end'], '2024-02-29')

    def test_scope_validation_rejects_unknown_fields_operators_and_entities(self):
        bad = [
            {'filters':[{'field':'division; DROP TABLE fact_sales_line','values':['x']}]},
            {'filters':[{'field':'division','op':'like','values':['%']}]},
            {'filters':[{'field':'division','values':["Footwear' OR 1=1 --"]}]},
            {'filters':[{'field':'loyalty','values':[1]}]},
            {'filters':[{'field':'customer_key','values':[-1]}]},
            {'dates':{'start':'2025-01-01'}},
            {'dimensions':['secret_table']},
            {'unrecognized':True},
        ]
        for candidate in bad:
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                sc.normalize_scope(candidate)

    def test_fingerprint_is_stable_for_aliases_case_and_filter_order(self):
        a = scoped(filters=[{'field':'division','values':['Footwear','Apparel']},{'field':'channel','values':['web']}])
        b = scoped(filters=[{'field':'channel_name','values':['Web']},{'field':'division_name','values':['Apparel','Footwear']}])
        self.assertEqual(sc.scope_fingerprint(a), sc.scope_fingerprint(b))
        self.assertNotEqual(sc.scope_fingerprint(a), sc.scope_fingerprint(sc.normalize_scope({'remove_filters':['channel']}, a)))

    def test_return_date_basis_cannot_be_silently_cohort(self):
        with self.assertRaisesRegex(ValueError, 'separate event grain'):
            sc.query_retail(scoped(return_basis='return_date'))

    def test_capabilities_are_explicit_and_include_domain_filters(self):
        result = sc.query_capabilities()
        for field in ['market_region','customer_segment','promotion_applied','loyalty_tier','discounted']:
            self.assertIn(field, result['filters'])
        self.assertIn('margin_cents', result['measures'])


class ScopedWarehouseTests(unittest.TestCase):
    def test_all_business_line_money_matches_header_and_deduped_reach(self):
        output = sc.query_retail(scoped(), ['sales','units','orders','customers'])
        with warehouse_session() as con:
            expected = con.execute('''SELECT sum(h.net_sales_cents),sum(h.units),count(*),
                count(DISTINCT CASE WHEN h.customer_key>0 THEN h.customer_key END)
                FROM fact_transaction h JOIN dim_date d USING(date_key)
                WHERE d.calendar_date BETWEEN ? AND ?''', [DATES['start'],DATES['end']]).fetchone()
        row = output['rows'][0]
        self.assertEqual(tuple(row[k] for k in ['sales_cents','units','orders','identified_buyers']), expected)

    def test_web_footwear_excluding_discounts_matches_independent_line_query(self):
        scope = scoped(filters=[{'field':'channel','values':['Web']},{'field':'division','values':['Footwear']},{'field':'discounted','values':[False]}])
        output = sc.query_retail(scope, ['sales','units','orders','customers','avg_price','aov'])
        with warehouse_session() as con:
            expected = con.execute('''SELECT sum(l.net_sales_cents),sum(l.quantity),count(DISTINCT h.transaction_key),
                count(DISTINCT CASE WHEN h.customer_key>0 THEN h.customer_key END)
                FROM fact_sales_line l JOIN fact_transaction h USING(transaction_key)
                JOIN dim_date d ON l.date_key=d.date_key JOIN v_product p ON p.sku_key=l.sku_key
                JOIN dim_channel c ON h.channel_key=c.channel_key
                WHERE d.calendar_date BETWEEN ? AND ? AND c.channel_name='Web' AND p.division_name='Footwear'
                  AND l.markdown_cents+l.promotion_discount_cents=0''', [DATES['start'],DATES['end']]).fetchone()
        row = output['rows'][0]
        self.assertEqual(tuple(row[k] for k in ['sales_cents','units','orders','identified_buyers']), expected)
        self.assertAlmostEqual(row['avg_price_cents'], expected[0]/expected[1])
        self.assertAlmostEqual(row['aov_cents'], expected[0]/expected[2])
        self.assertNotIn('Footwear', output['sql'])
        self.assertIn('Footwear', output['parameters'])

    def test_cohort_margin_and_returns_match_independent_return_aggregate(self):
        scope = scoped(return_basis='sales_cohort', filters=[{'field':'division','values':['Footwear']}])
        output = sc.query_retail(scope, ['sales','margin','returned_units','refund_cents'])
        with warehouse_session() as con:
            original = con.execute('''SELECT sum(l.net_sales_cents),sum(l.cost_of_goods_cents)
                FROM fact_sales_line l JOIN dim_date d USING(date_key) JOIN v_product p USING(sku_key)
                WHERE d.calendar_date BETWEEN ? AND ? AND p.division_name='Footwear' ''',[DATES['start'],DATES['end']]).fetchone()
            returned = con.execute('''SELECT sum(r.returned_quantity),sum(r.refund_net_cents),sum(r.recovered_cost_cents)
                FROM fact_return_line r JOIN fact_sales_line l ON r.sales_line_key=l.sales_line_key
                JOIN dim_date d ON l.date_key=d.date_key JOIN v_product p ON l.sku_key=p.sku_key
                WHERE d.calendar_date BETWEEN ? AND ? AND p.division_name='Footwear' ''',[DATES['start'],DATES['end']]).fetchone()
        row=output['rows'][0]
        self.assertEqual(row['sales_cents'],original[0]-returned[1])
        self.assertEqual(row['margin_cents'],original[0]-returned[1]-original[1]+returned[2])
        self.assertEqual(row['returned_units'],returned[0])
        self.assertEqual(row['refund_cents'],returned[1])

    def test_comparison_partitions_reconcile_without_adding_customers(self):
        scope = scoped(filters=[{'field':'loyalty','values':[True]}])
        grouped = sc.query_retail(scope,['sales','units','orders','customers'],['division'],True)['rows']
        totals = sc.query_retail(scope,['sales','units','orders','customers'],[],True)['rows']
        for total in totals:
            rows = [r for r in grouped if r['period']==total['period']]
            self.assertEqual(total['sales_cents'],sum(r['sales_cents'] for r in rows))
            self.assertEqual(total['units'],sum(r['units'] for r in rows))
            self.assertLess(total['identified_buyers'],sum(r['identified_buyers'] for r in rows))
            self.assertLess(total['orders'],sum(r['orders'] for r in rows))

    def test_empty_result_preserves_zero_counts_null_rates(self):
        scope=scoped(filters=[{'field':'customer_key','values':[9007199254740991]}])
        output=sc.query_retail(scope,['sales','orders','customers','avg_price','return_rate'])
        self.assertEqual(output['rows'][0]['sales_cents'],0)
        self.assertEqual(output['rows'][0]['orders'],0)
        self.assertIsNone(output['rows'][0]['avg_price_cents'])
        self.assertIsNone(output['rows'][0]['return_rate_pct'])

    def test_unequal_periods_are_visible_and_truncation_is_explicit(self):
        scope=scoped(dates={**DATES,'compare_end':'2024-01-30'})
        output=sc.query_retail(scope,['sales'],['sku'],True,limit=2)
        self.assertTrue(output['truncated'])
        self.assertEqual(len(output['rows']),2)
        self.assertTrue(any('Unequal period lengths' in w for w in output['warnings']))

    def test_market_region_includes_digital_and_promotion_filters_match(self):
        scope=scoped(filters=[{'field':'channel','values':['Web']},{'field':'market_region','values':['West']},{'field':'promotion_applied','values':[True]}])
        output=sc.query_retail(scope,['sales','orders'])
        with warehouse_session() as con:
            expected=con.execute('''SELECT sum(l.net_sales_cents),count(DISTINCT l.transaction_key)
                FROM fact_sales_line l JOIN fact_transaction h USING(transaction_key)
                JOIN dim_channel c USING(channel_key) JOIN dim_store st ON h.market_store_key=st.store_key
                JOIN dim_date d ON l.date_key=d.date_key WHERE d.calendar_date BETWEEN ? AND ?
                AND c.channel_name='Web' AND st.region='West' AND l.promotion_key>0''',[DATES['start'],DATES['end']]).fetchone()
        self.assertEqual(tuple(output['rows'][0].values()), expected)


class ScopedPlaybookTests(unittest.TestCase):
    def setUp(self):
        self.scope=scoped(filters=[{'field':'channel','values':['Web']}])

    def test_growth_reconciles_to_scoped_totals(self):
        report=sc.run_scoped_playbook('growth',DATES,self.scope)
        totals=sc.query_retail(self.scope,['sales'],[],True)['rows']
        actual={r['period']:r['sales_cents'] for r in totals}
        self.assertEqual(sum(r['change_cents'] for r in report['outputs'][0]['rows']),actual['current']-actual['comparison'])
        self.assertEqual(report['analysis_scope']['filters'],self.scope['filters'])
        self.assertIn('scoped adaptation',report['coverage'])

    def test_scorecard_ratios_and_reach_use_global_filtered_base(self):
        report=sc.run_scoped_playbook('scorecard',DATES,self.scope)
        self.assertEqual(report['analysis_scope']['return_basis'],'sales_cohort')
        summary=next(o['rows'] for o in report['outputs'] if o['name']=='scorecard_summary')
        division=report['outputs'][0]['rows']
        for row in summary:
            self.assertAlmostEqual(row['margin_rate_pct'],100*row['merchandise_margin_cents']/row['realized_sales_cents'])
            self.assertAlmostEqual(row['unit_return_rate_pct'],100*row['returned_units']/row['sold_units'])
            self.assertLess(row['identified_buyers'],sum(r['identified_buyers'] for r in division if r['period']==row['period']))

    def test_margin_bridge_reconciles(self):
        report=sc.run_scoped_playbook('margin',DATES,self.scope)
        for row in report['outputs'][0]['rows']:
            self.assertEqual(row['merchandise_margin_cents'],row['original_net_sales_cents']-row['returned_revenue_cents']-row['original_cogs_cents']+row['recovered_cost_cents'])

    def test_concentration_cumulative_series_is_complete(self):
        report=sc.run_scoped_playbook('concentration',DATES,self.scope)
        rows=report['outputs'][0]['rows']
        self.assertEqual(rows[-1]['cumulative_sales_cents'],sum(r['sales_cents'] for r in rows))
        self.assertEqual(rows[-1]['cumulative_sales_cents'],rows[-1]['total_sales_cents'])
        self.assertEqual([r['sales_cents'] for r in rows],sorted([r['sales_cents'] for r in rows],reverse=True))

    def test_unsupported_filtered_playbook_fails_instead_of_all_business(self):
        with patch.object(sc.data,'run_playbook') as original:
            for slug in ['inventory','cohorts','affinity','pvm']:
                with self.subTest(slug=slug),self.assertRaisesRegex(ValueError,'does not yet have a validated filtered adapter'):
                    sc.run_scoped_playbook(slug,DATES,self.scope)
            original.assert_not_called()

    def test_unchanged_all_business_delegates_to_original_recipe(self):
        with patch.object(sc.data,'run_playbook',return_value={'outputs':[]}) as original:
            report=sc.run_scoped_playbook('cohorts',DATES,scoped())
            original.assert_called_once()
            self.assertIn('Full validated original',report['coverage'])

    def test_custom_grouping_cannot_be_silently_discarded(self):
        with self.assertRaisesRegex(ValueError,'fixed validated grouping'):
            sc.run_scoped_playbook('growth',DATES,sc.normalize_scope({'dimensions':['category']},self.scope))


class ScopedSQLTests(unittest.TestCase):
    def setUp(self):
        self.scope=scoped(filters=[{'field':'channel','values':['Web']},{'field':'division','values':['Footwear']}])

    def test_custom_comparison_uses_exact_enforced_scope(self):
        result=sc.query_scoped_sql('SELECT period, sum(net_sales_cents) sales_cents, count(DISTINCT transaction_key) orders FROM scoped_sales GROUP BY 1 ORDER BY 1',self.scope,compare=True)
        expected=sc.query_retail(self.scope,['sales','orders'],[],True)
        self.assertEqual(result['rows'],expected['rows'])
        self.assertTrue(result['scope_enforced'])
        self.assertNotIn('Footwear',result['sql'])
        self.assertIn('Footwear',result['parameters'])

    def test_nested_ctes_and_parameters_cannot_widen_source_scope(self):
        result=sc.query_scoped_sql('''WITH daily AS (SELECT calendar_date, sum(net_sales_cents) sales_cents
            FROM scoped_sales WHERE calendar_date >= ? GROUP BY 1)
            SELECT sum(sales_cents) sales_cents FROM daily''',self.scope,['2025-01-15'])
        narrower=sc.normalize_scope({'dates':{'start':'2025-01-15','end':'2025-01-31'}},self.scope)
        self.assertEqual(result['rows'],sc.query_retail(narrower,['sales'])['rows'])
        self.assertTrue(all('2024' not in str(v) for v in result['parameters']))

    def test_rejects_direct_tables_hidden_subqueries_functions_and_shadowing(self):
        attempts=[
            'SELECT sum(net_sales_cents) FROM fact_sales_line',
            'SELECT (SELECT count(*) FROM fact_sales_line), count(*) FROM scoped_sales',
            'SELECT count(*) FROM main.scoped_sales',
            "SELECT * FROM query('SELECT * FROM fact_sales_line')",
            'WITH scoped_sales AS (SELECT 1 n) SELECT * FROM scoped_sales',
            'WITH fact_sales_line AS (SELECT * FROM fact_sales_line) SELECT count(*) FROM fact_sales_line UNION ALL SELECT count(*) FROM scoped_sales',
            'SELECT 123 AS sales_cents',
            'DELETE FROM fact_sales_line',
            'SELECT count(*) FROM scoped_sales; SELECT count(*) FROM fact_sales_line',
        ]
        for sql in attempts:
            with self.subTest(sql=sql),self.assertRaises(ValueError):
                sc.query_scoped_sql(sql,self.scope)

    def test_source_catalog_matches_actual_all_column_projection(self):
        result=sc.query_scoped_sql('SELECT * FROM scoped_sales LIMIT 1',self.scope)
        self.assertEqual(set(result['rows'][0]),set(sc.query_capabilities()['scoped_sql']['columns']))
        self.assertEqual(result['rows'][0]['period'],'current')


class ScopeMetricSemanticsTests(unittest.TestCase):
    def test_sales_recipe_does_not_silently_replace_requested_metric(self):
        scope=scoped(metric='units', filters=[{'field':'channel','values':['Web']}])
        with self.assertRaisesRegex(ValueError,'active units metric'):
            sc.run_scoped_playbook('trend',DATES,scope)


if __name__=='__main__':
    unittest.main()
