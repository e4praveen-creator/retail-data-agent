"""Bounded HTTP intake and response policy for the trusted local application.

The app header and browser-origin checks protect the local browser boundary;
they do not authenticate users. The supported launchers bind host loopback.
"""

import asyncio
import json
import logging
import re
import uuid

from fastapi import Request
from fastapi.responses import Response

LOG = logging.getLogger('retail_app')
MAX_REQUEST_BYTES = 64 * 1024
MAX_WORKSPACE_REQUEST_BYTES = 768 * 1024
BODY_TIMEOUT_SECONDS = 10
READ_METHODS = {'GET', 'HEAD', 'OPTIONS'}
LOCAL_ORIGINS = {
    f'http://{host}:{port}'
    for host in ('localhost', '127.0.0.1')
    for port in (8765, 8766)
}
HASHED_CHUNK = re.compile(r'^/static/chunks/[a-zA-Z0-9_-]+-[A-Z0-9]{8}\.js$')
SECURITY_HEADERS = {
    'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'none'; form-action 'self'",
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'Referrer-Policy': 'no-referrer',
    'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
}


async def _intake(request: Request):
    """Reject before dispatch; bound both declared and streamed request bodies."""
    if request.headers.get('range'):
        return Response('Range requests are not supported', status_code=400)
    if request.method not in READ_METHODS:
        origin = request.headers.get('origin')
        if origin and origin not in LOCAL_ORIGINS:
            return Response('Local app origin required', status_code=403)
        if request.headers.get('x-retail-app') != 'local':
            return Response('App request header required', status_code=403)

    limit = (MAX_WORKSPACE_REQUEST_BYTES
             if request.url.path.startswith('/api/workspace/') else MAX_REQUEST_BYTES)
    try:
        declared = int(request.headers.get('content-length', '0'))
        if declared < 0:
            raise ValueError()
    except ValueError:
        return Response('Invalid content length', status_code=400)
    if declared > limit:
        return Response('Request body is too large', status_code=413)
    if request.method in READ_METHODS:
        return None

    chunks = []
    size = 0
    try:
        async with asyncio.timeout(BODY_TIMEOUT_SECONDS):
            async for chunk in request.stream():
                size += len(chunk)
                if size > limit:
                    return Response('Request body is too large', status_code=413)
                chunks.append(chunk)
    except TimeoutError:
        return Response('Request body timed out', status_code=408)
    # Starlette's cached request passes this bounded body to the route handler.
    request._body = b''.join(chunks)
    return None


async def local_origin(request: Request, call_next):
    request_id = str(uuid.uuid4())
    try:
        response = await _intake(request)
        if response is None:
            response = await call_next(request)
    except Exception as exc:
        # Never log question text, provider payloads, credentials or raw errors.
        LOG.error('Request failed id=%s category=%s', request_id, type(exc).__name__)
        response = Response(json.dumps({
            'detail': 'The request could not be completed. Try again or check the local service.',
            'request_id': request_id,
        }), status_code=500, media_type='application/json')
    for key, value in SECURITY_HEADERS.items():
        response.headers[key] = value
    response.headers['X-Request-ID'] = request_id
    # Only content-addressed build chunks can persist across releases. Never
    # cache private APIs, entry scripts, guide responses, errors or redirects.
    response.headers['Cache-Control'] = (
        'public, max-age=31536000, immutable'
        if request.method in {'GET', 'HEAD'} and response.status_code == 200
        and HASHED_CHUNK.fullmatch(request.url.path)
        else 'no-store'
    )
    return response
