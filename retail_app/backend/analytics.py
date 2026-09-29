"""Deterministic EDA and statistical comparisons over measured evidence."""
import json
import math
from .data import APP, CATALOG, warehouse_session, runner, clean

BANK=json.loads((APP/'knowledge/hypotheses.json').read_text())

def hypothesis_bank(query=''):
    tokens=query.lower().split()
    ranked=sorted(BANK,key=lambda h:sum(t in json.dumps(h).lower() for t in tokens),reverse=True)
    return {'provenance':'18 Summit Field-specific candidate hypotheses, grounded in actual fields and documented generation rules. Milky Way is a workflow reference; these are not its historical enterprise bank.','hypotheses':ranked[:8] if query else ranked}

def profile_column(table,column):
    if table not in CATALOG:raise ValueError('Choose a catalog table.')
    fields={x['name']:x for x in CATALOG[table]['columns']}
    if column not in fields:raise ValueError('Column is not in that table.')
    t='"'+table+'"';c='"'+column+'"'
    numeric=any(x in fields[column]['type'].upper() for x in ['INT','DECIMAL','DOUBLE','FLOAT'])
    with warehouse_session() as con:
        sql=f'SELECT count(*) AS "rows", count({c}) non_null, count(DISTINCT {c}) distinct_values FROM {t}'
        result=runner.fetch(con,sql,[])[0]
        result['null_count']=result['rows']-result['non_null'];result['null_pct']=100*result['null_count']/result['rows'] if result['rows'] else None
        result.update(table=table,column=column,type=fields[column]['type'])
        if numeric:
            summary=f'SELECT min({c}) minimum,max({c}) maximum,avg({c}) mean,stddev_samp({c}) sample_stddev,quantile_cont({c},0.25) q1,median({c}) median,quantile_cont({c},0.75) q3 FROM {t}'
            result.update(runner.fetch(con,summary,[])[0])
            if result['q1'] is not None:
                iqr=result['q3']-result['q1'];lo=result['q1']-1.5*iqr;hi=result['q3']+1.5*iqr
                result['iqr_outlier_count']=con.execute(f'SELECT count(*) FROM {t} WHERE {c}<? OR {c}>?',[lo,hi]).fetchone()[0]
                result['outlier_rule']='Outside Q1 − 1.5×IQR or Q3 + 1.5×IQR; exploratory flag, not a deletion rule.'
        else:
            result['top_values']=runner.fetch(con,f'SELECT {c} value,count(*) frequency FROM {t} GROUP BY 1 ORDER BY 2 DESC LIMIT 12',[])
    result['scope']='Whole table; not filtered by UI dates. Numeric keys and codes are identifiers, not continuous quantities.'
    return clean(result)


def statistics_on_evidence(output,operation,column,other_column=None,group_column=None,group_a=None,group_b=None,independent_observations=False,design_note=''):
    import numpy as np
    from scipy import stats
    if output.get('truncated'):raise ValueError('Statistical tests require a complete query result. Requery independent aggregate units within the row limit.')
    rows=output.get('rows',[])
    def numeric(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)
    values=[r[column] for r in rows if numeric(r.get(column))]
    if not values:raise ValueError('No numeric observations in the selected column.')
    if operation=='describe':
        a=np.array(values,dtype=float)
        return clean({'n':len(a),'missing_or_non_numeric':len(rows)-len(a),'mean':float(a.mean()),'median':float(np.median(a)),'min':float(a.min()),'max':float(a.max()),'stddev':float(a.std(ddof=1)) if len(a)>1 else None,'q1':float(np.quantile(a,.25)),'q3':float(np.quantile(a,.75)),'units':column,'scope':'Returned query rows; inspect SQL for grain and filters.'})
    if not independent_observations or len(design_note.strip())<12:
        raise ValueError('State the observation unit and independence/design assumptions before statistical inference. Repeated customer/store/week rows are not automatically independent.')
    if operation=='spearman':
        pairs=[(r.get(column),r.get(other_column)) for r in rows if numeric(r.get(column)) and numeric(r.get(other_column))]
        if len(pairs)<5:raise ValueError('At least five complete observation pairs are required.')
        x,y=zip(*pairs)
        if len(set(x))<2 or len(set(y))<2:raise ValueError('Correlation is undefined for a constant variable.')
        test=stats.spearmanr(x,y)
        result={'n':len(pairs),'spearman_r':float(test.statistic),'p_value':float(test.pvalue)}
    elif operation in ('anova','kruskal'):
        labels=sorted({str(r.get(group_column)) for r in rows if numeric(r.get(column)) and r.get(group_column) is not None})
        groups=[[r[column] for r in rows if str(r.get(group_column))==label and numeric(r.get(column))] for label in labels]
        if len(groups)<3 or any(len(g)<3 for g in groups):raise ValueError('At least three groups with three independent observations each are required.')
        if sum(float(np.var(g)) for g in groups)==0:raise ValueError('Group comparisons require within-group variation.')
        variance_check=stats.levene(*groups,center='median')
        if operation=='anova' and variance_check.pvalue<.05:raise ValueError('Levene test flags unequal variances; classical ANOVA assumptions are doubtful. Use a justified robust/nonparametric design instead.')
        test=stats.f_oneway(*groups) if operation=='anova' else stats.kruskal(*groups)
        grand=np.mean([x for g in groups for x in g]);ss_between=sum(len(g)*(np.mean(g)-grand)**2 for g in groups);ss_total=sum((x-grand)**2 for g in groups for x in g)
        result={'groups':labels,'group_sizes':[len(g) for g in groups],'group_means':[float(np.mean(g)) for g in groups],'statistic':float(test.statistic),'p_value':float(test.pvalue),'levene_p_value':float(variance_check.pvalue),'eta_squared':float(ss_between/ss_total) if ss_total else None,'assumption_note':'Classical ANOVA assumes independent approximately normal residuals and equal variances; Levene is only a diagnostic. Kruskal tests rank distributions, not simply means.'}
    elif operation in ('welch_t','mann_whitney'):
        if group_a==group_b:raise ValueError('Choose two distinct groups.')
        a=[r[column] for r in rows if str(r.get(group_column))==group_a and numeric(r.get(column))]
        b=[r[column] for r in rows if str(r.get(group_column))==group_b and numeric(r.get(column))]
        if len(a)<3 or len(b)<3:raise ValueError('At least three independent observations in each group are required; small bases still need judgment.')
        if operation=='welch_t' and np.var(a)+np.var(b)==0:raise ValueError('Welch testing needs nonzero variation.')
        test=stats.ttest_ind(a,b,equal_var=False) if operation=='welch_t' else stats.mannwhitneyu(a,b,alternative='two-sided',method='auto')
        result={'group_a':group_a,'group_b':group_b,'n_a':len(a),'n_b':len(b),'mean_a':float(np.mean(a)),'mean_b':float(np.mean(b)),'mean_difference':float(np.mean(a)-np.mean(b)),'statistic':float(test.statistic),'p_value':float(test.pvalue)}
        if operation=='welch_t':
            va,vb=np.var(a,ddof=1),np.var(b,ddof=1);se=math.sqrt(va/len(a)+vb/len(b));df=(va/len(a)+vb/len(b))**2/((va/len(a))**2/(len(a)-1)+(vb/len(b))**2/(len(b)-1));critical=float(stats.t.ppf(.975,df))
            difference=float(np.mean(a)-np.mean(b));pooled=math.sqrt(((len(a)-1)*va+(len(b)-1)*vb)/(len(a)+len(b)-2))
            result.update(mean_difference_ci95=[difference-critical*se,difference+critical*se],degrees_of_freedom=float(df),hedges_g=(1-3/(4*(len(a)+len(b))-9))*difference/pooled if pooled else None)
    else:raise ValueError('Use describe, spearman, welch_t, mann_whitney, anova or kruskal.')
    result.update(method=operation,design_note=design_note,evidence_id=output.get('evidence_id'),interpretation='Exploratory association under stated assumptions, not causality. Unadjusted p-value: account for multiple testing. This is a frozen synthetic census; practical effect sizes and construction rules often matter more than significance.')
    if operation=='kruskal':
        result['descriptive_raw_value_eta_squared']=result.pop('eta_squared')
        result['effect_size_note']='This eta-squared describes variance in raw values; it is not a rank-based effect size for the Kruskal test.'
    if any(isinstance(v,float) and not math.isfinite(v) for v in result.values()):raise ValueError('Test is undefined for these observations.')
    return clean(result)
