"""Versioned local improvement workspace.

Drafts are mutable with optimistic revisions. Content versions and release
manifests are immutable; publication only moves one active pointer in a SQLite
transaction. A caller captures a snapshot once and passes it through its whole
answer/evaluation. Nothing is written by importing this module.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import json
import re
import sqlite3
import uuid
from collections import Counter
from functools import lru_cache

from . import storage
from .data import ROOT, APP

KINDS = ('knowledge', 'ontology', 'skill', 'output_profile', 'example', 'evaluation_suite')
PROFILE_IDS = ('quick-answer', 'business-review', 'analyst-detail')
BUILTIN_SKILLS = {
    'trend': 1, 'pvm': 2, 'growth': 3, 'margin': 4, 'seasonality': 5,
    'scorecard': 6, 'channels': 7, 'concentration': 8, 'pricing': 9,
    'promotions': 10, 'cohorts': 11, 'lapse': 12, 'segments': 13,
    'affinity': 14, 'loyalty': 15, 'returns': 16, 'velocity': 17,
    'inventory': 18, 'fulfillment': 19,
}
REQUIRED_SECTIONS = ('Headline', 'Scope and metric', 'Primary visual', 'Supporting values', 'Interpretation', 'Limitations', 'Next question')
MAX_CONTENT_BYTES = 512 * 1024
ID_RE = re.compile(r'^[a-z][a-z0-9-]{1,79}$')
SCHEMA = '''
CREATE TABLE IF NOT EXISTS workspace_migrations(version INTEGER PRIMARY KEY, applied TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS workspace_assets(
 id TEXT PRIMARY KEY, kind TEXT NOT NULL, name TEXT NOT NULL, owner TEXT NOT NULL,
 built_in INTEGER NOT NULL DEFAULT 0, created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS workspace_drafts(
 asset_id TEXT PRIMARY KEY, revision INTEGER NOT NULL, name TEXT NOT NULL,
 content TEXT NOT NULL, updated TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS workspace_versions(
 id TEXT PRIMARY KEY, asset_id TEXT NOT NULL, name TEXT NOT NULL, schema_version INTEGER NOT NULL,
 content TEXT NOT NULL, content_hash TEXT NOT NULL, created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS workspace_versions_asset ON workspace_versions(asset_id);
CREATE TABLE IF NOT EXISTS workspace_releases(
 id TEXT PRIMARY KEY, name TEXT NOT NULL, parent_release_id TEXT, asset_versions TEXT NOT NULL,
 snapshot_hash TEXT NOT NULL, validation TEXT NOT NULL, operator TEXT NOT NULL, rationale TEXT NOT NULL,
 created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS workspace_active(singleton INTEGER PRIMARY KEY CHECK(singleton=1), release_id TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS workspace_activations(
 id TEXT PRIMARY KEY, release_id TEXT NOT NULL, previous_release_id TEXT, action TEXT NOT NULL,
 operator TEXT NOT NULL, rationale TEXT NOT NULL, evaluation_run_id TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS workspace_feedback(
 id TEXT PRIMARY KEY, analysis_id TEXT NOT NULL, issue_types TEXT NOT NULL, correction TEXT NOT NULL,
 status TEXT NOT NULL, revision INTEGER NOT NULL, original_question TEXT NOT NULL,
 original_answer TEXT NOT NULL, provenance TEXT NOT NULL, evidence TEXT NOT NULL,
 linked_asset_id TEXT, linked_case_id TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP,
 updated TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TRIGGER IF NOT EXISTS workspace_versions_no_update BEFORE UPDATE ON workspace_versions BEGIN SELECT RAISE(ABORT, 'Workspace versions are immutable'); END;
CREATE TRIGGER IF NOT EXISTS workspace_versions_no_delete BEFORE DELETE ON workspace_versions BEGIN SELECT RAISE(ABORT, 'Workspace versions are immutable'); END;
CREATE TRIGGER IF NOT EXISTS workspace_releases_no_update BEFORE UPDATE ON workspace_releases BEGIN SELECT RAISE(ABORT, 'Workspace releases are immutable'); END;
CREATE TRIGGER IF NOT EXISTS workspace_releases_no_delete BEFORE DELETE ON workspace_releases BEGIN SELECT RAISE(ABORT, 'Workspace releases are immutable'); END;
'''


class WorkspaceError(ValueError):
    def __init__(self, message, code='invalid_request', status=400, errors=None):
        super().__init__(message)
        self.code, self.status, self.errors = code, status, errors or []

    def detail(self):
        return {'code': self.code, 'message': str(self), 'errors': self.errors}


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def _hash(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _identity(identity):
    if not isinstance(identity, str) or not ID_RE.fullmatch(identity):
        raise WorkspaceError('Use 2–80 lower-case letters, numbers and hyphens, beginning with a letter.', 'invalid_asset_id')
    return identity


def _content(content):
    if not isinstance(content, dict):
        raise WorkspaceError('Asset content must be a JSON object.', 'invalid_content')
    try:
        encoded = _json(content)
    except (ValueError, TypeError) as exc:
        raise WorkspaceError('Content must contain finite JSON values.', 'invalid_content') from exc
    if len(encoded.encode()) > MAX_CONTENT_BYTES:
        raise WorkspaceError('Asset content exceeds the 512 KiB limit.', 'content_too_large')
    return encoded


def _name(name):
    if not isinstance(name, str) or not name.strip() or len(name) > 160:
        raise WorkspaceError('Give the asset a name of 1–160 characters.', 'invalid_name')
    return name.strip()


@lru_cache(maxsize=1)
def load_builtin_contracts():
    """Join recipe/visual chapters by explicit chapter ID, never list position."""
    playbook_path = ROOT / 'retail-data-analyst/references/playbooks.md'
    visual_path = ROOT / 'retail-data-analyst/references/visual-specs.md'
    raw, visual_raw = playbook_path.read_text(), visual_path.read_text()
    chapters = list(re.finditer(r'^### Playbook (\d+) — (.+)$', raw, re.M))
    visual_chapters = list(re.finditer(r'^### (\d+)\. (.+)$', visual_raw, re.M))
    recipes, visuals = {}, {}
    for index, chapter in enumerate(chapters):
        stop = chapters[index + 1].start() if index + 1 < len(chapters) else len(raw)
        body = re.split(r'\n## ', raw[chapter.end():stop], maxsplit=1)[0]
        recipes[int(chapter.group(1))] = (chapter, body)
    for index, chapter in enumerate(visual_chapters):
        stop = visual_chapters[index + 1].start() if index + 1 < len(visual_chapters) else len(visual_raw)
        visuals[int(chapter.group(1))] = (chapter, visual_raw[chapter.end():stop].strip())
    if set(recipes) != set(BUILTIN_SKILLS.values()) or set(visuals) != set(BUILTIN_SKILLS.values()):
        raise WorkspaceError('Built-in recipe and visual chapter IDs do not match the stable skill manifest.', 'builtin_manifest_mismatch')
    result = {}
    for slug, number in BUILTIN_SKILLS.items():
        chapter, body = recipes[number]
        visual, visual_body = visuals[number]
        fields = {key: value.strip() for key, value in re.findall(r'\*\*([A-I])\. [^*]+\*\*\s*(.*?)(?=\n\n\*\*[A-I]\.|\Z)', body, re.S)}
        result[slug] = {
            'slug': slug, 'number': number, 'title': chapter.group(2),
            'required_inputs': fields.get('B', ''), 'method': fields.get('C', ''),
            'guardrails': fields.get('D', ''), 'output_template': fields.get('E', ''),
            'visual_summary': fields.get('F', ''), 'visual_spec': visual_body,
            'interpretation_guide': fields.get('H', ''), 'next_drills': fields.get('I', ''),
            'sections': list(REQUIRED_SECTIONS),
            'sources': [
                {'source': str(playbook_path.relative_to(ROOT)), 'line': raw[:chapter.start()].count('\n') + 1, 'sha256': hashlib.sha256(raw.encode()).hexdigest()},
                {'source': str(visual_path.relative_to(ROOT)), 'line': visual_raw[:visual.start()].count('\n') + 1, 'sha256': hashlib.sha256(visual_raw.encode()).hexdigest()},
            ],
        }
    return result


@lru_cache(maxsize=1)
def approved_tools():
    """Read declarations without importing the agent or creating model clients."""
    names = set()
    for filename in ('agent.py', 'conversation.py'):
        tree = ast.parse((APP / 'backend' / filename).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ('function', 'fn') and node.args:
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    names.add(first.value)
    return sorted(names)


def capabilities():
    from .scope import MEASURE_NAMES, FIELDS, RETURN_BASES
    return {'kinds': list(KINDS), 'measures': sorted(MEASURE_NAMES), 'dimensions': sorted(FIELDS),
            'tools': approved_tools(), 'handlers': ['method_only'] + ['playbook:' + slug for slug in BUILTIN_SKILLS],
            'profiles': list(PROFILE_IDS), 'return_bases': sorted(RETURN_BASES),
            'date_bases': ['sale_date', 'return_date', 'snapshot_date'],
            'deployment': 'trusted_local_single_user', 'arbitrary_code_upload': False,
            'required_output_safeguards': ['scope', 'evidence', 'limitations'], 'schema_version': 1}


def _seeds():
    for identity, name, detail in (
        ('quick-answer', 'Quick answer', 'concise'),
        ('business-review', 'Business review', 'standard'),
        ('analyst-detail', 'Analyst detail', 'detailed'),
    ):
        yield identity, 'output_profile', name, {
            'description': name + ' with measured values, scope, citations and limitations retained.',
            'detail': detail, 'required_sections': list(REQUIRED_SECTIONS),
            'chart_preference': 'auto', 'show_evidence': True, 'show_scope': True, 'show_limitations': True,
            'show_sources': True, 'tone': 'clear and evidence-led',
        }
    for slug, contract in load_builtin_contracts().items():
        yield 'skill-' + slug, 'skill', contract['title'], {
            'description': contract['title'], 'slug': slug, 'handler': 'playbook:' + slug,
            'trigger_examples': [contract['title']], 'required_concepts': [],
            'approved_tools': ['get_playbook_design', 'run_playbook', 'query_retail', 'create_visualization', 'present_answer'],
            'method': contract['method'], 'required_inputs': contract['required_inputs'],
            'allowed_filters': [], 'output_profile_id': 'business-review',
            'caveats': [contract['guardrails']], 'contract': contract,
            'source_refs': contract['sources'],
        }
    from .context import INDEX
    for document in INDEX.documents:
        source = document['path']
        chunks = []
        for chunk in INDEX.chunks:
            if chunk['source'] != source: continue
            chunks.append({k: v for k, v in chunk.items() if k not in ('terms', 'heading_terms')})
        identity = 'reference-' + re.sub('[^a-z0-9]+', '-', source.lower()).strip('-')[-50:] + '-' + document['sha256'][:8]
        yield identity, 'knowledge', source.split('/')[-1], {
            'description': 'Frozen built-in reference. Duplicate this item to add workspace guidance.',
            'body': INDEX.document(source), 'aliases': [],
            'source_refs': [{'source': source, 'sha256': document['sha256'], 'line': 1}],
            '_reference_chunks': chunks,
        }
    for identity, name, measure, units, aliases, meaning in (
        ('metric-sales', 'Sales before returns', 'sales_before_returns_cents', 'cents', ['net sales before returns'], 'Sales after discounts and before refunds, using original sale dates.'),
        ('metric-units', 'Sold units', 'units', 'units', ['quantity sold'], 'Original sold quantities using sale dates. Returned units are separate.'),
        ('metric-aov', 'Average order value', 'aov_cents', 'cents/order', ['aov'], 'Sales divided by distinct complete transaction orders; preserve header grain and avoid line fan-out.'),
        ('metric-return-rate', 'Unit return rate', 'return_rate_pct', 'percent', ['unit return rate percent'], 'Linked returned units divided by original sold units in the sales cohort; observe maturity and return coverage.'),
    ):
        yield identity, 'ontology', name, {'concept_type': 'metric', 'description': meaning, 'aliases': aliases,
            'measure': measure, 'units': units, 'date_basis': 'sale_date',
            'return_basis': 'sales_cohort' if identity == 'metric-return-rate' else 'before_returns'}
    path = APP / 'knowledge/enterprise_evaluations.json'
    if path.is_file():
        content = json.loads(path.read_text())
        yield content.get('id', 'enterprise-core'), 'evaluation_suite', content.get('name', 'Enterprise runtime contracts'), content


def _insert_version(con, asset_id, name, content):
    digest = _hash(content)
    identity = 'v-' + _hash({'asset_id': asset_id, 'name': name, 'content': content})[:32]
    con.execute('INSERT OR IGNORE INTO workspace_versions(id,asset_id,name,schema_version,content,content_hash) VALUES(?,?,?,?,?,?)',
                (identity, asset_id, name, 1, _json(content), digest))
    return identity


def _snapshot(con, mapping, release_id=None, parent=None):
    assets = []
    baseline_row = con.execute("SELECT asset_versions FROM workspace_releases WHERE id='release-baseline'").fetchone()
    baseline = json.loads(baseline_row[0]) if baseline_row else mapping
    for identity, version in sorted(mapping.items()):
        row = con.execute('SELECT a.id,a.kind,a.built_in,v.id AS version_id,v.name,v.content,v.content_hash FROM workspace_assets a JOIN workspace_versions v ON a.id=v.asset_id WHERE a.id=? AND v.id=?', (identity, version)).fetchone()
        if not row:
            raise WorkspaceError('Release references a missing asset version.', 'invalid_release', 409)
        item = dict(row)
        item['content'] = json.loads(item['content']); item['built_in'] = bool(item['built_in'])
        item['is_baseline'] = baseline.get(identity) == version
        assets.append(item)
    digest = _hash(mapping)
    return {'id': release_id, 'release_id': release_id, 'parent_release_id': parent,
            'asset_versions': dict(mapping), 'assets': assets, 'snapshot_hash': digest, 'hash': digest}


def _active_id(con):
    row = con.execute('SELECT release_id FROM workspace_active WHERE singleton=1').fetchone()
    return row[0] if row else None


def _get_snapshot(con, identity):
    row = con.execute('SELECT * FROM workspace_releases WHERE id=?', (identity,)).fetchone()
    if not row:
        raise WorkspaceError('Release not found.', 'release_not_found', 404)
    snapshot = _snapshot(con, json.loads(row['asset_versions']), row['id'], row['parent_release_id'])
    snapshot.update({'name': row['name'], 'created': row['created'], 'validation': json.loads(row['validation'])})
    return snapshot


def ensure_initialized():
    """Idempotent migration in the existing state DB; original tables untouched."""
    storage.state_directory().mkdir(parents=True, exist_ok=True)
    with storage.connection() as con:
        con.executescript(SCHEMA)
        con.execute('BEGIN IMMEDIATE')
        if con.execute('SELECT 1 FROM workspace_migrations WHERE version=1').fetchone():
            return
        mapping = {}
        for identity, kind, name, content in _seeds():
            con.execute('INSERT INTO workspace_assets(id,kind,name,owner,built_in) VALUES(?,?,?,?,1)', (identity, kind, name, 'built-in'))
            mapping[identity] = _insert_version(con, identity, name, content)
        snapshot = _snapshot(con, mapping)
        validation = validate_candidate(snapshot)
        if not validation['valid']:
            raise WorkspaceError('Built-in workspace failed validation.', 'invalid_seed', errors=validation['errors'])
        identity = 'release-baseline'
        con.execute('INSERT INTO workspace_releases(id,name,parent_release_id,asset_versions,snapshot_hash,validation,operator,rationale) VALUES(?,?,?,?,?,?,?,?)',
                    (identity, 'Built-in baseline', None, _json(mapping), snapshot['snapshot_hash'], _json(validation), 'migration', 'Imported existing recipes and domain references; no calculations changed.'))
        con.execute('INSERT INTO workspace_active(singleton,release_id) VALUES(1,?)', (identity,))
        con.execute('INSERT INTO workspace_activations(id,release_id,action,operator,rationale) VALUES(?,?,?,?,?)',
                    (str(uuid.uuid4()), identity, 'seed', 'migration', 'Initial built-in baseline'))
        # Preserve legacy feedback with original answer/evidence at migration time.
        for row in con.execute("SELECT f.*,a.question,a.payload FROM feedback f JOIN analyses a ON a.id=f.analysis_id WHERE f.rating='needs_review'").fetchall():
            answer = json.loads(row['payload'])
            con.execute('INSERT OR IGNORE INTO workspace_feedback(id,analysis_id,issue_types,correction,status,revision,original_question,original_answer,provenance,evidence) VALUES(?,?,?,?,?,?,?,?,?,?)',
                        (row['id'], row['analysis_id'], '["other"]', row['comment'] or '', 'new', 1, row['question'], answer.get('answer', ''), _json(answer.get('workspace', answer.get('workspace_provenance', {}))), _json(answer.get('outputs', []))))
        con.execute('INSERT INTO workspace_migrations(version) VALUES(1)')


def active_snapshot():
    ensure_initialized()
    with storage.connection() as con:
        return _get_snapshot(con, _active_id(con))


def get_snapshot(release_id):
    ensure_initialized()
    with storage.connection() as con:
        return _get_snapshot(con, release_id)


def _candidate(con, asset_ids=None):
    active = _get_snapshot(con, _active_id(con))
    mapping = active['asset_versions'].copy()
    if asset_ids is not None:
        if not isinstance(asset_ids, list) or any(not isinstance(item, str) for item in asset_ids):
            raise WorkspaceError('asset_ids must be a list of asset IDs.', 'invalid_asset_ids')
        for identity in asset_ids:
            if not con.execute('SELECT 1 FROM workspace_assets WHERE id=?', (identity,)).fetchone():
                raise WorkspaceError('Asset not found: ' + identity, 'asset_not_found', 404)
    for row in con.execute('SELECT * FROM workspace_drafts ORDER BY asset_id').fetchall():
        if asset_ids is None or row['asset_id'] in asset_ids:
            mapping[row['asset_id']] = _insert_version(con, row['asset_id'], row['name'], json.loads(row['content']))
    return _snapshot(con, mapping, parent=active['release_id'])


def candidate_snapshot(asset_ids=None):
    ensure_initialized()
    with storage.connection() as con:
        con.execute('BEGIN IMMEDIATE')
        return _candidate(con, asset_ids)


def capture_snapshot(release_id=None, candidate_version_ids=None):
    if release_id:
        return get_snapshot(release_id)
    if candidate_version_ids is not None:
        ensure_initialized()
        with storage.connection() as con:
            mapping = _get_snapshot(con, _active_id(con))['asset_versions'].copy()
            if isinstance(candidate_version_ids, dict):
                mapping.update(candidate_version_ids)
            else:
                for version in candidate_version_ids:
                    row = con.execute('SELECT asset_id FROM workspace_versions WHERE id=?', (version,)).fetchone()
                    if not row: raise WorkspaceError('Asset version not found.', 'version_not_found', 404)
                    mapping[row[0]] = version
            return _snapshot(con, mapping, parent=_active_id(con))
    return active_snapshot()


def create_asset(kind, name, content, id=None, owner='local-admin'):
    ensure_initialized()
    if kind not in KINDS: raise WorkspaceError('Unknown asset kind.', 'invalid_kind')
    name = _name(name); encoded = _content(content)
    identity = _identity(id or ('asset-' + uuid.uuid4().hex[:16]))
    with storage.connection() as con:
        con.execute('BEGIN IMMEDIATE')
        if con.execute('SELECT 1 FROM workspace_assets WHERE id=?', (identity,)).fetchone():
            raise WorkspaceError('This asset ID already exists.', 'asset_id_conflict', 409)
        con.execute('INSERT INTO workspace_assets(id,kind,name,owner) VALUES(?,?,?,?)', (identity, kind, name, str(owner)[:100]))
        con.execute('INSERT INTO workspace_drafts(asset_id,revision,name,content) VALUES(?,1,?,?)', (identity, name, encoded))
    return get_asset(identity)


def update_asset(asset_id, content, expected_revision, name=None):
    ensure_initialized(); encoded = _content(content)
    if isinstance(expected_revision, bool) or not isinstance(expected_revision, int):
        raise WorkspaceError('Supply the draft revision shown in the editor.', 'revision_required', 409)
    with storage.connection() as con:
        con.execute('BEGIN IMMEDIATE')
        asset = con.execute('SELECT * FROM workspace_assets WHERE id=?', (asset_id,)).fetchone()
        if not asset: raise WorkspaceError('Asset not found.', 'asset_not_found', 404)
        if asset['built_in']:
            raise WorkspaceError('Built-in assets are read-only. Duplicate this item to author a workspace version.', 'baseline_read_only', 409)
        row = con.execute('SELECT * FROM workspace_drafts WHERE asset_id=?', (asset_id,)).fetchone()
        revision = row['revision'] if row else 0
        if expected_revision != revision:
            raise WorkspaceError('This draft changed. Reload it before saving again.', 'stale_revision', 409)
        draft_name = _name(name if name is not None else (row['name'] if row else asset['name']))
        con.execute('INSERT INTO workspace_drafts(asset_id,revision,name,content) VALUES(?,?,?,?) ON CONFLICT(asset_id) DO UPDATE SET revision=excluded.revision,name=excluded.name,content=excluded.content,updated=CURRENT_TIMESTAMP',
                    (asset_id, revision + 1, draft_name, encoded))
    return get_asset(asset_id)


def _asset_record(con, asset, mapping):
    result = dict(asset); result['built_in'] = bool(result['built_in'])
    draft = con.execute('SELECT * FROM workspace_drafts WHERE asset_id=?', (asset['id'],)).fetchone()
    version_id = mapping.get(asset['id'])
    version = con.execute('SELECT * FROM workspace_versions WHERE id=?', (version_id,)).fetchone() if version_id else None
    result['published_version_id'] = version_id
    result['published_content'] = json.loads(version['content']) if version else None
    result['draft'] = {'revision': draft['revision'], 'name': draft['name'], 'content': json.loads(draft['content']), 'updated': draft['updated']} if draft else None
    result['draft_revision'] = draft['revision'] if draft else 0
    result['content'] = result['draft']['content'] if draft else result['published_content']
    result['effective_content'] = result['published_content']
    if draft: result['name'] = draft['name']
    elif version: result['name'] = version['name']
    different = draft and (not version or _hash(result['content']) != version['content_hash'] or draft['name'] != version['name'])
    result['status'] = 'draft' if different else 'published' if version else 'draft'
    return result


def get_asset(asset_id):
    ensure_initialized()
    with storage.connection() as con:
        asset = con.execute('SELECT * FROM workspace_assets WHERE id=?', (asset_id,)).fetchone()
        if not asset: raise WorkspaceError('Asset not found.', 'asset_not_found', 404)
        return _asset_record(con, asset, _get_snapshot(con, _active_id(con))['asset_versions'])


def list_assets(kind=None, q=''):
    ensure_initialized()
    if kind and kind not in KINDS: raise WorkspaceError('Unknown asset kind.', 'invalid_kind')
    with storage.connection() as con:
        mapping = _get_snapshot(con, _active_id(con))['asset_versions']
        rows = con.execute('SELECT * FROM workspace_assets ORDER BY kind,name,id').fetchall()
        assets = [_asset_record(con, row, mapping) for row in rows if not kind or row['kind'] == kind]
    if q: assets = [a for a in assets if q.casefold() in (a['name'] + ' ' + a['id'] + ' ' + _json(a['content'])).casefold()]
    return assets


def asset_versions(asset_id):
    get_asset(asset_id)
    with storage.connection() as con:
        rows = con.execute('SELECT * FROM workspace_versions WHERE asset_id=? ORDER BY rowid DESC', (asset_id,)).fetchall()
        return [{**dict(row), 'content': json.loads(row['content'])} for row in rows]


def _error(errors, asset, code, field, message):
    errors.append({'asset_id': asset.get('id'), 'code': code, 'field': field, 'message': message})


def validate_candidate(snapshot=None):
    if snapshot is None: snapshot = candidate_snapshot()
    errors, warnings = [], []
    assets = snapshot.get('assets', [])
    by_id = {a['id']: a for a in assets}
    aliases = {}
    caps = capabilities()
    for asset in assets:
        c = asset.get('content', {}); kind = asset['kind']
        if not isinstance(c, dict):
            _error(errors, asset, 'invalid_content', 'content', 'Content must be an object.'); continue
        if kind not in KINDS: _error(errors, asset, 'invalid_kind', 'kind', 'Unknown asset kind.')
        typed_strings = ('description', 'body', 'definition', 'concept_type', 'measure', 'units', 'date_basis',
                         'return_basis', 'field', 'from_id', 'to_id', 'handler', 'method', 'output_profile_id',
                         'detail', 'detail_level', 'chart_preference', 'question', 'answer', 'quality')
        malformed = False
        for field in typed_strings:
            if field in c and not isinstance(c[field], str):
                _error(errors, asset, 'invalid_text', field, 'Use text for this field.'); malformed = True
        for field in ('aliases', 'approved_tools', 'required_concepts', 'allowed_filters', 'trigger_examples', 'required_sections', 'caveats'):
            if field in c and (not isinstance(c[field], list) or any(not isinstance(value, str) for value in c[field])):
                _error(errors, asset, 'invalid_text_list', field, 'Use a list of text values.'); malformed = True
        if malformed: continue
        for field in ('aliases', 'source_refs'):
            if field in c and not isinstance(c[field], list): _error(errors, asset, 'invalid_list', field, 'Use a list.')
        if kind in ('knowledge', 'ontology'):
            if not any(isinstance(c.get(field), str) and c[field].strip() for field in ('description', 'body', 'definition')):
                _error(errors, asset, 'definition_required', 'description', 'Describe what this means.')
            alias_values = c.get('aliases', []) if isinstance(c.get('aliases', []), list) else []
            if kind == 'ontology': alias_values = [asset['name']] + alias_values
            for alias in alias_values:
                if not isinstance(alias, str) or not alias.strip():
                    _error(errors, asset, 'invalid_alias', 'aliases', 'Aliases must be nonempty text.'); continue
                key = ' '.join(alias.casefold().split())
                if key in aliases and aliases[key] != asset['id']:
                    _error(errors, asset, 'alias_conflict', 'aliases', f'Alias “{alias}” also belongs to {aliases[key]}.')
                aliases[key] = asset['id']
        if kind == 'ontology':
            concept_type = c.get('concept_type', 'concept')
            if concept_type not in ('concept', 'metric', 'entity', 'relationship'):
                _error(errors, asset, 'invalid_concept_type', 'concept_type', 'Choose concept, metric, entity or relationship.')
            if c.get('measure') and c['measure'] not in caps['measures']:
                _error(errors, asset, 'needs_data_support', 'measure', 'This measure has no approved executable mapping.')
            if c.get('field') and c['field'] not in caps['dimensions']:
                _error(errors, asset, 'needs_data_support', 'field', 'This field has no approved executable mapping.')
            if concept_type == 'metric' and not c.get('measure'):
                if c.get('documentary') is True or c.get('executable') is False:
                    _error(warnings, asset, 'documentary_only', 'measure', 'This definition is documentary and cannot create a new calculation.')
                else:
                    _error(errors, asset, 'needs_data_support', 'measure', 'Select an approved measure, or explicitly mark the concept documentary.')
            if c.get('measure'):
                for field in ('units', 'date_basis', 'return_basis'):
                    if not c.get(field): _error(errors, asset, 'metric_basis_required', field, 'Executable metrics must declare units, date basis and return basis.')
                measure = c['measure']
                canonical_units = ('cents/order' if measure == 'aov_cents' else 'cents/unit' if measure == 'avg_price_cents'
                                   else 'cents' if measure.endswith('_cents') else 'percent' if measure.endswith('_pct')
                                   else 'orders' if measure == 'orders' else 'customers' if measure == 'identified_buyers' else 'units')
                if c.get('units') and c['units'] != canonical_units:
                    _error(errors, asset, 'unit_mapping_mismatch', 'units', f'This approved measure returns {canonical_units}; display conversions belong in the answer layer.')
            if c.get('date_basis') and c['date_basis'] not in caps['date_bases']:
                _error(errors, asset, 'invalid_date_basis', 'date_basis', 'Choose sale_date, return_date or snapshot_date.')
            if c.get('return_basis') and c['return_basis'] not in caps['return_bases']:
                _error(errors, asset, 'invalid_return_basis', 'return_basis', 'Choose an approved return basis.')
            if c.get('measure') and c.get('date_basis') != 'sale_date':
                _error(errors, asset, 'needs_data_support', 'date_basis', 'The approved query measures use sale dates; other date grains require a developer adapter.')
            if c.get('measure') and c.get('return_basis') == 'return_date':
                _error(errors, asset, 'needs_data_support', 'return_basis', 'Return-date queries require their dedicated recipe; this mapping uses sales-cohort measures.')
            if concept_type == 'relationship':
                for field in ('from_id', 'to_id'):
                    target = by_id.get(c.get(field))
                    if not target or target['kind'] != 'ontology': _error(errors, asset, 'missing_reference', field, 'Select an ontology concept included in this release.')
        if kind == 'skill':
            for field in ('description', 'method'):
                if not isinstance(c.get(field), str) or not c[field].strip(): _error(errors, asset, 'skill_field_required', field, 'Describe the purpose and method.')
            handler = c.get('handler', 'method_only')
            if handler not in caps['handlers']: _error(errors, asset, 'unknown_handler', 'handler', 'This operation needs developer implementation; choose an approved handler.')
            if asset.get('built_in') and asset['id'].startswith('skill-') and handler != 'playbook:' + asset['id'][6:]:
                _error(errors, asset, 'builtin_handler_changed', 'handler', 'The built-in handler is stable. Duplicate this skill to select a different handler.')
            for field in ('approved_tools', 'required_concepts', 'allowed_filters', 'trigger_examples'):
                if field in c and not isinstance(c[field], list): _error(errors, asset, 'invalid_list', field, 'Use a list.')
            for tool in c.get('approved_tools', []) if isinstance(c.get('approved_tools', []), list) else []:
                if tool not in caps['tools']: _error(errors, asset, 'unsupported_tool', 'approved_tools', 'Tool is not permitted: ' + str(tool))
            for field in c.get('allowed_filters', []) if isinstance(c.get('allowed_filters', []), list) else []:
                if field not in caps['dimensions']: _error(errors, asset, 'unsupported_filter', 'allowed_filters', 'Filter is not supported: ' + str(field))
            for dependency in c.get('required_concepts', []) if isinstance(c.get('required_concepts', []), list) else []:
                target = by_id.get(dependency) if isinstance(dependency, str) else None
                if not target or target['kind'] not in ('ontology', 'knowledge'):
                    _error(errors, asset, 'missing_dependency', 'required_concepts', 'Required concept is not included: ' + str(dependency))
            if handler.startswith('playbook:') and 'run_playbook' not in c.get('approved_tools', []):
                _error(errors, asset, 'missing_tool', 'approved_tools', 'An executable playbook requires the approved run_playbook tool.')
        if kind in ('skill', 'example') and c.get('output_profile_id'):
            target = by_id.get(c['output_profile_id'])
            if not target or target['kind'] != 'output_profile': _error(errors, asset, 'missing_profile', 'output_profile_id', 'Choose an output profile included in this release.')
        if kind == 'output_profile':
            if c.get('detail', c.get('detail_level')) not in ('concise', 'standard', 'detailed'):
                _error(errors, asset, 'invalid_detail', 'detail', 'Choose concise, standard or detailed.')
            if c.get('chart_preference', 'auto') not in ('auto', 'chart', 'table'):
                _error(errors, asset, 'invalid_chart_preference', 'chart_preference', 'Choose auto, chart or table.')
            for field in ('show_evidence', 'show_scope', 'show_limitations'):
                if c.get(field, True) is not True: _error(errors, asset, 'required_safeguard', field, 'Profiles must retain evidence, scope and material limitations.')
            if c.get('show_sources', True) is not True: _error(errors, asset, 'required_safeguard', 'show_sources', 'Source citations must remain available.')
            rows = c.get('table_rows', c.get('max_table_rows', 10))
            if isinstance(rows, bool) or not isinstance(rows, int) or not 1 <= rows <= 100:
                _error(errors, asset, 'invalid_table_rows', 'max_table_rows', 'Choose between 1 and 100 preview rows.')
            if not isinstance(c.get('required_sections', []), list): _error(errors, asset, 'invalid_list', 'required_sections', 'Use a list of section names.')
        if kind == 'example':
            for field in ('question', 'answer'):
                if not isinstance(c.get(field), str) or not c[field].strip(): _error(errors, asset, 'example_field_required', field, 'Provide the example question and answer.')
            if c.get('quality', 'good') not in ('good', 'bad'): _error(errors, asset, 'invalid_example_quality', 'quality', 'Choose good or bad.')
        if kind == 'evaluation_suite':
            from .workspace_evaluations import validate_suite
            for message in validate_suite(c):
                _error(errors, asset, 'invalid_evaluation_suite', 'cases', message)
            cases = c.get('cases', [])
            if not isinstance(cases, list) or not cases:
                _error(errors, asset, 'evaluation_cases_required', 'cases', 'Add at least one evaluation case.')
            elif len(cases) > 200:
                _error(errors, asset, 'too_many_cases', 'cases', 'A suite may contain at most 200 cases.')
            else:
                seen = set()
                for index, case in enumerate(cases):
                    if not isinstance(case, dict) or not isinstance(case.get('id'), str) or not case['id']:
                        _error(errors, asset, 'invalid_case', f'cases.{index}', 'Each case needs a stable ID.'); continue
                    if case['id'] in seen: _error(errors, asset, 'duplicate_case', f'cases.{index}.id', 'Case IDs must be unique within the suite.')
                    seen.add(case['id'])
                    if not case.get('question'): _error(errors, asset, 'case_question_required', f'cases.{index}.question', 'Add the question under test.')
    return {'valid': not errors, 'errors': errors, 'warnings': warnings, 'asset_count': len(assets), 'snapshot_hash': snapshot.get('snapshot_hash')}


def validate_asset(asset_id):
    snapshot = candidate_snapshot([asset_id])
    validation = validate_candidate(snapshot)
    validation['errors'] = [e for e in validation['errors'] if e['asset_id'] == asset_id or e['code'] == 'alias_conflict']
    validation['warnings'] = [e for e in validation['warnings'] if e['asset_id'] == asset_id]
    validation['valid'] = not validation['errors']
    return validation


def create_candidate_release(asset_ids=None, name='Workspace candidate', rationale='', operator='local-admin'):
    ensure_initialized()
    with storage.connection() as con:
        con.execute('BEGIN IMMEDIATE')
        snapshot = _candidate(con, asset_ids)
        validation = validate_candidate(snapshot)
        identity = 'release-' + uuid.uuid4().hex[:20]
        con.execute('INSERT INTO workspace_releases(id,name,parent_release_id,asset_versions,snapshot_hash,validation,operator,rationale) VALUES(?,?,?,?,?,?,?,?)',
                    (identity, _name(name), snapshot['parent_release_id'], _json(snapshot['asset_versions']), snapshot['snapshot_hash'], _json(validation), str(operator)[:100], str(rationale)[:4000]))
    return get_release(identity)


def _release_record(con, row):
    result = dict(row)
    result['asset_versions'] = json.loads(result['asset_versions'])
    result['validation'] = json.loads(result['validation'])
    result['release_id'] = result['id']
    activation = con.execute('SELECT * FROM workspace_activations WHERE release_id=? ORDER BY rowid DESC LIMIT 1', (row['id'],)).fetchone()
    result['status'] = 'active' if _active_id(con) == row['id'] else 'published' if activation else 'candidate'
    result['last_activation'] = dict(activation) if activation else None
    return result


def get_release(release_id):
    ensure_initialized()
    with storage.connection() as con:
        row = con.execute('SELECT * FROM workspace_releases WHERE id=?', (release_id,)).fetchone()
        if not row: raise WorkspaceError('Release not found.', 'release_not_found', 404)
        return _release_record(con, row)


def list_releases():
    ensure_initialized()
    with storage.connection() as con:
        return [_release_record(con, row) for row in con.execute('SELECT * FROM workspace_releases ORDER BY rowid DESC').fetchall()]


def _evaluation_gate_state(con, run_id, candidate_hash):
    """Detect a concurrent review/new live run between gate check and commit."""
    if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='workspace_evaluation_runs'").fetchone():
        return None
    rows = con.execute('''SELECT id,status,updated,
        json_extract(payload,'$.review') AS review,
        json_extract(payload,'$.summary') AS summary,
        json_extract(payload,'$.completed_cases') AS completed_cases,
        json_extract(payload,'$.total_cases') AS total_cases
        FROM workspace_evaluation_runs
        WHERE id=? OR json_extract(payload,'$.candidate.snapshot_hash')=? ORDER BY id''', (run_id, candidate_hash)).fetchall()
    return _hash([dict(row) for row in rows])


def publish(release_id, expected_active_release_id, operator='local-admin', rationale='', evaluation_run_id=None):
    ensure_initialized()
    snapshot = get_snapshot(release_id)
    validation = validate_candidate(snapshot)
    if not validation['valid']:
        raise WorkspaceError('Fix validation errors before publishing.', 'publication_validation_failed', 422, validation['errors'])
    if not evaluation_run_id:
        raise WorkspaceError('Run the deterministic evaluation suite against this candidate before publishing.', 'evaluation_required', 422)
    with storage.connection() as con:
        gate_state = _evaluation_gate_state(con, evaluation_run_id, snapshot['snapshot_hash'])
    from .workspace_evaluations import publication_gate
    gate = publication_gate(evaluation_run_id, snapshot)
    if not gate.get('passed'):
        raise WorkspaceError('The evaluation run does not pass this candidate’s release gates.', 'evaluation_gate_failed', 422, gate.get('errors', []))
    with storage.connection() as con:
        con.execute('BEGIN IMMEDIATE')
        active = _active_id(con)
        if active != expected_active_release_id:
            raise WorkspaceError('The active release changed. Review the current release and retry.', 'stale_active_release', 409)
        if snapshot['parent_release_id'] != active:
            raise WorkspaceError('This candidate was built from an older release. Create a fresh candidate.', 'stale_candidate', 409)
        if gate_state != _evaluation_gate_state(con, evaluation_run_id, snapshot['snapshot_hash']):
            raise WorkspaceError('Evaluation or review changed during publication. Reload the run and retry.', 'stale_evaluation', 409)
        con.execute('UPDATE workspace_active SET release_id=? WHERE singleton=1', (release_id,))
        con.execute('INSERT INTO workspace_activations(id,release_id,previous_release_id,action,operator,rationale,evaluation_run_id) VALUES(?,?,?,?,?,?,?)',
                    (str(uuid.uuid4()), release_id, active, 'publish', str(operator)[:100], str(rationale)[:4000], evaluation_run_id))
    return get_release(release_id)


def rollback(release_id, expected_active_release_id, operator='local-admin', rationale=''):
    ensure_initialized()
    with storage.connection() as con:
        con.execute('BEGIN IMMEDIATE')
        snapshot = _get_snapshot(con, release_id)
        if _active_id(con) != expected_active_release_id:
            raise WorkspaceError('The active release changed. Reload before rolling back.', 'stale_active_release', 409)
        if not con.execute('SELECT 1 FROM workspace_activations WHERE release_id=?', (release_id,)).fetchone():
            raise WorkspaceError('Rollback requires a previously published release.', 'unpublished_rollback', 422)
        if not snapshot['validation']['valid']:
            raise WorkspaceError('This release did not pass validation.', 'invalid_rollback', 422)
        con.execute('UPDATE workspace_active SET release_id=? WHERE singleton=1', (release_id,))
        con.execute('INSERT INTO workspace_activations(id,release_id,previous_release_id,action,operator,rationale) VALUES(?,?,?,?,?,?)',
                    (str(uuid.uuid4()), release_id, expected_active_release_id, 'rollback', str(operator)[:100], str(rationale)[:4000]))
    return get_release(release_id)


def _frozen_index(snapshot):
    from .context import ContextIndex, tokens
    index = ContextIndex(files=[])
    for asset in snapshot['assets']:
        if not asset.get('built_in') or asset['kind'] != 'knowledge': continue
        for chunk in asset['content'].get('_reference_chunks', []):
            item = copy.deepcopy(chunk)
            item['terms'] = Counter(tokens(item['text']))
            item['heading_terms'] = set(tokens(item['heading'].split(' > ')[-1]))
            item['asset_id'] = asset['id']; item['version_id'] = asset['version_id']
            item['original_source'] = item['source']
            item['source'] = 'workspace/' + asset['id'] + '/' + asset['version_id']
            item['source_hash'] = asset['content'].get('source_refs', [{}])[0].get('sha256', asset['content_hash'])
            item['content_hash'] = asset['content_hash']; item['hash_basis'] = 'source_bytes'
            item['release_id'] = snapshot.get('release_id')
            index.chunks.append(item)
    index.df = Counter(t for chunk in index.chunks for t in chunk['terms'])
    index.average_length = sum(sum(c['terms'].values()) for c in index.chunks) / max(1, len(index.chunks))
    return index


def search_snapshot(snapshot, query, limit=6):
    """Search a supplied frozen snapshot. Evaluation cases never reach this path."""
    from .context import tokens
    if not isinstance(query, str): raise WorkspaceError('The retrieval query must be text.', 'invalid_query')
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 12:
        raise WorkspaceError('Choose 1–12 retrieval results.', 'invalid_limit')
    terms = set(tokens(query[:4000])); scored = []
    roles = {'knowledge': 'domain_reference', 'ontology': 'metric_contract', 'skill': 'playbook', 'example': 'worked_example'}
    for asset in snapshot['assets']:
        if asset['kind'] not in roles: continue
        if asset.get('built_in') and (asset['kind'] == 'knowledge' or asset.get('is_baseline', False)): continue
        content = asset['content']
        # Any evaluator/expected-answer metadata stays hidden even if an example was copied.
        safe = {key: value for key, value in content.items() if key not in ('expected', 'cases', 'golden', 'goldens', 'expected_answer', 'expected_sql', 'grader_settings', 'contract', '_reference_chunks')}
        body = _json(_reference_value(safe))
        aliases = content.get('aliases', [])
        aliases = [value for value in aliases if isinstance(value, str)] if isinstance(aliases, list) else []
        title_terms = set(tokens(asset['name'] + ' ' + ' '.join(aliases)))
        parts = [body[i:i+5000] for i in range(0, len(body), 5000)]
        for index, text in enumerate(parts):
            score = len(terms.intersection(set(tokens(text)))) + 4 * len(terms.intersection(title_terms))
            if not score: continue
            scored.append((score, asset['id'], index, {'source': 'workspace/' + asset['id'] + '/' + asset['version_id'],
                'line': index + 1, 'line_end': index + 1, 'heading': asset['name'], 'role': roles[asset['kind']],
                'text': text, 'source_note': 'Published workspace reference; definitions and examples are not measured evidence. Tool permissions remain enforced by code.',
                'asset_id': asset['id'], 'version_id': asset['version_id'], 'source_hash': asset['content_hash'],
                'release_id': snapshot.get('release_id'), 'truncated': len(parts) > 1}))
    scored.sort(key=lambda item: (-item[0], item[1], item[2]))
    results = []; seen = set(); size = 0
    for _, identity, _, result in scored:
        if identity in seen or size + len(result['text']) > 18000: continue
        results.append(result); seen.add(identity); size += len(result['text'])
        if len(results) >= limit: break
    builtins = _frozen_index(snapshot).search(query, limit)
    # Custom guidance gets at most half the result slots; physical data and
    # existing metric contracts remain available in the same frozen release.
    overlay = results[:max(1, limit // 2)]
    return overlay + builtins[:limit - len(overlay)]


def snapshot_context(snapshot, question, profile_id=None, output_profile_id=None):
    sources = search_snapshot(snapshot, question)
    by_id = {a['id']: a for a in snapshot['assets']}
    profile_id = output_profile_id or profile_id or 'business-review'
    profile = by_id.get(profile_id)
    if not profile or profile['kind'] != 'output_profile':
        raise WorkspaceError('This output profile is not included in the selected release.', 'profile_not_found', 422)
    selected = [by_id[s['asset_id']] for s in sources if by_id[s['asset_id']]['kind'] == 'skill']
    from .context import tokens
    words = set(tokens(question))
    scored_skills = []
    for skill in snapshot['assets']:
        if skill['kind'] != 'skill': continue
        content = skill['content']
        triggers = content.get('trigger_examples', [])
        triggers = [value for value in triggers if isinstance(value, str)] if isinstance(triggers, list) else []
        score = len(words.intersection(tokens(skill['name'] + ' ' + ' '.join(triggers))))
        if score: scored_skills.append((score, skill['id'], skill))
    for _, _, skill in sorted(scored_skills, key=lambda item: (-item[0], item[1]))[:2]:
        if skill not in selected: selected.append(skill)
    provenance = {'release_id': snapshot.get('release_id'), 'snapshot_hash': snapshot['snapshot_hash'],
                  'asset_versions': dict(snapshot['asset_versions']),
                  'skill_versions': {a['id']: a['version_id'] for a in selected},
                  'output_profile_id': profile_id, 'output_profile_version': profile['version_id'],
                  'sources': [{'asset_id': s['asset_id'], 'version_id': s['version_id'], 'sha256': s['source_hash']} for s in sources]}
    return {'context_sources': sources, 'skills': [_model_asset(a) for a in selected], 'output_profile': _model_asset(profile), 'provenance': provenance}


MODEL_FIELDS = {
    'skill': {'description', 'slug', 'handler', 'trigger_examples', 'required_concepts', 'approved_tools', 'method', 'required_inputs', 'allowed_filters', 'output_profile_id', 'caveats', 'source_refs'},
    'output_profile': {'description', 'detail', 'detail_level', 'required_sections', 'chart_preference', 'show_evidence', 'show_scope', 'show_limitations', 'show_sources', 'show_method', 'max_table_rows', 'table_rows', 'tone'},
}
HIDDEN_FIELDS = {'expected', 'cases', 'golden', 'goldens', 'expected_answer', 'expected_sql', 'grader_settings', '_reference_chunks'}


def _reference_value(value):
    if isinstance(value, dict): return {key: _reference_value(item) for key, item in value.items() if key not in HIDDEN_FIELDS}
    if isinstance(value, list): return [_reference_value(item) for item in value]
    return value


def _model_asset(asset):
    result = {key: copy.deepcopy(asset[key]) for key in ('id', 'kind', 'name', 'version_id', 'content_hash') if key in asset}
    result['content'] = _reference_value({key: value for key, value in asset['content'].items() if key in MODEL_FIELDS.get(asset['kind'], set())})
    return result


def read_version_source(source):
    """Read a registry reference by its exact recorded version, never a path."""
    parts = source.split('/') if isinstance(source, str) else []
    if len(parts) != 3 or parts[0] != 'workspace': raise WorkspaceError('Unknown workspace source.', 'source_not_found', 404)
    ensure_initialized()
    with storage.connection() as con:
        row = con.execute('SELECT v.*,a.kind FROM workspace_versions v JOIN workspace_assets a ON a.id=v.asset_id WHERE v.asset_id=? AND v.id=?', (parts[1], parts[2])).fetchone()
        if not row or row['kind'] == 'evaluation_suite': raise WorkspaceError('Source not found.', 'source_not_found', 404)
        content = _reference_value(json.loads(row['content']))
        body = content.get('body') if row['kind'] == 'knowledge' else None
        text = body if isinstance(body, str) else json.dumps(content, ensure_ascii=False, indent=2)
        return {'source': source, 'text': text, 'name': row['name'], 'sha256': hashlib.sha256(text.encode()).hexdigest(),
                'content_hash': row['content_hash'], 'version_id': row['id']}


def preview(query, asset_ids=None, limit=6):
    snapshot = candidate_snapshot(asset_ids)
    validation = validate_candidate(snapshot)
    invalid = {error['asset_id'] for error in validation['errors']}
    preview_snapshot = {**snapshot, 'assets': [asset for asset in snapshot['assets'] if asset['id'] not in invalid]}
    return {'snapshot': {k: v for k, v in snapshot.items() if k != 'assets'},
            'results': search_snapshot(preview_snapshot, query, limit), 'validation': validation,
            'excluded_asset_ids': sorted(invalid)}


def output_profiles():
    return [a for a in active_snapshot()['assets'] if a['kind'] == 'output_profile']


def status():
    assets = list_assets()
    available = capabilities()
    available['profiles'] = [a['id'] for a in assets if a['kind'] == 'output_profile']
    return {'active_release': get_release(active_snapshot()['release_id']),
            'counts': {kind: sum(a['kind'] == kind for a in assets) for kind in KINDS},
            'draft_count': sum(a['status'] == 'draft' for a in assets), 'capabilities': available}


ISSUE_TYPES = ('scope', 'definition', 'calculation', 'chart', 'explanation', 'citation', 'other')


def create_feedback(analysis_id, issue_types=None, correction=''):
    ensure_initialized()
    issue_types = issue_types or ['other']
    if not isinstance(issue_types, list) or any(issue not in ISSUE_TYPES for issue in issue_types):
        raise WorkspaceError('Choose valid feedback issue types.', 'invalid_issue_type')
    if not isinstance(correction, str) or len(correction) > 8000: raise WorkspaceError('Correction must be at most 8,000 characters.', 'invalid_correction')
    with storage.connection() as con:
        row = con.execute('SELECT question,payload FROM analyses WHERE id=?', (analysis_id,)).fetchone()
        if not row: raise WorkspaceError('Answer not found.', 'analysis_not_found', 404)
        answer = json.loads(row['payload']); identity = 'feedback-' + uuid.uuid4().hex[:20]
        con.execute('INSERT INTO workspace_feedback(id,analysis_id,issue_types,correction,status,revision,original_question,original_answer,provenance,evidence) VALUES(?,?,?,?,?,?,?,?,?,?)',
                    (identity, analysis_id, _json(issue_types), correction, 'new', 1, row['question'], answer.get('answer', ''),
                     _json(answer.get('workspace', answer.get('workspace_provenance', answer.get('provenance', {})))), _json(answer.get('outputs', []))))
    return get_feedback(identity)


def _feedback_row(row):
    result = dict(row)
    for field in ('issue_types', 'provenance', 'evidence'): result[field] = json.loads(result[field])
    return result


def get_feedback(identity):
    ensure_initialized()
    with storage.connection() as con:
        row = con.execute('SELECT * FROM workspace_feedback WHERE id=?', (identity,)).fetchone()
        if not row: raise WorkspaceError('Feedback not found.', 'feedback_not_found', 404)
        return _feedback_row(row)


def list_feedback():
    ensure_initialized()
    with storage.connection() as con:
        return [_feedback_row(row) for row in con.execute('SELECT * FROM workspace_feedback ORDER BY rowid DESC LIMIT 500').fetchall()]


def update_feedback(identity, expected_revision, status, correction=None):
    if status not in ('new', 'reviewed', 'resolved', 'dismissed'):
        raise WorkspaceError('Choose new, reviewed, resolved or dismissed.', 'invalid_feedback_status')
    ensure_initialized()
    with storage.connection() as con:
        con.execute('BEGIN IMMEDIATE')
        row = con.execute('SELECT * FROM workspace_feedback WHERE id=?', (identity,)).fetchone()
        if not row: raise WorkspaceError('Feedback not found.', 'feedback_not_found', 404)
        if row['revision'] != expected_revision or isinstance(expected_revision, bool):
            raise WorkspaceError('Feedback changed. Reload before updating.', 'stale_revision', 409)
        if correction is not None and (not isinstance(correction, str) or len(correction) > 8000):
            raise WorkspaceError('Correction must be at most 8,000 characters.', 'invalid_correction')
        con.execute('UPDATE workspace_feedback SET status=?,correction=?,revision=revision+1,updated=CURRENT_TIMESTAMP WHERE id=?',
                    (status, row['correction'] if correction is None else correction, identity))
    return get_feedback(identity)


def convert_feedback(identity, expected_revision, suite_id=None, case=None):
    """Create a draft case. A correction is a review note, never an auto-golden."""
    ensure_initialized()
    with storage.connection() as con:
        con.execute('BEGIN IMMEDIATE')
        row = con.execute('SELECT * FROM workspace_feedback WHERE id=?', (identity,)).fetchone()
        if not row: raise WorkspaceError('Feedback not found.', 'feedback_not_found', 404)
        if row['revision'] != expected_revision or isinstance(expected_revision, bool): raise WorkspaceError('Feedback changed. Reload before converting.', 'stale_revision', 409)
        if row['status'] != 'reviewed': raise WorkspaceError('Review this feedback before creating a regression case.', 'feedback_review_required', 422)
        if row['linked_case_id']: raise WorkspaceError('This feedback already has a regression case.', 'feedback_already_converted', 409)
        case = copy.deepcopy(case or {})
        case_id = case.get('id', 'regression-' + uuid.uuid4().hex[:12])
        case.update({'id': case_id, 'question': case.get('question', row['original_question']),
                     'name': case.get('name', 'Regression from reviewed feedback'), 'category': case.get('category', 'feedback'),
                     'mode': case.get('mode', 'live'), 'requires_human_review': True,
                     'review_status': 'needs_expected_result', 'feedback_id': identity, 'review_note': row['correction']})
        case.setdefault('contract', {'type': 'live_answer', 'inputs': {}})
        if suite_id:
            asset = con.execute('SELECT * FROM workspace_assets WHERE id=? AND kind=?', (suite_id, 'evaluation_suite')).fetchone()
            if not asset: raise WorkspaceError('Evaluation suite not found.', 'suite_not_found', 404)
            draft = con.execute('SELECT * FROM workspace_drafts WHERE asset_id=?', (suite_id,)).fetchone()
            if draft: content, revision, name = json.loads(draft['content']), draft['revision'], draft['name']
            else:
                active = _get_snapshot(con, _active_id(con))
                current = next((a for a in active['assets'] if a['id'] == suite_id), None)
                if not current: raise WorkspaceError('Suite has no draft or active version.', 'suite_not_found', 404)
                content, revision, name = current['content'], 0, current['name']
            if any(item.get('id') == case_id for item in content.get('cases', [])): raise WorkspaceError('Case ID already exists in this suite.', 'case_id_conflict', 409)
            content.setdefault('cases', []).append(case)
        else:
            suite_id = 'regression-' + uuid.uuid4().hex[:12]
            name, revision = 'Reviewed feedback regressions', 0
            content = {'description': 'Cases require reviewed expectations before release qualification.', 'review_status': 'needs_review', 'cases': [case]}
            con.execute('INSERT INTO workspace_assets(id,kind,name,owner) VALUES(?,?,?,?)', (suite_id, 'evaluation_suite', name, 'local-admin'))
        con.execute('INSERT INTO workspace_drafts(asset_id,revision,name,content) VALUES(?,?,?,?) ON CONFLICT(asset_id) DO UPDATE SET revision=excluded.revision,content=excluded.content,updated=CURRENT_TIMESTAMP',
                    (suite_id, revision + 1, name, _content(content)))
        con.execute('UPDATE workspace_feedback SET linked_asset_id=?,linked_case_id=?,revision=revision+1,updated=CURRENT_TIMESTAMP WHERE id=?', (suite_id, case_id, identity))
    return {'feedback': get_feedback(identity), 'asset': get_asset(suite_id)}
