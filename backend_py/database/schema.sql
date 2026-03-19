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
    mode TEXT DEFAULT 'agent',
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

-- Ingested documents: small docs store full_text, big docs use FAISS (document_indexes)
CREATE TABLE IF NOT EXISTS documents (
    upload_id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    page_count INTEGER NOT NULL DEFAULT 0,
    full_text TEXT,
    has_faiss INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS document_indexes (
    upload_id TEXT PRIMARY KEY,
    index_blob BLOB NOT NULL,
    docstore_blob BLOB NOT NULL,
    FOREIGN KEY (upload_id) REFERENCES documents(upload_id)
);

-- Saved slide templates (presentation types + slide guidance)
CREATE TABLE IF NOT EXISTS slide_templates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  slides_json TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_slide_templates_name ON slide_templates(name);

-- Branding logos (two roles: 'my' and 'target') with small data URLs for embedding
CREATE TABLE IF NOT EXISTS branding_logos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  role TEXT NOT NULL UNIQUE CHECK (role IN ('my', 'target')),
  filename TEXT,
  content_type TEXT,
  png_bytes BLOB,
  small_data_url TEXT,
  logo_url TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Global logo placement preferences (single row, id=1)
CREATE TABLE IF NOT EXISTS branding_logo_prefs (
  id INTEGER PRIMARY KEY CHECK (id = 1),
  my_corner TEXT,
  target_corner TEXT,
  my_width_emu INTEGER,
  my_height_emu INTEGER,
  my_margin_emu INTEGER,
  target_width_emu INTEGER,
  target_height_emu INTEGER,
  target_margin_emu INTEGER,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
