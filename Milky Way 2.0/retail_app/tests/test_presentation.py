"""Answer design is source-derived, numeric visuals remain evidence-bound."""
import json
import os
import unittest
from unittest.mock import patch
import httpx
from retail_app.backend import agent, data
from retail_app.backend.presentation import contracts, get_contract, validate_chart, validate_presentation, finish_presentation, unmatched_money, SECTIONS

class PresentationTests(unittest.TestCase):
    def test_all_19_source_templates_have_complete_designs(self):
        self.assertEqual(len(contracts()),19)
        for slug,c in contracts().items():
            for key in ('output_template','visual_spec','guardrails','interpretation_guide','next_drills'):
                self.assertTrue(c[key],(slug,key))
            self.assertEqual(c['sections'],list(SECTIONS))
            self.assertNotIn('##',c['next_drills'])
        self.assertIn('eligible',get_contract('cohorts')['visual_spec'])
        self.assertIn('waterfall',get_contract('pvm')['visual_spec'])

    def test_invalid_chart_and_unknown_evidence_are_rejected(self):
        evidence=[{'evidence_id':'E1','rows':[{'category':'A','sales_cents':200},{'category':'B','sales_cents':100}]}]
        validate_chart({'kind':'pareto','output_index':0,'x':'category','y':'sales_cents'},evidence)
        for spec in [{'kind':'bar','output_index':-1,'x':'category','y':'sales_cents'},
                     {'kind':'bar','output_index':0,'x':'category','y':'missing'},
                     {'kind':'scatter','output_index':0,'x':'category','y':'sales_cents'},
                     {'kind':'stacked','output_index':0,'x':'category','y':'sales_cents'}]:
            with self.assertRaises(ValueError):validate_chart(spec,evidence)

    def test_heatmap_requires_one_row_per_cell_and_preserves_null(self):
        e=[{'rows':[{'a':'A','b':'90d','rate':None,'base':0}]}]
        validate_chart({'kind':'heatmap','output_index':0,'x':'a','y':'b','value':'rate','denominator':'base'},e)
        e[0]['rows']*=2
        with self.assertRaisesRegex(ValueError,'one measured row'):validate_chart({'kind':'heatmap','output_index':0,'x':'a','y':'b','value':'rate'},e)

    def test_share_charts_reject_negative_measures(self):
        with self.assertRaisesRegex(ValueError,'nonnegative'):validate_chart({'kind':'pareto','output_index':0,'x':'a','y':'n'},[{'rows':[{'a':'A','n':-1}]}])

    def test_contribution_axes_follow_playbook_and_accept_evidence_id(self):
        e=[{'evidence_id':'E4','rows':[{'division':'A','change_cents':-100},{'division':'B','change_cents':200}]}]
        chart=validate_chart({'kind':'bar','evidence_id':'E4','x':'change_cents','y':'division'},e)
        self.assertEqual((chart['x'],chart['y'],chart['orientation'],chart['output_index']),('division','change_cents','horizontal',0))
        with self.assertRaises(ValueError):validate_chart({'kind':'bar','evidence_id':'E4','output_index':1,'x':'division','y':'change_cents'},e)

    def test_decimal_query_measures_remain_numeric_for_charts(self):
        output=data.select_sql("SELECT 'A' AS entity_name, CAST(10.25 AS DECIMAL(12,2)) sales_usd UNION ALL SELECT 'B',CAST(20.5 AS DECIMAL(12,2))")
        self.assertEqual(output['rows'][0]['sales_usd'],10.25)
        validate_chart({'kind':'bar','output_index':0,'x':'entity_name','y':'sales_usd'},[output])

    def test_currency_claims_catch_factor_ten_and_wrong_totals(self):
        e=[{'rows':[{'sales_cents':100000000},{'sales_cents':20809926}],'truncated':False}]
        self.assertEqual(unmatched_money('Total $1,208,099.26 or $1.21M.',e),[])
        self.assertEqual(unmatched_money('Total $120,809.93.',e),['$120,809.93'])

    def test_currency_claims_do_not_sum_truncated_previews(self):
        e=[{'rows':[{'sales_cents':100},{'sales_cents':200}],'truncated':True}]
        self.assertEqual(unmatched_money('$3.00',e),['$3.00'])

    def test_currency_claims_validate_explicit_cents_and_dollars(self):
        e=[{'rows':[{'sales_cents':57653466900}]}]
        self.assertEqual(unmatched_money('57,653,466,900 cents; 576,534,669 USD; 576.53 million dollars.',e),[])
        self.assertEqual(unmatched_money('5,765,346,690,000 cents on 2,429,986 orders.',e),['5,765,346,690,000 cents'])
        self.assertEqual(unmatched_money('576,534,669 cents.',e),['576,534,669 cents'])
        self.assertEqual(unmatched_money('-$576,534,669.',e),['-$576,534,669'])

    def test_structured_answer_rejects_cents_conversion_error(self):
        design={'headline':'Sales were 12,300 cents.','scope':'Current period.','metric_basis':'Net sales before returns.','interpretation':'Measured sales.','limitations':[],'next_questions':[],'supporting_evidence_ids':['E1']}
        with self.assertRaisesRegex(ValueError,'monetary claims'):
            validate_presentation(design,[{'evidence_id':'E1','rows':[{'sales_cents':123}]}])

    def test_totals_get_cards_and_documentation_gets_no_fake_chart(self):
        total=finish_presentation({'answer':'Total [E1]','outputs':[{'rows':[{'sales_cents':123}]}]})
        self.assertEqual(total['presentation']['visual_status'],'metric_cards')
        gap=finish_presentation({'answer':'No causal design exists.','outputs':[]})
        self.assertEqual(gap['presentation']['visual_status'],'no_measured_data')
        self.assertFalse(gap['charts'])

    def test_multirow_results_get_evidence_bound_fallback_visual(self):
        result=finish_presentation({'answer':'Measured sales [E1]','outputs':[{'rows':[{'division':'A','sales_cents':10},{'division':'B','sales_cents':20}]}]})
        self.assertEqual(result['charts'][0]['output_index'],0)
        self.assertEqual(result['charts'][0]['y'],'sales_cents')
        self.assertEqual(result['presentation']['supporting_evidence_ids'],['E1'])

    def test_structured_tool_retains_scope_and_supporting_evidence(self):
        design={'playbook_slug':'growth','headline':'B contributed more [E1].','scope':'Web only, January 2025 vs January 2024.','metric_basis':'Net merchandise sales before returns, USD.','interpretation':'A measured contribution, not a cause [E1].','limitations':['Synthetic data.'],'next_questions':['Split by SKU.'],'supporting_evidence_ids':['E1']}
        with self.assertRaises(ValueError):validate_presentation(design,[])
        def response(output):return httpx.Response(200,json={'output':output})
        def call(name,args,identity):return response([{'type':'function_call','name':name,'arguments':json.dumps(args),'call_id':identity}])
        replies=[call('execute_sql',{'sql':"SELECT 'A' division, 10 sales_cents UNION ALL SELECT 'B',20"},'1'),call('create_visualization',{'kind':'bar','output_index':0,'x':'division','y':'sales_cents'},'2'),call('present_answer',design,'3'),response([{'type':'message','content':[{'type':'output_text','text':'The structured answer is ready.'}]}])]
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test','OPENAI_MODEL':'test'}),patch.object(agent.MODEL_HTTP,'post',side_effect=replies):
            result=agent.run_agent('Show growth',data.dates_for('2025-01-01','2025-01-31','2024-01-01','2024-01-31'))
        self.assertEqual(result['presentation']['scope'],design['scope'])
        self.assertEqual(result['presentation']['supporting_evidence_ids'],['E1'])
        self.assertIn(design['headline'],result['answer'])
        self.assertEqual(len(result['charts']),1)

if __name__=='__main__':unittest.main()
