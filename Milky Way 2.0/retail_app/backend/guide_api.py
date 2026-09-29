"""Serve the packaged handbook and its explicitly linked public references."""

from functools import lru_cache
from pathlib import Path
import re
from urllib.parse import quote, unquote, urlsplit

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse

from . import data

router = APIRouter()
PRIVATE_PARTS = {'state', 'backups', 'tmp', 'node_modules', 'sources', 'data'}
PUBLIC_SUFFIXES = {
    '.py', '.jsx', '.js', '.json', '.md', '.html', '.png', '.svg', '.mmd',
    '.sql', '.txt', '.yaml', '.yml', '.sh', '.toml',
}


def _public_path(target: Path, root: Path) -> bool:
    """A handbook link can never turn state or secret files into a download."""
    if not target.is_relative_to(root):
        return False
    parts = target.relative_to(root).parts
    if any(part in PRIVATE_PARTS or part.startswith('.') for part in parts):
        return False
    return target.suffix in PUBLIC_SUFFIXES or target.name == 'Dockerfile'


def _reference_signature(directory: Path):
    # Stat rather than read every chapter on each click; changes invalidate the
    # cached link set. Historical state and runtime directories are never scanned.
    return tuple((str(p), p.stat().st_mtime_ns, p.stat().st_size)
                 for p in sorted(directory.rglob('*.md')) if not p.is_symlink())


@lru_cache(maxsize=2)
def _linked_references(root: Path, signature: tuple) -> frozenset:
    allowed = set()
    for filename, _, _ in signature:
        document = Path(filename)
        if not _public_path(document.resolve(), root):
            continue
        for href in re.findall(r'!?\[[^\]]*\]\(([^\n)]+)\)', document.read_text()):
            parsed = urlsplit(href.strip().strip('<>'))
            if not parsed.scheme and not parsed.netloc and parsed.path:
                target = (document.parent / unquote(parsed.path)).resolve()
                if _public_path(target, root):
                    allowed.add(target)
    return frozenset(allowed)


@router.get('/guide')
def developer_guide():
    root = data.ROOT.resolve()
    directory = data.APP / 'docs/developer'

    def local_link(match):
        href = match.group(1)
        parsed = urlsplit(href)
        if href.startswith('#') or parsed.scheme or parsed.netloc:
            return match.group(0)
        target = (directory / unquote(parsed.path)).resolve()
        if not _public_path(target, root):
            return match.group(0)
        return 'href="/api/guide-file?path=' + quote(str(target.relative_to(root)), safe='') + '"'

    handbook = directory / 'HANDBOOK.html'
    if not handbook.is_file():
        raise HTTPException(503, 'Build the developer handbook before serving it.')
    html = re.sub(r'href="([^"]+)"', local_link, handbook.read_text())
    return HTMLResponse(html, headers={'Cache-Control': 'no-store'})


@router.get('/api/guide-file')
def guide_file(path: str = Query(max_length=500)):
    root = data.ROOT.resolve()
    directory = data.APP / 'docs/developer'
    target = (root / path).resolve()
    if (not _public_path(target, root) or not target.is_file()
            or target not in _linked_references(root, _reference_signature(directory))):
        raise HTTPException(404, 'Guide reference not found.')
    if target.suffix in ('.png', '.svg', '.html'):
        return FileResponse(target)
    # Stream source references without interpreting their content as markup.
    return FileResponse(target, media_type='text/plain; charset=utf-8')
