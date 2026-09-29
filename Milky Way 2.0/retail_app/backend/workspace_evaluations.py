"""Persistent, bounded evaluation jobs kept separate from interactive chat.

Expected outcomes are server-side graders, never model instructions. Deterministic
contracts verify real runtime functions; they do not claim to assess live narrative
quality. Live runs require explicit billable consent and human semantic review.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory

from . import data, storage
from .runtime import JobCancelled, JobControl

FIXTURE_PATH = data.APP / 'knowledge/enterprise_evaluations.json'
MAX_CASES = 120
MAX_MODEL_CALLS = 40
MAX_TOKENS = 200000
MAX_QUEUED = 4
ACTIVE = {'queued', 'running', 'cancelling'}
_POOL = ThreadPoolExecutor(max_workers=1, thread_name_prefix='workspace-evaluation')
_LOCK = threading.RLock()
_CONTROLS = {}
_MISSING = object()
_SCHEMA = '''
CREATE TABLE IF NOT EXISTS workspace_evaluation_runs(
 id TEXT PRIMARY KEY, created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, status TEXT NOT NULL,
 payload TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS workspace_evaluation_status ON workspace_evaluation_runs(status);
'''
TYPES = {'scope', 'retrieval', 'query', 'chart', 'presentation', 'citations',
         'measured_values', 'comparison', 'playbook_contract', 'workspace_profile', 'workspace_skill', 'live_answer'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), default=str).encode()).hexdigest()


def _db():
    """Schema initialization stays inside the normal connection transaction."""
    return storage.connection()


def _store(run):
    encoded = json.dumps(run, default=str, allow_nan=False)
    if len(encoded.encode()) > 24 * 1024 * 1024:
        raise ValueError('Evaluation results exceeded the 24 MB run limit.')
    with _db() as con:
        con.executescript(_SCHEMA)
        con.execute('INSERT INTO workspace_evaluation_runs(id,status,payload) VALUES(?,?,?) '
                    'ON CONFLICT(id) DO UPDATE SET status=excluded.status,payload=excluded.payload,updated=CURRENT_TIMESTAMP',
                    (run['id'], run['status'], encoded))


def _read(run_id):
    with _db() as con:
        con.executescript(_SCHEMA)
        row = con.execute('SELECT payload,created,updated FROM workspace_evaluation_runs WHERE id=?', (run_id,)).fetchone()
    if not row:
        raise ValueError('Evaluation run not found.')
    value = json.loads(row['payload'])
    value.update(created=row['created'], updated=row['updated'])
    return value


def _public(run, include_results=True):
    value = copy.deepcopy(run)
    # Suites/snapshots are separately inspectable assets; never duplicate hidden
    # golden content into run outputs or a model-facing preview.
    for name in ('suite', 'baseline_snapshot', 'candidate_snapshot'):
        value.pop(name, None)
    if not include_results:
        value.pop('results', None)
    return value


def get_run(run_id):
    return _public(_read(run_id))


def list_runs():
    with _db() as con:
        con.executescript(_SCHEMA)
        rows = con.execute('SELECT payload,created,updated FROM workspace_evaluation_runs ORDER BY rowid DESC LIMIT 100').fetchall()
    return [_public({**json.loads(row['payload']), 'created': row['created'], 'updated': row['updated']}, False) for row in rows]


def _latest_live_runs(candidate_hash):
    """Release policy uses the entire candidate history, independently of the
    bounded recent-history list shown in the administrator UI.
    """
    with _db() as con:
        con.executescript(_SCHEMA)
        rows = con.execute('''SELECT r.id,r.status,
            json_extract(r.payload,'$.suite_id') AS suite_id,
            json_extract(r.payload,'$.summary') AS summary,
            json_extract(r.payload,'$.review') AS review
            FROM workspace_evaluation_runs r
            JOIN (SELECT max(rowid) AS latest_row FROM workspace_evaluation_runs
                  WHERE json_extract(payload,'$.mode')='live'
                    AND json_extract(payload,'$.candidate.snapshot_hash')=?
                  GROUP BY json_extract(payload,'$.suite_id')) latest
              ON r.rowid=latest.latest_row''', (candidate_hash,)).fetchall()
    return [{**dict(row), 'summary': json.loads(row['summary'] or '{}'),
             'review': json.loads(row['review'] or '{}')} for row in rows]


def recover_interrupted_runs():
    """Call once at process startup, before accepting new jobs."""
    recovered = 0
    with _db() as con:
        con.executescript(_SCHEMA)
        rows = con.execute("SELECT id,payload FROM workspace_evaluation_runs WHERE status IN ('queued','running','cancelling')").fetchall()
        for row in rows:
            run = json.loads(row['payload'])
            run.update(status='interrupted', error='Service restarted before this run completed. Start a new run to retry.')
            con.execute('UPDATE workspace_evaluation_runs SET status=?,payload=?,updated=CURRENT_TIMESTAMP WHERE id=?',
                        ('interrupted', json.dumps(run), row['id']))
            recovered += 1
    return recovered


def shutdown():
    with _LOCK:
        for control in _CONTROLS.values():
            control.cancel()


def validate_suite(content):
    errors = []
    cases = content.get('cases') if isinstance(content, dict) else None
    if not isinstance(cases, list) or not 1 <= len(cases) <= MAX_CASES:
        return ['A suite requires 1 to 120 concrete cases.']
    ids = set()
    for case in cases:
        if not isinstance(case, dict):
            errors.append('Each evaluation case must be an object.'); continue
        identity = case.get('id')
        if not isinstance(identity, str) or not identity or identity in ids:
            errors.append('Cases require unique nonempty IDs.')
        ids.add(str(identity))
        if not isinstance(case.get('question'), str) or not case['question'].strip() or len(case['question']) > 4000:
            errors.append(f'{identity}: provide a question of at most 4,000 characters.')
        if not isinstance(case.get('asset_ids', []), list) or any(not isinstance(value, str) for value in case.get('asset_ids', [])):
            errors.append(f'{identity}: asset_ids must be a list of related workspace asset IDs.')
        contract = case.get('contract', {})
        if not isinstance(contract, dict) or contract.get('type') not in TYPES:
            errors.append(f'{identity}: choose a supported runtime contract.'); continue
        if not isinstance(contract.get('inputs', {}), dict):
            errors.append(f'{identity}: contract inputs must be an object.')
        expected = case.get('expected', {})
        if not isinstance(expected, dict) or not expected:
            errors.append(f'{identity}: specify expected checks; unchecked cases cannot pass.')
        elif set(expected) - {'error_contains', 'equals', 'contains', 'not_contains', 'min_length', 'required_source_roles'}:
            errors.append(f'{identity}: unsupported expected check.')
        else:
            for key in ('equals', 'contains', 'not_contains', 'min_length'):
                if key in expected and not isinstance(expected[key], dict):
                    errors.append(f'{identity}: {key} must map output paths to expected values.')
            if 'error_contains' in expected and (not isinstance(expected['error_contains'], str) or not expected['error_contains'].strip()):
                errors.append(f'{identity}: expected rejection must name a nonempty error fragment.')
            if 'error_contains' in expected and len(expected) != 1:
                errors.append(f'{identity}: rejection cases must use error_contains alone; output checks need a separate successful case.')
            if isinstance(expected.get('min_length'), dict) and any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in expected['min_length'].values()):
                errors.append(f'{identity}: minimum lengths must be nonnegative integers.')
            if 'required_source_roles' in expected and (not isinstance(expected['required_source_roles'], list) or any(not isinstance(v, str) for v in expected['required_source_roles'])):
                errors.append(f'{identity}: source roles must be a list of names.')
            if not any(bool(expected.get(key)) for key in ('error_contains', 'equals', 'contains', 'not_contains', 'min_length', 'required_source_roles')):
                errors.append(f'{identity}: provide at least one nonempty implemented check.')
        if contract.get('type') == 'live_answer' and case.get('mode', 'live') != 'live':
            errors.append(f'{identity}: live_answer requires live mode.')
        if contract.get('type') != 'live_answer' and case.get('mode', 'deterministic') != 'deterministic':
            errors.append(f'{identity}: runtime contracts require deterministic mode.')
    if len(json.dumps(content).encode()) > 256 * 1024:
        errors.append('Evaluation suite exceeds 256 KB.')
    return errors


def seed_suite():
    return json.loads(FIXTURE_PATH.read_text())


def list_suites():
    from . import workspace_assets as registry
    snapshot = registry.active_snapshot()
    suites = []
    for asset in snapshot.get('assets', []):
        if asset.get('kind') != 'evaluation_suite':
            continue
        content = asset['content']
        suites.append({'id': asset['id'], 'name': asset['name'], 'version_id': asset['version_id'],
                       'case_count': len(content.get('cases', [])), 'content': content,
                       'categories': sorted({c.get('category', 'general') for c in content.get('cases', [])}),
                       'validation_errors': validate_suite(content)})
    if not suites:
        content = seed_suite()
        suites.append({'id': content['id'], 'name': content['name'], 'version_id': digest(content),
                       'case_count': len(content['cases']), 'content': content,
                       'categories': sorted({c['category'] for c in content['cases']}),
                       'validation_errors': validate_suite(content)})
    return suites


def _sources_fingerprint():
    from .context import INDEX
    files = {str(path.name): hashlib.sha256(path.read_bytes()).hexdigest()
             for path in Path(__file__).parent.glob('*.py')}
    stat = data.DB.stat() if data.DB.exists() else None
    warehouse = {'path': str(data.DB), 'size': stat.st_size if stat else None,
                 'mtime_ns': stat.st_mtime_ns if stat else None,
                 'identity_method': 'size and modification time; not a full warehouse content checksum'}
    return {'code_hash': digest(files), 'context_hash': digest(INDEX.documents),
            'warehouse': warehouse, 'warehouse_hash': digest(warehouse)}


def _path(value, path):
    for part in str(path).split('.') if path else []:
        if isinstance(value, dict):
            value = value.get(part, _MISSING)
        elif isinstance(value, list) and part.isdigit() and int(part) < len(value):
            value = value[int(part)]
        else:
            return _MISSING
    return value


def grade(output, expected, error=None):
    """Only implemented checks produce passes; empty/unknown checks fail closed."""
    checks = []
    def record(name, passed, detail):
        checks.append({'name': name, 'passed': bool(passed), 'detail': detail})
    if 'error_contains' in expected:
        wanted = str(expected['error_contains'])
        record('expected rejection', error is not None and wanted.casefold() in error.casefold(),
               'Runtime rejected the input as expected.' if error and wanted.casefold() in error.casefold() else f'Expected rejection containing {wanted!r}; observed {error!r}.')
    elif error:
        record('runtime execution', False, error)
    else:
        for path, wanted in expected.get('equals', {}).items():
            actual = _path(output, path)
            record(f'{path} equals', actual == wanted, f'Observed {str(actual)[:200]}; expected {str(wanted)[:200]}.')
        for kind in ('contains', 'not_contains'):
            for path, wanted in expected.get(kind, {}).items():
                found = _path(output, path)
                if found is _MISSING:
                    record(f'{path} {kind}', False, 'Required output path is missing.')
                    continue
                actual = json.dumps(found, default=str).casefold()
                words = wanted if isinstance(wanted, list) else [wanted]
                passed = all((str(word).casefold() in actual) == (kind == 'contains') for word in words)
                record(f'{path} {kind}', passed, f'Checked {len(words)} specified text or value patterns.')
        for path, minimum in expected.get('min_length', {}).items():
            actual = _path(output, path)
            record(f'{path} minimum length', isinstance(actual, (list, dict, str)) and len(actual) >= minimum,
                   f'Required at least {minimum} items or characters.')
        roles = {source.get('role') for source in output.get('sources', [])} if isinstance(output, dict) else set()
        if 'required_source_roles' in expected:
            wanted = set(expected['required_source_roles'])
            record('source roles', wanted <= roles, f'Required roles {sorted(wanted)}; observed {sorted(str(x) for x in roles)}.')
    if not checks:
        record('defined grading contract', False, 'No supported checks were specified.')
    return checks


def model_snapshot(snapshot):
    """Defense in depth: evaluation goldens cannot enter model input snapshots."""
    result = copy.deepcopy(snapshot)
    result['assets'] = [a for a in result.get('assets', []) if a.get('kind') not in {'evaluation_suite', 'evaluation_case'}]
    return result


def semantic_output(output):
    """Compare returned values, scope and answer shape independently of SQL text,
    timings, token usage and generated IDs. Source versions have their own diff.
    This is a structural comparison, not a semantic model judge.
    """
    if not isinstance(output, dict):
        return output
    result = {key: copy.deepcopy(value) for key, value in output.items()
              if key not in {'id', 'created', 'updated', 'trace', 'usage', 'workspace', 'context', 'sources', 'sql', 'parameters'}}
    if isinstance(result.get('presentation'), dict):
        result['presentation'].pop('generated_at', None)
    if isinstance(result.get('outputs'), list):
        result['outputs'] = [{key: value for key, value in item.items() if key not in {'sql', 'parameters', 'elapsed_ms', 'created'}}
                             if isinstance(item, dict) else item for item in result['outputs']]
    return result


def execute_contract(case, snapshot, control, live_budget=None):
    from . import scope, evidence, presentation
    contract = case['contract']; args = copy.deepcopy(contract.get('inputs', {})); kind = contract['type']
    control.check_cancelled()
    if kind == 'scope':
        return scope.normalize_scope(args.get('candidate', {}), args.get('previous'), args.get('dates'))
    if kind == 'retrieval':
        from .workspace_runtime import search
        hits = search(snapshot, args.get('query', case['question']), args.get('limit', 6))
        return {'sources': hits, 'text': '\n'.join(hit.get('text', '') for hit in hits)}
    if kind == 'workspace_profile':
        from .presentation import apply_output_profile
        profile = next((asset for asset in snapshot.get('assets', [])
                        if asset.get('kind') == 'output_profile' and asset['id'] == args['profile_id']), None)
        if not profile:
            raise ValueError('Output profile is absent from this snapshot.')
        return apply_output_profile(copy.deepcopy(args['payload']), profile['content'])
    if kind == 'workspace_skill':
        asset = next((asset for asset in snapshot.get('assets', [])
                      if asset.get('kind') == 'skill' and asset['id'] == args['skill_id']), None)
        if not asset:
            raise ValueError('Skill is absent from this snapshot.')
        from .workspace_assets import snapshot_context
        return snapshot_context(snapshot, args.get('question', case['question']))
    if kind == 'query':
        return data.select_sql(args['sql'], args.get('parameters'), args.get('limit', 50))
    if kind == 'chart':
        return presentation.validate_chart(args['spec'], args['evidence'])
    if kind == 'presentation':
        return presentation.validate_presentation(args['presentation'], args['evidence'])
    if kind == 'citations':
        answer, warnings = evidence.check_citations(args['answer'], args.get('evidence', []), args.get('sources', []))
        return {'answer': answer, 'warnings': warnings}
    if kind == 'measured_values':
        return {'text': evidence.bind_measured_values(args['text'], args['evidence'])}
    if kind == 'comparison':
        return evidence.comparison_from_evidence(args['arguments'], args['evidence'])
    if kind == 'playbook_contract':
        return presentation.get_contract(args['slug'])
    if kind == 'live_answer':
        from .agent import run_agent
        if live_budget is None:
            raise ValueError('Live execution requires an explicitly funded run budget.')
        # Temporary state includes memories, analyses and investigations. No global
        # STATE reassignment occurs; separate jobs retain independent ContextVars.
        with TemporaryDirectory(prefix='milkyway-evaluation-') as temporary:
            with storage.use_state(temporary):
                conversation_id = storage.create_conversation('Isolated evaluation')['id']
                if args.get('scope'):
                    from .investigations import update_session
                    update_session(conversation_id, {'scope': scope.normalize_scope(args['scope'], dates=args.get('dates', {})),
                                                     'ui_dates': args.get('dates', {})})
                return run_agent(case['question'], args.get('dates', {}), prior=args.get('prior'), notify=control,
                                 budget=live_budget, workspace_snapshot=model_snapshot(snapshot),
                                 output_profile_id=args.get('output_profile_id'), conversation_id=conversation_id)
    raise ValueError('Unsupported evaluation contract.')


def _side(case, snapshot, control, live_budget=None):
    started = time.monotonic(); output = {}; error = None
    try:
        with data.query_control(control):
            output = data.clean(execute_contract(case, snapshot, control, live_budget))
    except JobCancelled:
        raise
    except Exception as exc:
        error = str(exc)[:1000]
    checks = grade(output, case['expected'], error)
    if case['contract']['type'] == 'live_answer' and error is None:
        from .evidence import check_citations
        _, citation_warnings = check_citations(output.get('answer', ''), output.get('outputs', []), output.get('context', []))
        evidence_checks = output.get('evidence_checks') or {}
        recorded_warnings = [str(value) for value in output.get('warnings', [])]
        recorded_citations = [str(value) for value in evidence_checks.get('citation_warnings', [])
                              if 'reference' in str(value).casefold()]
        recorded_citations += [value for value in recorded_warnings if 'cited references that were not returned' in value.casefold()]
        sanitized_reference = bool(re.search(r'\[Unverified reference:', output.get('answer', ''), re.I))
        all_citation_warnings = list(dict.fromkeys(citation_warnings + recorded_citations))
        citations_pass = not all_citation_warnings and not sanitized_reference
        checks.append({'name': 'registered answer references', 'passed': citations_pass,
                       'detail': 'Every cited reference exists in this answer.' if citations_pass else
                       ' '.join(all_citation_warnings) or 'Answer contains a sanitized unverified reference.'})
        unverified_amounts = evidence_checks.get('unverified_amounts', [])
        currency_warnings = [value for value in recorded_warnings if value.startswith('Currency check:')]
        currency_pass = not unverified_amounts and not currency_warnings and '[unverified amount]' not in output.get('answer', '').casefold()
        checks.append({'name': 'measured monetary claims', 'passed': currency_pass,
                       'detail': 'No runtime monetary mismatch was recorded; semantic support still requires review.' if currency_pass else
                       'Runtime flagged unsupported monetary claims: ' + ', '.join(map(str, unverified_amounts)) + ' ' + ' '.join(currency_warnings)})
        actual_hash = output.get('workspace', {}).get('snapshot_hash')
        checks.append({'name': 'frozen answer provenance', 'passed': actual_hash == snapshot.get('snapshot_hash', snapshot.get('hash')),
                       'detail': 'Answer must retain the evaluated snapshot hash.'})
    passed = all(check['passed'] for check in checks)
    sources = output.get('context', output.get('sources', [])) if isinstance(output, dict) else []
    encoded = json.dumps(output)
    output_hash = digest(semantic_output(output))
    truncated = len(encoded.encode()) > 120000
    if truncated:
        # Keep summaries and checks, never truncate serialized JSON into invalid data.
        output = {'preview': encoded[:6000], 'omitted_large_result': True, 'sha256': output_hash}
    return {'status': 'passed' if passed else 'failed', 'output': output, 'output_hash': output_hash,
            'output_truncated': truncated, 'checks': checks,
            'failures': [check['detail'] for check in checks if not check['passed']],
            'sources': [{key: source.get(key) for key in ('source', 'source_id', 'line', 'role', 'sha256', 'source_hash', 'content_hash', 'version_id')}
                        for source in sources[:20] if isinstance(source, dict)],
            'elapsed_ms': round((time.monotonic() - started) * 1000)}


def compare_sides(baseline, candidate):
    return {'outcome_changed': baseline['status'] != candidate['status'],
            'output_changed': baseline['output_hash'] != candidate['output_hash'],
            'source_changed': baseline['sources'] != candidate['sources'],
            'regression': baseline['status'] == 'passed' and candidate['status'] != 'passed',
            'improvement': baseline['status'] != 'passed' and candidate['status'] == 'passed'}


def _summary(run):
    results = run['results']
    return {'baseline_passed': sum(r['baseline']['status'] == 'passed' for r in results),
            'candidate_passed': sum(r['candidate']['status'] == 'passed' for r in results),
            'hard_failures': sum(r['candidate']['status'] != 'passed' for r in results),
            'regressions': sum(r['diff']['regression'] for r in results),
            'improvements': sum(r['diff']['improvement'] for r in results),
            'semantic_review': 'pending' if run['mode'] == 'live' else 'not_tested',
            'checks_scope': 'Real runtime contracts; live answer quality is not tested.' if run['mode'] == 'deterministic' else 'Deterministic checks of live outputs; human semantic review required.'}


def _worker(run_id, state_dir):
    with storage.use_state(state_dir):
        with _LOCK:
            control = _CONTROLS[run_id]
        run = _read(run_id)
        try:
            control.check_cancelled()
            run['status'] = 'running'; _store(run)
            budget = {'calls': 0, 'evidence_count': 0, 'max_model_calls': run['limits']['max_model_calls'],
                      'max_total_tokens': run['limits']['max_tokens']}
            for case in run['suite']['cases']:
                if case['id'] not in run['case_ids']:
                    continue
                control.check_cancelled()
                if _sources_fingerprint() != run['provenance']:
                    raise ValueError('Warehouse, code or built-in context changed during this run. Start a new comparison.')
                pair = {}
                for side in ('baseline', 'candidate'):
                    control.check_cancelled()
                    if _sources_fingerprint() != run['provenance']:
                        raise ValueError('Evaluation inputs changed before a comparison side. Start a new run.')
                    # Reset agent content ledgers per side while carrying run-wide usage.
                    side_budget = {key: budget.get(key, 0) for key in ('requests', 'input_tokens', 'output_tokens', 'total_tokens', 'reserved_tokens')}
                    side_budget.update(calls=0, evidence_count=0, max_model_calls=budget['max_model_calls'], max_total_tokens=budget['max_total_tokens'])
                    try:
                        pair[side] = _side(case, run[side + '_snapshot'], control, side_budget if run['mode'] == 'live' else None)
                    finally:
                        for key in ('requests', 'input_tokens', 'output_tokens', 'total_tokens', 'reserved_tokens'):
                            budget[key] = side_budget.get(key, 0)
                        run['usage'] = {key: budget.get(key, 0) for key in ('requests', 'input_tokens', 'output_tokens', 'total_tokens', 'reserved_tokens')}
                    if _sources_fingerprint() != run['provenance']:
                        raise ValueError('Evaluation inputs changed during a comparison side. Start a new run.')
                run['results'].append({'case_id': case['id'], 'name': case.get('name', case['question']),
                                       'question': case['question'], 'category': case.get('category', 'general'), **pair,
                                       'diff': compare_sides(pair['baseline'], pair['candidate']),
                                       'review_status': 'pending' if run['mode'] == 'live' or case.get('requires_human_review') else 'not_required'})
                run['completed_cases'] = len(run['results']); run['summary'] = _summary(run)
                run['usage'] = {key: budget.get(key, 0) for key in ('requests', 'input_tokens', 'output_tokens', 'total_tokens', 'reserved_tokens')}
                _store(run)
            control.check_cancelled()
            run['status'] = 'completed'
        except JobCancelled:
            run.update(status='cancelled', error='Evaluation cancelled. Completed cases remain available.')
        except Exception as exc:
            run.update(status='failed', error=str(exc)[:1000])
        finally:
            run['summary'] = _summary(run)
            _store(run)
            with _LOCK:
                _CONTROLS.pop(run_id, None)


def start_run(suite_id, baseline_release_id=None, candidate_release_id=None, candidate_version_ids=None,
              mode='deterministic', max_cases=MAX_CASES, max_model_calls=0, max_tokens=0,
              confirm_billable=False, background=True):
    from . import workspace_assets as registry
    if mode not in {'deterministic', 'live'}:
        raise ValueError('Evaluation mode must be deterministic or live.')
    if isinstance(max_cases, bool) or not 1 <= max_cases <= MAX_CASES:
        raise ValueError('Run case limit must be between 1 and 120.')
    if not 0 <= max_model_calls <= MAX_MODEL_CALLS or not 0 <= max_tokens <= MAX_TOKENS:
        raise ValueError('Live run limits are at most 40 model calls and 200,000 tokens.')
    if mode == 'live':
        if not confirm_billable or max_model_calls < 2 or max_tokens < 2000:
            raise ValueError('Live comparison is billable. Explicitly confirm and provide at least 2 model calls and 2,000 tokens.')
        from .agent import configured
        if not configured():
            raise ValueError('Configure the model and API key before a live evaluation.')
    baseline = registry.capture_snapshot(release_id=baseline_release_id)
    candidate = registry.capture_snapshot(release_id=candidate_release_id, candidate_version_ids=candidate_version_ids)
    # Prefer the candidate suite so unpublished case edits can be tested before release.
    suite_asset = next((a for a in candidate.get('assets', []) if a['id'] == suite_id and a['kind'] == 'evaluation_suite'), None)
    suite_entry = ({'content': suite_asset['content'], 'version_id': suite_asset['version_id']} if suite_asset else
                   next((s for s in list_suites() if s['id'] == suite_id), None))
    if suite_entry is None:
        raise ValueError('Evaluation suite not found.')
    suite = copy.deepcopy(suite_entry['content'])
    errors = validate_suite(suite)
    if errors:
        raise ValueError(' '.join(errors[:8]))
    applicable = [c for c in suite['cases'] if c.get('mode', 'live' if c['contract']['type'] == 'live_answer' else 'deterministic') == mode]
    if not applicable:
        raise ValueError(f'This suite contains no {mode} cases. Add cases for this mode first.')
    selected = applicable[:max_cases]
    changed_assets = [a for a in candidate.get('assets', []) if a.get('kind') != 'evaluation_suite'
                      and baseline.get('asset_versions', {}).get(a['id']) != a.get('version_id')]
    declared = {identity for case in selected for identity in case.get('asset_ids', [])}
    for case in selected:
        args = case['contract'].get('inputs', {})
        declared.update(str(args[key]) for key in ('profile_id', 'skill_id') if args.get(key))
    coverage = {'changed_assets': [{'id': a['id'], 'name': a['name'], 'kind': a['kind'], 'version_id': a['version_id']} for a in changed_assets],
                'declared_asset_ids': sorted(declared),
                'uncovered_assets': [a['id'] for a in changed_assets if a['id'] not in declared],
                'note': 'Case-to-asset coverage is declared by authors, not proof of semantic quality. Operator review must assess applicability and any uncovered assets.'}
    identity = str(uuid.uuid4())
    with _LOCK:
        if len(_CONTROLS) >= MAX_QUEUED:
            raise ValueError('The evaluation queue is full (one worker and three waiting runs).')
        run = {'id': identity, 'status': 'queued', 'suite_id': suite_id, 'suite_version_id': suite_entry['version_id'],
               'suite_hash': digest(suite), 'suite': suite, 'mode': mode, 'case_ids': [c['id'] for c in selected],
               'total_cases': len(selected), 'applicable_case_count': len(applicable), 'completed_cases': 0,
               'limits': {'max_cases': max_cases, 'max_model_calls': max_model_calls, 'max_tokens': max_tokens},
               'billable_consent': bool(confirm_billable) if mode == 'live' else False,
               'baseline_snapshot': copy.deepcopy(baseline), 'candidate_snapshot': copy.deepcopy(candidate),
               'baseline': {'release_id': baseline.get('release_id'), 'snapshot_hash': baseline.get('snapshot_hash', baseline.get('hash'))},
               'candidate': {'release_id': candidate.get('release_id'), 'snapshot_hash': candidate.get('snapshot_hash', candidate.get('hash'))},
               'provenance': _sources_fingerprint(), 'model': __import__('os').getenv('OPENAI_MODEL') if mode == 'live' else None,
               'grading_version': 'runtime-contracts-v1', 'results': [], 'summary': {}, 'coverage': coverage,
               'review': {'status': 'pending', 'semantic_quality': 'unreviewed' if mode == 'live' else 'not_tested'}}
        run['summary'] = _summary(run)
        _store(run)
        _CONTROLS[identity] = JobControl(lambda message: None, timeout=900)
        state_dir = storage.state_directory()
        if background:
            _POOL.submit(_worker, identity, state_dir)
    if not background:
        _worker(identity, state_dir)
    return get_run(identity)


def cancel_run(run_id):
    with _LOCK:
        run = _read(run_id)
        if run['status'] not in ACTIVE:
            return _public(run)
        control = _CONTROLS.get(run_id)
        if control:
            control.cancel()
            # Only request cancellation here. The worker owns durable progress and
            # completion, avoiding stale read/overwrite races on case results.
        else:
            run.update(status='interrupted', error='No worker remains for this run; start a new run.')
            _store(run)
    value = get_run(run_id)
    if control and value['status'] in ACTIVE:
        value['status'] = 'cancelling'
    return value


def review_run(run_id, reviewer, decision, notes):
    if not reviewer.strip() or not notes.strip() or decision not in {'approved', 'rejected'}:
        raise ValueError('Review requires an operator name, approved/rejected decision and review notes.')
    with _LOCK:
        run = _read(run_id)
        if run['status'] != 'completed':
            raise ValueError('Complete the run before recording review.')
        if decision == 'approved' and run['summary']['hard_failures']:
            raise ValueError('Hard failures cannot be overridden by a review approval.')
        run['review'] = {'status': decision, 'reviewer': reviewer[:120], 'notes': notes[:4000],
                         'recorded_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                         'applicability_review': 'operator_reviewed',
                         'coverage_gaps_acknowledged': run.get('coverage', {}).get('uncovered_assets', []),
                         'semantic_quality': 'human_reviewed' if run['mode'] == 'live' else 'not_tested'}
        for result in run['results']:
            if result['review_status'] == 'pending':
                result['review_status'] = decision
        _store(run)
    return _public(run)


def publication_gate(run_id, candidate_snapshot):
    errors = []
    if not run_id:
        return {'passed': False, 'errors': ['Run the full deterministic evaluation suite on this candidate before publishing.'], 'run_id': None}
    run = _read(run_id)
    if run['status'] != 'completed': errors.append('Evaluation run must be completed.')
    if run['mode'] != 'deterministic': errors.append('A deterministic runtime suite is required; live grading alone cannot authorize release.')
    # A user-created one-case suite is useful for iteration but cannot replace the
    # documented foundation. Its core contracts and expectations must stay intact.
    core_cases = {case['id']: case for case in seed_suite()['cases']}
    executed = {case['id']: case for case in run['suite']['cases'] if case['id'] in run['case_ids']}
    if any(identity not in executed or digest(executed[identity]['contract']) != digest(case['contract'])
           or digest(executed[identity]['expected']) != digest(case['expected'])
           for identity, case in core_cases.items()):
        errors.append('Run the complete bundled Enterprise runtime contracts suite; custom checks supplement the core release checks.')
    if run['candidate']['snapshot_hash'] != candidate_snapshot.get('snapshot_hash', candidate_snapshot.get('hash')):
        errors.append('Evaluation candidate differs from this release. Run the suite again.')
    if run['completed_cases'] != run['applicable_case_count'] or run['total_cases'] != run['applicable_case_count']:
        errors.append('All applicable suite cases must run; a sampled run cannot authorize release.')
    if not run['completed_cases'] or run['summary'].get('hard_failures', 1): errors.append('Candidate has missing or failed deterministic checks.')
    if run['review'].get('status') != 'approved': errors.append('An operator must approve the run after reviewing checks and coverage applicability.')
    if run['provenance'] != _sources_fingerprint(): errors.append('Code, context or warehouse changed after evaluation.')
    # Live grading is optional. Once used for this candidate it is visible release
    # evidence: a failed or unreviewed live result cannot be silently ignored.
    candidate_hash = run['candidate']['snapshot_hash']
    live_runs = _latest_live_runs(candidate_hash)
    for other in live_runs:
        if other['status'] != 'completed' or other['summary'].get('hard_failures', 1) or other['review'].get('status') != 'approved':
            errors.append('Live suite ' + other['suite_id'] + ' requires a completed passing run and explicit human approval.')
    return {'passed': not errors, 'errors': errors, 'run_id': run_id,
            'live_answer_quality': 'checked' if live_runs else 'not_tested',
            'semantic_review': 'human_review_required_or_recorded' if live_runs else 'not_tested',
            'scope': 'Deterministic runtime contracts only; this gate does not certify narrative quality.'}
