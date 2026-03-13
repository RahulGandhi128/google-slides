"""
GWS Slides Assistant - FastAPI Backend
"""
import json
import logging
import os

from dotenv import load_dotenv
from contextlib import asynccontextmanager

# Load .env from backend_py or project root
load_dotenv()
load_dotenv("../.env")


def _json_safe(obj):
    """Return JSON-serializable copy; protobuf can leak into tool args."""
    try:
        return json.loads(json.dumps(obj, default=str))
    except (TypeError, ValueError):
        return {}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
import tempfile

from agent import run_agent
from agent.planner import generate_plan
from agent.research import run_research_agent
from gws import drive_files_list
from database import init_db
from database.drive_files import upsert_drive_files, get_drive_files_from_db
from database.documents import ingest_document, list_documents as list_docs_db
from database.chat_sessions import (
    create_session,
    create_session_if_needed,
    update_session_title,
    add_message,
    list_sessions,
    get_session_with_messages,
    delete_session,
)
from icon.icons import ensure_index, get_icon_by_name, svg_to_png_bytes
from fastapi.responses import Response


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    ensure_index()
    yield


app = FastAPI(title="GWS Slides Assistant", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/plan")
async def plan(request: dict):
    """Planner mode: single-topic plan request. Returns JSON plan or natural-language response."""
    topic = request.get("topic", "").strip()
    if not topic:
        raise HTTPException(status_code=400, detail="topic required")

    session_id = create_session_if_needed(request.get("sessionId"))
    add_message(session_id, "user", topic)
    update_session_title(session_id, topic[:100] if len(topic) > 100 else topic)

    try:
        plan_obj, raw = generate_plan(topic, document_context=None)
        plan_json = json.dumps(plan_obj) if plan_obj else None
        add_message(session_id, "assistant", raw, plan_json=plan_json)
        return {
            "sessionId": session_id,
            "plan": plan_obj,
            "content": raw,
            "hasPlan": plan_obj is not None,
        }
    except Exception as e:
        add_message(session_id, "assistant", f"Error: {e}")
        return {
            "sessionId": session_id,
            "error": str(e),
            "plan": None,
            "content": f"Error: {e}",
            "hasPlan": False,
        }


@app.post("/api/research")
async def research(request: dict):
    """Deep research on zero or more attached documents. Uses research agent (list_documents + document_search)."""
    query = (request.get("query") or request.get("topic") or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="query or topic required")

    # Accept documents list or legacy single documentId
    documents = request.get("documents")
    if documents is None or not isinstance(documents, list):
        documents = []
        doc_id = request.get("documentId") or request.get("upload_id")
        if doc_id:
            documents = [{
                "upload_id": doc_id,
                "filename": request.get("documentFilename") or request.get("filename") or "",
            }]

    session_id = create_session_if_needed(request.get("sessionId"))
    add_message(session_id, "user", query)
    update_session_title(session_id, (query[:100]) or "Research")

    try:
        result = run_research_agent(query=query, documents=documents)
        content = str(result["text"])
        add_message(session_id, "assistant", content)
        return {
            "sessionId": session_id,
            "message": {"role": "assistant", "content": content},
            "toolCalls": [
                {"name": str(t["name"]), "args": _json_safe(t.get("args", {}))}
                for t in result.get("tool_calls", [])
            ],
        }
    except Exception as e:
        add_message(session_id, "assistant", f"Error: {e}")
        return {
            "sessionId": session_id,
            "error": str(e),
            "message": {"role": "assistant", "content": f"Error: {e}"},
            "toolCalls": [],
        }


@app.post("/api/execute-plan")
async def execute_plan(request: dict):
    """Execute a presentation plan: pass plan to agent to build the deck."""
    plan = request.get("plan")
    if not plan or not isinstance(plan, dict):
        raise HTTPException(status_code=400, detail="plan object required")

    session_id = create_session_if_needed(request.get("sessionId"))
    title = plan.get("title", "Untitled Presentation")
    slides = plan.get("slides", [])
    aesthetics = plan.get("aesthetics", {})

    def _norm(s):
        """Normalize literal \\n to real newlines in plan content."""
        if not isinstance(s, str):
            return s
        return s.replace("\\n", "\n").replace("\\r", "\r")

    plan_text = f"Create a Google Slides presentation from this plan. Title: {title}\n\n"
    plan_text += f"Theme/aesthetics: {aesthetics.get('theme', '')}. Primary color: {aesthetics.get('primary_color', '')}. Icon style: {aesthetics.get('suggested_icons_style', '')}.\n\n"
    plan_text += "Slides to create:\n"
    for s in slides:
        plan_text += f"\n--- Slide {s.get('slide_number', '?')}: {s.get('title', '')} ---\n"
        plan_text += f"Layout: {s.get('layout', '')}\n"
        plan_text += f"Details: {_norm(s.get('details', s.get('content', '')))}\n"
        plan_text += f"Content: {_norm(s.get('content', ''))}\n"
        if s.get("elements"):
            plan_text += f"Elements: {json.dumps(s['elements'])}\n"

    add_message(session_id, "user", f"Build presentation: {title}")
    messages = [{"role": "user", "content": plan_text}]
    current_file = request.get("currentFile")

    try:
        result = run_agent(messages, current_file=current_file)
        content = str(result["text"])
        add_message(session_id, "assistant", content)
        return {
            "sessionId": session_id,
            "message": {"role": "assistant", "content": content},
            "toolCalls": [
                {"name": str(t["name"]), "args": _json_safe(t.get("args", {}))}
                for t in result.get("tool_calls", [])
            ],
        }
    except Exception as e:
        err_msg = f"Error: {e}. Ensure gws is installed and authenticated (gws auth login -s slides,drive)"
        add_message(session_id, "assistant", err_msg)
        return {
            "sessionId": session_id,
            "error": str(e),
            "message": {"role": "assistant", "content": err_msg},
            "toolCalls": [],
        }


@app.post("/api/chat")
async def chat(request: dict):
    messages = request.get("messages", [])
    if not messages:
        raise HTTPException(status_code=400, detail="messages array required")
    current_file = request.get("currentFile")
    document_id = request.get("documentId") or request.get("upload_id")
    current_document = (
        {"upload_id": document_id, "filename": request.get("documentFilename", "")}
        if document_id
        else None
    )
    session_id = create_session_if_needed(request.get("sessionId"))

    last_user = next((m for m in reversed(messages) if m.get("role") == "user"), None)
    if last_user:
        user_content = last_user.get("content", "")
        if isinstance(user_content, list):
            user_content = user_content[0].get("text", "") if user_content else ""
        add_message(session_id, "user", str(user_content))
        update_session_title(session_id, (str(user_content)[:100]) or "New chat")

    try:
        result = run_agent(messages, current_file=current_file, current_document=current_document)
        content = str(result["text"])
        add_message(session_id, "assistant", content)
        return {
            "sessionId": session_id,
            "message": {"role": "assistant", "content": content},
            "toolCalls": [
                {"name": str(t["name"]), "args": _json_safe(t.get("args", {}))}
                for t in result.get("tool_calls", [])
            ],
        }
    except Exception as e:
        err_msg = f"Error: {e}. Ensure gws is installed and authenticated (gws auth login -s slides,drive)"
        add_message(session_id, "assistant", err_msg)
        return {
            "sessionId": session_id,
            "error": str(e),
            "message": {"role": "assistant", "content": err_msg},
            "toolCalls": [],
        }


@app.get("/api/chat/sessions")
async def get_chat_sessions(limit: int = 50):
    """List chat sessions, most recent first."""
    return {"sessions": list_sessions(limit=limit)}


@app.get("/api/chat/sessions/{session_id:int}")
async def get_chat_session(session_id: int):
    """Get a chat session with all messages (content + plan, no tools)."""
    session = get_session_with_messages(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@app.delete("/api/chat/sessions/{session_id:int}")
async def delete_chat_session(session_id: int):
    """Delete a chat session and its messages."""
    if not delete_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"ok": True}


@app.post("/api/documents/ingest")
async def documents_ingest(file: UploadFile = File(...)):
    """Ingest a PDF or DOCX file. File is chunked and FAISS-indexed; original filename is kept."""
    suffix = os.path.splitext(file.filename or "")[1].lower()
    if suffix not in (".pdf", ".docx"):
        raise HTTPException(status_code=400, detail="Only .pdf and .docx are supported")
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        try:
            original_name = file.filename or ""
            result = ingest_document(tmp_path, filename=original_name)
            return result
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/documents")
async def documents_list(limit: int = 100):
    """List ingested documents (upload_id, filename, page_count, has_faiss)."""
    return {"documents": list_docs_db(limit=limit)}


@app.get("/api/tools")
async def list_tools():
    return {
        "tools": [
            {"name": "presentations_create", "description": "Create a new presentation"},
            {"name": "presentations_get", "description": "Get presentation content"},
            {"name": "presentations_batch_update", "description": "Add slides, insert text"},
            {"name": "pages_get_thumbnail", "description": "Get slide thumbnail"},
            {"name": "drive_files_list", "description": "List Drive files"},
            {"name": "add_icon_to_slide", "description": "Search and add Phosphor icon to a slide"},
            {"name": "list_documents", "description": "List ingested PDF/DOCX documents"},
            {"name": "document_search", "description": "Semantic search over an ingested document"},
            {"name": "get_document_text", "description": "Get full text of a small ingested document"},
        ]
    }


@app.get("/api/health")
async def health():
    return {"status": "ok", "backend": "python-fastapi"}


@app.get("/api/icon/png")
async def get_icon_png(name: str):
    """
    Serve icon as PNG by name. Used by add_icon_to_slide when data URL exceeds 2KB.
    Requires ICON_BASE_URL to be set to a publicly reachable URL (e.g. ngrok) for Google to fetch.
    """
    icon = get_icon_by_name(name)
    if not icon or not icon.get("svg"):
        raise HTTPException(status_code=404, detail=f"Icon '{name}' not found")
    try:
        png_bytes = svg_to_png_bytes(icon["svg"], output_width=128, output_height=128)
        return Response(content=png_bytes, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/drive/files")
async def list_drive_files(page_size: int = 30, q: str | None = None, refresh: bool = False):
    """
    List files in Google Drive. Fetches via gws CLI, stores in DB, returns files.
    refresh=true forces a fresh fetch from Drive (same as normal - always fetches).
    Sample response: {"files": [{"id":"...","name":"...","mimeType":"...","modifiedTime":"...","webViewLink":"...","iconLink":"..."}], "nextPageToken":"..."}
    """
    try:
        result = drive_files_list(page_size=page_size, q=q)
        files = result.get("files") or []
        upsert_drive_files(files)
        return {"files": files, "nextPageToken": result.get("nextPageToken")}
    except Exception as e:
        # Fallback to DB cache if gws fails
        try:
            cached = get_drive_files_from_db()
            if cached:
                return {"files": cached, "fromCache": True, "error": str(e)}
        except Exception:
            pass
        raise HTTPException(status_code=502, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
