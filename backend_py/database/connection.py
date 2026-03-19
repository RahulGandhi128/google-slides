"""
Database connection - SQLite, URL configurable via DATABASE_URL in .env.
Default: sqlite:///./database/app.db
"""
import os
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Default: sqlite in backend_py/database/app.db
DEFAULT_URL = "sqlite:///./database/app.db"
DATABASE_URL = os.environ.get("DATABASE_URL", DEFAULT_URL)

# For relative paths like ./database/app.db, resolve to absolute
if DATABASE_URL.startswith("sqlite:///./"):
    db_path = DATABASE_URL.replace("sqlite:///./", "")
    base_dir = Path(__file__).resolve().parent.parent
    abs_path = (base_dir / db_path).resolve()
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    DATABASE_URL = f"sqlite:///{abs_path}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=os.environ.get("SQL_ECHO", "").lower() == "true",
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Yield a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create tables from schema.sql if not exists."""
    schema_path = Path(__file__).parent / "schema.sql"
    if schema_path.exists():
        with open(schema_path) as f:
            sql = f.read()
        with engine.connect() as conn:
            for raw in sql.split(";"):
                stmt = raw.strip()
                if not stmt or all(line.strip().startswith("--") or not line.strip() for line in stmt.split("\n")):
                    continue
                stmt = "\n".join(line for line in stmt.split("\n") if not line.strip().startswith("--"))
                if stmt.strip():
                    conn.execute(text(stmt))
            conn.commit()

    # Ensure drive_files exists (fallback if schema was applied before it was added)
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS drive_files (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                mime_type TEXT,
                modified_time TEXT,
                web_view_link TEXT,
                icon_link TEXT,
                synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_drive_files_modified ON drive_files(modified_time)"))
        conn.commit()

    # Migrations: add new columns if missing (for existing DBs)
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE chat_sessions ADD COLUMN title TEXT DEFAULT 'New chat'"))
            conn.commit()
        except Exception:
            pass  # column may already exist
        try:
            conn.execute(text("ALTER TABLE chat_messages ADD COLUMN plan_json TEXT"))
            conn.commit()
        except Exception:
            pass

    # Documents and FAISS indexes (for RAG)
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS documents (
                upload_id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                page_count INTEGER NOT NULL DEFAULT 0,
                full_text TEXT,
                has_faiss INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS document_indexes (
                upload_id TEXT PRIMARY KEY,
                index_blob BLOB NOT NULL,
                docstore_blob BLOB NOT NULL
            )
        """))
        conn.commit()

    # Migrations: add mode column to chat_messages if missing (for agent type)
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE chat_messages ADD COLUMN mode TEXT DEFAULT 'agent'"))
            conn.commit()
        except Exception:
            pass  # column may already exist

    # Branding logos tables (for deterministic logo placement)
    with engine.connect() as conn:
        conn.execute(text("""
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
            )
        """))
        conn.execute(text("""
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
            )
        """))
        conn.commit()

    # Migrations: add sizing columns to branding_logo_prefs if missing
    with engine.connect() as conn:
        for col in (
            "my_width_emu INTEGER",
            "my_height_emu INTEGER",
            "my_margin_emu INTEGER",
            "target_width_emu INTEGER",
            "target_height_emu INTEGER",
            "target_margin_emu INTEGER",
        ):
            try:
                conn.execute(text(f"ALTER TABLE branding_logo_prefs ADD COLUMN {col}"))
                conn.commit()
            except Exception:
                pass

    # Migration: add logo_url to branding_logos (for public URL option)
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE branding_logos ADD COLUMN logo_url TEXT"))
            conn.commit()
        except Exception:
            pass  # column may already exist
