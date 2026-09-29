
CREATE TABLE IF NOT EXISTS analyses (id TEXT PRIMARY KEY, created TEXT DEFAULT CURRENT_TIMESTAMP, question TEXT, payload TEXT);
CREATE TABLE IF NOT EXISTS memories (id TEXT PRIMARY KEY, created TEXT DEFAULT CURRENT_TIMESTAMP, text TEXT, source TEXT);
CREATE TABLE IF NOT EXISTS conversations (id TEXT PRIMARY KEY, title TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP, updated TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS messages (id TEXT PRIMARY KEY, conversation_id TEXT, role TEXT, text TEXT, analysis_id TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS chat_jobs (id TEXT PRIMARY KEY, conversation_id TEXT, status TEXT, message TEXT, error TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS feedback(id TEXT PRIMARY KEY,analysis_id TEXT,rating TEXT,comment TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS messages_conversation ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS jobs_conversation ON chat_jobs(conversation_id,status);


CREATE TABLE IF NOT EXISTS retail_sessions (
 conversation_id TEXT PRIMARY KEY, payload TEXT NOT NULL, updated TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS retail_investigations (
 id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL, payload TEXT NOT NULL,
 revision INTEGER NOT NULL, updated TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS retail_investigations_chat ON retail_investigations(conversation_id);
CREATE TABLE IF NOT EXISTS retail_investigation_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, investigation_id TEXT NOT NULL,
 revision INTEGER NOT NULL, action TEXT NOT NULL, snapshot TEXT NOT NULL, created TEXT NOT NULL,
 UNIQUE(investigation_id,revision));
CREATE TABLE IF NOT EXISTS retail_hypothesis_tests (
 id TEXT PRIMARY KEY, investigation_id TEXT NOT NULL, node_id TEXT NOT NULL,
 investigation_revision INTEGER NOT NULL, payload TEXT NOT NULL, created TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS retail_hypothesis_tests_investigation ON retail_hypothesis_tests(investigation_id);


CREATE TABLE IF NOT EXISTS workspace_migrations(version INTEGER PRIMARY KEY, applied TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS workspace_assets(
 id TEXT PRIMARY KEY, kind TEXT NOT NULL, name TEXT NOT NULL, owner TEXT NOT NULL,
 built_in INTEGER NOT NULL DEFAULT 0, created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS workspace_drafts(
 asset_id TEXT PRIMARY KEY, revision INTEGER NOT NULL, name TEXT NOT NULL,
 content TEXT NOT NULL, updated TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS workspace_versions(
 id TEXT PRIMARY KEY, asset_id TEXT NOT NULL, name TEXT NOT NULL, schema_version INTEGER NOT NULL,
 content TEXT NOT NULL, content_hash TEXT NOT NULL, created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS workspace_versions_asset ON workspace_versions(asset_id);
CREATE TABLE IF NOT EXISTS workspace_releases(
 id TEXT PRIMARY KEY, name TEXT NOT NULL, parent_release_id TEXT, asset_versions TEXT NOT NULL,
 snapshot_hash TEXT NOT NULL, validation TEXT NOT NULL, operator TEXT NOT NULL, rationale TEXT NOT NULL,
 created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS workspace_active(singleton INTEGER PRIMARY KEY CHECK(singleton=1), release_id TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS workspace_activations(
 id TEXT PRIMARY KEY, release_id TEXT NOT NULL, previous_release_id TEXT, action TEXT NOT NULL,
 operator TEXT NOT NULL, rationale TEXT NOT NULL, evaluation_run_id TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS workspace_feedback(
 id TEXT PRIMARY KEY, analysis_id TEXT NOT NULL, issue_types TEXT NOT NULL, correction TEXT NOT NULL,
 status TEXT NOT NULL, revision INTEGER NOT NULL, original_question TEXT NOT NULL,
 original_answer TEXT NOT NULL, provenance TEXT NOT NULL, evidence TEXT NOT NULL,
 linked_asset_id TEXT, linked_case_id TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP,
 updated TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TRIGGER IF NOT EXISTS workspace_versions_no_update BEFORE UPDATE ON workspace_versions BEGIN SELECT RAISE(ABORT, 'Workspace versions are immutable'); END;
CREATE TRIGGER IF NOT EXISTS workspace_versions_no_delete BEFORE DELETE ON workspace_versions BEGIN SELECT RAISE(ABORT, 'Workspace versions are immutable'); END;
CREATE TRIGGER IF NOT EXISTS workspace_releases_no_update BEFORE UPDATE ON workspace_releases BEGIN SELECT RAISE(ABORT, 'Workspace releases are immutable'); END;
CREATE TRIGGER IF NOT EXISTS workspace_releases_no_delete BEFORE DELETE ON workspace_releases BEGIN SELECT RAISE(ABORT, 'Workspace releases are immutable'); END;


CREATE TABLE IF NOT EXISTS workspace_evaluation_runs(
 id TEXT PRIMARY KEY, created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, status TEXT NOT NULL,
 payload TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS workspace_evaluation_status ON workspace_evaluation_runs(status);
