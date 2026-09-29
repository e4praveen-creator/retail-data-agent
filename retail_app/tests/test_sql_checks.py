"""Regression for a real model-generated channel filter mistake. No network/data I/O."""
import unittest
import duckdb
from retail_app.backend.sql_checks import validate_model_sql


class SqlChecksTests(unittest.TestCase):
    def setUp(self):self.con=duckdb.connect()
    def tearDown(self):self.con.close()
    def accept(self,sql):validate_model_sql(sql,self.con)
    def reject(self,sql,message='join'):
        with self.assertRaisesRegex(ValueError,message):validate_model_sql(sql,self.con)

    def test_observed_mobile_app_filter_is_disconnected(self):
        self.reject("SELECT sum(sl.net_sales_cents) FROM fact_sales_line sl JOIN dim_date d ON d.date_key=sl.date_key JOIN dim_channel ch ON ch.channel_key=(SELECT channel_key FROM dim_channel WHERE channel_name='Mobile app') JOIN v_product p ON p.sku_key=sl.sku_key WHERE ch.channel_name='Mobile app' AND p.division_name='Footwear'")

    def test_legitimate_header_channel_path(self):
        self.accept("SELECT sum(sl.net_sales_cents) FROM fact_sales_line sl JOIN fact_transaction t ON t.transaction_key=sl.transaction_key JOIN dim_channel c ON c.channel_key=t.channel_key WHERE c.channel_name='Mobile app'")

    def test_wrong_schema_key_still_rejected_when_condition_is_relational(self):
        self.reject('SELECT * FROM fact_sales_line sl JOIN dim_channel c ON sl.sku_key=c.channel_key','channel belongs')

    def test_right_only_left_only_and_independent_filters(self):
        for condition in ['b.id=1','a.id=1','a.id=1 AND b.id=2','1=1','TRUE']:
            with self.subTest(condition=condition):self.reject('SELECT * FROM a JOIN b ON '+condition)

    def test_subquery_alias_does_not_imply_outer_connectivity(self):
        self.reject('SELECT * FROM fact_transaction t JOIN dim_channel ch ON ch.channel_key=(SELECT t.channel_key FROM fact_transaction t LIMIT 1)')

    def test_disjunction_must_link_every_branch(self):
        self.reject('SELECT * FROM a JOIN b ON a.id=b.id OR b.flag=1')
        self.accept('SELECT * FROM a JOIN b ON a.id=b.id OR a.alt=b.alt')
        self.accept('SELECT * FROM a JOIN b ON (a.id=b.id OR b.flag=1) AND a.other=b.other')

    def test_using_and_comma_where_relations(self):
        self.accept('SELECT sum(fact_sales_line.net_sales_cents) FROM fact_sales_line JOIN fact_transaction USING(transaction_key) JOIN dim_channel USING(channel_key)')
        self.accept('SELECT * FROM a,b WHERE a.id=b.id AND b.flag=1')
        self.reject('SELECT * FROM a,b WHERE b.flag=1')

    def test_cte_lineage_and_subquery_alias(self):
        self.accept('WITH lines AS (SELECT * FROM fact_sales_line) SELECT sum(sl.net_sales_cents) FROM lines sl JOIN fact_transaction t ON sl.transaction_key=t.transaction_key JOIN dim_channel c ON c.channel_key=t.channel_key')
        self.reject('WITH lines AS (SELECT * FROM fact_sales_line) SELECT * FROM lines sl JOIN dim_channel c ON sl.sku_key=c.channel_key','channel belongs')
        self.accept('SELECT * FROM (SELECT * FROM fact_transaction) t JOIN dim_channel c ON t.channel_key=c.channel_key')

    def test_scalar_aggregate_cross_joins_and_ctes(self):
        self.accept('WITH current AS (SELECT sum(net_sales_cents) n FROM fact_sales_line), baseline AS (SELECT sum(net_sales_cents) n FROM fact_sales_line) SELECT * FROM current CROSS JOIN baseline')
        self.accept('SELECT * FROM fact_transaction t CROSS JOIN (SELECT count(*) total FROM fact_transaction) totals')
        self.accept('SELECT * FROM fact_transaction t JOIN (SELECT count(*) total FROM fact_transaction) totals ON TRUE')
        self.accept('SELECT * FROM fact_transaction t CROSS JOIN (SELECT 1 AS marker) params')

    def test_grouped_and_window_aggregates_are_not_scalar(self):
        self.reject('SELECT * FROM a CROSS JOIN (SELECT id,count(*) n FROM b GROUP BY id) totals')
        self.reject('SELECT * FROM a CROSS JOIN (SELECT count(*) OVER () n FROM b) totals')
        self.reject('SELECT * FROM a CROSS JOIN (SELECT id,count(*) n FROM b GROUP BY ALL) totals')

    def test_unnest_projection_does_not_establish_scalar_cardinality(self):
        self.reject('SELECT * FROM a CROSS JOIN (SELECT unnest([1,2]) n) x')
        self.reject('SELECT * FROM a CROSS JOIN (SELECT unnest(list(id)) n FROM b) x')

    def test_nested_invalid_subquery_is_validated(self):
        self.reject('SELECT (SELECT count(*) FROM a JOIN b ON b.id=1) n FROM fact_transaction')

    def test_simple_queries_union_and_qualified_functions(self):
        self.accept('SELECT 1')
        self.accept('SELECT channel_key FROM fact_transaction UNION ALL SELECT channel_key FROM dim_channel')
        self.accept('SELECT * FROM a JOIN b ON cast(a.id AS VARCHAR)=cast(b.id AS VARCHAR)')
        self.accept('SELECT * FROM a JOIN b ON b.day BETWEEN a.start AND a.finish')
        self.accept('SELECT * FROM range(2) r JOIN dim_date d ON r.range=d.date_key')

    def test_observed_header_fanout_inside_slice_cte(self):
        self.reject("WITH slice AS (SELECT t.net_sales_cents,t.units FROM fact_transaction t JOIN dim_date d ON d.date_key=t.date_key JOIN dim_channel ch ON ch.channel_key=t.channel_key JOIN fact_sales_line sl ON sl.transaction_key=t.transaction_key JOIN v_product p ON p.sku_key=sl.sku_key WHERE ch.channel_name='Mobile app' AND p.division_name='Footwear') SELECT sum(net_sales_cents),sum(units) FROM slice",'Header-grain')

    def test_header_additive_fields_and_distinct_amount_are_rejected_after_line_join(self):
        for expression in ['sum(t.net_sales_cents)','sum(t.units)','sum(t.shipping_cents)','sum(DISTINCT t.net_sales_cents)','t.units','t.*','*']:
            with self.subTest(expression=expression):
                self.reject('SELECT '+expression+' FROM fact_transaction t JOIN fact_sales_line sl ON sl.transaction_key=t.transaction_key','Header-grain')

    def test_header_projection_aliases_and_cte_column_renames_remain_tainted(self):
        self.reject('WITH receipts AS (SELECT transaction_key,net_sales_cents AS revenue FROM fact_transaction) SELECT sum(r.revenue) FROM receipts r JOIN fact_sales_line sl USING(transaction_key)','Header-grain')
        self.reject('WITH receipts(order_id,revenue) AS (SELECT transaction_key,units FROM fact_transaction) SELECT sum(r.revenue) FROM receipts r JOIN fact_sales_line sl ON sl.transaction_key=r.order_id','Header-grain')
        self.reject('SELECT sum(r.amount) FROM (SELECT transaction_key,units AS amount FROM fact_transaction) r JOIN fact_sales_line sl USING(transaction_key)','Header-grain')

    def test_legitimate_line_grain_totals_and_distinct_orders(self):
        self.accept('SELECT sum(sl.net_sales_cents),sum(sl.quantity),count(DISTINCT t.transaction_key) FROM fact_transaction t JOIN fact_sales_line sl ON sl.transaction_key=t.transaction_key')
        self.accept('WITH slice AS (SELECT sl.net_sales_cents AS revenue,sl.quantity,t.transaction_key FROM fact_transaction t JOIN fact_sales_line sl USING(transaction_key)) SELECT sum(revenue),sum(quantity),count(DISTINCT transaction_key) FROM slice')
        self.accept('SELECT sl.* FROM fact_transaction t JOIN fact_sales_line sl USING(transaction_key)')

    def test_header_only_measures_and_channel_totals_remain_allowed(self):
        self.accept('SELECT sum(t.net_sales_cents),sum(t.units) FROM fact_transaction t JOIN dim_channel ch ON t.channel_key=ch.channel_key')
        self.accept('WITH slice AS (SELECT net_sales_cents,units FROM fact_transaction WHERE date_key BETWEEN 20250701 AND 20250731) SELECT sum(net_sales_cents),sum(units) FROM slice')

    def test_unparseable_or_multiple_statements_fail_closed(self):
        self.reject('SELECT (','parseable')
        self.reject('SELECT 1; SELECT 2','one parseable')
        self.reject('WITH RECURSIVE x(i) AS (SELECT 1 UNION ALL SELECT i+1 FROM x WHERE i<3) SELECT * FROM x','cannot be verified')


if __name__=='__main__':unittest.main(verbosity=2)
