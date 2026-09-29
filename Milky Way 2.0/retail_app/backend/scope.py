"""Durable retail scope and bound, grain-safe analytical queries.

A scope is a value object, not SQL. Filter updates replace the same field while
retaining other fields; an empty filter list clears all filters. Calendar-return
activity and snapshot inventory require their own recipes rather than an implicit
change of grain. No source recipe is rewritten.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from functools import lru_cache

from . import data

# expression, value type, complete reference lookup (where appropriate)
FIELDS = {
    'channel_name': ('ch.channel_name', 'text', ('dim_channel', 'channel_name')),
    'channel_key': ('s.channel_key', 'int', None),
    'division_name': ('p.division_name', 'text', ('dim_division', 'division_name')),
    'department_name': ('p.department_name', 'text', ('dim_department', 'department_name')),
    'category_name': ('p.category_name', 'text', ('dim_category', 'category_name')),
    'style_name': ('p.style_name', 'text', ('dim_style', 'style_name')),
    'sku_code': ('p.sku_code', 'text', ('dim_sku', 'sku_code')),
    'sku_key': ('s.sku_key', 'int', None),
    'brand_name': ('p.brand_name', 'text', ('dim_brand', 'brand_name')),
    'color_name': ('p.color_name', 'text', ('dim_color', 'color_name')),
    'size_label': ('p.size_label', 'text', ('dim_size', 'size_label')),
    'price_tier': ('p.price_tier', 'text', ('dim_style', 'price_tier')),
    'is_private_label': ('p.is_private_label', 'bool', None),
    'store_name': ('st.store_name', 'text', ('dim_store', 'store_name')),
    'selling_store_key': ('s.selling_store_key', 'int', None),
    'region': ('st.region', 'text', ('dim_store', 'region')),
    'market_store_name': ('mt.store_name', 'text', ('dim_store', 'store_name')),
    'market_store_key': ('s.market_store_key', 'int', None),
    'market_region': ('mt.region', 'text', ('dim_store', 'region')),
    'customer_key': ('s.customer_key', 'int', None),
    'customer_segment': ('cu.customer_segment', 'text', ('dim_customer', 'customer_segment')),
    'age_band': ('cu.age_band', 'text', ('dim_customer', 'age_band')),
    'identified': ('s.customer_key > 0', 'bool', None),
    'loyalty_tier': ('lo.loyalty_tier', 'text', ('dim_loyalty', 'loyalty_tier')),
    'loyalty_attached': ('s.loyalty_key > 0', 'bool', None),
    'promotion_name': ('pr.promotion_name', 'text', ('dim_promotion', 'promotion_name')),
    'promotion_key': ('s.promotion_key', 'int', None),
    'promotion_applied': ('s.promotion_key > 0', 'bool', None),
    'discounted': ('s.markdown_cents + s.promotion_discount_cents > 0', 'bool', None),
    'fulfillment_method': ('fm.fulfillment_method', 'text', ('dim_fulfillment_method', 'fulfillment_method')),
    'calendar_date': ('s.calendar_date', 'date', None),
    'week_start': ("CAST(date_trunc('week', s.calendar_date + INTERVAL 1 DAY) - INTERVAL 1 DAY AS DATE)", 'date', None),
    'month': ("CAST(date_trunc('month', s.calendar_date) AS DATE)", 'date', None),
    'quarter': ("CAST(date_trunc('quarter', s.calendar_date) AS DATE)", 'date', None),
    'calendar_year': ('s.calendar_year', 'int', None),
    'retail_year': ('s.retail_year', 'int', None),
    'retail_week': ('s.retail_week', 'int', None),
    'selling_price_bucket_usd': ('CAST(floor(s.selling_unit_price_cents/1000.0)*10 AS INTEGER)', 'int', None),
    'regular_price_bucket_usd': ('CAST(floor(s.regular_unit_price_cents/1000.0)*10 AS INTEGER)', 'int', None),
}
ALIASES = {
    'channel': 'channel_name', 'division': 'division_name', 'department': 'department_name',
    'category': 'category_name', 'style': 'style_name', 'sku': 'sku_code', 'brand': 'brand_name',
    'color': 'color_name', 'size': 'size_label', 'store': 'store_name', 'selling_store': 'store_name',
    'market_store': 'market_store_name', 'customer': 'customer_key', 'segment': 'customer_segment',
    'loyalty': 'loyalty_attached', 'member': 'loyalty_attached', 'promotion': 'promotion_name',
    'promoted': 'promotion_applied', 'fulfillment': 'fulfillment_method', 'day': 'calendar_date',
    'calendar_month': 'month', 'calendar_week': 'week_start', 'week': 'week_start', 'year': 'calendar_year', 'private_label': 'is_private_label',
}
VALUE_ALIASES = {'channel_name': {'app': 'Mobile app', 'mobile': 'Mobile app', 'website': 'Web',
                                   'online': 'Web', 'pos': 'Store POS', 'store': 'Store POS'}}
DATE_KEYS = ('start', 'end', 'compare_start', 'compare_end')
RETURN_BASES = {'before_returns', 'sales_cohort', 'return_date'}
MEASURE_ALIASES = {
    'sales': 'sales_cents', 'net_sales': 'sales_cents', 'revenue': 'sales_cents',
    'net_sales_cents': 'sales_cents', 'sold_units': 'units', 'quantity': 'units',
    'customers': 'identified_buyers', 'buyers': 'identified_buyers',
    'avg_price': 'avg_price_cents', 'average_price': 'avg_price_cents', 'aov': 'aov_cents',
    'margin': 'margin_cents', 'merchandise_margin': 'merchandise_margin_cents',
    'returns': 'returned_units', 'return_rate': 'return_rate_pct',
    'refunds': 'refund_cents', 'refund_net_cents': 'refund_cents', 'discount': 'discount_cents',
    'gross_sales': 'gross_sales_cents',
}
MEASURE_NAMES = {
    'sales_cents', 'sales_before_returns_cents', 'sales_after_returns_cents',
    'units', 'net_units', 'orders', 'identified_buyers', 'avg_price_cents', 'aov_cents',
    'margin_cents', 'merchandise_margin_cents', 'margin_before_returns_cents', 'margin_rate_pct',
    'returned_units', 'refund_cents', 'return_rate_pct', 'cost_of_goods_cents',
    'recovered_cost_cents', 'gross_sales_cents', 'markdown_cents', 'promotion_discount_cents', 'discount_cents',
}
JOIN_SQL = '''FROM v_sales_after_returns s
JOIN v_product p ON s.sku_key=p.sku_key
JOIN dim_channel ch ON s.channel_key=ch.channel_key
JOIN dim_store st ON s.selling_store_key=st.store_key
JOIN dim_store mt ON s.market_store_key=mt.store_key
JOIN dim_customer cu ON s.customer_key=cu.customer_key
JOIN dim_loyalty lo ON s.loyalty_key=lo.loyalty_key
JOIN dim_promotion pr ON s.promotion_key=pr.promotion_key
JOIN dim_fulfillment_method fm ON s.fulfillment_method_key=fm.fulfillment_method_key'''


def _field(value):
    if not isinstance(value, str):
        raise ValueError('Scope fields must be field names.')
    name = ALIASES.get(value, value)
    if name not in FIELDS:
        raise ValueError(f'Unsupported retail scope field {value!r}. Supported fields: '+', '.join(FIELDS))
    return name


def _measure(value):
    if not isinstance(value, str):
        raise ValueError('Measures must be names from the retail metric catalog.')
    name = MEASURE_ALIASES.get(value, value)
    if name not in MEASURE_NAMES:
        raise ValueError(f'Unsupported retail measure {value!r}. Supported measures: '+', '.join(sorted(MEASURE_NAMES)))
    return name


def _iso(value):
    if value in (None, ''):
        return None
    if isinstance(value, dt.datetime):
        value = value.date()
    try:
        return dt.date.fromisoformat(str(value)).isoformat()
    except (TypeError, ValueError):
        raise ValueError('Scope dates must be ISO calendar dates (YYYY-MM-DD).') from None


@lru_cache(maxsize=48)
def _labels(db_path, field):
    table, column = FIELDS[field][2]
    with data.warehouse_session() as con:
        return tuple(row[0] for row in con.execute(f'SELECT DISTINCT {column} FROM {table}').fetchall())


def _value(field, value):
    kind, lookup = FIELDS[field][1:]
    if kind == 'int':
        if isinstance(value, bool) or not isinstance(value, (int, float)) or int(value) != value or not 0 <= value <= 2**53-1:
            raise ValueError(f'{field} requires a nonnegative integer value.')
        return int(value)
    if kind == 'bool':
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.lower() in ('true', 'false'):
            return value.lower() == 'true'
        raise ValueError(f'{field} requires true or false.')
    if kind == 'date':
        normalized = _iso(value)
        if not normalized:
            raise ValueError(f'{field} requires a date.')
        return normalized
    if not isinstance(value, str) or not value.strip() or len(value) > 200:
        raise ValueError(f'{field} requires a nonempty text value of at most 200 characters.')
    value = value.strip()
    value = VALUE_ALIASES.get(field, {}).get(value.casefold(), value)
    if lookup:
        known = {str(x).casefold(): x for x in _labels(str(data.DB), field)}
        if value.casefold() not in known:
            example = ', '.join(str(v) for v in list(known.values())[:12])
            raise ValueError(f'Unknown {field} value {value!r}. Examples: {example}. Inspect its dimension table for the complete list.')
        value = known[value.casefold()]
    return value


def normalize_scope(candidate, previous=None, dates=None):
    """Merge a validated patch into durable scope; never invent comparison dates.

    ``filters`` patches by field; ``[]`` clears all; ``remove_filters`` removes
    specific fields. ``dimensions`` replaces the grouping. Explicit current date
    changes drop old comparisons unless the patch supplies a new pair.
    """
    if candidate is None:
        candidate = {}
    if not isinstance(candidate, dict) or previous is not None and not isinstance(previous, dict):
        raise ValueError('Analysis scope must be an object.')
    allowed = {'dates', *DATE_KEYS, 'metric', 'return_basis', 'filters', 'dimensions', 'remove_filters', 'reset_filters'}
    unknown = set(candidate) - allowed
    if unknown:
        raise ValueError('Unknown scope properties: '+', '.join(sorted(unknown)))
    previous = previous or {}
    date_values = {k: None for k in DATE_KEYS}
    for source in (dates or {}, previous.get('dates') or {}):
        if not isinstance(source, dict):
            raise ValueError('Scope dates must be an object.')
        date_values.update({k: _iso(source[k]) for k in DATE_KEYS if k in source})
    patch_dates = candidate.get('dates') or {}
    if not isinstance(patch_dates, dict) or set(patch_dates)-set(DATE_KEYS):
        raise ValueError('Use start, end, compare_start and compare_end inside dates.')
    patch_dates = {**patch_dates, **{k: candidate[k] for k in DATE_KEYS if k in candidate}}
    patch_dates = {k: _iso(v) for k, v in patch_dates.items()}
    if any(k in patch_dates and patch_dates[k] != date_values[k] for k in ('start', 'end')):
        date_values.update(compare_start=None, compare_end=None)
    date_values.update(patch_dates)
    for first, last in (('start', 'end'), ('compare_start', 'compare_end')):
        a, b = date_values[first], date_values[last]
        if bool(a) != bool(b):
            raise ValueError(f'Provide both {first} and {last}, or neither.')
        if a and (a > b or a < '2024-01-01' or b > '2025-12-31'):
            raise ValueError('Sales dates must be ordered within 2024-01-01 through 2025-12-31.')
    if date_values['compare_start'] and not date_values['start']:
        raise ValueError('A comparison requires a current sales period.')
    if date_values['compare_end'] and date_values['compare_end'] >= date_values['start']:
        raise ValueError('Comparison must end before the current sales period begins.')
    metric = _measure(candidate.get('metric', previous.get('metric', 'sales_cents')))
    basis = candidate.get('return_basis', previous.get('return_basis', 'before_returns'))
    if not isinstance(basis, str):
        raise ValueError('return_basis must be a supported basis name.')
    basis = {'cohort': 'sales_cohort', 'original_sales': 'before_returns', 'calendar': 'return_date'}.get(basis, basis)
    if basis not in RETURN_BASES:
        raise ValueError('return_basis must be before_returns, sales_cohort, or return_date.')
    raw_filters = candidate.get('filters', None)
    if raw_filters is not None and (not isinstance(raw_filters, list) or len(raw_filters) > 24):
        raise ValueError('Provide at most 24 retail filters.')
    filters = {} if candidate.get('reset_filters') or raw_filters == [] else {x['field']: x for x in previous.get('filters', [])}
    removed = candidate.get('remove_filters', [])
    if not isinstance(removed, list):
        raise ValueError('remove_filters must be a list of field names.')
    for field in removed:
        filters.pop(_field(field), None)
    for item in raw_filters or []:
        if not isinstance(item, dict) or set(item)-{'field', 'op', 'values'}:
            raise ValueError('Each filter needs field, op and values.')
        field = _field(item.get('field'))
        raw_op = item.get('op', 'in')
        if not isinstance(raw_op, str):
            raise ValueError('Filter operators must be names such as eq or in.')
        op = {'=': 'eq', '==': 'eq', '!=': 'ne', 'not in': 'not_in'}.get(raw_op, raw_op)
        if op not in {'eq', 'ne', 'in', 'not_in', 'gt', 'gte', 'lt', 'lte', 'between'}:
            raise ValueError('Filter operators: eq, ne, in, not_in, gt, gte, lt, lte, between.')
        values = item.get('values')
        if not isinstance(values, list) or not 1 <= len(values) <= 100:
            raise ValueError('Each filter requires between 1 and 100 values.')
        if op in {'eq', 'ne', 'gt', 'gte', 'lt', 'lte'} and len(values) != 1 or op == 'between' and len(values) != 2:
            raise ValueError(f'Wrong number of values for {op}.')
        if op in {'gt', 'gte', 'lt', 'lte', 'between'} and FIELDS[field][1] not in {'int', 'date'}:
            raise ValueError('Ordered filters require a numeric or date field.')
        values = list(dict.fromkeys(_value(field, v) for v in values))
        if op == 'between' and (len(values) != 2 or values[0] > values[1]):
            raise ValueError('between requires ordered lower and upper bounds.')
        if op in {'in', 'not_in'}:
            values = sorted(values)
        filters[field] = {'field': field, 'op': op, 'values': values}
    dims = candidate.get('dimensions', previous.get('dimensions', []))
    if not isinstance(dims, list) or len(dims) > 8:
        raise ValueError('Choose at most 8 grouping dimensions.')
    dims = list(dict.fromkeys(_field(d) for d in dims))
    return {'dates': date_values, 'metric': metric, 'return_basis': basis,
            'filters': [filters[k] for k in sorted(filters)], 'dimensions': dims}


def scope_fingerprint(scope):
    normalized = normalize_scope(scope)
    return hashlib.sha256(json.dumps(normalized, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def scope_description(scope):
    scope = normalize_scope(scope)
    description = '; '.join(f"{f['field']} {f['op']} {', '.join(map(str, f['values']))}" for f in scope['filters']) or 'All business'
    return description + ('; grouped by '+', '.join(scope['dimensions']) if scope['dimensions'] else '')


def _predicates(scope):
    clauses, parameters = [], []
    op_sql = {'eq': '=', 'ne': '<>', 'gt': '>', 'gte': '>=', 'lt': '<', 'lte': '<='}
    for f in scope['filters']:
        expression = '('+FIELDS[f['field']][0]+')'
        if f['op'] in {'in', 'not_in'}:
            operator = 'NOT IN' if f['op'] == 'not_in' else 'IN'
            clauses.append(expression+' '+operator+' ('+','.join('?' for _ in f['values'])+')')
        elif f['op'] == 'between':
            clauses.append(expression+' BETWEEN ? AND ?')
        else:
            clauses.append(expression+' '+op_sql[f['op']]+' ?')
        parameters.extend(f['values'])
    return clauses, parameters


def _expressions(basis):
    sales = 's.realized_net_sales_cents' if basis == 'sales_cohort' else 's.net_sales_cents'
    margin = 's.merchandise_margin_cents' if basis == 'sales_cohort' else '(s.net_sales_cents-s.cost_of_goods_cents)'
    summed = {
        'sales_cents': sales, 'sales_before_returns_cents': 's.net_sales_cents',
        'sales_after_returns_cents': 's.realized_net_sales_cents', 'units': 's.quantity',
        'net_units': '(s.quantity-s.returned_units)', 'margin_cents': margin,
        'merchandise_margin_cents': 's.merchandise_margin_cents',
        'margin_before_returns_cents': '(s.net_sales_cents-s.cost_of_goods_cents)',
        'returned_units': 's.returned_units', 'refund_cents': 's.refund_net_cents',
        'cost_of_goods_cents': 's.cost_of_goods_cents',
        'recovered_cost_cents': '(s.cost_of_goods_cents-s.net_cost_of_goods_cents)',
        'gross_sales_cents': 's.gross_sales_cents', 'markdown_cents': 's.markdown_cents',
        'promotion_discount_cents': 's.promotion_discount_cents',
        'discount_cents': '(s.markdown_cents+s.promotion_discount_cents)',
    }
    expressions = {k: f'coalesce(sum({v}),0)' for k, v in summed.items()}
    expressions.update({
        'orders': 'count(DISTINCT s.transaction_key)',
        'identified_buyers': 'count(DISTINCT CASE WHEN s.customer_key>0 THEN s.customer_key END)',
        'avg_price_cents': f'1.0*sum({sales})/nullif(sum(s.quantity),0)',
        'aov_cents': f'1.0*sum({sales})/nullif(count(DISTINCT s.transaction_key),0)',
        'margin_rate_pct': f'100.0*sum({margin})/nullif(sum({sales}),0)',
        'return_rate_pct': '100.0*sum(s.returned_units)/nullif(sum(s.quantity),0)',
    })
    return expressions


def query_retail(scope, measures=None, dimensions=None, compare=False, limit=500):
    """Query completed-sale lines with bound predicates and distinct reach counts.

    Product/promotion filters select matching lines. Orders are orders containing
    those lines; AOV is selected merchandise per matching order, not full-basket
    AOV. Cohort return facts are aggregated before joining at original-sale grain.
    """
    scope = normalize_scope(scope)
    if not scope['dates']['start']:
        raise ValueError('Set start and end dates before querying retail metrics.')
    if scope['return_basis'] == 'return_date':
        raise ValueError('Return-date activity has a separate event grain. Use scoped SQL on sales and return events joined to original-sale attributes; do not use sale-cohort results as calendar return activity.')
    if not isinstance(compare, bool):
        raise ValueError('compare must be true or false.')
    if compare and not scope['dates']['compare_start']:
        raise ValueError('A comparison query requires explicit compare_start and compare_end dates.')
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
        raise ValueError('Query previews must contain between 1 and 500 rows.')
    if measures is None:
        measures = [scope['metric']]
    if not isinstance(measures, list) or not 1 <= len(measures) <= 24:
        raise ValueError('Choose between 1 and 24 supported retail measures.')
    measures = list(dict.fromkeys(_measure(x) for x in measures))
    dims = scope['dimensions'] if dimensions is None else normalize_scope({'dimensions': dimensions})['dimensions']
    scope = {**scope, 'dimensions': dims}
    expressions = _expressions(scope['return_basis'])
    filters, filter_values = _predicates(scope)
    selections, parameters, where = [], [], []
    dates = scope['dates']
    if compare:
        selections.append("CASE WHEN s.calendar_date BETWEEN ? AND ? THEN 'current' ELSE 'comparison' END AS period")
        parameters += [dates['start'], dates['end']]
        where.append('(s.calendar_date BETWEEN ? AND ? OR s.calendar_date BETWEEN ? AND ?)')
        parameters += [dates[k] for k in DATE_KEYS]
    else:
        where.append('s.calendar_date BETWEEN ? AND ?')
        parameters += [dates['start'], dates['end']]
    selections += [f'{FIELDS[d][0]} AS {d}' for d in dims]
    selections += [f'{expressions[m]} AS {m}' for m in measures]
    where += filters
    parameters += filter_values
    group_count = len(dims) + int(compare)
    sql = 'SELECT '+',\n'.join(selections)+'\n'+JOIN_SQL+'\nWHERE '+' AND '.join(where)
    if group_count:
        sql += '\nGROUP BY '+','.join(str(i+1) for i in range(group_count))
        sql += '\nORDER BY '+','.join(str(i+1) for i in range(group_count))
    with data.warehouse_session() as con:
        cursor = con.execute(sql, parameters)
        columns = [c[0] for c in cursor.description]
        fetched = cursor.fetchmany(limit+1)
        rows = data.clean([dict(zip(columns, row)) for row in fetched[:limit]])
    warnings = ['Synthetic retail evidence is descriptive and does not establish causality.',
        'Orders and identified buyers are distinct within each group; they may overlap across product or promotion groups.',
        'Product/promotion filters select merchandise lines: AOV is selected merchandise per matching order.']
    if any(m in {'merchandise_margin_cents', 'sales_after_returns_cents', 'net_units', 'returned_units', 'refund_cents', 'return_rate_pct', 'recovered_cost_cents'} for m in measures) or scope['return_basis']=='sales_cohort':
        warnings.append('Returns are linked to the original sales cohort through the frozen 2026-03-01 extract, not deducted on their return date.')
    if any(f['field'] in {'region','store_name','selling_store_key'} for f in scope['filters']) or any(d in {'region','store_name','selling_store_key'} for d in dims):
        warnings.append('Store and region refer to the selling store; digital orders have selling_store_key 0. Use market_store/market_region for digital attribution.')
    if compare:
        current_days = (dt.date.fromisoformat(dates['end'])-dt.date.fromisoformat(dates['start'])).days+1
        comparison_days = (dt.date.fromisoformat(dates['compare_end'])-dt.date.fromisoformat(dates['compare_start'])).days+1
        if current_days != comparison_days:
            warnings.append(f'Unequal period lengths: current {current_days} days; comparison {comparison_days} days. Totals are not daily-normalized.')
    return {'name': 'scoped_retail_query', 'rows': rows, 'row_count': len(rows), 'truncated': len(fetched)>limit,
            'sql': sql, 'parameters': parameters, 'scope': scope, 'scope_fingerprint': scope_fingerprint(scope),
            'dimensions': dims, 'measures': measures, 'warnings': warnings,
            'basis': 'Original sale date; '+scope['return_basis']+'; USD money stored as integer cents; tax and shipping excluded.',
            'grain': 'Original merchandise sales line; preaggregated linked returns; distinct matching orders and identified buyers.',
            'limits': {'max_rows': limit}, 'sources': ['v_sales_after_returns', 'v_product', 'dim_channel', 'dim_store', 'dim_customer', 'dim_loyalty', 'dim_promotion', 'dim_fulfillment_method']}


def _rename(output, name, mapping):
    """Label recipe-compatible measured columns without changing their values."""
    result = {**output, 'name': name}
    result['rows'] = [{mapping.get(k,k): v for k,v in row.items()} for row in output['rows']]
    result['column_mapping'] = mapping
    return result


def run_scoped_playbook(slug, dates, scope):
    """Run a full original recipe or an explicitly scoped supported adaptation.

    Safe adapted recipes: trend, growth, margin, scorecard, concentration. Other
    methods need explicit cohort/basket/snapshot semantics; refusing those is
    preferable to silently reporting an all-business recipe under a filter.
    """
    if slug not in data.SLUGS:
        raise ValueError('Unknown playbook: '+str(slug))
    scope = normalize_scope(scope, dates=dates)
    period = scope['dates']
    if not period['start']:
        raise ValueError('Choose start and end dates before running a playbook.')
    original_dates = {k: dt.date.fromisoformat(v) for k,v in period.items() if v}
    if not scope['filters'] and not scope['dimensions'] and len(original_dates)==4 and scope['return_basis']=='before_returns' and scope['metric']=='sales_cents':
        if original_dates['end']-original_dates['start'] == original_dates['compare_end']-original_dates['compare_start']:
            report = data.run_playbook(slug, original_dates)
            report['analysis_scope'] = scope
            report['scope_fingerprint'] = scope_fingerprint(scope)
            report['coverage'] = 'Full validated original playbook and visual contract.'
            return report
    safe = {'trend','growth','margin','scorecard','concentration'}
    if slug not in safe:
        raise ValueError(f'The {slug} playbook does not yet have a validated filtered adapter. Do not run its all-business recipe under this scope. Read get_playbook_design, then use query_retail for supported measures or explicit scoped SQL with the recipe’s cohort/basket/snapshot denominator. Label the result as an adapted analysis, not the complete playbook.')
    if scope['dimensions'] and scope['dimensions'] != (['week_start'] if slug=='trend' else ['style_name'] if slug=='concentration' else ['division_name']):
        raise ValueError(f'{slug} has a fixed validated grouping. Clear dimensions to run it, or use query_retail with the requested custom grouping.')
    if slug in {'growth','margin','scorecard'} and not period['compare_start']:
        raise ValueError(f'The {slug} playbook requires explicit current and comparison periods.')
    if slug in {'trend','growth','concentration'} and scope['metric'] not in {'sales_cents','sales_before_returns_cents'}:
        raise ValueError(f'The {slug} visual contract measures sales before returns. Use query_retail for the active {scope["metric"]} metric instead of silently substituting sales.')
    if slug in {'trend','growth','concentration'} and scope['return_basis'] != 'before_returns':
        raise ValueError(f'The {slug} visual contract uses sales before returns. Use query_retail for the requested return basis, or explicitly select before_returns.')
    if slug in {'margin','scorecard'}:
        # This is the original contract, not a model-selected alternate definition.
        scope = {**scope, 'return_basis': 'sales_cohort'}
    outputs = []
    if slug == 'trend':
        output = query_retail(scope, ['sales_before_returns_cents','units','orders'], ['week_start'], bool(period['compare_start']))
        if not period['compare_start']:
            output['rows'] = [{'period':'current',**r} for r in output['rows']]
        outputs = [_rename(output, 'weekly_sales', {'units':'sold_units'})]
    elif slug == 'growth':
        output = query_retail(scope, ['sales_before_returns_cents'], ['division_name'], True)
        grouped = {}
        for row in output['rows']:
            record = grouped.setdefault(row['division_name'], {'division_name':row['division_name'], 'current_sales_cents':0, 'comparison_sales_cents':0})
            record[row['period']+'_sales_cents'] = row['sales_before_returns_cents']
        for row in grouped.values():
            row['change_cents'] = row['current_sales_cents']-row['comparison_sales_cents']
        output = {**output, 'name':'division_contributions', 'rows':sorted(grouped.values(), key=lambda r:abs(r['change_cents']), reverse=True), 'derivation':'Pivot measured period totals; change = current minus comparison.'}
        output['row_count'] = len(output['rows'])
        outputs = [output]
    elif slug == 'margin':
        output = query_retail(scope, ['sales_before_returns_cents','refund_cents','cost_of_goods_cents','recovered_cost_cents','sales_after_returns_cents','merchandise_margin_cents'], ['division_name'], True)
        outputs = [_rename(output, 'division_margin_components', {'sales_before_returns_cents':'original_net_sales_cents','refund_cents':'returned_revenue_cents','cost_of_goods_cents':'original_cogs_cents','sales_after_returns_cents':'realized_sales_cents'})]
    elif slug == 'scorecard':
        measures = ['sales_after_returns_cents','units','merchandise_margin_cents','returned_units','orders','identified_buyers','margin_rate_pct','return_rate_pct']
        mapping = {'sales_after_returns_cents':'realized_sales_cents', 'units':'sold_units', 'return_rate_pct':'unit_return_rate_pct'}
        outputs = [_rename(query_retail(scope, measures, ['division_name'], True), 'division_scorecard', mapping),
                   _rename(query_retail(scope, measures, [], True), 'scorecard_summary', mapping)]
    elif slug == 'concentration':
        output = query_retail(scope, ['sales_before_returns_cents'], ['style_name'])
        if output['truncated']:
            raise ValueError('Concentration output exceeds the supported full ranking. Narrow the scope before computing cumulative shares.')
        rows = sorted(output['rows'], key=lambda r:(-r['sales_before_returns_cents'],r['style_name']))
        total = sum(r['sales_before_returns_cents'] for r in rows)
        cumulative = 0
        for row in rows:
            row['sales_cents'] = row.pop('sales_before_returns_cents')
            cumulative += row['sales_cents']
            row['cumulative_sales_cents'] = cumulative
            row['total_sales_cents'] = total
        outputs = [{**output, 'name':'style_pareto', 'rows':rows, 'derivation':'Full descending measured style ranking and cumulative sum.'}]
    for i, output in enumerate(outputs):
        output['evidence_id'] = f'E{i+1}'
    from .presentation import get_contract, report_headline
    warnings = list(dict.fromkeys(w for output in outputs for w in output['warnings']))
    warnings.append('Validated scoped adaptation: filters apply to every output; original source recipes remain unchanged.')
    if slug in {'margin','scorecard'}:
        warnings.append('This playbook explicitly uses sales-cohort realized revenue and merchandise margin after observed returns.')
    report = {'slug':slug, 'title':data.TITLES[data.SLUGS.index(slug)], 'period':period,
              'scope':scope_description(scope), 'analysis_scope':scope, 'scope_fingerprint':scope_fingerprint(scope),
              'basis':outputs[0]['basis'], 'outputs':outputs, 'warnings':warnings,
              'coverage':'Validated scoped adaptation with recipe-compatible primary visual and supporting evidence.',
              'checks':[{'name':'Bound scope filters applied to every output', 'passed':True},
                        {'name':'No truncated evidence used in playbook output', 'passed':not any(o['truncated'] for o in outputs)}],
              'sources':sorted(set(s for o in outputs for s in o['sources'])), 'output_design':get_contract(slug)}
    report['summary'] = data.summarize(slug, outputs)
    report['summary'] = report_headline(report)
    return data.clean(report)


def query_capabilities():
    """Small explicit catalog for the model; no customer records or credentials."""
    return {
        'dimensions': list(FIELDS),
        'measures': sorted(MEASURE_NAMES),
        'filters': {name:{'type': details[1], 'operators': ['eq','ne','in','not_in'] + (['gt','gte','lt','lte','between'] if details[1] in {'int','date'} else [])} for name,details in FIELDS.items()},
        'return_bases': {'before_returns':'Sales and generic margin before linked returns.',
                         'sales_cohort':'Sales and generic margin after all linked returns observed through 2026-03-01, grouped on original sale date.',
                         'return_date':'Requires explicit event-grain SQL; query_retail refuses this basis.'},
        'aliases': ALIASES, 'measure_aliases': MEASURE_ALIASES,
        'scoped_playbooks': ['trend','growth','margin','scorecard','concentration'],
        'scoped_sql': {'relation':'scoped_sales', 'columns': SCOPED_SALES_COLUMNS, 'period_values':['current','comparison'], 'rules':'Use scoped_sales only, including within custom CTEs. Dates and filters are enforced. compare=true includes explicit comparison dates. Money is cents; quantity is sold units. Count orders/customer keys distinctly, excluding customer_key=0 for identified buyers. net_sales_cents is BEFORE returns; realized_net_sales_cents and merchandise_margin_cents are AFTER linked cohort returns.'},
        'scope_patch_rules': 'Filters upsert by field. filters=[] clears all. remove_filters removes selected fields. dimensions replaces grouping. Changed current dates clear stale comparison unless a new comparison is supplied. Dates can remain unset for explanations.',
        'limitations': ['AOV under a merchandise filter is selected merchandise value per matching order, not full-basket AOV.',
                       'Distinct orders and identified customers can overlap across product groups.',
                       'Region means selling-store region; use market_region for digital market attribution.',
                       'Customer segment is the dataset static descriptive label, not a recomputed behavioral segment.',
                       'query_scoped_sql enforces the active dates and filters through scoped_sales; metric formulas and joins still require review. Arbitrary unscoped SQL does not inherit that guarantee.'],
    }


# Actual flattened view columns, plus explicitly joined scope attributes.
SCOPED_SALES_COLUMNS = {
    c['name']: c['type'] for c in data.CATALOG['fact_sales_line']['columns']
}
SCOPED_SALES_COLUMNS.update({
    'calendar_date':'DATE', 'calendar_year':'INTEGER', 'calendar_month':'INTEGER',
    'retail_year':'INTEGER', 'retail_week':'INTEGER', 'retail_period':'INTEGER',
    'channel_key':'INTEGER', 'customer_key':'INTEGER', 'loyalty_key':'INTEGER',
    'selling_store_key':'INTEGER', 'market_store_key':'INTEGER', 'fulfillment_method_key':'INTEGER',
    'style_key':'INTEGER', 'style_name':'VARCHAR', 'brand_name':'VARCHAR',
    'category_name':'VARCHAR', 'department_name':'VARCHAR', 'division_name':'VARCHAR',
    'returned_units':'BIGINT', 'refund_net_cents':'BIGINT', 'realized_net_sales_cents':'BIGINT',
    'net_cost_of_goods_cents':'BIGINT', 'merchandise_margin_cents':'BIGINT',
})
BASE_SALES_COLUMN_NAMES = frozenset(SCOPED_SALES_COLUMNS)
SCOPED_SALES_COLUMNS.update({name: {'text':'VARCHAR','int':'BIGINT','bool':'BOOLEAN','date':'DATE'}[details[1]] for name,details in FIELDS.items() if name not in SCOPED_SALES_COLUMNS})
SCOPED_SALES_COLUMNS['period'] = 'VARCHAR'


def _validate_scoped_relations(sql, con):
    """Parse model SQL: all table access must come through the scoped relation.

    This is a relation-access guarantee, not a proof of aggregations or causal
    reasoning. CTEs and subqueries are allowed; direct warehouse tables, qualified
    relations, table functions, and shadowing scoped_sales are rejected.
    """
    statements = con.extract_statements(sql)
    if len(statements) != 1 or statements[0].type != data.duckdb.StatementType.SELECT:
        raise ValueError('Provide one read-only SELECT over scoped_sales.')
    parsed = json.loads(con.execute('SELECT json_serialize_sql(?)',[sql]).fetchone()[0])
    if parsed.get('error') or len(parsed.get('statements',[])) != 1:
        raise ValueError('Provide one parseable SELECT over scoped_sales.')
    seen = False
    def visit(value, inherited):
        nonlocal seen
        if isinstance(value,list):
            for child in value:
                visit(child, inherited)
            return
        if not isinstance(value,dict):
            return
        allowed = set(inherited)
        # A nonrecursive CTE cannot see itself or a later CTE. Otherwise an
        # identically named physical table could escape the scope boundary.
        for cte in value.get('cte_map',{}).get('map',[]):
            name = cte['key'].casefold()
            if name == 'scoped_sales':
                raise ValueError('Do not replace or shadow scoped_sales; it is the enforced analysis scope.')
            visit(cte['value'], allowed)
            allowed.add(name)
        if value.get('type') == 'TABLE_FUNCTION':
            raise ValueError('Scoped SQL must use scoped_sales or its CTEs; table functions can bypass the analysis scope and are not allowed.')
        if value.get('type') == 'RECURSIVE_CTE_NODE':
            raise ValueError('Recursive CTEs are not supported for scoped retail evidence.')
        if value.get('type') == 'BASE_TABLE':
            table = value.get('table_name','').casefold()
            if value.get('schema_name') or value.get('catalog_name') or table not in allowed:
                raise ValueError(f'Custom retail SQL cannot read {table!r} outside the active scope. Query scoped_sales instead; its available columns are listed in query_capabilities.')
            seen = seen or table == 'scoped_sales'
        for key, child in value.items():
            if key != 'cte_map':
                visit(child, allowed)
    visit(parsed, {'scoped_sales'})
    if not seen:
        raise ValueError('A measured custom query must read scoped_sales; constant-only SQL is not retail evidence.')


def query_scoped_sql(sql, scope, parameters=None, compare=False, limit=500):
    """Execute arbitrary SELECT analytics over an enforced, flattened sale scope.

    ``scoped_sales`` exposes original v_sales_after_returns columns plus all
    canonical dimension/filter fields and ``period``. Original line money and
    cohort return columns are both explicit; return_basis never renames columns.
    User SQL cannot access other warehouse relations. This limits dates/filters,
    not errors inside user aggregations (for example a self-join fan-out).
    """
    scope = normalize_scope(scope)
    dates = scope['dates']
    if not dates['start']:
        raise ValueError('Set start and end before a custom retail query.')
    if scope['return_basis']=='return_date':
        raise ValueError('scoped_sales uses original sales-date cohorts. Return-date event queries need their own explicit scope implementation; do not relabel cohort returns as calendar activity.')
    if not isinstance(compare,bool) or compare and not dates['compare_start']:
        raise ValueError('compare=true requires explicit comparison dates.')
    if not isinstance(sql,str) or not sql.strip() or len(sql)>24000:
        raise ValueError('Provide one scoped SELECT of at most 24,000 characters.')
    if parameters is None:
        parameters=[]
    if not isinstance(parameters,list) or len(parameters)>100:
        raise ValueError('Custom SQL parameters must be a list of at most 100 scalar values.')
    if any(not isinstance(v,(str,int,float,bool,type(None))) for v in parameters):
        raise ValueError('Custom SQL parameters must be scalar JSON values.')
    with data.warehouse_session() as con:
        _validate_scoped_relations(sql, con)
    selections = ['s.*'] + [f'{details[0]} AS {name}' for name,details in FIELDS.items() if name not in BASE_SALES_COLUMN_NAMES]
    if compare:
        selections.append("CASE WHEN s.calendar_date BETWEEN ? AND ? THEN 'current' ELSE 'comparison' END AS period")
        bound_values = [dates['start'], dates['end']]+[dates[k] for k in DATE_KEYS]
        where=['(s.calendar_date BETWEEN ? AND ? OR s.calendar_date BETWEEN ? AND ?)']
    else:
        selections.append("'current' AS period")
        bound_values = [dates['start'], dates['end']]
        where=['s.calendar_date BETWEEN ? AND ?']
    filters, filter_values = _predicates(scope)
    where += filters
    bound_values += filter_values
    base = 'SELECT '+',\n'.join(selections)+'\n'+JOIN_SQL+'\nWHERE '+' AND '.join(where)
    query = 'WITH scoped_sales AS (\n'+base+'\n)\nSELECT * FROM (\n'+sql.strip().rstrip(';')+'\n) AS scoped_result'
    result = data.select_sql(query, bound_values+parameters, limit)
    result.update(name='scoped_custom_query', requested_sql=sql, scope=scope,
                  scope_fingerprint=scope_fingerprint(scope), scope_enforced=True,
                  basis='Original sale date; complete matching merchandise lines; preaggregated linked returns through 2026-03-01.',
                  warnings=['Dates and filters are enforced through scoped_sales; custom metric formulas and join cardinality still require evidence review.',
                            'Original and return-adjusted cents columns are explicitly separate; use the requested return basis.',
                            'Distinct orders and identified buyers may overlap across product groups.'])
    return result
