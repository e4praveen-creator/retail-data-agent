#!/usr/bin/env python3
"""Create a consistent, verified backup of local conversations and evidence.

Works while the local app is running, including SQLite WAL contents. This does
not back up the API key, synthetic warehouse, source code, or model settings.
"""
import argparse
import datetime as dt
import os
from pathlib import Path
import sqlite3
from contextlib import closing
from .backend import config

APP=Path(__file__).resolve().parent


def backup_state(state_dir, output):
    source=Path(state_dir)/'app.sqlite3'
    output=Path(output).expanduser().resolve()
    if not source.is_file():
        raise ValueError('No conversation database was found in the state directory.')
    if output==source.resolve():
        raise ValueError('The backup must be a different file from the live database.')
    output.parent.mkdir(parents=True,exist_ok=True)
    # Exclusive file creation avoids overwriting a prior backup or following an
    # existing symlink. SQLite's backup API provides a transaction-consistent copy.
    descriptor=os.open(str(output),os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    os.close(descriptor)
    try:
        with closing(sqlite3.connect(source.resolve().as_uri()+'?mode=ro',uri=True,timeout=20)) as origin:
            with closing(sqlite3.connect(str(output))) as target:
                origin.backup(target,pages=256,sleep=.05)
                result=target.execute('PRAGMA integrity_check').fetchone()[0]
                if result!='ok':raise ValueError('Backup verification failed; the incomplete backup was removed.')
    except Exception:
        output.unlink(missing_ok=True)
        raise
    return output


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['backup'])
    parser.add_argument('--state-dir',type=Path,default=Path(os.getenv('RETAIL_STATE_DIR',str(APP/'state'))))
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    timestamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output=args.output or args.state_dir/'backups'/f'retail-chat-{timestamp}.sqlite3'
    try:created=backup_state(args.state_dir,output)
    except FileExistsError:raise SystemExit('A backup already exists at that path. Choose another output path.')
    except (OSError,sqlite3.Error):raise SystemExit('Backup failed. Check disk space and access to the state/output directories.')
    except ValueError as error:raise SystemExit(str(error))
    print('Verified conversation backup: '+str(created))
    print('This backup excludes the API key and synthetic warehouse.')


if __name__=='__main__':main()
