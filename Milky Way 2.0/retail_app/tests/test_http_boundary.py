"""HTTP resource limits and documentation privacy, without data/model access."""

import asyncio
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi import FastAPI, Request
from fastapi.responses import Response
from fastapi.testclient import TestClient

from retail_app.backend import guide_api, http_boundary


class HttpBoundaryTests(unittest.IsolatedAsyncioTestCase):
    def request(self, chunks, **headers):
        async def receive():
            return chunks.pop(0)
        return Request({'type': 'http', 'method': 'POST', 'path': '/api/chat',
                        'headers': [(key.encode(), value.encode()) for key, value in {
                            'x-retail-app': 'local', **headers}.items()]}, receive)

    async def test_streamed_body_enforces_limit_without_content_length(self):
        request = self.request([
            {'type': 'http.request', 'body': b'x' * 5, 'more_body': True},
            {'type': 'http.request', 'body': b'x' * 5, 'more_body': False},
        ])
        with patch.object(http_boundary, 'MAX_REQUEST_BYTES', 8):
            self.assertEqual((await http_boundary._intake(request)).status_code, 413)

    async def test_request_body_deadline_is_bounded(self):
        async def delayed_receive():
            await asyncio.sleep(1)
            return {'type': 'http.request', 'body': b'', 'more_body': False}
        request = self.request([])
        request._receive = delayed_receive
        with patch.object(http_boundary, 'BODY_TIMEOUT_SECONDS', 0.01):
            self.assertEqual((await http_boundary._intake(request)).status_code, 408)

    async def test_bad_lengths_and_range_requests_never_read_body(self):
        for length in ('-1', 'not-a-number'):
            request = self.request([], **{'content-length': length})
            self.assertEqual((await http_boundary._intake(request)).status_code, 400)
        request = self.request([], range='bytes=0-1')
        self.assertEqual((await http_boundary._intake(request)).status_code, 400)

    async def test_bounded_body_is_preserved_for_route_parsing(self):
        request = self.request([
            {'type': 'http.request', 'body': b'{"question":', 'more_body': True},
            {'type': 'http.request', 'body': b'"sales"}', 'more_body': False},
        ])
        self.assertIsNone(await http_boundary._intake(request))
        self.assertEqual(await request.json(), {'question': 'sales'})

    async def test_intake_errors_are_sanitized_and_correlated(self):
        async def failed_route(request):
            raise RuntimeError('sensitive internal details')
        request = self.request([{'type': 'http.request', 'body': b'', 'more_body': False}])
        with self.assertLogs('retail_app', level='ERROR') as logs:
            response = await http_boundary.local_origin(request, failed_route)
        self.assertEqual(response.status_code, 500)
        self.assertNotIn('sensitive', response.body.decode())
        self.assertNotIn('sensitive', ''.join(logs.output))
        self.assertIn(response.headers['X-Request-ID'], response.body.decode())


class AssetPolicyTests(unittest.TestCase):
    def test_only_successful_content_addressed_chunks_are_cacheable(self):
        app = FastAPI()
        app.middleware('http')(http_boundary.local_origin)

        @app.get('/{path:path}')
        def asset(path: str):
            return Response('fixture', status_code=404 if 'missing' in path else 200)

        with TestClient(app) as client:
            cached = client.get('/static/chunks/admin-ABCD1234.js')
            self.assertEqual(cached.headers['Cache-Control'], 'public, max-age=31536000, immutable')
            for path in ('/static/app.js', '/api/status', '/guide', '/',
                         '/static/chunks/guess.js', '/static/chunks/missing-ABCD1234.js'):
                response = client.get(path)
                self.assertEqual(response.headers['Cache-Control'], 'no-store', path)
                self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')


class GuideBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.directory = self.root / 'retail_app/docs/developer'
        self.directory.mkdir(parents=True)
        self.document = self.directory / 'README.md'
        self.document.write_text('')
        self.source = self.root / 'retail_app/backend/example.py'
        self.source.parent.mkdir()
        self.source.write_text('print("example")')
        self.patches = [patch.object(guide_api.data, 'ROOT', self.root),
                        patch.object(guide_api.data, 'APP', self.root / 'retail_app')]
        for item in self.patches:
            item.start()
        app = FastAPI()
        app.include_router(guide_api.router)
        self.client = TestClient(app)
        guide_api._linked_references.cache_clear()

    def tearDown(self):
        self.client.close()
        for item in reversed(self.patches):
            item.stop()
        guide_api._linked_references.cache_clear()
        self.temp.cleanup()

    def test_only_documented_public_references_are_served(self):
        path = 'retail_app/backend/example.py'
        self.assertEqual(self.client.get('/api/guide-file', params={'path': path}).status_code, 404)
        self.document.write_text('[Source](../../backend/example.py)')
        response = self.client.get('/api/guide-file', params={'path': path})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, self.source.read_text())
        self.assertTrue(response.headers['Content-Type'].startswith('text/plain'))
        self.document.write_text('Link removed; signature invalidates its cache.')
        self.assertEqual(self.client.get('/api/guide-file', params={'path': path}).status_code, 404)

    def test_linked_private_files_and_symlinks_still_fail_closed(self):
        private = self.root / 'retail_app/state/private.json'
        private.parent.mkdir()
        private.write_text('{"private": true}')
        secret = self.root / 'retail_app/.env'
        secret.write_text('not-a-real-key')
        link = self.source.parent / 'linked.json'
        link.symlink_to(private)
        self.document.write_text('[State](../../state/private.json)\n[Secret](../../.env)\n[Symlink](../../backend/linked.json)')
        for path in ('retail_app/state/private.json', 'retail_app/.env',
                     'retail_app/backend/linked.json', '../outside.md'):
            self.assertEqual(self.client.get('/api/guide-file', params={'path': path}).status_code, 404)

    def test_link_cache_is_reused_until_document_metadata_changes(self):
        self.document.write_text('[Source](../../backend/example.py)')
        for _ in range(2):
            self.client.get('/api/guide-file', params={'path': 'retail_app/backend/example.py'})
        stats = guide_api._linked_references.cache_info()
        self.assertEqual(stats.misses, 1)
        self.assertEqual(stats.hits, 1)

    def test_missing_handbook_returns_actionable_unavailable_response(self):
        response = self.client.get('/guide')
        self.assertEqual(response.status_code, 503)
        self.assertIn('Build the developer handbook', response.text)
