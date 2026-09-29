"""Durable conversational scope and versioned, evidence-backed investigations.

This module deliberately has no model or warehouse access. The agent supplies actual
tool results, and declared numeric criteria determine descriptive verdicts. SQLite
transactions and revision checks prevent an older run overwriting a user's edit.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
import json
import math
import operator
import uuid

from . import storage


SCHEMA = '''
CREATE TABLE IF NOT EXISTS retail_sessions (
 conversation_id TEXT PRIMARY KEY, payload TEXT NOT NULL, updated TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS retail_investigations (
 id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL, payload TEXT NOT NULL,
 revision INTEGER NOT NULL, updated TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS retail_investigations_chat ON retail_investigations(conversation_id);
CREATE TABLE IF NOT EXISTS retail_investigation_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, investigation_id TEXT NOT NULL,
 revision INTEGER NOT NULL, action TEXT NOT NULL, snapshot TEXT NOT NULL, created TEXT NOT NULL,
 UNIQUE(investigation_id,revision));
CREATE TABLE IF NOT EXISTS retail_hypothesis_tests (
 id TEXT PRIMARY KEY, investigation_id TEXT NOT NULL, node_id TEXT NOT NULL,
 investigation_revision INTEGER NOT NULL, payload TEXT NOT NULL, created TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS retail_hypothesis_tests_investigation ON retail_hypothesis_tests(investigation_id);
'''
VERDICTS = {'supported_descriptively', 'contradicted', 'inconclusive', 'data_missing'}
NODE_STATUSES = {'planned', 'testing', 'tested', 'stale', 'excluded'}
INVESTIGATION_STATUSES = {'active', 'complete', 'incomplete', 'paused', 'superseded'}
NODE_FIELDS = {'id', 'parent_id', 'statement', 'test', 'falsifier', 'kind', 'scope',
               'criterion', 'status', 'notes', 'overlaps_with', 'partition_dimension'}
OPERATORS = {'gt': operator.gt, 'gte': operator.ge, 'lt': operator.lt,
             'lte': operator.le, 'eq': operator.eq, 'ne': operator.ne}


class RevisionConflict(ValueError):
    """The caller based its mutation on a superseded investigation version."""


def _now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


def _json(value, limit=4 * 1024 * 1024):
    try:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError('Investigation values must be finite JSON data.') from exc
    if len(text.encode('utf-8')) > limit:
        raise ValueError('Investigation data is too large. Narrow the evidence.')
    return text


def _copy(value):
    return json.loads(_json(value))


def _text(value, name, limit=12000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f'{name} must be nonempty text of at most {limit} characters.')
    return value.strip()


def _scope(value):
    if not isinstance(value, dict):
        raise ValueError('Scope must be an object with explicit dates and filters.')
    return json.loads(_json(value, 32000))


@contextmanager
def _connection(write=False):
    with storage.connection() as con:
        con.executescript(SCHEMA)
        if write:
            con.execute('BEGIN IMMEDIATE')
        yield con


def _conversation(con, identity):
    if not con.execute('SELECT 1 FROM conversations WHERE id=?', (identity,)).fetchone():
        raise ValueError('Conversation not found.')


def _session(con, identity):
    _conversation(con, identity)
    row = con.execute('SELECT payload FROM retail_sessions WHERE conversation_id=?', (identity,)).fetchone()
    return json.loads(row['payload']) if row else {
        'conversation_id': identity, 'scope': {}, 'summary': '', 'preferences': {},
        'investigation_id': None, 'ui_dates': {}, 'revision': 0,
    }


def _save_session(con, session):
    session['updated'] = _now()
    session['revision'] = session.get('revision', 0) + 1
    con.execute('INSERT INTO retail_sessions(conversation_id,payload,updated) VALUES(?,?,?) '
                'ON CONFLICT(conversation_id) DO UPDATE SET payload=excluded.payload,updated=excluded.updated',
                (session['conversation_id'], _json(session, 64000), session['updated']))
    return session


def get_session(conversation_id):
    with _connection() as con:
        return _session(con, conversation_id)


def _load(con, identity):
    row = con.execute('SELECT payload FROM retail_investigations WHERE id=?', (identity,)).fetchone()
    if not row:
        raise ValueError('Investigation not found.')
    result = json.loads(row['payload'])
    _conversation(con, result['conversation_id'])
    return result


def _check_revision(snapshot, expected_revision):
    if expected_revision is not None:
        if isinstance(expected_revision, bool) or not isinstance(expected_revision, int):
            raise ValueError('Expected revision must be an integer.')
        if snapshot['revision'] != expected_revision:
            raise RevisionConflict('The investigation changed. Reload its latest revision before continuing.')
    if snapshot['status'] == 'superseded':
        raise RevisionConflict('A newer investigation replaced this one. Continue the current investigation.')


def _persist(con, snapshot, action):
    snapshot['updated'] = _now()
    encoded = _json(snapshot)
    con.execute('INSERT INTO retail_investigations(id,conversation_id,payload,revision,updated) VALUES(?,?,?,?,?) '
                'ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,revision=excluded.revision,updated=excluded.updated',
                (snapshot['id'], snapshot['conversation_id'], encoded, snapshot['revision'], snapshot['updated']))
    con.execute('INSERT INTO retail_investigation_events(investigation_id,revision,action,snapshot,created) VALUES(?,?,?,?,?)',
                (snapshot['id'], snapshot['revision'], action, encoded, snapshot['updated']))
    return snapshot


def _snapshot(con, snapshot):
    # Test snapshots are immutable separate rows. Edits never rewrite old evidence.
    result = _copy(snapshot)
    histories = {node['id']: [] for node in result['hypotheses']}
    for row in con.execute('SELECT payload FROM retail_hypothesis_tests WHERE investigation_id=? ORDER BY rowid', (result['id'],)):
        test = json.loads(row['payload'])
        node = next((n for n in result['hypotheses'] if n['id'] == test['node_id']), None)
        test['superseded'] = not node or test['id'] != node.get('latest_test_id') or node['status'] != 'tested'
        histories.setdefault(test['node_id'], []).append(test)
    for node in result['hypotheses']:
        node['test_history'] = histories[node['id']]
    return result


def get_investigation(identity):
    with _connection() as con:
        return _snapshot(con, _load(con, identity))


def current_investigation(conversation_id):
    with _connection() as con:
        identity = _session(con, conversation_id).get('investigation_id')
        return _snapshot(con, _load(con, identity)) if identity else None


def _invalidate(snapshot, identities=None, excluded=False):
    affected = set(identities or [n['id'] for n in snapshot['hypotheses']])
    while True:
        expanded = affected | {n['id'] for n in snapshot['hypotheses'] if n.get('parent_id') in affected}
        if expanded == affected:
            break
        affected = expanded
    for node in snapshot['hypotheses']:
        if node['id'] in affected:
            node.update(revision=snapshot['revision'], verdict=None, interpretation='', evidence=[],
                        latest_test_id=None, updated=_now())
            if excluded:
                node['status'] = 'excluded'
            elif node['status'] != 'excluded':
                node['status'] = 'stale'
    snapshot.update(status='active', summary='')
    return affected


def _invalidate_ancestors(snapshot, parent_id):
    """A changed child makes an older parent synthesis stale, not its siblings."""
    while parent_id:
        parent = next(n for n in snapshot['hypotheses'] if n['id'] == parent_id)
        if parent['status'] == 'tested':
            parent.update(status='stale', verdict=None, interpretation='', evidence=[], latest_test_id=None,
                          revision=snapshot['revision'], updated=_now())
        parent_id = parent.get('parent_id')


def update_session(conversation_id, patch):
    if not isinstance(patch, dict) or set(patch) - {'scope', 'summary', 'preferences', 'investigation_id', 'ui_dates'}:
        raise ValueError('Session updates accept scope, summary, preferences, ui_dates and investigation_id only.')
    with _connection(write=True) as con:
        session = _session(con, conversation_id)
        if 'scope' in patch:
            scope = _scope(patch['scope'])
            if scope != session['scope'] and session.get('investigation_id'):
                investigation = _load(con, session['investigation_id'])
                investigation['revision'] += 1
                _invalidate(investigation)
                investigation['scope'] = scope
                investigation['baseline'] = None
                for node in investigation['hypotheses']:
                    node['scope'] = scope
                _persist(con, investigation, 'scope_changed')
            session['scope'] = scope
        if 'summary' in patch:
            if not isinstance(patch['summary'], str) or len(patch['summary']) > 16000:
                raise ValueError('Session summary must be text of at most 16000 characters.')
            session['summary'] = patch['summary']
        if 'preferences' in patch:
            if not isinstance(patch['preferences'], dict):
                raise ValueError('Preferences must be an object.')
            session['preferences'] = _copy(patch['preferences'])
        if 'ui_dates' in patch:
            if not isinstance(patch['ui_dates'], dict):
                raise ValueError('Interface dates must be an object.')
            session['ui_dates'] = _copy(patch['ui_dates'])
        if 'investigation_id' in patch:
            identity = patch['investigation_id']
            if identity is not None and _load(con, identity)['conversation_id'] != conversation_id:
                raise ValueError('The investigation belongs to another conversation.')
            session['investigation_id'] = identity
        return _save_session(con, session)


def create_investigation(conversation_id, question, scope, baseline=None):
    question = _text(question, 'Question')
    scope = _scope(scope)
    with _connection(write=True) as con:
        session = _session(con, conversation_id)
        if session.get('investigation_id'):
            previous = _load(con, session['investigation_id'])
            if previous['status'] != 'superseded':
                previous['revision'] += 1
                previous['status'] = 'superseded'
                _persist(con, previous, 'superseded')
        snapshot = {'id': str(uuid.uuid4()), 'conversation_id': conversation_id, 'question': question,
                    'scope': scope, 'baseline': _copy(baseline), 'revision': 1, 'status': 'active',
                    'summary': '', 'hypotheses': [], 'created': _now()}
        _persist(con, snapshot, 'created')
        session.update(scope=scope, investigation_id=snapshot['id'])
        _save_session(con, session)
        return _snapshot(con, snapshot)


def _criterion(criterion):
    if not isinstance(criterion, dict) or set(criterion) - {'column', 'operator', 'threshold', 'row'}:
        raise ValueError('Criterion accepts column, operator, threshold and zero-based row only.')
    _text(criterion.get('column'), 'Criterion column', 200)
    if criterion.get('operator') not in OPERATORS:
        raise ValueError('Criterion operator must be gt, gte, lt, lte, eq or ne.')
    _number(criterion.get('threshold'), 'Criterion threshold')
    row = criterion.get('row', 0)
    if isinstance(row, bool) or not isinstance(row, int) or row < 0:
        raise ValueError('Criterion row must be a nonnegative zero-based integer.')
    return {**criterion, 'row': row}


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(label + ' must be a finite number.')
    return Decimal(str(value))


def _validate_node(snapshot, node):
    for field in ('statement', 'test', 'falsifier'):
        node[field] = _text(node.get(field), 'Hypothesis ' + field, 6000)
    if node['kind'] not in {'partition', 'mechanism', 'baseline', 'hypothesis'}:
        raise ValueError('Hypothesis kind must be partition, mechanism, baseline or hypothesis.')
    if node['status'] not in NODE_STATUSES:
        raise ValueError('Invalid hypothesis status.')
    if node.get('criterion') is not None:
        node['criterion'] = _criterion(node['criterion'])
    node['scope'] = _scope(node['scope'])
    nodes = {n['id']: n for n in snapshot['hypotheses']}
    parent_id = node.get('parent_id')
    visited = {node['id']}
    while parent_id:
        if parent_id in visited:
            raise ValueError('Hypothesis parents cannot form a cycle.')
        visited.add(parent_id)
        parent = nodes.get(parent_id)
        if not parent:
            raise ValueError('The parent hypothesis does not exist in this investigation.')
        if parent['status'] == 'excluded' and node['status'] != 'excluded':
            raise ValueError('Reactivate the parent before adding or restoring a child.')
        parent_id = parent.get('parent_id')
    if not isinstance(node.get('overlaps_with', []), list):
        raise ValueError('overlaps_with must be a list of hypothesis IDs.')
    for identity in node.get('overlaps_with', []):
        if identity not in nodes or identity == node['id']:
            raise ValueError('An overlap must reference another existing hypothesis.')


def _upsert(con, snapshot, patch):
    if not isinstance(patch, dict) or set(patch) - NODE_FIELDS:
        raise ValueError('Hypothesis changes contain unknown or read-only fields.')
    identity = patch.get('id') or str(uuid.uuid4())
    _text(identity, 'Hypothesis ID', 100)
    current = next((n for n in snapshot['hypotheses'] if n['id'] == identity), None)
    if patch.get('status') == 'tested':
        raise ValueError('Only record_test may mark a hypothesis tested.')
    if current:
        node = {**current, **_copy(patch)}
        if 'criterion' not in patch and any(field in patch and patch[field] != current.get(field)
                                           for field in ('statement', 'test', 'falsifier')):
            # A user's rewritten explanation cannot inherit an older decision rule.
            node['criterion'] = None
    else:
        if len(snapshot['hypotheses']) >= 80:
            raise ValueError('An investigation supports at most 80 hypotheses. Start a focused follow-up.')
        node = {'id': identity, 'parent_id': None, 'kind': 'mechanism', 'status': 'planned',
                'scope': _copy(snapshot['scope']), 'criterion': None, 'overlaps_with': [],
                'verdict': None, 'interpretation': '', 'evidence': [], 'created': _now(), **_copy(patch)}
    _validate_node(snapshot, node)
    snapshot['revision'] += 1
    if current:
        _invalidate_ancestors(snapshot, current.get('parent_id'))
    _invalidate_ancestors(snapshot, node.get('parent_id'))
    if current:
        _invalidate(snapshot, [identity], excluded=node['status'] == 'excluded')
        # Editing an already tested or otherwise changed node invalidates its result.
        requested_status = patch.get('status')
        node.update(status='excluded' if node['status'] == 'excluded' else
                    requested_status if requested_status in {'planned', 'testing'} else 'stale',
                    verdict=None, interpretation='', evidence=[], latest_test_id=None)
        snapshot['hypotheses'] = [node if n['id'] == identity else n for n in snapshot['hypotheses']]
    else:
        snapshot['hypotheses'].append(node)
    node.update(revision=snapshot['revision'], updated=_now())
    snapshot.update(status='active', summary='')
    _persist(con, snapshot, 'hypothesis_edited' if current else 'hypothesis_added')
    return _snapshot(con, snapshot)


def upsert_hypothesis(investigation_id, node, expected_revision=None):
    with _connection(write=True) as con:
        snapshot = _load(con, investigation_id)
        _check_revision(snapshot, expected_revision)
        return _upsert(con, snapshot, node)


def edit_hypothesis(investigation_id, node_id, patch, expected_revision=None):
    if not isinstance(patch, dict) or ('id' in patch and patch['id'] != node_id):
        raise ValueError('The hypothesis ID cannot be changed.')
    patch = _copy(patch)
    if 'excluded' in patch:
        excluded = patch.pop('excluded')
        if not isinstance(excluded, bool):
            raise ValueError('Excluded must be a boolean.')
        status = 'excluded' if excluded else 'planned'
        if 'status' in patch and patch['status'] != status:
            raise ValueError('Excluded and status updates disagree.')
        patch['status'] = status
    with _connection(write=True) as con:
        snapshot = _load(con, investigation_id)
        _check_revision(snapshot, expected_revision)
        if not any(n['id'] == node_id for n in snapshot['hypotheses']):
            raise ValueError('Hypothesis not found.')
        return _upsert(con, snapshot, {**patch, 'id': node_id})


def _evidence(evidence):
    if not isinstance(evidence, dict):
        raise ValueError('Supply the full measured evidence result, not a citation or model prose.')
    evidence = _copy(evidence)
    if evidence.get('truncated') or evidence.get('model_preview_truncated'):
        raise ValueError('A hypothesis test requires complete, nontruncated evidence.')
    rows = evidence.get('rows')
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError('Evidence must contain measured rows.')
    if evidence.get('row_count', len(rows)) != len(rows):
        raise ValueError('Evidence row count does not match the complete result.')
    sql = evidence.get('sql')
    calculation = evidence.get('calculation')
    reproducible_sql = isinstance(sql, str) and bool(sql.strip()) and isinstance(evidence.get('parameters', []), (list, dict))
    reproducible_calculation = isinstance(calculation, dict) and bool(calculation) and bool(
        evidence.get('source_evidence_ids') or evidence.get('source_evidence_id') or calculation.get('source_evidence_ids'))
    if not reproducible_sql and not reproducible_calculation:
        raise ValueError('Measured evidence needs its query and parameters or a calculation with source evidence IDs.')
    return evidence


def evaluate_criterion(evidence, criterion):
    """Evaluate one predeclared numeric predicate; never infer causal identification.

    The caller must pass a real query-tool result, not model-created evidence.
    Empty/null results are data_missing, not a false hypothesis. Missing column names,
    truncated results and nonnumeric values are rejected for correction.
    """
    criterion = _criterion(criterion)
    evidence = _evidence(evidence)
    row_index = criterion['row']
    rows = evidence['rows']
    if rows and row_index >= len(rows):
        raise ValueError('The criterion row is outside the measured result. Correct the test query or declared row.')
    if rows and criterion['column'] not in rows[row_index]:
        raise ValueError('The test query must return the declared criterion column ' + criterion['column'] +
                         '. This is a query schema mismatch, not missing business data. Compute the declared statistic with that alias and rerun the test.')
    if not rows or rows[row_index][criterion['column']] is None:
        return {'verdict': 'data_missing', 'observed': None, 'criterion': criterion,
                'reason': 'The specified measured cell is absent or null.'}
    observed = evidence['rows'][row_index][criterion['column']]
    measured = _number(observed, 'Measured criterion cell')
    passes = OPERATORS[criterion['operator']](measured, _number(criterion['threshold'], 'Criterion threshold'))
    return {'verdict': 'supported_descriptively' if passes else 'contradicted',
            'observed': observed, 'criterion': criterion,
            'reason': 'The declared numeric criterion ' + ('holds' if passes else 'does not hold') +
                      ' in the measured result. This checks the predicate, not causal identification or the hypothesis wording.'}


def reconcile_partition(evidence, value_column, total, partition_columns, tolerance=0.01, member_ids_column=None):
    """Check additive coverage and unique partition keys, optionally row membership.

    For an evidence-backed total pass {evidence: result, column: name, row: 0}.
    A numeric total is allowed for local arithmetic but is explicitly unverified.
    Distinct grouped labels alone cannot prove distinct underlying observations.
    """
    evidence = _evidence(evidence)
    if not isinstance(partition_columns, list) or not partition_columns or not all(isinstance(c, str) and c for c in partition_columns):
        raise ValueError('Declare the columns identifying each mutually exclusive partition.')
    if not evidence['rows']:
        raise ValueError('A partition needs measured rows.')
    total_verified = isinstance(total, dict)
    if total_verified:
        source = _evidence(total.get('evidence'))
        if source.get('scope') != evidence.get('scope'):
            raise ValueError('Partition and total evidence must use the same scope.')
        index = total.get('row', 0)
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(source['rows']):
            raise ValueError('The total must reference a valid measured row.')
        total = source['rows'][index].get(total.get('column'))
    measured_total = _number(total, 'Total')
    tolerance_number = _number(tolerance, 'Tolerance')
    if tolerance_number < 0:
        raise ValueError('Tolerance cannot be negative.')
    keys, member_ids, values = set(), set(), []
    for row in evidence['rows']:
        if any(c not in row or row[c] is None for c in partition_columns):
            raise ValueError('Every partition must have an explicit key; include an Unknown category for missing values.')
        key = _json([row[c] for c in partition_columns])
        if key in keys:
            raise ValueError('Duplicate partition keys would double-count a group.')
        keys.add(key)
        values.append(_number(row.get(value_column), 'Partition value'))
        if member_ids_column:
            members = row.get(member_ids_column)
            if not isinstance(members, list):
                raise ValueError('Partition membership must contain observation-ID lists.')
            encoded_members = [_json(m) for m in members]
            if len(set(encoded_members)) != len(encoded_members) or set(encoded_members) & member_ids:
                raise ValueError('Partition membership overlaps and would double-count observations.')
            member_ids.update(encoded_members)
    subtotal = sum(values, Decimal(0))
    residual = measured_total - subtotal
    return {'reconciled': abs(residual) <= tolerance_number, 'sum': float(subtotal), 'total': float(measured_total),
            'residual': float(residual), 'tolerance': tolerance, 'partition_count': len(keys),
            'total_evidence_verified': total_verified, 'unique_partition_keys': True,
            'membership_disjoint_verified': bool(member_ids_column),
            'limitation': '' if member_ids_column else 'Unique group labels and reconciled totals do not prove disjoint underlying observations.'}


def record_test(investigation_id, node_id, evidence, verdict, interpretation, expected_revision=None):
    if verdict not in VERDICTS:
        raise ValueError('Invalid verdict. Use supported_descriptively, contradicted, inconclusive or data_missing.')
    interpretation = _text(interpretation, 'Test interpretation')
    with _connection(write=True) as con:
        snapshot = _load(con, investigation_id)
        _check_revision(snapshot, expected_revision)
        node = next((n for n in snapshot['hypotheses'] if n['id'] == node_id), None)
        if not node:
            raise ValueError('Hypothesis not found.')
        if node['status'] == 'excluded':
            raise ValueError('Restore the excluded hypothesis before testing it.')
        if con.execute('SELECT COUNT(*) FROM retail_hypothesis_tests WHERE investigation_id=?', (investigation_id,)).fetchone()[0] >= 500:
            raise ValueError('This investigation has reached 500 tests. Start a focused follow-up.')
        if evidence is None:
            if verdict != 'data_missing':
                raise ValueError('Missing evidence permits only a data_missing verdict.')
            measured, evaluation = None, {'verdict': 'data_missing', 'reason': interpretation, 'observed': None}
        else:
            measured = _evidence(evidence)
            if measured.get('scope') != node['scope']:
                raise ValueError('The measured evidence scope differs from the hypothesis scope. Rerun the correct slice.')
            if node.get('criterion') is not None:
                evaluation = evaluate_criterion(measured, node['criterion'])
                if verdict != evaluation['verdict']:
                    raise ValueError('The proposed verdict disagrees with the measured criterion: ' + evaluation['verdict'] + '.')
            else:
                if verdict not in {'inconclusive', 'data_missing'}:
                    raise ValueError('Declare a measurable criterion before assigning a supported or contradicted verdict.')
                evaluation = {'verdict': verdict, 'reason': 'No automatic criterion was declared; this result remains unresolved.', 'observed': None}
        snapshot['revision'] += 1
        # A parent's earlier synthesis depended on this branch and must be refreshed.
        _invalidate_ancestors(snapshot, node.get('parent_id'))
        test = {'id': str(uuid.uuid4()), 'node_id': node_id, 'investigation_id': investigation_id,
                'investigation_revision': snapshot['revision'], 'hypothesis_revision': node['revision'],
                'statement': node['statement'], 'test': node['test'], 'falsifier': node['falsifier'],
                'scope': _copy(node['scope']), 'criterion': _copy(node.get('criterion')),
                'evidence': measured, 'verdict': evaluation['verdict'], 'evaluation': evaluation,
                'interpretation': interpretation, 'created': _now()}
        con.execute('INSERT INTO retail_hypothesis_tests(id,investigation_id,node_id,investigation_revision,payload,created) VALUES(?,?,?,?,?,?)',
                    (test['id'], investigation_id, node_id, snapshot['revision'], _json(test), test['created']))
        node.update(status='tested', verdict=evaluation['verdict'], interpretation=interpretation,
                    evidence=[measured] if measured else [], latest_test_id=test['id'],
                    revision=snapshot['revision'], updated=_now())
        snapshot.update(status='active', summary='')
        _persist(con, snapshot, 'test_recorded')
        return _snapshot(con, snapshot)


def finish_investigation(identity, summary, status='complete', expected_revision=None):
    summary = _text(summary, 'Investigation summary', 20000)
    if status == 'partial':
        status = 'incomplete'
    if status not in {'complete', 'incomplete', 'paused', 'active'}:
        raise ValueError('Investigation completion status must be complete, partial, incomplete, paused or active.')
    with _connection(write=True) as con:
        snapshot = _load(con, identity)
        _check_revision(snapshot, expected_revision)
        parents = {n.get('parent_id') for n in snapshot['hypotheses'] if n['status'] != 'excluded'}
        unresolved = [n['id'] for n in snapshot['hypotheses']
                      if n['id'] not in parents and n['status'] not in {'tested', 'excluded'}]
        if status == 'complete' and (not snapshot['hypotheses'] or unresolved):
            raise ValueError('Unfinished hypotheses remain. Use incomplete or finish their tests before marking the investigation complete.')
        snapshot.update(revision=snapshot['revision'] + 1, summary=summary, status=status)
        _persist(con, snapshot, 'finished')
        return _snapshot(con, snapshot)


def revision_history(identity):
    """Read-only audit metadata; immutable full revision snapshots stay in SQLite."""
    with _connection() as con:
        _load(con, identity)
        return [dict(row) for row in con.execute(
            'SELECT revision,action,created FROM retail_investigation_events WHERE investigation_id=? ORDER BY revision', (identity,))]


def delete_conversation_state(con, conversation_id):
    """Called within storage's explicit chat-delete transaction; never touches data."""
    identities = [r[0] for r in con.execute("SELECT id FROM retail_investigations WHERE conversation_id=?", (conversation_id,))]
    for identity in identities:
        con.execute('DELETE FROM retail_hypothesis_tests WHERE investigation_id=?', (identity,))
        con.execute('DELETE FROM retail_investigation_events WHERE investigation_id=?', (identity,))
    con.execute('DELETE FROM retail_investigations WHERE conversation_id=?', (conversation_id,))
    con.execute('DELETE FROM retail_sessions WHERE conversation_id=?', (conversation_id,))


def set_baseline(identity, evidence, expected_revision=None):
    """Refresh the measured baseline after a scope edit without replacing the tree."""
    with _connection(write=True) as con:
        snapshot=_load(con,identity)
        _check_revision(snapshot,expected_revision)
        if not isinstance(evidence,dict) or evidence.get('scope')!=snapshot['scope'] or not evidence.get('rows'):
            raise ValueError('The baseline must contain measured evidence from the investigation scope.')
        snapshot.update(baseline=_copy(evidence),revision=snapshot['revision']+1)
        _persist(con,snapshot,'baseline_refreshed')
        return _snapshot(con,snapshot)
