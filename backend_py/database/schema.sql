-- GWS Slides Assistant - SQLite Schema
-- Run this to initialize the database

CREATE TABLE IF NOT EXISTS chat_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT DEFAULT 'New chat',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL DEFAULT '',
    plan_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id);

-- Drive files cache (synced from gws drive files list)
CREATE TABLE IF NOT EXISTS drive_files (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    mime_type TEXT,
    modified_time TEXT,
    web_view_link TEXT,
    icon_link TEXT,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_drive_files_modified ON drive_files(modified_time);
