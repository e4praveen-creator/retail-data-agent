"""Reconcile visual evidence to the unchanged recipes and independent fact grains."""
import datetime as dt
import importlib.util
from pathlib import Path
import unittest

import duckdb
from retail_app.backend.visual_data import attach_visual_outputs

ROOT = Path(__file__).resolve().parents[2]
DATES = {'start': dt.date(2025, 1, 1), 'end': dt.date(2025, 3, 31),
         'compare_start': dt.date(2024, 1, 3), 'compare_end': dt.date(2024, 4, 1)}


class VisualEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('visual_test_runner', ROOT/'retail-data-analyst/scripts/run_analysis.py')
        cls.runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.runner)
        cls.con = duckdb.connect(str(ROOT/'retail_data/data/full/retail.duckdb'), read_only=True,
                                 config={'enable_external_access': False, 'threads': 2, 'memory_limit': '1GB'})
        cls.reports = {}
        for slug in ['scorecard', 'channels', 'promotions', 'loyalty', 'returns', 'inventory', 'fulfillment', 'segments', 'lapse', 'pricing']:
            baseline = cls.runner.run_one(cls.con, slug, DATES, 5000)
            cls.reports[slug] = (baseline, attach_visual_outputs(cls.con, slug, DATES, baseline))

    @classmethod
    def tearDownClass(cls):
        cls.con.close()

    def rows(self, slug, name):
        return next(o['rows'] for o in self.reports[slug][1] if o['name'] == name)

    def test_original_recipes_unchanged_and_every_addition_read_only_bounded(self):
        for baseline, complete in self.reports.values():
            self.assertEqual(complete[:len(baseline)], baseline)
            self.assertGreater(len(complete), len(baseline))
            for output in complete[len(baseline):]:
                statements = self.con.extract_statements(output['sql'])
                self.assertEqual(len(statements), 1)
                self.assertEqual(statements[0].type, duckdb.StatementType.SELECT)
                self.assertFalse(output['truncated'])
                self.assertEqual(output['row_count'], len(output['rows']))
                self.assertLessEqual(output['row_count'], 5000)

    def test_scorecard_reach_deduplicated_across_divisions(self):
        for row in self.rows('scorecard', 'scorecard_summary'):
            start, end = (DATES['start'], DATES['end']) if row['period']=='current' else (DATES['compare_start'], DATES['compare_end'])
            orders, buyers = self.con.execute('''SELECT count(*),count(DISTINCT CASE WHEN customer_key>0 THEN customer_key END)
                FROM fact_transaction h JOIN dim_date d USING(date_key) WHERE calendar_date BETWEEN ? AND ?''', [start, end]).fetchone()
            self.assertEqual(row['orders'], orders)
            self.assertEqual(row['identified_buyers'], buyers)
            division_rows = [r for r in self.rows('scorecard', 'division_scorecard') if r['period']==row['period']]
            self.assertEqual(row['realized_sales_cents'], sum(r['realized_sales_cents'] for r in division_rows))
            self.assertLess(row['identified_buyers'], sum(r['identified_buyers'] for r in division_rows))

    def test_channel_and_store_totals_do_not_fan_out_headers(self):
        rows = self.rows('channels', 'channels_growth_margin')
        expected = [r for r in self.rows('channels', 'channel_orders') if r['period']=='current']
        self.assertEqual(sum(r['orders'] for r in rows), sum(r['orders'] for r in expected))
        self.assertEqual(sum(r['current_sales_cents'] for r in rows), sum(r['sales_before_returns_cents'] for r in expected))
        stores = self.rows('channels', 'stores_growth_margin')
        pos = next(r for r in rows if r['channel_name']=='Store POS')
        self.assertEqual(sum(r['current_sales_cents'] for r in stores), pos['current_sales_cents'])
        self.assertEqual(sum(r['merchandise_margin_cents'] for r in stores), pos['merchandise_margin_cents'])
        for row in rows:
            self.assertAlmostEqual(row['margin_rate_pct'], 100*row['merchandise_margin_cents']/row['realized_sales_cents'])
            self.assertAlmostEqual(row['aov_before_returns_cents'], row['current_sales_cents']/row['orders'])

    def test_promotion_timeline_reconciles_campaign_redemptions(self):
        campaign = self.rows('promotions', 'campaign_associated_sales')[0]
        rows = self.rows('promotions', 'promotion_timeline')
        self.assertEqual(sum(r['redeemed_units'] for r in rows), campaign['redeemed_units'])
        self.assertEqual(sum(r['promotion_discount_cents'] for r in rows), campaign['promotion_discount_cents'])
        self.assertEqual(sum(r['associated_cohort_merchandise_margin_cents'] for r in rows), campaign['associated_cohort_merchandise_margin_cents'])
        self.assertTrue(any(r['overlaps_campaign'] for r in rows))
        self.assertTrue(any(not r['overlaps_campaign'] for r in rows))
        for row in rows:
            self.assertEqual(row['promotion_key'], campaign['promotion_key'])
            if row['redeemed_units']:
                self.assertTrue(row['overlaps_campaign'])
            self.assertGreaterEqual(row['scope_units'], row['redeemed_units'])

    def test_loyalty_monthly_attachment_preserves_order_and_sales_totals(self):
        monthly = self.rows('loyalty', 'loyalty_monthly_mix')
        for total in self.rows('loyalty', 'loyalty_attachment'):
            group = [r for r in monthly if r['loyalty_usage']==total['loyalty_usage']]
            for metric in ['orders', 'sales_before_returns_cents', 'sold_units']:
                self.assertEqual(sum(r[metric] for r in group), total[metric])

    def test_elapsed_returns_and_reasons_share_original_sale_cohort(self):
        cells = self.rows('returns', 'return_cohort_elapsed')
        originals = self.rows('returns', 'division_channel_return_cohorts')
        self.assertEqual(sum(r['returned_units'] for r in cells), sum(r['returned_units'] for r in originals))
        first_bin = [r for r in cells if r['elapsed_day_bin']=='0–30 days']
        self.assertEqual(sum(r['original_units'] for r in first_bin), sum(r['original_units'] for r in originals))
        self.assertEqual(sum(r['returned_units'] for r in self.rows('returns', 'cohort_return_reasons')), sum(r['returned_units'] for r in cells))
        self.assertTrue(all(r['fully_mature_60d'] for r in cells))
        for row in cells:
            self.assertAlmostEqual(row['return_rate_pct'], 100*row['returned_units']/row['original_units'])
        self.assertAlmostEqual(sum(r['returned_unit_share_pct'] for r in self.rows('returns', 'cohort_return_reasons')), 100)

    def test_inventory_keeps_stock_snapshots_separate_and_reconciles_flows(self):
        weekly = self.rows('inventory', 'inventory_weekly')
        for index, row in enumerate(weekly):
            self.assertEqual(row['opening_units']+row['receipt_units']+row['restocked_units']-row['sold_units']-row['shrink_units'], row['closing_units'])
            if index:
                self.assertEqual(row['opening_units'], weekly[index-1]['closing_units'])
            self.assertEqual(row['week_start'].weekday(), 0)
            self.assertEqual(row['week_end'].weekday(), 6)
        self.assertEqual(weekly[-1]['closing_units'], sum(r['closing_units'] for r in self.rows('inventory', 'latest_inventory_by_division')))

    def test_fulfillment_monthly_orders_match_headers_and_margin_uses_realized_sales(self):
        monthly = self.rows('fulfillment', 'fulfillment_monthly_mix')
        outcomes = self.rows('fulfillment', 'fulfillment_outcome_metrics')
        for row in outcomes:
            by_method = [r for r in monthly if r['fulfillment_method']==row['fulfillment_method']]
            self.assertEqual(sum(r['orders'] for r in by_method), row['orders'])
            self.assertEqual(sum(r['sales_before_returns_cents'] for r in by_method), row['sales_before_returns_cents'])
            self.assertAlmostEqual(row['margin_rate_pct'], 100*row['merchandise_margin_cents']/row['realized_sales_cents'])

    def test_segment_profiles_retain_original_membership_and_dollar_totals(self):
        profiles = {r['segment']:r for r in self.rows('segments', 'segment_profiles')}
        for baseline in self.rows('segments', 'behavior_groups'):
            row = profiles[baseline['segment']]
            for metric in ['identified_buyers', 'orders', 'sales_cents']:
                self.assertEqual(row[metric], baseline[metric])
            self.assertAlmostEqual(row['margin_per_buyer_cents']*row['identified_buyers'], row['merchandise_margin_cents'], places=3)
            self.assertAlmostEqual(row['discount_share_pct'], 100*row['discount_cents']/row['gross_sales_cents'])
            self.assertGreaterEqual(row['categories_per_buyer'], 1)

    def test_lapse_states_mutually_exclusive_and_retain_historical_customer_base(self):
        rows = self.rows('lapse', 'lapse_monthly_states')
        for row in rows:
            self.assertEqual(row['active_buyers']+row['lapsed_buyers']+row['reactivated_buyers'], row['identified_buyers'])
            buyers = self.con.execute('''SELECT count(DISTINCT customer_key) FROM fact_transaction h
                JOIN dim_date d USING(date_key) WHERE customer_key>0 AND calendar_date<=?''', [row['observation_date']]).fetchone()[0]
            self.assertEqual(row['identified_buyers'], buyers)
            self.assertEqual(row['lapse_threshold_days'], 90)
        recent = self.rows('lapse', 'recency_distribution')
        self.assertEqual(rows[-1]['identified_buyers'], sum(r['identified_buyers'] for r in recent))
        self.assertEqual(rows[-1]['lapsed_buyers'], sum(r['identified_buyers'] for r in recent if r['recency_band'] in ['91-180 days', '181+ days']))

    def test_price_histograms_weight_both_distributions_by_units(self):
        rows = self.rows('pricing', 'pricing_distribution')
        expected = sum(r['units'] for r in self.rows('pricing', 'division_price_realization'))
        self.assertEqual({r['price_basis'] for r in rows}, {'actual', 'regular'})
        for basis in ['actual', 'regular']:
            self.assertEqual(sum(r['units'] for r in rows if r['price_basis']==basis), expected)
        self.assertTrue(all(r['bin_width_usd']==10 and r['usd_bucket_start']%10==0 for r in rows))


if __name__ == '__main__':
    unittest.main()
