#!/usr/bin/env python3
"""Back up local state, check the repository, or preview safe generated-file cleanup.

Run from the Milky Way 2.0 root with the installed Python environment:
    python -m retail_app.maintenance backup
    python -m retail_app.maintenance check
    python -m retail_app.maintenance clean          # preview only
    python -m retail_app.maintenance clean --apply

Cleanup never removes state, datasets, dependencies, production assets or source.
"""
import argparse
from contextlib import closing
from dataclasses import dataclass
import datetime as dt
import os
from pathlib import Path
import shutil
import sqlite3
import stat
import subprocess
import sys

APP = Path(__file__).resolve().parent
ROOT = APP.parent

# Keep this explicit: an arbitrary file placed in tmp is not necessarily disposable.
GENERATED_TEMP_FILES = frozenset({
    'frontend-fixtures.json',
    'structured-answer-fixture.json',
    'render-handbook.mjs',
    'test_frontend.mjs',
    'test_playbook_visuals.mjs',
    'test_answer_report.mjs',
    'test_milkyway_frontend.mjs',
    'test_improvement_frontend.mjs',
    'test_frontend_delivery.mjs',
})
PROTECTED_DIRECTORIES = frozenset({
    '.git', '.venv', '.venv-runtime', 'node_modules', '.pnpm-store', 'state',
    'data', 'sources', 'backups', 'static', 'tmp',
})
SOURCE_DIRECTORIES = ('retail_app', 'retail_data', 'retail-data-analyst')


@dataclass(frozen=True)
class CleanupItem:
    """A scanned regular file plus its identity, checked again before removal."""

    relative_path: str
    size: int
    device: int
    inode: int
    modified_ns: int


def _cleanup_item(root, path):
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
        return None
    return CleanupItem(
        path.relative_to(root).as_posix(), metadata.st_size, metadata.st_dev,
        metadata.st_ino, metadata.st_mtime_ns,
    )


def cleanup_candidates(root=ROOT):
    """List only known build outputs and Python bytecode; do not follow symlinks."""
    root = Path(root).absolute()
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Cleanup requires a real project directory, not a symlink.')
    found = []
    for directory in SOURCE_DIRECTORIES:
        source = root / directory
        if source.is_symlink() or not source.is_dir():
            continue
        for base, directories, files in os.walk(source, followlinks=False):
            directories[:] = sorted(
                name for name in directories
                if name not in PROTECTED_DIRECTORIES and not (Path(base) / name).is_symlink()
            )
            for name in sorted(files):
                path = Path(base) / name
                if name == '.DS_Store' or name.endswith(('.pyc', '.pyo')):
                    item = _cleanup_item(root, path)
                    if item:
                        found.append(item)
    temp = root / 'retail_app' / 'tmp'
    if not (root / 'retail_app').is_symlink() and not temp.is_symlink() and temp.is_dir():
        for name in sorted(GENERATED_TEMP_FILES):
            path = temp / name
            if path.exists() and not path.is_symlink():
                item = _cleanup_item(root, path)
                if item:
                    found.append(item)
    return sorted(found, key=lambda item: item.relative_path)


def _open_directory(root_descriptor, parts):
    """Open each directory relative to its parent without traversing a symlink."""
    descriptor = os.dup(root_descriptor)
    try:
        for part in parts:
            next_descriptor = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor,
            )
            os.close(descriptor)
            descriptor = next_descriptor
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def _allowed_cleanup_path(relative):
    """Reject forged items and protected paths even when called outside the CLI."""
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts or len(path.parts) < 2:
        return False
    if path.parts[:2] == ('retail_app', 'tmp'):
        return len(path.parts) == 3 and path.name in GENERATED_TEMP_FILES
    return (
        path.parts[0] in SOURCE_DIRECTORIES
        and not any(part in PROTECTED_DIRECTORIES for part in path.parts[1:-1])
        and (path.name == '.DS_Store' or path.suffix in {'.pyc', '.pyo'})
    )


def apply_cleanup(items, root=ROOT):
    """Delete scanned files with pinned parent descriptors, never recursively.

    If a file or directory changed after preview, skip it. POSIX no-follow opens
    and relative unlink prevent a swapped parent symlink from escaping the root.
    Empty bytecode directories are removed; other directories remain intact.
    """
    if not hasattr(os, 'O_NOFOLLOW') or os.unlink not in os.supports_dir_fd:
        raise ValueError('Safe cleanup requires POSIX no-follow directory operations.')
    root_descriptor = os.open(Path(root), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    removed, skipped, bytecode_directories = [], [], set()
    try:
        for item in items:
            if not _allowed_cleanup_path(item.relative_path):
                skipped.append(item.relative_path)
                continue
            path = Path(item.relative_path)
            try:
                parent_descriptor = _open_directory(root_descriptor, path.parts[:-1])
                try:
                    current = os.stat(path.name, dir_fd=parent_descriptor, follow_symlinks=False)
                    identity = (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns)
                    expected = (item.device, item.inode, item.size, item.modified_ns)
                    if not stat.S_ISREG(current.st_mode) or current.st_nlink != 1 or identity != expected:
                        skipped.append(item.relative_path)
                        continue
                    os.unlink(path.name, dir_fd=parent_descriptor)
                    removed.append(item)
                    if path.parent.name == '__pycache__':
                        bytecode_directories.add(path.parent)
                finally:
                    os.close(parent_descriptor)
            except (FileNotFoundError, NotADirectoryError, OSError):
                skipped.append(item.relative_path)
        for directory in sorted(bytecode_directories, key=str):
            try:
                parent_descriptor = _open_directory(root_descriptor, directory.parts[:-1])
                try:
                    os.rmdir(directory.name, dir_fd=parent_descriptor)
                finally:
                    os.close(parent_descriptor)
            except OSError:
                # A running process may recreate bytecode; never remove contents recursively.
                pass
    finally:
        os.close(root_descriptor)
    return removed, skipped


def check_repository(target='all', root=ROOT):
    """Run existing offline checks in dependency order without installing anything."""
    if target not in {'all', 'backend', 'frontend', 'docs'}:
        raise ValueError('Unknown check target.')
    root = Path(root)
    app = root / 'retail_app'
    frontend = target in {'all', 'frontend'}
    if sys.version_info < (3, 12):
        raise ValueError('Checks require Python 3.12 or newer; use .venv-runtime/bin/python.')
    pnpm = shutil.which('pnpm') if frontend else None
    if frontend and (not pnpm or not shutil.which('node')):
        raise ValueError('Node and pnpm must be on PATH. Install the documented pinned toolchain first.')
    if frontend and not (app / 'node_modules' / '.bin' / 'esbuild').is_file():
        raise ValueError('Frontend dependencies are missing. Run pnpm install --frozen-lockfile in retail_app first.')
    if target == 'frontend' and any(not (app / 'tmp' / name).is_file() for name in (
        'frontend-fixtures.json', 'structured-answer-fixture.json',
    )):
        raise ValueError('Frontend fixtures are missing. Run check --target backend first, or use check for all stages.')
    commands = []
    if target in {'all', 'backend'}:
        commands += [
            ('Installed Python dependencies', [sys.executable, '-m', 'pip', 'check'], root),
            ('Offline backend regressions', [sys.executable, '-m', 'retail_app.tests.run_all'], root),
        ]
    if frontend:
        commands += [
            ('Frontend rendering regressions', [pnpm, 'test:frontend'], app),
            ('Production frontend build', [pnpm, 'run', 'build'], app),
        ]
    if target in {'all', 'docs'}:
        commands.append((
            'Handbook links and source fingerprints',
            [sys.executable, str(app / 'docs' / 'developer' / 'verify_docs.py')], root,
        ))
    environment = {
        **os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'PIP_DISABLE_PIP_VERSION_CHECK': '1',
        'PIP_NO_CACHE_DIR': '1', 'COREPACK_ENABLE_NETWORK': '0', 'COREPACK_ENABLE_DOWNLOAD_PROMPT': '0',
    }
    for label, command, directory in commands:
        print(f'\nChecking: {label}', flush=True)
        completed = subprocess.run(command, cwd=directory, env=environment, check=False)
        if completed.returncode:
            print(f'Check failed: {label}. Later stages were not run.', file=sys.stderr)
            return completed.returncode
    print('\nAll requested checks passed. Live model and browser acceptance are separate release gates.')
    return 0


def backup_state(state_dir, output):
    """Create a transaction-consistent backup without overwriting existing files."""
    source = Path(state_dir) / 'app.sqlite3'
    output = Path(output).expanduser().resolve()
    if not source.is_file():
        raise ValueError('No conversation database was found in the state directory.')
    if output == source.resolve():
        raise ValueError('The backup must be a different file from the live database.')
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(str(output), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    try:
        with closing(sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True, timeout=20)) as origin:
            with closing(sqlite3.connect(str(output))) as target:
                origin.backup(target, pages=256, sleep=.05)
                if target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise ValueError('Backup verification failed; the incomplete backup was removed.')
    except Exception:
        output.unlink(missing_ok=True)
        raise
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest='action', required=True)
    backup_parser = subparsers.add_parser('backup', help='Verify a SQLite backup, including committed WAL contents.')
    backup_parser.add_argument('--state-dir', type=Path)
    backup_parser.add_argument('--output', type=Path)
    clean_parser = subparsers.add_parser('clean', help='Preview allowlisted generated-file cleanup.')
    clean_parser.add_argument('--apply', action='store_true', help='Remove only the listed, unchanged regular files.')
    check_parser = subparsers.add_parser('check', help='Run existing offline release checks without installing dependencies.')
    check_parser.add_argument('--target', choices=['all', 'backend', 'frontend', 'docs'], default='all')
    args = parser.parse_args(argv)
    try:
        if args.action == 'check':
            return check_repository(args.target)
        if args.action == 'clean':
            items = cleanup_candidates()
            for item in items:
                print(f'{item.size:>10} bytes  {item.relative_path}')
            total = sum(item.size for item in items)
            print(f'{len(items)} allowlisted files, {total:,} bytes ({total / 1024**2:.2f} MiB).')
            if args.apply:
                removed, skipped = apply_cleanup(items)
                print(f'Removed {len(removed)} files, {sum(item.size for item in removed):,} bytes; skipped {len(skipped)} changed/unavailable files.')
                return 1 if skipped else 0
            print('Preview only. Run clean --apply to remove these files. State, data, dependencies and production assets are retained.')
            return 0
        # Load the application's environment only for operations that use state.
        from .backend import config  # noqa: F401
        state_dir = args.state_dir or Path(os.getenv('RETAIL_STATE_DIR', str(APP / 'state')))
        timestamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        output = args.output or state_dir / 'backups' / f'retail-chat-{timestamp}.sqlite3'
        created = backup_state(state_dir, output)
        print('Verified conversation backup: ' + str(created))
        print('This backup excludes the API key and synthetic warehouse.')
        return 0
    except FileExistsError:
        parser.exit(1, 'A backup already exists at that path. Choose another output path.\n')
    except (OSError, sqlite3.Error):
        parser.exit(1, 'Maintenance failed. Check disk space, file permissions and the installed toolchain.\n')
    except ValueError as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    raise SystemExit(main())
