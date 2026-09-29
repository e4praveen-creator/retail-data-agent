"""Trusted-local administrator API for the versioned improvement workspace."""
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from . import workspace_assets as assets

router = APIRouter(prefix='/api/workspace', tags=['Improve workspace'])


class RequestModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class AssetCreate(RequestModel):
    id: str | None = None
    kind: str
    name: str = Field(min_length=1, max_length=160)
    content: dict[str, Any]
    owner: str = Field(default='local-admin', max_length=100)


class AssetUpdate(RequestModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    content: dict[str, Any]
    expected_revision: int = Field(ge=0, strict=True)


class Preview(RequestModel):
    query: str = Field(default='', max_length=4000)
    asset_ids: list[str] | None = Field(default=None, max_length=300)
    limit: int = Field(default=6, ge=1, le=12)


class Candidate(RequestModel):
    asset_ids: list[str] | None = Field(default=None, max_length=300)
    name: str = Field(default='Workspace candidate', min_length=1, max_length=160)
    rationale: str = Field(default='', max_length=4000)
    operator: str = Field(default='local-admin', max_length=100)


class Activation(RequestModel):
    expected_active_release_id: str
    operator: str = Field(default='local-admin', max_length=100)
    rationale: str = Field(default='', max_length=4000)
    evaluation_run_id: str | None = None


class FeedbackCreate(RequestModel):
    analysis_id: str
    issue_types: list[str] = Field(default_factory=lambda: ['other'], max_length=7)
    correction: str = Field(default='', max_length=8000)


class FeedbackUpdate(RequestModel):
    expected_revision: int = Field(ge=1, strict=True)
    status: str
    correction: str | None = Field(default=None, max_length=8000)


class FeedbackConvert(RequestModel):
    expected_revision: int = Field(ge=1, strict=True)
    suite_id: str | None = None
    case: dict[str, Any] | None = None


class OutputPreview(RequestModel):
    profile_id: str = 'business-review'
    fixture_id: str = 'monthly-sales'
    asset_ids: list[str] | None = None


def _call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except assets.WorkspaceError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail()) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={'code': 'invalid_request', 'message': str(exc)}) from exc


@router.get('/status')
def workspace_status():
    return _call(assets.status)


@router.get('/capabilities')
def workspace_capabilities():
    result = _call(assets.capabilities)
    result['profiles'] = [a['id'] for a in _call(assets.list_assets, 'output_profile')]
    return result


@router.get('/assets')
def list_assets(kind: str | None = None, q: str = Query(default='', max_length=4000)):
    return {'assets': _call(assets.list_assets, kind, q)}


@router.post('/assets', status_code=201)
def create_asset(req: AssetCreate):
    return _call(assets.create_asset, **req.model_dump())


@router.get('/assets/{identity}')
def get_asset(identity: str):
    return _call(assets.get_asset, identity)


@router.put('/assets/{identity}')
def update_asset(identity: str, req: AssetUpdate):
    return _call(assets.update_asset, identity, **req.model_dump())


@router.get('/assets/{identity}/versions')
def versions(identity: str):
    return {'versions': _call(assets.asset_versions, identity)}


@router.post('/assets/{identity}/validate')
def validate_asset(identity: str):
    return _call(assets.validate_asset, identity)


@router.post('/preview')
def preview(req: Preview):
    return _call(assets.preview, **req.model_dump())


@router.get('/sources/{asset_id}/{version_id}')
def source(asset_id: str, version_id: str):
    return _call(assets.read_version_source, 'workspace/' + asset_id + '/' + version_id)


@router.get('/releases')
def releases():
    return {'releases': _call(assets.list_releases), 'active_release_id': _call(assets.active_snapshot)['release_id']}


@router.post('/releases', status_code=201)
def candidate(req: Candidate):
    return _call(assets.create_candidate_release, **req.model_dump())


@router.get('/releases/{identity}')
def release(identity: str):
    return _call(assets.get_release, identity)


@router.post('/releases/{identity}/publish')
def publish(identity: str, req: Activation):
    return _call(assets.publish, identity, **req.model_dump())


@router.post('/releases/{identity}/rollback')
def rollback(identity: str, req: Activation):
    return _call(assets.rollback, identity, **req.model_dump(exclude={'evaluation_run_id'}))


@router.get('/output-profiles')
def profiles():
    return {'profiles': _call(assets.output_profiles)}


@router.get('/feedback')
def feedback():
    return {'feedback': _call(assets.list_feedback)}


@router.post('/feedback', status_code=201)
def create_feedback(req: FeedbackCreate):
    return _call(assets.create_feedback, **req.model_dump())


@router.put('/feedback/{identity}')
def update_feedback(identity: str, req: FeedbackUpdate):
    return _call(assets.update_feedback, identity, **req.model_dump())


@router.post('/feedback/{identity}/convert')
def convert_feedback(identity: str, req: FeedbackConvert):
    return _call(assets.convert_feedback, identity, **req.model_dump())


def measured_output_preview(profile_id='business-review', fixture_id='monthly-sales', asset_ids=None):
    from . import scope
    from .presentation import apply_output_profile
    if fixture_id not in ('monthly-sales', 'channel-sales'):
        raise assets.WorkspaceError('Choose monthly-sales or channel-sales.', 'fixture_not_found', 404)
    snapshot = assets.candidate_snapshot(asset_ids if asset_ids is not None else [profile_id])
    validation = assets.validate_candidate(snapshot)
    errors = [e for e in validation['errors'] if e['asset_id'] == profile_id]
    if errors: raise assets.WorkspaceError('Fix this profile before previewing.', 'profile_validation_failed', 422, errors)
    selected = assets.snapshot_context(snapshot, 'Sales output design preview', profile_id)
    dimension = 'month' if fixture_id == 'monthly-sales' else 'channel_name'
    effective = scope.normalize_scope({'dates': {'start': '2025-01-01', 'end': '2025-03-31'},
                                       'metric': 'sales_before_returns_cents', 'return_basis': 'before_returns', 'filters': []})
    output = scope.query_retail(effective, ['sales_before_returns_cents', 'units', 'orders'], [dimension], False)
    output.update(name='Measured workspace preview', evidence_id='E1')
    presentation = {
        'version': 1, 'sections': list(assets.REQUIRED_SECTIONS), 'playbook_slug': None,
        'headline': 'Measured sales preview for January–March 2025 [E1].',
        'scope': '2025-01-01 through 2025-03-31, all channels/products, grouped by ' + dimension + '.',
        'metric_basis': 'Sales after discounts before returns, monetary values in cents; units and distinct matching orders [E1].',
        'interpretation': 'The table and chart use a fresh warehouse query for this fixed preview scope [E1].',
        'limitations': ['Synthetic retail data; this preview tests presentation and does not measure causal effects.'],
        'next_questions': ['Which business scope should the production answer use?'], 'supporting_evidence_ids': ['E1'],
    }
    payload = {'mode': 'workspace_preview', 'answer': presentation['headline'], 'outputs': [output],
               'presentation': presentation, 'warnings': presentation['limitations'], 'charts': [],
               'checks': [{'name': 'Measured warehouse preview', 'passed': True}], 'scope': effective,
               'workspace': selected['provenance']}
    result = apply_output_profile(payload, selected['output_profile'])
    return {'fixture_id': fixture_id, 'measured': True, 'profile': selected['output_profile'],
            'snapshot_hash': snapshot['snapshot_hash'], 'result': result, 'validation': validation}


@router.post('/output-preview')
def output_preview(req: OutputPreview):
    return _call(measured_output_preview, **req.model_dump())
