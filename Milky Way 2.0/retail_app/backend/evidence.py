"""Deterministic evidence references and bounded model context."""
import json
import math
import re
from decimal import Decimal


def check_citations(answer, evidence, sources=()):
    valid = {e['evidence_id'] for e in evidence if e.get('evidence_id')}
    valid.update(s['source_id'] for s in sources if s.get('source_id'))
    missing = set()
    def replace(match):
        ids = re.findall(r'\b[ED]\d+\b', match.group())
        unknown = set(ids) - valid
        missing.update(unknown)
        return '[Unverified reference: ' + ', '.join(ids) + ']' if unknown else match.group()
    answer = re.sub(r'\[[ED]\d+(?:\s*[,;]\s*[ED]?\d+)*\]', replace, answer)
    warnings = []
    if missing:
        warnings.append('The answer cited references that were not returned: ' + ', '.join(sorted(missing)) + '. These are marked unverified; do not treat them as supporting evidence.')
    return answer, warnings


def comparison_from_evidence(arguments, evidence):
    """Arithmetic may reference measured cells, never promote supplied numbers."""
    if 'current' in arguments or 'comparison' in arguments:
        raise ValueError('Reference measured evidence IDs, row indices and column names instead of supplying numbers.')
    values = []
    source_ids = []
    for side in ('current', 'comparison'):
        identity = arguments[side + '_evidence_id']
        source = next((e for e in evidence if e.get('evidence_id') == identity), None)
        row = arguments.get(side + '_row', 0)
        if source is None or not isinstance(row, int) or isinstance(row, bool) or not 0 <= row < len(source['rows']):
            raise ValueError('Choose an existing evidence ID and a valid zero-based row.')
        value = source['rows'][row].get(arguments[side + '_column'])
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError('Both selected evidence cells must contain finite numbers.')
        values.append(Decimal(str(value)))
        source_ids.append(identity)
    current, comparison = values
    money_unit = arguments['current_column'].endswith('_cents') and arguments['comparison_column'].endswith('_cents')
    return {**({'current_cents':float(current),'comparison_cents':float(comparison),'change_cents':float(current-comparison)} if money_unit else {}), 'current': float(current), 'comparison': float(comparison),
            'change': float(current - comparison),
            'change_pct': float(100 * (current - comparison) / comparison) if comparison else None,
            'source_evidence_ids': list(dict.fromkeys(source_ids)),
            'basis': 'Arithmetic on the referenced cells; matching units and metric definitions still require review.'}


def bounded_history(prior, limit=12000):
    """Preserve recent complete messages, including late corrections, first."""
    if not prior:
        return {}
    messages = prior.get('messages') if isinstance(prior, dict) else None
    if messages is None:
        return {'previous_question': prior.get('question', ''),
                'previous_answer': str(prior.get('answer', ''))[-8000:],
                'last_period': prior.get('period')} if isinstance(prior, dict) else {}
    selected = []; used = 0
    for message in reversed(messages[-12:]):
        item = {'role': message.get('role', 'user'), 'content': str(message.get('content', ''))}
        if len(item['content']) > 8000:
            item['content'] = '[Earlier text omitted] ' + item['content'][-8000:]
        size = len(json.dumps(item))
        if used + size > limit:
            break
        selected.append(item); used += size
    return {'messages': list(reversed(selected)), 'last_period': prior.get('last_period'),
            'earlier_messages_omitted': len(selected) < len(messages)}


def model_preview(value, row_limit=20):
    """Trim structured previews without cutting serialized JSON in the middle."""
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if key == 'rows' and isinstance(item, list):
                result[key] = [model_preview(row, row_limit) for row in item[:row_limit]]
                if len(item) > row_limit:
                    result['model_preview_truncated'] = True
                    result['full_result_row_count'] = len(item)
            else:
                result[key] = model_preview(item, row_limit)
        return result
    if isinstance(value, list):
        return [model_preview(item, row_limit) for item in value[:50]]
    if isinstance(value, str) and len(value) > 6000:
        return value[:6000] + ' [preview truncated]'
    return value


def register_sources(budget, sources):
    ledger = budget.setdefault('sources', [])
    found = []
    for source in sources:
        existing = next((s for s in ledger if (s['source'], s['line']) == (source['source'], source['line'])), None)
        if existing is None:
            existing = {**source, 'source_id': 'D' + str(len(ledger) + 1)}
            ledger.append(existing)
        found.append(existing)
    return found


def bind_measured_values(value, evidence):
    """Render explicit cell references deterministically, including cents-to-USD."""
    if isinstance(value,list):return [bind_measured_values(v,evidence) for v in value]
    if not isinstance(value,str):return value
    def replace(match):
        identity,index,column,suffix=match.groups()
        suffix=suffix or ''
        source=next((e for e in evidence if e.get('evidence_id')==identity),None)
        if source is None or int(index)>=len(source.get('rows',[])):
            raise ValueError('Measured-value token references an unavailable evidence row.')
        measured=source['rows'][int(index)].get(column)
        if isinstance(measured,bool) or not isinstance(measured,(int,float)) or not math.isfinite(measured):
            raise ValueError('Measured-value tokens must reference finite numeric cells.')
        if column.endswith('_cents'):
            suffix='' if suffix.strip().lower() in ('cents','usd','dollars') else suffix
            return f'${measured/100:,.2f}'+suffix
        if column.endswith(('_pct','_percent')):
            suffix='' if suffix.strip().lower() in ('%','percent') else suffix
            return f'{measured:,.2f}%'+suffix
        formatted=f'{measured:,.0f}' if measured==int(measured) else f'{measured:,.4f}'.rstrip('0').rstrip('.')
        return formatted+suffix
    return re.sub(r'\{\{(E\d+):(\d+):([A-Za-z_][A-Za-z0-9_]*)\}\}([ \t]*(?:%|cents\b|USD\b|dollars\b|percent\b))?',replace,value,flags=re.I)
