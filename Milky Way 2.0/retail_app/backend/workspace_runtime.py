"""Bridge immutable workspace releases into the existing agent and answer path."""
import copy
from . import workspace_assets
from .presentation import apply_output_profile


def capture(snapshot=None):
    # Copy at the boundary: callers cannot edit a running answer's configuration.
    return copy.deepcopy(snapshot if snapshot is not None else workspace_assets.active_snapshot())


def search(snapshot, query, limit=6):
    return workspace_assets.search_snapshot(snapshot,query,limit=limit)


def settings(snapshot, question, profile_id=None):
    return workspace_assets.snapshot_context(snapshot,question,output_profile_id=profile_id)


def attach(payload, snapshot, question, profile_id=None, resolved=None):
    selected = resolved or settings(snapshot,question,profile_id)
    profile = selected.get('output_profile') or {}
    provenance = copy.deepcopy(selected.get('provenance') or {})
    provenance.update(release_id=snapshot.get('release_id',snapshot.get('id')),
                      snapshot_hash=snapshot.get('snapshot_hash'),
                      asset_versions=copy.deepcopy(snapshot.get('asset_versions',{})),
                      selected_skills=copy.deepcopy(selected.get('skills',[])),
                      output_profile=copy.deepcopy(profile),
                      context_sources=copy.deepcopy(payload.get('context') or selected.get('context_sources',[])))
    payload={**payload,'workspace':provenance}
    return apply_output_profile(payload,profile)
