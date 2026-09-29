"""Single Retail Agent capabilities and durable conversational investigation context."""
import json
import re
from copy import deepcopy
from . import investigations as inv
from . import scope as scopes
from .data import clean, select_sql
from .storage import memories, save_memory

RESPONSE_TYPES = ('explanation', 'analysis', 'investigation')


def prepare_turn(question, dates, prior, conversation_id):
    session = inv.get_session(conversation_id) if conversation_id else {}
    current = session.get('scope') or scopes.normalize_scope({}, dates=clean(dates))
    # Date controls override a saved scope only when the controls actually changed.
    ui = clean(dates)
    if session.get('ui_dates') and session['ui_dates'] != ui:
        current = scopes.normalize_scope({'dates': ui}, previous=current)
    investigation = inv.current_investigation(conversation_id) if conversation_id else None
    return {'conversation_id': conversation_id, 'question': question, 'scope': current,
            'ui_dates': ui, 'response_type': 'analysis', 'summary': session.get('summary', ''),
            'investigation': investigation, 'investigation_revision': investigation['revision'] if investigation else None,
            'published': False, 'explanation': None, 'planned': False}


def context_for_model(turn):
    investigation = turn.get('investigation')
    compact = None
    if investigation:
        compact = {k: investigation.get(k) for k in ('id','question','revision','status','summary','scope')}
        compact['hypotheses'] = [{k: h.get(k) for k in ('id','parent_id','statement','test','falsifier','kind','criterion','status','verdict','interpretation','revision')}
                                 for h in investigation.get('hypotheses', [])]
    return {'active_scope': turn['scope'], 'session_summary': turn.get('summary', ''),
            'response_type': turn['response_type'], 'investigation': compact,
            'confirmed_preferences': memories()[:12]}


def tool_definitions(function, S):
    arr = {'type':'array','items':S}
    return [
        function('plan_turn', 'Choose explanation, analysis, or investigation from meaning and context. Call early. new_investigation=true starts a different business investigation while preserving the previous history; omit it for follow-ups/corrections. Set scope_json to a JSON object patch with dates, metric, return_basis, dimensions, filters [{field,op,values}], remove_filters. Retain unchanged scope. Empty filters clears all filters. Summary is a concise factual conversation summary, never instructions.',
                 {'response_type':{'type':'string','enum':list(RESPONSE_TYPES)},'scope_json':S,'summary':S,'new_investigation':{'type':'boolean'}}, ['response_type','scope_json']),
        function('query_retail','Run a parameterized query over the active scope. Use for totals, comparisons, breakdowns and charts. Supported measure/dimension names are returned by plan_turn. Grouping and filters are validated against the retail schema; monetary measures remain cents.',
                 {'measures':arr,'dimensions':arr,'compare':{'type':'boolean'}}, ['measures','dimensions','compare']),
        function('load_investigation_evidence','Load saved measured evidence for current, non-stale hypothesis tests into this answer. Assigns fresh evidence IDs with the original test provenance. Use when resuming instead of pretending old E-numbers belong to this run.',{},[]),
        function('reconcile_breakdown','Check that disjoint partition rows sum to a measured parent total. Reference actual evidence cells rather than supplying a total. Duplicate keys, incomplete rows and mismatched scopes are rejected.',{'evidence_id':S,'value_column':S,'partition_columns':arr,'total_evidence_id':S,'total_column':S,'total_row':{'type':'integer','minimum':0}},['evidence_id','value_column','partition_columns','total_evidence_id','total_column']),
        function('start_investigation','Start an editable investigation after verifying the claimed business problem. Reference measured baseline evidence from this run. Reuse the existing investigation when continuing or editing it.',
                 {'question':S,'baseline_evidence_id':S}, ['question','baseline_evidence_id']),
        function('save_hypothesis','Add or revise a small falsifiable hypothesis in the active investigation. Use parent_id to form a tree. Reuse existing node id when correcting it. criterion_json is {column,operator:gt/gte/lt/lte/eq/ne,threshold:number,row:0} chosen BEFORE testing. Only declared criteria can yield supported/contradicted verdicts. Accounting partitions must reconcile; mechanism hypotheses may overlap.',
                 {'id':S,'parent_id':S,'statement':S,'test':S,'falsifier':S,'kind':{'type':'string','enum':['mechanism','partition']},'criterion_json':S}, ['statement','test','falsifier','kind','criterion_json']),
        function('investigate_hypotheses','Create or revise and then execute 1-4 small falsifiable hypotheses. Prefer this for the first RCA pass. hypotheses_json is a JSON array of {id,parent_id optional,statement,test,falsifier,kind:mechanism or partition,criterion:{column,operator,threshold,row},sql}. Criteria are saved BEFORE any test executes. SQL reads scoped_sales; quantity is units. Each query returns the column named by its criterion. Existing IDs revise user-edited nodes.',{'hypotheses_json':S}),
        function('test_hypothesis','Execute read-only SQL for one saved hypothesis using its exact scope and prespecified criterion. The app computes the verdict from measured values. Select concise numeric test columns and preserve reproducible SQL. It records immutable evidence and the hypothesis revision.',
                 {'hypothesis_id':S,'sql':S,'interpretation':S}),
        function('assess_hypothesis','Attach existing measured evidence to a saved hypothesis; the app evaluates its prespecified criterion. For unavailable evidence set data_missing=true and explain the missing field/design. Supported descriptive findings never establish causality.',
                 {'hypothesis_id':S,'evidence_id':S,'interpretation':S,'data_missing':{'type':'boolean'}}, ['hypothesis_id','interpretation','data_missing']),
        function('exclude_hypothesis','Exclude a user-rejected hypothesis while preserving its history. Dependent findings become stale. Use only when the user requests exclusion or a clearly inapplicable duplicate is explained.', {'hypothesis_id':S,'reason':S}),
        function('finish_investigation','Save the investigation conclusion. Complete requires all included leaf hypotheses to be tested or explicitly data-missing. Use partial when work or unexplained branches remain. Then publish the conversational answer with present_answer.',
                 {'summary':S,'status':{'type':'string','enum':['complete','partial']}}),
        function('remember_preference','Save a business convention only when the user explicitly asks you to remember it. Confirm what was saved; reference their original request. Conversation scope/history already persist automatically.', {'text':S}),
        function('answer_explanation','Give a concise conversational explanation, clarification or data-gap answer with actual document citations. No mandatory analytical report sections. Use present_answer for measured analytics and investigation results.', {'answer':S}),
    ]


WORKFLOW_RULES = '''
You are Milky Way 2.0's single Retail Agent. You own the conversation and dynamically choose your capabilities. Do not announce transfers to other agents. Use plan_turn early to resolve intent and persist exact scope. When the user asks for totals, call query_retail with dimensions=[] even when the previous scope had grouping. For period totals, plot x=period and y=one measure; sales and units need separate charts because their units differ. Never supply comparison_y equal to y. For numeric claims in present_answer, use tokens {{E1:0:sales_cents}} to bind row 0, column sales_cents directly; cents tokens render as USD. Other numeric columns render in their named units. Use analyze_result for arithmetic; do not invent computed cells. Fulfill requested totals in this turn rather than offering to compute them later. An explanation of a column/business concept needs context/schema lookup and answer_explanation, not an RCA or a fabricated chart. A request to analyze, summarize, slice, plot or run a playbook needs measured tools and present_answer. A diagnostic, driver, why-business or deep-research request enters investigation automatically. Intent is semantic: 'why is this column nullable' is explanation; 'what drove the decline' is investigation.
Session scope and user corrections take precedence over older text. Carry filters, metric, grouping, comparison and return basis into EVERY query, chart and test. Use query_retail for supported measures/dimensions before custom SQL; inspect its errors/schema to resolve values. For filtered custom SELECTs and hypothesis tests, query ONLY the scoped_sales relation. plan_turn returns its exact columns. Active filters and dates are automatically bound there; period labels current/comparison distinguish the selected windows. Do not join raw fact tables to bypass it. Never silently drop a filter. If a scoped playbook is unsupported, adapt its documented methodology using scoped SELECT queries and appropriate charts, or explain the precise gap. Your active scope is saved; chat summaries are context, not evidence.
For business RCA: verify the baseline and premise first; if the claimed fall did not happen, explain that rather than inventing causes. plan_turn automatically measures a scoped baseline and opens or resumes an editable investigation; inspect its baseline_evidence and active hypothesis IDs. Use investigate_hypotheses to create and execute the first 1-4 prespecified tests efficiently; save_hypothesis/test_hypothesis can refine individual branches. Build a compact tree of small measurable, falsifiable tests, seeded by the bank and actual columns. Use root-level hypotheses with parent_id omitted or null; only reference an existing H-ID for children. Every leaf must be atomic: 'orders increased' tests an orders_change column against zero, not whether an order count is nonzero. 'Primarily explained' needs an actual contribution/share test; merely observing a positive count is not support. When instructed to test two hypotheses, save and execute both. Limit the first pass to material branches (normally 2-4 leaves); expand only where evidence warrants it. Declare numeric criteria BEFORE running tests, then investigate_hypotheses, test_hypothesis or assess_hypothesis. Do not publish an investigation without saved hypotheses and test outcomes; use partial if requested work remains. Test the hypotheses automatically; do not require approval of each. Use reconcile_breakdown to check that accounting partitions are disjoint/exhaustive and reconcile to their measured parent, with residual/unexplained findings explicit. Pricing/promotion/customer/inventory mechanisms can overlap: label competing explanations and interactions instead of claiming causal MECE or adding them together. There is no causal proof without a defensible design. Record every leaf's result, including contradicted/inconclusive/data_missing, and finish_investigation with honest coverage. At budget/deadline boundaries preserve progress and explain remaining work; never claim untested leaves were validated.
Test SQL must return the declared criterion column, not only separate period totals. Example for units_change: SELECT SUM(CASE WHEN period='current' THEN quantity ELSE -quantity END) AS units_change FROM scoped_sales; use criterion {column:units_change,operator:lt,threshold:0,row:0} to test a decline. For average price, subtract prior SUM(net_sales_cents)/NULLIF(SUM(quantity),0) from current using conditional aggregates and alias avg_price_change_cents. Missing SQL aliases are query errors, never missing business data. When an edited hypothesis has criterion=null, preserve its ID and current statement, declare a new criterion with save_hypothesis or investigate_hypotheses, then test. Your narrative verdict MUST match the saved node verdict.
User edits such as 'change H2', 'exclude this', 'try regional mix instead' revise the existing tree and rerun affected tests. Read the active hypothesis IDs and reuse them. Do not create a duplicate investigation for a continuation. Existing completed tests include saved evidence; query fresh evidence where scope/version changed. Omit private reasoning; show concise test plans, findings and limitations. For requests to remember a preference, save it with remember_preference; other session context persists without that tool.
'''


def _sync(turn):
    if turn.get('conversation_id'):
        inv.update_session(turn['conversation_id'], {'scope':turn['scope'],'summary':turn.get('summary',''),
                           'ui_dates':turn['ui_dates'],'investigation_id':turn['investigation']['id'] if turn.get('investigation') else None})


def _set_investigation(turn, snapshot):
    turn['investigation'] = snapshot
    turn['investigation_revision'] = snapshot['revision']
    turn['response_type'] = 'investigation'
    _sync(turn)
    return snapshot


def _current(turn):
    if not turn.get('investigation'): raise ValueError('Start an investigation using measured baseline evidence first.')
    snapshot = inv.get_investigation(turn['investigation']['id'])
    if snapshot['revision'] != turn['investigation_revision']:
        raise ValueError('The investigation was edited while this answer was running. Continue from the latest revision.')
    return snapshot


def assert_current(turn):
    if turn.get('investigation') and turn.get('response_type') == 'investigation': _current(turn)


def _evidence(identity, evidence):
    result = next((e for e in evidence if e.get('evidence_id') == identity), None)
    if not result: raise ValueError('Choose an evidence ID measured in this run.')
    return deepcopy(result)


def handle_tool(name, a, turn, evidence, add_evidence):
    """Return (handled, result); mutation paths are revision-checked."""
    if name == 'plan_turn':
        if turn.get('investigation'): _current(turn)
        if a['response_type'] not in RESPONSE_TYPES: raise ValueError('Unknown response type.')
        patch = json.loads(a.get('scope_json') or '{}')
        updated = scopes.normalize_scope(patch, previous=turn['scope'])
        turn['scope'] = updated
        turn['response_type'] = a['response_type']; turn['planned'] = True
        turn['summary'] = str(a.get('summary') or turn.get('summary',''))[:6000]
        _sync(turn)
        # update_session invalidates affected investigation findings on scope change.
        if turn.get('conversation_id'):
            turn['investigation'] = inv.current_investigation(turn['conversation_id'])
            turn['investigation_revision'] = turn['investigation']['revision'] if turn['investigation'] else None
        baseline=None
        if turn['response_type']=='investigation' and turn.get('conversation_id') and (a.get('new_investigation') or not turn.get('investigation') or not turn['investigation'].get('baseline')):
            metric=turn['scope'].get('metric','sales_cents')
            output=scopes.query_retail(turn['scope'],list(dict.fromkeys([metric,'units','orders'])),[],bool(turn['scope']['dates'].get('compare_start')))
            baseline=add_evidence(output)
            if a.get('new_investigation') or not turn.get('investigation'):
                _set_investigation(turn,inv.create_investigation(turn['conversation_id'],turn['question'],turn['scope'],baseline))
            else:
                _set_investigation(turn,inv.set_baseline(turn['investigation']['id'],baseline,turn['investigation_revision']))
        return True, {**context_for_model(turn), 'baseline_evidence':baseline, 'query_schema': scopes.query_capabilities() if hasattr(scopes,'query_capabilities') else 'Inspect query_retail validation messages for available dimensions and measures.'}
    if name == 'query_retail':
        if 'period' in a.get('dimensions',[]):
            a={**a,'dimensions':[d for d in a['dimensions'] if d!='period'],'compare':True}
        output = scopes.query_retail(turn['scope'],a.get('measures'),a.get('dimensions'),a.get('compare',False))
        measured=add_evidence(output)
        if a.get('dimensions'):
            totals=add_evidence(scopes.query_retail(turn['scope'],a.get('measures'),[],a.get('compare',False)))
            return True, {'output':measured,'total_evidence':totals,'guidance':'Use total_evidence for the requested period headline totals. Group rows can be charted independently. Do not sum distinct customer/order groups.'}
        return True, measured
    if name == 'load_investigation_evidence':
        snap = _current(turn); loaded=[]
        if snap.get('baseline') and snap['baseline'].get('scope')==turn['scope']:
            loaded.append(add_evidence({**deepcopy(snap['baseline']),'saved_origin':{'investigation_id':snap['id'],'kind':'baseline'}}))
        for node in snap['hypotheses']:
            if node.get('status')!='tested': continue
            for saved in node.get('evidence',[]):
                if saved.get('scope')==turn['scope']:
                    loaded.append(add_evidence({**deepcopy(saved),'saved_origin':{'investigation_id':snap['id'],'hypothesis_id':node['id'],'test_id':node.get('latest_test_id')}}))
        return True, {'outputs':loaded}
    if name == 'reconcile_breakdown':
        source=_evidence(a['evidence_id'],evidence);parent=_evidence(a['total_evidence_id'],evidence)
        if source.get('scope') != turn['scope'] or parent.get('scope') != turn['scope']:
            raise ValueError('Reconciliation requires evidence from the active scope.')
        check=inv.reconcile_partition(source,a['value_column'],{'evidence':parent,'column':a['total_column'],'row':a.get('total_row',0)},a['partition_columns'])
        return True, add_evidence({'name':'partition_reconciliation','rows':[check],'truncated':False,'row_count':1,'sql':'','parameters':[], 'calculation':a,'source_evidence_ids':[a['evidence_id'],a['total_evidence_id']]})
    if name == 'start_investigation':
        if not turn.get('conversation_id'): raise ValueError('Investigations need a saved conversation. Use the chat interface.')
        if turn.get('investigation') and turn['investigation'].get('status') not in ('complete',):
            return True, _current(turn)
        baseline = _evidence(a['baseline_evidence_id'], evidence)
        if baseline.get('scope') != turn['scope']: raise ValueError('Baseline scope changed. Query fresh baseline evidence first.')
        return True, _set_investigation(turn,inv.create_investigation(turn['conversation_id'],a['question'],turn['scope'],baseline))
    if name == 'save_hypothesis':
        snap = _current(turn)
        node = {k:v for k,v in a.items() if k not in ('criterion_json',) and v != ''}
        node['criterion'] = json.loads(a.get('criterion_json') or 'null')
        if node.get('parent_id') in ('root','ROOT','baseline',snap['id']):node.pop('parent_id')
        validate_atomic_hypothesis(node)
        if not node.get('id'):node['id']='H'+str(len(snap['hypotheses'])+1)
        return True, _set_investigation(turn,inv.upsert_hypothesis(snap['id'],node,expected_revision=snap['revision']))
    if name == 'investigate_hypotheses':
        items=json.loads(a['hypotheses_json'])
        if not isinstance(items,list) or not 1<=len(items)<=4:
            raise ValueError('Provide one to four falsifiable leaf hypotheses per batch.')
        planned=[]
        for item in items:
            if not isinstance(item,dict) or not item.get('criterion') or not item.get('sql'):
                raise ValueError('Every hypothesis needs a prespecified criterion and scoped SQL.')
            snap=_current(turn)
            node={k:v for k,v in item.items() if k in ('id','parent_id','statement','test','falsifier','kind','criterion') and v is not None and v!=''}
            node.setdefault('id','H'+str(len(snap['hypotheses'])+1));node.setdefault('kind','mechanism')
            if node.get('parent_id') in ('root','ROOT','baseline',snap['id']):node.pop('parent_id')
            validate_atomic_hypothesis(node)
            updated=inv.upsert_hypothesis(snap['id'],node,expected_revision=snap['revision'])
            _set_investigation(turn,updated);planned.append((node['id'],item['sql']))
        results=[]
        for identity,sql in planned:
            _,result=handle_tool('test_hypothesis',{'hypothesis_id':identity,'sql':sql,'interpretation':'The declared test criterion was evaluated on measured evidence. Interpret this as descriptive support or contradiction, not causal proof.'},turn,evidence,add_evidence)
            results.append({'hypothesis_id':identity,'evidence':result['evidence']})
        return True, {'investigation':_current(turn),'tests':results}
    if name in ('test_hypothesis','assess_hypothesis'):
        snap = _current(turn)
        node = next((h for h in snap['hypotheses'] if h['id']==a['hypothesis_id']),None)
        if not node: raise ValueError('Unknown hypothesis ID.')
        if not node.get('criterion') and not a.get('data_missing'):
            raise ValueError('This hypothesis has no prespecified criterion, possibly because the user edited it. Use save_hypothesis or investigate_hypotheses with the SAME ID and current statement to declare a fresh numeric criterion before testing.')
        if name == 'test_hypothesis':
            output = add_evidence(execute_model_sql(a['sql'],turn))
        elif a.get('data_missing'):
            output = None
        else: output = _evidence(a.get('evidence_id'), evidence)
        if output is not None and output.get('scope') != turn['scope']:
            raise ValueError('Evidence belongs to another scope. Rerun the test using the current filters and dates.')
        # record_test computes the prespecified criterion; the model cannot override it.
        if output is None: verdict='data_missing'
        elif node.get('criterion'): verdict=inv.evaluate_criterion(output,node['criterion'])['verdict']
        else: verdict='inconclusive'
        updated = inv.record_test(snap['id'],node['id'],output,verdict,a['interpretation'],expected_revision=snap['revision'])
        return True, {'investigation':_set_investigation(turn,updated),'evidence':output}
    if name == 'exclude_hypothesis':
        snap = _current(turn)
        return True,_set_investigation(turn,inv.edit_hypothesis(snap['id'],a['hypothesis_id'],{'excluded':True,'notes':a['reason']},expected_revision=snap['revision']))
    if name == 'finish_investigation':
        snap = _current(turn)
        return True,_set_investigation(turn,inv.finish_investigation(snap['id'],a['summary'],a['status'],expected_revision=snap['revision']))
    if name == 'remember_preference':
        if not re.search(r'\b(remember|keep in mind|from now on|always use|by default|save this|save that)\b',turn['question'],re.I):
            raise ValueError('Only save durable preferences when the user explicitly requests it. Session history and scope are already saved.')
        return True,save_memory(a['text'],'User request: '+turn['question'][:500])
    if name == 'answer_explanation':
        if any(o.get('rows') and o.get('name') not in ('dataset_inspection','column_profile') for o in evidence):
            raise ValueError('Measured analysis requires present_answer with evidence, scope and visualization.')
        turn['response_type']='explanation';turn['explanation']=a['answer'];turn['published']=True;_sync(turn)
        return True, {'status':'answer_ready'}
    return False, None


def execute_model_sql(sql, turn):
    """Filtered custom queries can only access the bound scoped relation."""
    if turn['scope'].get('filters') or re.search(r'\bscoped_sales\b',sql,re.I):
        return scopes.query_scoped_sql(sql,turn['scope'],compare=True)
    return select_sql(sql)


def validate_evidence_scope(turn, evidence, identities):
    for identity in identities:
        item=_evidence(identity,evidence)
        if item.get('scope') is not None and item['scope'] != turn['scope']:
            raise ValueError('Evidence '+identity+' belongs to an earlier scope. Query fresh data or restore that scope before presenting it.')


def validate_atomic_hypothesis(node):
    """Reject common non-tests: a positive level cannot establish a change/driver."""
    criterion=node.get('criterion')
    if not criterion:return
    column=criterion.get('column','').lower()
    statement=node.get('statement','').lower()
    comparative=bool(re.search(r'declin|increas|decreas|fell|fall|rose|rise|growth|grew|higher|lower|change|drop',statement))
    change_measure=bool(re.search(r'change|delta|diff|growth|contribution|share|ratio|pct|percent|p_value',column))
    if comparative and not change_measure and criterion.get('threshold')==0:
        raise ValueError('A nonzero level does not test a change. Query a current-minus-comparison column such as units_change, and declare its directional criterion before testing.')
    if re.search(r'primar|majority|main driver|most of',statement) and not re.search(r'contribution|share|diff',column):
        raise ValueError('A primary-driver claim requires quantified contribution/share evidence. Use a smaller directional hypothesis or compute a reconciled contribution first.')
    if 'contribution' in statement and not re.search(r'contribution|share',column):
        raise ValueError('A contribution claim needs a quantified contribution column. For a simple directional test use wording such as orders increased or average selling price increased, without claiming an attributed contribution.')
