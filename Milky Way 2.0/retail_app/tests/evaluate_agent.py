"""Manually run billable, evidence-based agent regressions.

List cases without credentials, imports of the app, model calls or report writes:
    python -m retail_app.tests.evaluate_agent --list
Run explicitly with the existing server configuration (incurs OpenAI API usage):
    python -m retail_app.tests.evaluate_agent --live
    python -m retail_app.tests.evaluate_agent --live --case explicit_date_override

Reports are private local files in ignored retail_app/state/evaluation/<run>.json.
Temporary application state prevents changing saved chats or learned conventions.
Automated checks compare measured result values, not SQL strings or answer prose.
Every case still requires manual narrative, metric, lineage and semantic review.
"""
import argparse
from collections import Counter
import datetime as dt
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
import re
import tempfile
import time
import uuid


APP = Path(__file__).resolve().parents[1]
CASES_PATH = Path(__file__).with_name('golden_questions.json')
FACT_SOURCES = {'fact_transaction', 'fact_sales_line', 'v_sales',
                'v_sales_after_returns', 'v_merchandise_activity'}
MONEY_TOLERANCE_CENTS = Decimal('0.5')  # less than one stored cent


def cited_references(answer):
    """Recognize individual and comma/semicolon-grouped evidence/source IDs."""
    found = set()
    for group in re.findall(r'\[[ED]\d+(?:\s*[,;]\s*[ED]?\d+)*\]', answer):
        prefix = None
        for part in re.split(r'\s*[,;]\s*', group[1:-1]):
            if part[0] in 'ED':
                prefix, digits = part[0], part[1:]
            else:
                digits = part
            found.add(prefix + digits)
    return found


def parsed_source_tables(connection, sql):
    """Find referenced base tables/views in the parser AST without binding views.

    CTE labels are resolved to their definitions only when used. Unused CTEs,
    string literals and comments cannot confer warehouse provenance. A CTE
    named like a warehouse fact does not itself count as that fact. Qualified
    physical references (main.fact_transaction) remain distinct from CTE names.
    This is a source-presence gate, not a proof of expression-level lineage.
    """
    parsed = json.loads(connection.execute('SELECT json_serialize_sql(?)', [sql]).fetchone()[0])
    if parsed.get('error') or len(parsed.get('statements', [])) != 1:
        raise ValueError('Evidence must contain one parseable SELECT statement.')
    sources = set()

    def walk(value, scope, active):
        if isinstance(value, list):
            for child in value:
                walk(child, scope, active)
            return
        if not isinstance(value, dict):
            return
        if 'cte_map' in value:
            local_scope = dict(scope)
            for entry in value['cte_map'].get('map', []):
                local_scope[entry['key'].lower()] = (entry['value']['query'], local_scope)
            for key, child in value.items():
                if key != 'cte_map':
                    walk(child, local_scope, active)
            return
        if value.get('type') == 'BASE_TABLE':
            table = value['table_name'].lower()
            qualified = bool(value.get('schema_name') or value.get('catalog_name'))
            if table in scope and not qualified:
                query, cte_scope = scope[table]
                identity = id(query)
                if identity not in active:
                    walk(query, cte_scope, active | {identity})
            else:
                sources.add(table)
            return
        for child in value.values():
            walk(child, scope, active)

    walk(parsed['statements'][0]['node'], {}, set())
    return sources


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        return None
    try:
        result = Decimal(str(value))
        return result if result.is_finite() else None
    except InvalidOperation:
        return None


def metric_match(row, expected, kind):
    """Accept varied meaningful aliases; never extract numbers from answer text."""
    for name, value in row.items():
        label = name.lower()
        actual = number(value)
        if actual is None:
            continue
        if kind == 'money_cents':
            if not re.search(r'sales|revenue', label):
                continue
            if re.search(r'gross|tax|shipping|discount|refund|margin|cost|percent|pct|average|avg|aov', label):
                continue
            if 'cent' in label:
                normalized, unit = actual, 'cents'
            elif re.search(r'usd|dollar', label):
                normalized, unit = actual * 100, 'USD'
            else:
                continue  # an unlabeled monetary field needs human unit review
            tolerance = MONEY_TOLERANCE_CENTS
        else:
            vocabulary = r'orders|order_count|transactions|transaction_count|receipts' if kind == 'orders' else r'units|quantity'
            if not re.search(vocabulary, label) or re.search(r'avg|average|per_|return|refund|pct|percent', label):
                continue
            normalized, unit, tolerance = actual, kind, Decimal(0)
        if abs(normalized - Decimal(str(expected))) <= tolerance:
            return {'column': name, 'observed': str(actual), 'observed_unit': unit,
                    'normalized': str(normalized), 'expected': str(expected),
                    'absolute_tolerance': str(tolerance)}
    return None


def build_prior(case, scope):
    if not case.get('prior_messages'):
        return None
    messages = [dict(message) for message in case['prior_messages']]
    padding = case.get('prior_padding')
    if padding:
        messages[padding['message_index']]['content'] *= padding['repeat']
    return {'messages': messages, 'last_period': scope}


def row_set(rows):
    return Counter(json.dumps(row, sort_keys=True, default=str) for row in rows)


def inspect_evidence(result, data):
    """Replay bounded fact-backed queries so answer-only magic numbers cannot pass.

    Table references are a provenance gate, not a semantic SQL/lineage proof.
    Golden grading compares returned values; it does not require a SQL template.
    """
    verified, diagnostics = [], []
    cited = cited_references(result.get('answer', ''))
    for output in result.get('outputs', []):
        identity = output.get('evidence_id')
        if (not identity or not output.get('sql') or output.get('calculation')
                or output.get('name') == 'dataset_inspection'):
            continue
        try:
            with data.connect() as connection:
                sources = parsed_source_tables(connection, output['sql'])
            if not (sources & FACT_SOURCES):
                continue
            replay = data.select_sql(output['sql'], output.get('parameters') or [], limit=500)
            exact = row_set(output.get('rows', [])) == row_set(replay['rows'])
            diagnostic = {'evidence_id': identity, 'source_tables': sorted(sources),
                          'replayed_values_match': exact, 'cited_in_answer': identity in cited,
                          'complete_result': not output.get('truncated') and not replay['truncated']}
            diagnostics.append(diagnostic)
            if exact and diagnostic['complete_result']:
                verified.append({**diagnostic, 'rows': replay['rows']})
        except Exception as exc:
            # The exception type is useful without echoing possibly sensitive payloads.
            diagnostics.append({'evidence_id': identity, 'replay_error_type': type(exc).__name__})
    return verified, diagnostics


def grade(case, result, golden, data):
    answer = result.get('answer', '')
    ids = {out.get('evidence_id') for out in result.get('outputs', [])}
    source_ids = {source.get('source_id') for source in result.get('context', [])}
    cited = cited_references(answer)
    checks = {'answer_present': bool(answer.strip()),
              'unknown_evidence_ids': sorted(reference for reference in cited if reference.startswith('E') and reference not in ids),
              'unknown_document_ids': sorted(reference for reference in cited if reference.startswith('D') and reference not in source_ids),
              'unverified_reference_marker_absent': '[Unverified reference:' not in answer}
    verified, replay = inspect_evidence(result, data)
    matches = None
    if case['metrics']:
        # All requested totals must coexist in one complete, replayed evidence row.
        for output in verified:
            for row in output['rows']:
                measured = {metric: metric_match(row, golden[metric], kind)
                            for metric, kind in case['metrics'].items()}
                if all(measured.values()) and output['cited_in_answer']:
                    matches = {'evidence_id': output['evidence_id'], 'metrics': measured}
                    break
            if matches:
                break
        checks['golden_metrics_in_cited_replayed_row'] = matches is not None
    structural_pass = (checks['answer_present'] and not checks['unknown_evidence_ids'] and not checks['unknown_document_ids']
                       and checks['unverified_reference_marker_absent'])
    return {
        'automated_checks_passed': structural_pass and (bool(matches) if case['metrics'] else True),
        'automatic_scope': 'Structural and independent numeric-result checks only; no automated semantic or causal approval.',
        'checks': checks, 'metric_matches': matches, 'evidence_replay': replay,
        'manual_review': {'status': 'required', 'criteria': case['manual_review'],
                          'note': 'For causal_gap_abstention, only response/citation structure is checked automatically; a human must assess abstention and causal claims.'
                          if not case['metrics'] else 'Verify scope, joins, units, narrative claims and citations. Numeric coincidence is not semantic proof.'}
    }


def redact(value):
    """Defense in depth: never persist the configured credential or key-shaped text."""
    if isinstance(value, dict):
        return {key: redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        key = os.environ.get('OPENAI_API_KEY')
        if key:
            value = value.replace(key, '[redacted]')
        return re.sub(r'\bsk-(?:proj-)?[A-Za-z0-9_-]{12,}', '[redacted]', value)
    return value


def save_report(report):
    directory = APP / 'state' / 'evaluation'
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = directory / (report['run_id'] + '.json')
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
        json.dump(redact(report), stream, indent=2, default=str, allow_nan=False)
        stream.write('\n')
    return path


def main(argv=None):
    specification = json.loads(CASES_PATH.read_text())
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--live', action='store_true', help='Explicitly permit billable OpenAI calls.')
    parser.add_argument('--list', action='store_true', help='List cases; never call the model or write a report.')
    parser.add_argument('--case', action='append', choices=[case['id'] for case in specification['cases']], help='Run selected cases; repeat for more than one.')
    args = parser.parse_args(argv)
    selected = [case for case in specification['cases'] if not args.case or case['id'] in args.case]
    if args.list or not args.live:
        for case in selected:
            print(case['id'] + ': ' + case['question'])
        print('No API calls or reports written. Add --live to run billable evaluations.')
        return 0

    run_id = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:10]
    report = {'run_id': run_id, 'suite_version': specification['version'],
              'started_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'cases': [],
              'live_calls_explicitly_requested': True, 'isolated_application_state': True,
              'money_tolerance_cents': str(MONEY_TOLERANCE_CENTS),
              'count_tolerance': 0, 'manual_semantic_review_required': True,
              'release_approved': False,
              'limitations': ['Five narrow scenarios are not a broad accuracy benchmark.',
                             'Currency columns must label cents or USD; ambiguous units fail automated matching.',
                             'Golden values are never included in the agent prompt.',
                             'A numeric result match and query replay cannot prove correct reasoning, lineage or causality.']}
    old_state = os.environ.get('RETAIL_STATE_DIR')
    try:
        with tempfile.TemporaryDirectory(prefix='retail-agent-evaluation-') as isolated:
            os.environ['RETAIL_STATE_DIR'] = isolated
            # This imports the allowlisted .env loader after isolating state. No secret is printed.
            from retail_app.backend import agent, data
            from retail_app.backend.runtime import JobControl
            if not agent.configured():
                print('Model configuration is missing. Configure OPENAI_API_KEY and OPENAI_MODEL locally; no API calls made.')
                return 2
            report['model'] = os.environ.get('OPENAI_MODEL')
            scope = specification['ui_scope']
            dates = data.dates_for(**scope)
            for case in selected:
                print('Running ' + case['id'] + ' (billable).', flush=True)
                started = time.monotonic()
                record = {'id': case['id'], 'question': case['question'], 'ui_scope': scope}
                try:
                    golden = data.select_sql(case['golden_sql'])['rows'][0] if case.get('golden_sql') else {}
                    question = case['question'] + (' ' + specification['evidence_request'] if case['metrics'] else '')
                    result = agent.run_agent(question, dates, prior=build_prior(case, scope), notify=JobControl(lambda _: None))
                    record.update(golden_sql=case.get('golden_sql'), golden_result=golden,
                                  grading=grade(case, result, golden, data), result=result)
                    print(case['id'] + ': automated checks ' + ('passed' if record['grading']['automated_checks_passed'] else 'failed') + '; manual review required.', flush=True)
                except Exception as exc:
                    record.update(error_type=type(exc).__name__,
                                  error='Evaluation did not complete. Inspect model configuration, provider status and bounded runtime settings.',
                                  grading={'automated_checks_passed': False, 'manual_review': {'status': 'required'}})
                    print(case['id'] + ': did not complete (' + type(exc).__name__ + ').', flush=True)
                record['elapsed_seconds'] = round(time.monotonic() - started, 2)
                report['cases'].append(record)
    finally:
        if old_state is None:
            os.environ.pop('RETAIL_STATE_DIR', None)
        else:
            os.environ['RETAIL_STATE_DIR'] = old_state
    report['automated_checks_passed'] = bool(report['cases']) and all(case['grading']['automated_checks_passed'] for case in report['cases'])
    report['finished_utc'] = dt.datetime.now(dt.timezone.utc).isoformat()
    path = save_report(report)
    print('Private local report: ' + str(path))
    print('This run does not approve production release; complete the manual criteria in the report.')
    return 0 if report['automated_checks_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
