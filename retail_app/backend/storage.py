"""Durable local state. Every connection is closed; chat completion is atomic."""
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from .data import APP

STATE = Path(os.getenv('RETAIL_STATE_DIR', str(APP / 'state')))
STATE.mkdir(parents=True, exist_ok=True)
SCHEMA = '''
CREATE TABLE IF NOT EXISTS analyses (id TEXT PRIMARY KEY, created TEXT DEFAULT CURRENT_TIMESTAMP, question TEXT, payload TEXT);
CREATE TABLE IF NOT EXISTS memories (id TEXT PRIMARY KEY, created TEXT DEFAULT CURRENT_TIMESTAMP, text TEXT, source TEXT);
CREATE TABLE IF NOT EXISTS conversations (id TEXT PRIMARY KEY, title TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP, updated TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS messages (id TEXT PRIMARY KEY, conversation_id TEXT, role TEXT, text TEXT, analysis_id TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS chat_jobs (id TEXT PRIMARY KEY, conversation_id TEXT, status TEXT, message TEXT, error TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS feedback(id TEXT PRIMARY KEY,analysis_id TEXT,rating TEXT,comment TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS messages_conversation ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS jobs_conversation ON chat_jobs(conversation_id,status);
'''


@contextmanager
def connection():
    con = sqlite3.connect(str(STATE / 'app.sqlite3'), timeout=20)
    con.row_factory = sqlite3.Row
    try:
        con.execute('PRAGMA busy_timeout=20000')
        con.execute('PRAGMA journal_mode=WAL')
        con.executescript(SCHEMA)
        with con:
            yield con
    finally:
        con.close()


chat_connection = connection


def _save_analysis(con, question, payload):
    from .presentation import finish_presentation
    if payload.get('mode')!='suggestions':
        payload=finish_presentation(payload,playbook_visuals=payload.get('playbook_visuals'))
    payload = {**payload, 'id': str(uuid.uuid4())}
    encoded = json.dumps(payload)
    if len(encoded.encode('utf-8')) > 12 * 1024 * 1024:
        raise ValueError('The answer is too large to save. Please narrow the question.')
    con.execute('INSERT INTO analyses(id,question,payload) VALUES(?,?,?)',
                (payload['id'], question, encoded))
    return payload


def save_analysis(question, payload):
    with connection() as con:
        return _save_analysis(con, question, payload)


def history():
    with connection() as con:
        return [dict(r) for r in con.execute('SELECT id,created,question FROM analyses ORDER BY created DESC, rowid DESC LIMIT 100')]


def get_analysis(identity):
    with connection() as con:
        row = con.execute('SELECT payload FROM analyses WHERE id=?', (identity,)).fetchone()
    if not row:
        raise ValueError('Analysis not found.')
    return json.loads(row['payload'])


def memories(query=''):
    with connection() as con:
        return [dict(r) for r in con.execute('SELECT * FROM memories WHERE text LIKE ? ORDER BY created DESC LIMIT 30', ('%' + query + '%',))]


def save_memory(text, source):
    identity = str(uuid.uuid4())
    with connection() as con:
        con.execute('INSERT INTO memories(id,text,source) VALUES(?,?,?)', (identity, text, source))
    return {'id': identity, 'text': text, 'source': source}


def create_conversation(title='New chat'):
    identity = str(uuid.uuid4())
    with connection() as con:
        con.execute('INSERT INTO conversations(id,title) VALUES(?,?)', (identity, title[:100]))
    return {'id': identity, 'title': title[:100]}


def conversations():
    with connection() as con:
        return [dict(r) for r in con.execute('SELECT * FROM conversations ORDER BY updated DESC,rowid DESC LIMIT 100')]


def conversation(identity, before=None, limit=50):
    """Read one bounded page, including evidence without an N+1 query pattern."""
    limit=max(1,min(int(limit),100))
    with connection() as con:
        row=con.execute('SELECT * FROM conversations WHERE id=?',(identity,)).fetchone()
        if not row:raise ValueError('Conversation not found.')
        result=dict(row)
        result['messages']=[]
        result['total_messages']=con.execute('SELECT count(*) FROM messages WHERE conversation_id=?',(identity,)).fetchone()[0]
        args=[identity]
        predicate='m.conversation_id=?'
        if before is not None:
            predicate+=' AND m.rowid<?';args.append(before)
        args.append(limit)
        page_bytes=0
        cursor=con.execute('SELECT m.rowid AS sequence,m.*,a.payload FROM messages m LEFT JOIN analyses a ON m.analysis_id=a.id WHERE '+predicate+' ORDER BY m.rowid DESC LIMIT ?',args)
        try:
            for row in cursor:
                message=dict(row)
                payload=message.pop('payload')
                size=len(payload or '')+len(message['text'] or '')
                if page_bytes+size>16*1024*1024 and result['messages']:break
                page_bytes+=size
                if payload:message['analysis']=json.loads(payload)
                result['messages'].append(message)
        finally:cursor.close()
        result['messages'].reverse()
        first=result['messages'][0]['sequence'] if result['messages'] else before
        result['has_older']=bool(first and con.execute('SELECT 1 FROM messages WHERE conversation_id=? AND rowid<? LIMIT 1',(identity,first)).fetchone())
        result['older_cursor']=first if result['has_older'] else None
        result['active_job']=next((dict(r) for r in con.execute("SELECT * FROM chat_jobs WHERE conversation_id=? AND status IN ('running','cancelling') ORDER BY rowid DESC LIMIT 1",(identity,))),None)
    return result


def _add_message(con, identity, role, text, analysis_id=None):
    if not con.execute('SELECT 1 FROM conversations WHERE id=?', (identity,)).fetchone():
        raise ValueError('Conversation not found.')
    if con.execute('SELECT count(*) FROM messages WHERE conversation_id=?', (identity,)).fetchone()[0] >= 1000:
        raise ValueError('This chat has reached 1,000 messages. Start a new chat to continue.')
    message_id = str(uuid.uuid4())
    con.execute('INSERT INTO messages(id,conversation_id,role,text,analysis_id) VALUES(?,?,?,?,?)',
                (message_id, identity, role, text, analysis_id))
    con.execute('UPDATE conversations SET updated=CURRENT_TIMESTAMP WHERE id=?', (identity,))
    return message_id


def add_message(identity, role, text, analysis_id=None):
    with connection() as con:
        return _add_message(con, identity, role, text, analysis_id)


def rename_conversation(identity, title):
    with connection() as con:
        changed = con.execute('UPDATE conversations SET title=?,updated=CURRENT_TIMESTAMP WHERE id=?', (title[:100], identity)).rowcount
        if not changed:
            raise ValueError('Conversation not found.')
    return {'id': identity, 'title': title[:100]}


def chat_job(identity, conversation_id, status, message='', error=''):
    with connection() as con:
        con.execute('INSERT INTO chat_jobs(id,conversation_id,status,message,error) VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET status=excluded.status,message=excluded.message,error=excluded.error', (identity, conversation_id, status, message, error))


def get_chat_job(identity):
    with connection() as con:
        row = con.execute('SELECT * FROM chat_jobs WHERE id=?', (identity,)).fetchone()
    if not row:
        raise ValueError('Job not found.')
    return dict(row)


def finish_chat(identity, job_id, question, payload):
    """Either the analysis, assistant message and completion all commit, or none do."""
    with connection() as con:
        con.execute('BEGIN IMMEDIATE')
        payload = _save_analysis(con, question, payload)
        _add_message(con, identity, 'assistant', payload['answer'], payload['id'])
        if job_id:
            changed = con.execute("UPDATE chat_jobs SET status='complete',message='Answer ready',error='' WHERE id=? AND status='running'", (job_id,)).rowcount
            if not changed:
                raise ValueError('This answer is no longer running.')
        return payload


def delete_conversation(identity):
    """Remove chat-owned evidence/feedback atomically; never deletes the warehouse."""
    with connection() as con:
        con.execute('BEGIN IMMEDIATE')
        if not con.execute('SELECT 1 FROM conversations WHERE id=?', (identity,)).fetchone():
            raise ValueError('Conversation not found.')
        if con.execute("SELECT 1 FROM chat_jobs WHERE conversation_id=? AND status IN ('running','cancelling')", (identity,)).fetchone():
            raise ValueError('Stop the active answer before deleting this chat.')
        ids = [r[0] for r in con.execute('SELECT analysis_id FROM messages WHERE conversation_id=? AND analysis_id IS NOT NULL', (identity,))]
        con.execute('DELETE FROM messages WHERE conversation_id=?', (identity,))
        con.execute('DELETE FROM chat_jobs WHERE conversation_id=?', (identity,))
        con.execute('DELETE FROM conversations WHERE id=?', (identity,))
        for analysis_id in ids:
            if not con.execute('SELECT 1 FROM messages WHERE analysis_id=?', (analysis_id,)).fetchone():
                con.execute('DELETE FROM feedback WHERE analysis_id=?', (analysis_id,))
                con.execute('DELETE FROM analyses WHERE id=?', (analysis_id,))
    return {'deleted': True, 'id': identity}


def recover_interrupted_jobs():
    with connection() as con:
        con.execute("UPDATE chat_jobs SET status='interrupted',message='The server restarted before this answer completed. Your question was saved; send it again to retry.' WHERE status IN ('running','cancelling')")
