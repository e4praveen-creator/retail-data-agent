"""Fail closed on disconnected model-generated joins using DuckDB's parsed AST.

This is a narrow guard, not a proof of SQL/business correctness. It does not
validate foreign keys, join cardinality, aggregation grain, or causal claims.
Validated named playbook SQL is not routed through this model-query guard.
"""
import json
from dataclasses import dataclass, field

GUIDANCE = (' Inspect the catalog, use qualified aliases and an explicit key relationship '
            '(or USING), then correct the SQL. Do not replace the join with a constant filter.')
HEADER_MEASURES={'line_count','units','gross_sales_cents','markdown_cents','promotion_discount_cents','net_sales_cents','tax_cents','cost_of_goods_cents','shipping_cents','total_paid_cents'}
GRAIN_GUIDANCE=(' Header additive measures repeat when orders are joined to sales lines. '
                'For product-filtered totals use fact_sales_line.net_sales_cents and quantity; '
                'count orders with COUNT(DISTINCT t.transaction_key). Keep header-only totals '
                'in a separate header-grain query. SUM(DISTINCT amount) is not a valid fix '
                'because different orders can have equal amounts.')
AGGREGATES = {'sum','count','count_star','avg','min','max','median','quantile_cont',
              'quantile_disc','stddev','stddev_samp','stddev_pop','var_samp','var_pop',
              'variance','bool_and','bool_or','first','last','arg_min','arg_max',
              'list','array_agg','string_agg','approx_count_distinct','any_value'}


@dataclass
class Relation:
    aliases: set = field(default_factory=set)
    tables: set = field(default_factory=set)
    scalar: bool = False
    headers: dict = field(default_factory=dict)
    header_outputs: set = field(default_factory=set)


def _refs(expression):
    """Only references in this expression scope; a subquery owns its own aliases."""
    if isinstance(expression,list):
        return set().union(*(_refs(item) for item in expression)) if expression else set()
    if not isinstance(expression,dict):return set()
    if expression.get('class')=='SUBQUERY':return set()
    if expression.get('class')=='COLUMN_REF':
        names=expression.get('column_names',[])
        return {names[-2].lower()} if len(names)>=2 else set()
    return set().union(*(_refs(value) for value in expression.values())) if expression else set()


def _connected(expression,left,right):
    if not isinstance(expression,dict):return False
    kind=expression.get('type')
    if kind=='CONJUNCTION_AND':
        return any(_connected(child,left,right) for child in expression.get('children',[]))
    if kind=='CONJUNCTION_OR':
        children=expression.get('children',[])
        return bool(children) and all(_connected(child,left,right) for child in children)
    if expression.get('class')=='BETWEEN':
        value=_refs(expression.get('input'))
        bounds=_refs(expression.get('lower'))|_refs(expression.get('upper'))
        return bool((value & left and bounds & right) or (value & right and bounds & left))
    if expression.get('class')!='COMPARISON':return False
    a,b=_refs(expression.get('left')),_refs(expression.get('right'))
    return bool((a & left and b & right) or (a & right and b & left))


def _aggregate_projection(expression,inside_aggregate=False):
    """Return (safe scalar aggregate expression, contains aggregate)."""
    if isinstance(expression,list):
        values=[_aggregate_projection(item,inside_aggregate) for item in expression]
        return all(ok for ok,_ in values),any(agg for _,agg in values)
    if not isinstance(expression,dict):return True,False
    kind=expression.get('class')
    if kind=='WINDOW' or (kind=='FUNCTION' and expression.get('function_name','').lower()=='unnest'):return False,False
    if kind in ('COLUMN_REF','STAR') and not inside_aggregate:return False,False
    if kind=='SUBQUERY':return True,False  # Scalar SQL expression is bounded by DuckDB.
    aggregate=kind=='FUNCTION' and expression.get('function_name','').lower() in AGGREGATES
    values=[_aggregate_projection(value,inside_aggregate or aggregate) for value in expression.values()]
    return all(ok for ok,_ in values),aggregate or any(agg for _,agg in values)


def _expression_subqueries(expression,ctes):
    if isinstance(expression,list):
        for item in expression:_expression_subqueries(item,ctes)
    elif isinstance(expression,dict):
        if expression.get('class')=='SUBQUERY':
            _query(expression['subquery']['node'],ctes)
            return
        for item in expression.values():_expression_subqueries(item,ctes)


def _uses_header_measure(expression,headers):
    """Track header amount lineage without confusing matching line column names."""
    if isinstance(expression,list):return any(_uses_header_measure(x,headers) for x in expression)
    if not isinstance(expression,dict):return False
    kind=expression.get('class')
    if kind=='SUBQUERY':return False  # Its SELECT is checked in its own scope.
    if kind=='COLUMN_REF':
        names=[str(name).lower() for name in expression.get('column_names',[])]
        if not names:return False
        choices=[headers.get(names[-2],set())] if len(names)>=2 else headers.values()
        return any(names[-1] in fields or '*' in fields for fields in choices)
    if kind=='STAR':
        alias=expression.get('relation_name','').lower()
        return bool(headers.get(alias)) if alias else any(headers.values())
    return any(_uses_header_measure(value,headers) for value in expression.values())


def _header_outputs(projections,headers):
    outputs=set()
    for expression in projections:
        if not _uses_header_measure(expression,headers):continue
        alias=expression.get('alias','').lower()
        names=expression.get('column_names',[])
        if alias:outputs.add(alias)
        elif expression.get('class')=='COLUMN_REF' and names:outputs.add(names[-1].lower())
        elif expression.get('class')=='STAR':
            relation=expression.get('relation_name','').lower()
            choices=[headers.get(relation,set())] if relation else headers.values()
            for fields in choices:outputs.update(fields)
        else:
            # DuckDB assigns names to unaliased expressions. Require explicit
            # aliases before using such derived header measures in line joins.
            outputs.add('*')
    return outputs


def _relation(node,ctes,where):
    kind=node.get('type')
    alias=node.get('alias','').lower()
    if kind=='BASE_TABLE':
        table=node.get('table_name','').lower()
        source=ctes.get(table) if not node.get('schema_name') else None
        fields=set(source.header_outputs) if source else (set(HEADER_MEASURES) if table=='fact_transaction' else set())
        return Relation({alias or table},set(source.tables) if source else {table},source.scalar if source else False,{alias or table:fields} if fields else {})
    if kind=='EMPTY':return Relation(scalar=True)
    if kind=='TABLE_FUNCTION':
        return Relation({alias or node.get('function',{}).get('function_name','').lower()})
    if kind=='SUBQUERY':
        source=_query(node['subquery']['node'],ctes)
        fields=set(source.header_outputs)
        if fields and node.get('column_name_alias'):fields={str(name).lower() for name in node['column_name_alias']}
        return Relation({alias} if alias else set(),source.tables,source.scalar,{alias:fields} if fields else {})
    if kind=='JOIN':
        left=_relation(node['left'],ctes,where)
        right=_relation(node['right'],ctes,where)
        condition=node.get('condition')
        _expression_subqueries(condition,ctes)
        using=bool(node.get('using_columns'))
        connected=_connected(condition,left.aliases,right.aliases)
        # Comma/CROSS syntax with an explicit WHERE key link is an equivalent
        # inner join. A grouped subquery is not treated as a one-row aggregate.
        cross=node.get('ref_type')=='CROSS'
        if cross:connected=connected or _connected(where,left.aliases,right.aliases)
        scalar_product=left.scalar or right.scalar
        if not (using or connected or scalar_product):
            raise ValueError('The join does not establish a verified relationship between its left and right inputs.'+GUIDANCE)
        tables=left.tables|right.tables
        if {'fact_sales_line','dim_channel'}<=tables and not tables & {'fact_transaction','v_sales'}:
            raise ValueError('Retail channel belongs to fact_transaction, not fact_sales_line. Join sales lines to fact_transaction on transaction_key and then to dim_channel on channel_key, or use v_sales.'+GUIDANCE)
        headers={**left.headers,**right.headers}
        if alias and headers:headers={alias:set().union(*headers.values())}
        return Relation({alias} if alias else left.aliases|right.aliases,tables,left.scalar and right.scalar,headers)
    raise ValueError('This SQL table expression cannot be verified safely. Use catalog tables, explicit SELECT subqueries or CTEs.'+GUIDANCE)


def _query(node,inherited):
    ctes=dict(inherited)
    for item in node.get('cte_map',{}).get('map',[]):
        source=_query(item['value']['query']['node'],ctes)
        if source.header_outputs and item['value'].get('aliases'):
            source.header_outputs={str(name).lower() for name in item['value']['aliases']}
        ctes[item['key'].lower()]=source
    kind=node.get('type')
    if kind=='SET_OPERATION_NODE':
        left=_query(node['left'],ctes);right=_query(node['right'],ctes)
        return Relation(tables=left.tables|right.tables,header_outputs={'*'} if left.header_outputs or right.header_outputs else set())
    if kind!='SELECT_NODE':
        raise ValueError('This SQL query structure cannot be verified safely. Use an ordinary SELECT with explicit key joins.'+GUIDANCE)
    relation=_relation(node.get('from_table',{'type':'EMPTY'}),ctes,node.get('where_clause'))
    for key,value in node.items():
        if key not in ('from_table','cte_map'):_expression_subqueries(value,ctes)
    if {'fact_transaction','fact_sales_line'}<=relation.tables and _uses_header_measure(node.get('select_list',[]),relation.headers):
        raise ValueError('Header-grain measures cannot be projected or aggregated after sales-line expansion.'+GRAIN_GUIDANCE)
    grouped=bool(node.get('group_expressions') or node.get('group_sets'))
    safe,has_aggregate=_aggregate_projection(node.get('select_list',[]))
    scalar=not grouped and safe and (relation.scalar or has_aggregate)
    # Star/column projections preserve a known one-row FROM relation, except
    # row-expanding UNNEST/window projections cannot establish scalar cardinality.
    if relation.scalar and not grouped:
        def expands(value):
            if isinstance(value,list):return any(expands(x) for x in value)
            if not isinstance(value,dict):return False
            if value.get('class')=='FUNCTION' and value.get('function_name','').lower()=='unnest':return True
            return any(expands(x) for x in value.values())
        scalar=not expands(node.get('select_list',[]))
    return Relation(tables=relation.tables,scalar=scalar,header_outputs=_header_outputs(node.get('select_list',[]),relation.headers))


def validate_model_sql(sql,connection):
    """Validate a single model SELECT before execution; never execute its SQL.

    `connection` is the existing read-only DuckDB connection. Serialization parses
    SQL without binding or scanning its tables. Unsupported parser shapes fail
    with correction guidance, so a model can inspect schema and retry.
    """
    try:
        parsed=json.loads(connection.execute('SELECT json_serialize_sql(?)',[sql]).fetchone()[0])
    except Exception:
        raise ValueError('The SQL join structure could not be parsed safely.'+GUIDANCE) from None
    if parsed.get('error') or len(parsed.get('statements',[]))!=1:
        raise ValueError('Provide one parseable SELECT statement for verification.'+GUIDANCE)
    try:
        _query(parsed['statements'][0]['node'],{})
    except (KeyError,TypeError,RecursionError):
        raise ValueError('The SQL structure is unsupported by the join verifier.'+GUIDANCE) from None
