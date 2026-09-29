"""Repository cleanup boundaries and offline developer-check orchestration."""
from contextlib import redirect_stdout, redirect_stderr
from dataclasses import replace
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from retail_app import maintenance


class RepositoryMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.addCleanup(self.temporary.cleanup)

    def create(self, relative, content=b'disposable'):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def test_allowlist_preserves_private_state_data_sources_dependencies_and_assets(self):
        removable = self.create('retail_app/backend/__pycache__/agent.cpython-312.pyc')
        self.create('retail_app/tmp/test_frontend.mjs')
        protected = [
            'retail_app/state/__pycache__/saved.pyc',
            'retail_app/state/backups/backup.sqlite3',
            'retail_app/tmp/browser-acceptance-state/app.sqlite3',
            'retail_app/tmp/my-notes.json',
            'retail_app/backend/agent.py',
            'retail_app/static/chunks/chunk-Q7WA.js',
            'retail_app/static/cache.pyc',
            'retail_app/node_modules/example/cache.pyc',
            'retail_app/.env',
            'retail_data/data/full/cache.pyc',
            'sources/cache.pyc',
            '.venv-runtime/lib/cache.pyc',
        ]
        for relative in protected:
            self.create(relative)
        items = maintenance.cleanup_candidates(self.root)
        self.assertEqual(len(items), 2)
        removed, skipped = maintenance.apply_cleanup(items, self.root)
        self.assertEqual((len(removed), skipped), (2, []))
        self.assertFalse(removable.exists())
        self.assertFalse(removable.parent.exists())
        for relative in protected:
            self.assertTrue((self.root / relative).is_file(), relative)

    def test_symlink_files_directories_and_tmp_are_not_followed(self):
        target = self.create('private/secret.pyc', b'keep')
        app = self.root / 'retail_app'
        app.mkdir()
        (app / 'backend').symlink_to(target.parent, target_is_directory=True)
        (app / 'tmp').symlink_to(target.parent, target_is_directory=True)
        (app / 'secret.pyc').symlink_to(target)
        self.assertEqual(maintenance.cleanup_candidates(self.root), [])
        self.assertEqual(target.read_bytes(), b'keep')

    def test_swapped_parent_symlink_after_preview_cannot_delete_external_file(self):
        cached = self.create('retail_app/backend/cache.pyc')
        items = maintenance.cleanup_candidates(self.root)
        target = self.create('private/cache.pyc', b'keep')
        original = cached.parent
        original.rename(original.with_name('backend-saved'))
        original.symlink_to(target.parent, target_is_directory=True)
        removed, skipped = maintenance.apply_cleanup(items, self.root)
        self.assertEqual(removed, [])
        self.assertEqual(skipped, ['retail_app/backend/cache.pyc'])
        self.assertEqual(target.read_bytes(), b'keep')

    def test_changed_file_and_hardlinked_file_are_not_removed(self):
        changed = self.create('retail_app/backend/changed.pyc')
        items = maintenance.cleanup_candidates(self.root)
        changed.write_bytes(b'new content from another process')
        hardlink = self.root / 'retail_app/backend/hardlink.pyc'
        os.link(changed, hardlink)
        self.assertEqual(maintenance.cleanup_candidates(self.root), [])
        removed, skipped = maintenance.apply_cleanup(items, self.root)
        self.assertEqual(removed, [])
        self.assertEqual(len(skipped), 1)
        self.assertTrue(changed.exists())
        self.assertTrue(hardlink.exists())

    def test_forged_protected_or_traversal_item_is_rejected(self):
        original = self.create('retail_app/backend/cache.pyc')
        item = maintenance.cleanup_candidates(self.root)[0]
        protected = self.create('retail_app/state/cache.pyc')
        forged = [replace(item, relative_path=relative) for relative in (
            '../outside.pyc', str(original), 'retail_app/state/cache.pyc',
            'retail_app/tmp/browser-acceptance-state/app.sqlite3',
        )]
        removed, skipped = maintenance.apply_cleanup(forged, self.root)
        self.assertEqual(removed, [])
        self.assertEqual(len(skipped), 4)
        self.assertTrue(protected.exists())
        self.assertTrue(original.exists())

    def test_nonempty_bytecode_directory_retains_unknown_file(self):
        self.create('retail_app/backend/__pycache__/agent.pyc')
        note = self.create('retail_app/backend/__pycache__/important-note.txt')
        maintenance.apply_cleanup(maintenance.cleanup_candidates(self.root), self.root)
        self.assertTrue(note.exists())

    def test_cli_clean_defaults_to_preview(self):
        original = self.create('retail_app/backend/cache.pyc')
        items = maintenance.cleanup_candidates(self.root)
        with patch.object(maintenance, 'cleanup_candidates', return_value=items), \
                patch.object(maintenance, 'apply_cleanup') as apply, redirect_stdout(io.StringIO()) as output:
            self.assertEqual(maintenance.main(['clean']), 0)
        apply.assert_not_called()
        self.assertIn('Preview only', output.getvalue())
        self.assertTrue(original.exists())

    def test_frontend_check_fails_before_running_when_fixtures_are_missing(self):
        self.create('retail_app/node_modules/.bin/esbuild')
        with patch.object(maintenance.shutil, 'which', return_value='/tool'), \
                patch.object(maintenance.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'fixtures are missing'):
                maintenance.check_repository('frontend', self.root)
        run.assert_not_called()

    def test_all_checks_run_backend_before_frontend_build_and_docs_without_installing(self):
        self.create('retail_app/node_modules/.bin/esbuild')
        with patch.object(maintenance.shutil, 'which', side_effect=lambda tool: '/tools/' + tool), \
                patch.object(maintenance.subprocess, 'run') as run, redirect_stdout(io.StringIO()):
            run.return_value.returncode = 0
            self.assertEqual(maintenance.check_repository('all', self.root), 0)
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(len(commands), 5)
        self.assertEqual(commands[0][-2:], ['pip', 'check'])
        self.assertEqual(commands[1][-1], 'retail_app.tests.run_all')
        self.assertEqual(commands[2], ['/tools/pnpm', 'test:frontend'])
        self.assertEqual(commands[3], ['/tools/pnpm', 'run', 'build'])
        self.assertTrue(commands[4][-1].endswith('verify_docs.py'))
        for call in run.call_args_list:
            self.assertEqual(call.kwargs['env']['COREPACK_ENABLE_NETWORK'], '0')
            self.assertNotIn('install', call.args[0])

    def test_check_failure_stops_later_stages(self):
        self.create('retail_app/node_modules/.bin/esbuild')
        with patch.object(maintenance.shutil, 'which', return_value='/tool'), \
                patch.object(maintenance.subprocess, 'run') as run, \
                redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            run.return_value.returncode = 3
            self.assertEqual(maintenance.check_repository('all', self.root), 3)
        self.assertEqual(run.call_count, 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
