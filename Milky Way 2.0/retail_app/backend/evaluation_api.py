"""Local operator evaluation routes; protected by the application's local origin middleware."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from . import workspace_evaluations as evaluations
from .workspace_assets import WorkspaceError

router = APIRouter(prefix='/api/evaluations', tags=['Workspace evaluations'])

class RunRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    suite_id: str = Field(min_length=1, max_length=160)
    baseline_release_id: str | None = None
    candidate_release_id: str | None = None
    candidate_version_ids: list[str] | None = Field(default=None, max_length=300)
    mode: str = 'deterministic'
    max_cases: int = Field(default=120, ge=1, le=120, strict=True)
    max_model_calls: int = Field(default=0, ge=0, le=40, strict=True)
    max_tokens: int = Field(default=0, ge=0, le=200000, strict=True)
    confirm_billable: bool = Field(default=False, strict=True)

class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reviewer: str = Field(min_length=1, max_length=120)
    decision: str
    notes: str = Field(min_length=1, max_length=4000)


def _call(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except WorkspaceError as error:
        raise HTTPException(status_code=error.status, detail=error.detail()) from error
    except ValueError as error:
        missing = str(error) in ('Evaluation run not found.', 'Evaluation suite not found.')
        raise HTTPException(status_code=404 if missing else 400,
                            detail={'code': 'evaluation_not_found' if missing else 'invalid_evaluation_request',
                                    'message': str(error)}) from error

@router.get('/suites')
def suites():
    return {'suites': _call(evaluations.list_suites), 'limits': {'max_cases': evaluations.MAX_CASES,
            'max_model_calls': evaluations.MAX_MODEL_CALLS, 'max_tokens': evaluations.MAX_TOKENS,
            'queue_capacity': evaluations.MAX_QUEUED, 'workers': 1}}

@router.post('/runs')
def create_run(request: RunRequest):
    return _call(evaluations.start_run, **request.model_dump())

@router.get('/runs')
def runs():
    return {'runs': _call(evaluations.list_runs)}

@router.get('/runs/{run_id}')
def run(run_id: str):
    return _call(evaluations.get_run, run_id)

@router.post('/runs/{run_id}/cancel')
def cancel(run_id: str):
    return _call(evaluations.cancel_run, run_id)

@router.post('/runs/{run_id}/review')
def review(run_id: str, request: ReviewRequest):
    return _call(evaluations.review_run, run_id, **request.model_dump())
