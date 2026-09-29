"""Source-derived playbook answer contracts and evidence-bound presentations."""
from functools import lru_cache
from pathlib import Path
import datetime as dt
import math
import re

ROOT = Path(__file__).resolve().parents[2]
SLUGS = ('trend','pvm','growth','margin','seasonality','scorecard','channels','concentration','pricing','promotions','cohorts','lapse','segments','affinity','loyalty','returns','velocity','inventory','fulfillment')
SECTIONS = ('Headline','Scope and metric','Primary visual','Supporting values','Interpretation','Limitations','Next question')


@lru_cache(maxsize=1)
def contracts():
    path = ROOT / 'retail-data-analyst/references/playbooks.md'
    raw = path.read_text()
    visual_path = ROOT / 'retail-data-analyst/references/visual-specs.md'
    visual_raw = visual_path.read_text()
    chapters = list(re.finditer(r'^### Playbook (\d+) — (.+)$', raw, re.M))
    visuals = list(re.finditer(r'^### (\d+)\. (.+)$', visual_raw, re.M))
    result = {}
    for index, chapter in enumerate(chapters):
        body = raw[chapter.end():chapters[index+1].start() if index+1<len(chapters) else raw.find('## Requests to route',chapter.end())]
        body = re.split(r'\n## ',body,maxsplit=1)[0]
        fields = {key: value.strip() for key,value in re.findall(r'\*\*([A-I])\. [^*]+\*\*\s*(.*?)(?=\n\n\*\*[A-I]\.|\Z)',body,re.S)}
        v = visuals[index]
        exact_visual = visual_raw[v.end():visuals[index+1].start() if index+1<len(visuals) else len(visual_raw)].strip()
        result[SLUGS[index]] = {
            'slug':SLUGS[index], 'number':index+1, 'title':chapter.group(2),
            'required_inputs':fields.get('B',''), 'method':fields.get('C',''), 'guardrails':fields.get('D',''),
            'output_template':fields.get('E',''), 'visual_summary':fields.get('F',''), 'visual_spec':exact_visual,
            'interpretation_guide':fields.get('H',''), 'next_drills':fields.get('I',''),
            'sections':list(SECTIONS),
            'sources':[{'source':str(path.relative_to(ROOT)), 'line':raw[:chapter.start()].count('\n')+1},
                       {'source':str(visual_path.relative_to(ROOT)), 'line':visual_raw[:v.start()].count('\n')+1}],
        }
    return result


def get_contract(slug):
    if slug not in contracts():
        raise ValueError('Choose a documented playbook slug: '+', '.join(SLUGS))
    return contracts()[slug]


def finite(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)


def unmatched_money(text,evidence):
    """Catch currency transcription/conversion mistakes, not business semantics.

    Rounded USD or cents claims may match measured cells or column sums in a
    complete result. A match does not establish that summing that column is valid.
    """
    allowed=[]
    for output in evidence:
        rows=output.get('rows',[])
        if not rows:continue
        for key in rows[0]:
            scale=100 if key.endswith('_cents') else 1 if key.endswith(('_usd','_dollars')) else None
            if scale is None:continue
            values=[r[key]/scale for r in rows if finite(r.get(key))]
            allowed.extend(values)
            if values and not output.get('truncated'):allowed.append(sum(values))
    if not allowed:return []
    missing=[]
    number=r'(?P<number>[+-]?\d[\d,]*(?:\.\d+)?)'
    multiplier=r'(?P<multiplier>thousand|million|billion|[KMB])?'
    patterns=(rf'(?P<sign>[+-]?)\$\s*{number}\s*{multiplier}\b',
              rf'(?<![\w.$,]){number}\s*{multiplier}\s+(?P<unit>cents?|USD|dollars?)\b')
    matches=sorted((m for pattern in patterns for m in re.finditer(pattern,text,re.I)),key=lambda m:m.start())
    for match in matches:
        raw=match['number'].replace(',','')
        factor={None:1,'k':1000,'m':1000000,'b':1000000000,'thousand':1000,'million':1000000,'billion':1000000000}[(match['multiplier'] or '').lower() or None]
        unit_scale=100 if match.groupdict().get('unit','').lower().startswith('cent') else 1
        value=float(raw)*factor/unit_scale
        if match.groupdict().get('sign')=='-':value=-value
        places=len(raw.split('.')[1]) if '.' in raw else 0
        tolerance=.5*10**(-places)*factor/unit_scale+1e-7
        if not any(abs(value-observed)<=tolerance for observed in allowed):missing.append(match.group().strip())
    return list(dict.fromkeys(missing))


def validate_chart(spec, evidence):
    spec=dict(spec)
    index = spec.get('output_index')
    if spec.get('evidence_id'):
        found=next((i for i,out in enumerate(evidence) if out.get('evidence_id')==spec['evidence_id']),None)
        if found is None or (index is not None and index!=found):
            raise ValueError('Use an existing evidence ID, with a matching output index if both are supplied.')
        index=found;spec['output_index']=index
    if not isinstance(index,int) or isinstance(index,bool) or not 0<=index<len(evidence):
        raise ValueError('Choose an existing zero-based evidence output index.')
    rows = evidence[index].get('rows',[])
    kind = spec.get('kind')
    if kind not in ('line','bar','scatter','waterfall','heatmap','stacked','pareto'):
        raise ValueError('Choose a supported visualization type.')
    x,y = spec.get('x'),spec.get('y')
    if kind=='bar' and rows and x and y and all(finite(row.get(x)) for row in rows) and all(isinstance(row.get(y),str) for row in rows):
        x,y=y,x;spec.update(x=x,y=y,orientation='horizontal')
    required = [x,y]
    if kind=='heatmap': required.append(spec.get('value'))
    if kind=='stacked': required.append(spec.get('series'))
    required += [spec[k] for k in ('size','numerator','denominator','comparison_y') if spec.get(k)]
    if not rows or any(not key or any(key not in row for row in rows) for key in required):
        raise ValueError('Every chart field must exist in the selected evidence rows.')
    numeric = [spec['value']] if kind=='heatmap' else [y]
    if kind=='scatter': numeric.append(x)
    numeric += [spec[k] for k in ('size','numerator','denominator','comparison_y') if spec.get(k)]
    if any(any(row[key] is not None and not finite(row[key]) for row in rows) for key in numeric):
        raise ValueError('Chart measures must be numeric, with nulls for unavailable observations.')
    if kind in ('stacked','pareto') and any(row[y] is not None and row[y]<0 for row in rows):
        raise ValueError('Shares and Pareto charts require nonnegative measures.')
    if spec.get('comparison_y') and (y.endswith('_cents') != spec['comparison_y'].endswith('_cents')):
        raise ValueError('Current and comparison measures must use compatible units on the shared axis.')
    if kind=='heatmap' and len({(str(row[x]),str(row[y])) for row in rows})!=len(rows):
        raise ValueError('Aggregate to one measured row per heatmap cell first.')
    return {k:v for k,v in spec.items() if k in ('kind','output_index','evidence_id','x','y','series','value','numerator','denominator','size','title','comparison_y','orientation')}


def automatic_chart(evidence,slug=None):
    """Conservative readable fallback; no invented values, units or aggregation."""
    for i,out in enumerate(evidence):
        rows=out.get('rows',[])
        if len(rows)<2 or out.get('name') in ('dataset_inspection','column_profile'):continue
        keys=list(rows[0])
        values=[k for k in keys if not k.endswith(('_key','_id')) and all(r.get(k) is None or finite(r.get(k)) for r in rows) and any(finite(r.get(k)) for r in rows)]
        dims=[k for k in keys if any(isinstance(r.get(k),str) for r in rows)]
        if not values or not dims:continue
        y=next((k for k in values if 'sales' in k or 'revenue' in k),values[0])
        if slug=='growth':y=next((k for k in values if ('change' in k or 'delta' in k) and 'total' not in k and not re.search(r'pct|percent|share',k)),y)
        x=next((k for k in dims if re.search(r'date|month|week',k)),dims[0])
        # Repeated labels need another series or aggregation, not overplotted bars.
        if len({str(r.get(x)) for r in rows})!=len(rows):continue
        return [{'kind':'line' if re.search(r'date|month|week',x) else 'bar','output_index':i,'x':x,'y':y,'automatic':True,**({'orientation':'horizontal'} if slug=='growth' else {})}]
    return []


def validate_presentation(arguments,evidence):
    required=('headline','scope','metric_basis','interpretation','limitations','next_questions','supporting_evidence_ids')
    if any(key not in arguments for key in required):
        raise ValueError('Provide the full playbook answer structure: '+', '.join(required))
    for key in ('headline','scope','metric_basis','interpretation'):
        if not isinstance(arguments[key],str) or not arguments[key].strip() or len(arguments[key])>8000:
            raise ValueError('Answer sections must be nonempty text of at most 8,000 characters.')
    for key in ('limitations','next_questions','supporting_evidence_ids'):
        value=arguments[key]
        if not isinstance(value,list) or len(value)>12 or any(not isinstance(v,str) or len(v)>2000 for v in value):
            raise ValueError('Use a short list of text values for '+key)
    valid={o.get('evidence_id') for o in evidence}
    if not set(arguments['supporting_evidence_ids'])<=valid:
        raise ValueError('Supporting tables must reference measured evidence from this run.')
    if not arguments['supporting_evidence_ids'] and any(o.get('rows') and o.get('name')!='dataset_inspection' for o in evidence):
        raise ValueError('Include at least one measured evidence table in the supporting values.')
    slug=arguments.get('playbook_slug') or None
    if slug: get_contract(slug)
    unsupported=unmatched_money(arguments['headline']+'\n'+arguments['interpretation'],evidence)
    if unsupported:
        raise ValueError('These monetary claims do not match measured cells or complete result-column totals: '+', '.join(unsupported)+'. Check cents-to-USD conversion and compute/reconcile headline totals from evidence before presenting.')
    return {**{k:arguments[k] for k in required},'playbook_slug':slug,'sections':list(SECTIONS),'version':1}


def money(value):return f'${value/100:,.2f}'
def pct(n,d):return f'{100*n/d:.2f}%' if d else 'unavailable (zero base)'


def report_headline(report):
    slug=report['slug']; rows=report['outputs'][0]['rows']
    if not rows:return 'No measured observations were returned for this scope.'
    extras={o['name']:o['rows'] for o in report['outputs']}
    r=rows[0]
    if slug in ('trend','pvm','growth','margin','inventory','returns','promotions'):return report['summary']
    if slug=='seasonality':
        r=max(rows,key=lambda x:x['sales_before_returns_cents'])
        return f"The largest observed retail-week total was {money(r['sales_before_returns_cents'])}, in retail year {r['retail_year']} week {r['retail_week']}; boundary weeks may be partial."
    if slug=='scorecard':
        now=[r for r in rows if r['period']=='current'];before=[r for r in rows if r['period']=='comparison']
        current=sum(r['realized_sales_cents'] for r in now); prior=sum(r['realized_sales_cents'] for r in before)
        return f"Realized sales after observed returns were {money(current)}, changing {money(current-prior)}; cohort merchandise margin was {money(sum(r['merchandise_margin_cents'] for r in now))}."
    if slug=='channels':
        now=[r for r in rows if r['period']=='current'];r=max(now,key=lambda x:x['sales_before_returns_cents']) if now else r
        return f"{r['channel_name']} had the largest current sales total, {money(r['sales_before_returns_cents'])}, from {r['orders']:,} orders. Compare growth and margin before interpreting channel performance."
    if slug=='concentration':
        n=max(1,math.ceil(len(rows)*.1));total=r['total_sales_cents'];part=sum(x['sales_cents'] for x in rows[:n])
        return f"The top {n} of {len(rows)} observed styles account for {pct(part,total)} of sales before returns."
    if slug=='pricing':
        units=sum(x['units'] for x in rows);sales=sum(x['realized_sales_cents'] for x in rows)
        return f"Unit-weighted realized selling price was {money(sales/units) if units else 'unavailable'}, across {units:,} units; markdowns totaled {money(sum(x['markdown_cents'] for x in rows))}."
    if slug=='cohorts':
        numerator=sum(x['repeat_buyers_90'] for x in rows);denominator=sum(x['eligible_90'] for x in rows)
        return f"{numerator:,} of {denominator:,} eligible identified buyers repeated within 90 days ({pct(numerator,denominator)}). Immature cohort cells are not zero."
    if slug=='lapse':return f"{sum(x['identified_buyers'] for x in rows):,} identified buyers are classified by observed recency as of {report['period']['end']}; this does not establish permanent churn."
    if slug=='segments':
        r=max(rows,key=lambda x:x['sales_cents'])
        return f"The {r['segment']} group contributes {money(r['sales_cents'])} in identified sales from {r['identified_buyers']:,} buyers. Groups follow the documented behavioral rules."
    if slug=='affinity':
        eligible=[x for x in rows if x['joint_baskets']>=100];r=max(eligible,key=lambda x:x['lift']) if eligible else None
        return f"{r['category_a']} and {r['category_b']} have the highest observed lift among pairs with at least 100 joint baskets: {r['lift']:.2f}×, based on {r['joint_baskets']:,} joint baskets." if r else 'No pair meets the displayed floor of 100 joint baskets.'
    if slug=='loyalty':
        total=sum(x['sales_before_returns_cents'] for x in rows)
        return f"Loyalty attachment is shown against {money(total)} of merchandise sales before returns. Attachment differences are descriptive, not program impact."
    if slug=='velocity':return f"{len(rows):,} SKU observations compare sales per selected week with the latest available stock. Zero-sale items have undefined weeks of supply, not zero supply."
    if slug=='fulfillment':
        r=max(rows,key=lambda x:x['orders']);total=sum(x['orders'] for x in rows)
        return f"{r['fulfillment_method']} represents {pct(r['orders'],total)} of {total:,} completed orders. Service speed and fulfillment cost are not available."
    return report['summary']


def report_presentation(report):
    contract=get_contract(report['slug']) if report['slug'] in SLUGS else None
    period=report['period']
    scope=f"{report['scope']} · {period['start']}–{period['end']}; comparison {period['compare_start']}–{period['compare_end']}."
    return {'version':1,'sections':list(SECTIONS),'playbook_slug':report['slug'] if contract else None,
            'headline':report_headline(report),'scope':scope,'metric_basis':report['basis'],
            'interpretation':contract['interpretation_guide'] if contract else 'Assess the measured values against the hypothesis falsifier; execution alone does not confirm a hypothesis.',
            'limitations':report['warnings'],'next_questions':[contract['next_drills']] if contract else ['Which competing explanation or falsifier should be tested next?'],
            'supporting_evidence_ids':[o['evidence_id'] for o in report['outputs'] if o.get('evidence_id')],
            'contract':contract, 'interpretation_is_guidance':True}


def finish_presentation(result, supplied=None, playbook_visuals=None):
    outputs=result.get('outputs',[])
    for i,out in enumerate(outputs):out.setdefault('evidence_id','E'+str(i+1))
    p=supplied or result.get('presentation') or (report_presentation(result['report']) if result.get('report') else None)
    if p is None:
        text=result.get('answer','')
        p={'version':1,'sections':list(SECTIONS),'playbook_slug':None,'headline':text.split('\n\n')[0],
           'scope':'Effective dates and filters are stated in the answer and saved SQL; date controls are defaults only.',
           'metric_basis':'Use the labeled source measures and return treatment in the answer.',
           'interpretation':text,'limitations':result.get('warnings',[]),'next_questions':['What narrower breakdown would help you decide the next step?'],
           'supporting_evidence_ids':[o['evidence_id'] for o in outputs if o.get('name')!='dataset_inspection'][:3], 'fallback':True}
    p=dict(p)
    has_design=result.get('report',{}).get('slug') in SLUGS
    if not has_design and not result.get('charts') and not playbook_visuals:
        result['charts']=automatic_chart(outputs,p.get('playbook_slug'))
    result['playbook_visuals']=playbook_visuals or []
    p['visual_status']='available' if has_design or result.get('charts') or playbook_visuals else ('metric_cards' if any(len(o.get('rows',[]))==1 and any(finite(v) for v in o['rows'][0].values()) for o in outputs) else 'no_measured_data')
    p['generated_at']=dt.datetime.now(dt.timezone.utc).isoformat()
    p['sources']=sorted(set(re.findall(r'\b(?:fact_\w+|dim_\w+|v_\w+)\b',' '.join(o.get('sql','') for o in outputs))))
    result['presentation']=p
    if result.get('report'):result['answer']=presentation_markdown(p)
    return result


def presentation_markdown(p):
    parts=[p['headline'],'**Scope and metric**',p['scope'],p['metric_basis']]
    if p['supporting_evidence_ids']:
        parts+=['**Supporting values**',' '.join('['+identity+']' for identity in p['supporting_evidence_ids'])+' — measured tables and visuals are available in the app.']
    parts+=['**Interpretation**',p['interpretation'],'**Limitations**']
    parts += ['- '+item for item in p['limitations']]
    parts += ['**Next question**']+['- '+item for item in p['next_questions']]
    return '\n\n'.join(parts)
