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
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import tempfile

from agent import run_agent
from agent.planner import generate_plan
from agent_excel import run_sheets_agent
from agent.research import run_research_agent
from gws import drive_files_list, presentations_get
from database import init_db
from database.drive_files import upsert_drive_files, get_drive_files_from_db
from database.documents import ingest_document, list_documents as list_docs_db
from database.slide_templates import list_templates as list_slide_templates, upsert_template as upsert_slide_template
from database.branding_logos import (
    list_logos as list_branding_logos,
    upsert_logo as upsert_branding_logo,
    upsert_logo_url as upsert_branding_logo_url,
    get_small_data_url_by_role,
    get_logo_image_url_by_role,
    get_logo_url_for_scaffold,
    get_logo_png_bytes,
    upsert_logo_prefs,
    get_logo_prefs,
)
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
    add_message(session_id, "user", topic, mode="design")
    update_session_title(session_id, topic[:100] if len(topic) > 100 else topic)

    document_context = request.get("documentContext")
    design_settings = request.get("designSettings") or {}
    color_palette = request.get("colorPalette")  # optional: { "dominant": "#hex", "palette": ["#hex", ...] }
    current_file = request.get("currentFile") or {}
    page_size_emu = None
    try:
        pres_id = (current_file.get("id") or "").strip() if isinstance(current_file, dict) else ""
        if pres_id:
            pres = presentations_get(pres_id)
            ps = pres.get("pageSize") or {}
            w = (ps.get("width") or {}) if isinstance(ps, dict) else {}
            h = (ps.get("height") or {}) if isinstance(ps, dict) else {}
            # Slides API typically returns PT magnitudes here.
            def _dim_to_emu(dim: dict) -> int | None:
                try:
                    mag = float(dim.get("magnitude"))
                    unit = (dim.get("unit") or "").upper()
                    if unit == "EMU":
                        return int(round(mag))
                    if unit == "PT":
                        return int(round(mag * 12700.0))
                except Exception:
                    return None
                return None

            w_emu = _dim_to_emu(w)
            h_emu = _dim_to_emu(h)
            if w_emu and h_emu:
                page_size_emu = {"pageWidthEmu": w_emu, "pageHeightEmu": h_emu, "marginEmu": 457200}
    except Exception:
        page_size_emu = None
    try:
        plan_obj, raw = generate_plan(
            topic,
            document_context=document_context,
            design_settings=design_settings,
            color_palette=color_palette,
            page_size_emu=page_size_emu,
        )
        plan_json = json.dumps(plan_obj) if plan_obj else None
        add_message(session_id, "assistant", raw, plan_json=plan_json, mode="design")
        return {
            "sessionId": session_id,
            "plan": plan_obj,
            "content": raw,
            "hasPlan": plan_obj is not None,
        }
    except Exception as e:
        add_message(session_id, "assistant", f"Error: {e}", mode="design")
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

    # Optional slide template (presentation type with slide outline/guidance)
    slide_template = request.get("slideTemplate")

    session_id = create_session_if_needed(request.get("sessionId"))
    add_message(session_id, "user", query, mode="research")
    update_session_title(session_id, (query[:100]) or "Research")

    ground_response = request.get("groundResponse", False)

    # If a slide template is provided, prepend it as context for the research agent
    template_context = ""
    if isinstance(slide_template, dict):
        name = (slide_template.get("name") or "").strip() or "Presentation"
        slides = slide_template.get("slides") or []
        lines = [f"Presentation template: {name}", ""]
        for idx, s in enumerate(slides):
            if not isinstance(s, dict):
                continue
            title = (s.get("title") or "").strip() or f"Slide {idx + 1}"
            guidance = (s.get("guidance") or "").strip()
            if guidance:
                lines.append(f"{idx + 1}. {title} — {guidance}")
            else:
                lines.append(f"{idx + 1}. {title}")
        template_context = "\n".join(lines).strip()

    # Build lightweight chat history (last 5 messages before this one) for additional context
    history_block = ""
    try:
        session = get_session_with_messages(session_id)
        msgs = session.get("messages", []) if session else []
        # Exclude the just-added user message; take last 5 before it
        if msgs:
            prior = msgs[:-1][-5:]
            if prior:
                lines = ["Conversation history (most recent last):"]
                for m in prior:
                    role = (m.get("role") or "").capitalize()
                    content = m.get("content") or ""
                    lines.append(f"{role}: {content}")
                history_block = "\n".join(lines).strip()
    except Exception:
        history_block = ""

    effective_query = query
    if template_context:
        effective_query = f"{template_context}\n\nUser request:\n{effective_query}"
    if history_block:
        effective_query = f"{history_block}\n\n{effective_query}"

    try:
        result = run_research_agent(query=effective_query, documents=documents, ground_response=ground_response)
        content = str(result["text"])
        add_message(session_id, "assistant", content, mode="research")
        return {
            "sessionId": session_id,
            "message": {"role": "assistant", "content": content},
            "toolCalls": [
                {"name": str(t["name"]), "args": _json_safe(t.get("args", {}))}
                for t in result.get("tool_calls", [])
            ],
        }
    except Exception as e:
        add_message(session_id, "assistant", f"Error: {e}", mode="research")
        return {
            "sessionId": session_id,
            "error": str(e),
            "message": {"role": "assistant", "content": f"Error: {e}"},
            "toolCalls": [],
        }


@app.post("/api/research-modify")
async def research_modify(request: dict):
    """Find replacement content per slide from extracted presentation + optional instructions and docs. Returns replacementSlides in a new output card."""
    extracted_slides = request.get("extractedSlides") or request.get("extracted_slides")
    if not extracted_slides or not isinstance(extracted_slides, list):
        raise HTTPException(status_code=400, detail="extractedSlides (array) required")

    instructions = (request.get("instructions") or request.get("query") or "").strip()
    documents = request.get("documents")
    if documents is None or not isinstance(documents, list):
        documents = []
        doc_id = request.get("documentId") or request.get("upload_id")
        if doc_id:
            documents = [
                {
                    "upload_id": doc_id,
                    "filename": request.get("documentFilename") or request.get("filename") or "",
                }
            ]

    session_id = create_session_if_needed(request.get("sessionId"))
    user_label = "Find replacements" + (f": {instructions[:80]}…" if len(instructions) > 80 else f": {instructions}" if instructions else "")
    add_message(session_id, "user", user_label, mode="research")

    query = instructions or "Find replacement content for each slide from the documents. Output only the JSON with a 'slides' array."
    try:
        result = run_research_agent(
            query=query,
            documents=documents,
            mode="modify",
            extracted_slides=extracted_slides,
        )
        content = str(result.get("text") or "")
        replacement_slides = result.get("replacement_slides")
        add_message(session_id, "assistant", content, mode="research")
        out = {
            "sessionId": session_id,
            "message": {"role": "assistant", "content": content, "mode": "research"},
            "toolCalls": [
                {"name": str(t["name"]), "args": _json_safe(t.get("args", {}))}
                for t in result.get("tool_calls", [])
            ],
        }
        if replacement_slides is not None:
            out["message"]["replacementSlides"] = replacement_slides
        return out
    except Exception as e:
        add_message(session_id, "assistant", f"Error: {e}", mode="research")
        return {
            "sessionId": session_id,
            "error": str(e),
            "message": {"role": "assistant", "content": f"Error: {e}", "mode": "research"},
            "toolCalls": [],
        }


def _text_from_text_content(text_obj: dict) -> str:
    """Extract plain text from a TextContent object (shape.text or tableCell.text)."""
    text_elements = (text_obj or {}).get("textElements") or []
    chunk = []
    for te in text_elements:
        run = te.get("textRun") or {}
        content = (run.get("content") or "").strip()
        if content:
            chunk.append(content)
    return " ".join(chunk).strip()


def _extract_text_from_element(el: dict) -> str | None:
    """Extract text from a single page element (shape, table, wordArt). Returns None if no text."""
    # Shape (including nested shapes inside groups)
    shape = el.get("shape") or {}
    text = _text_from_text_content(shape.get("text"))
    if text:
        return text
    # Table: iterate rows and cells
    table = el.get("table") or {}
    table_parts = []
    for row in table.get("tableRows") or []:
        row_parts = []
        for cell in row.get("tableCells") or []:
            ct = _text_from_text_content(cell.get("text"))
            if ct:
                row_parts.append(ct)
        if row_parts:
            table_parts.append(" | ".join(row_parts))
    if table_parts:
        return "\n".join(table_parts)
    # WordArt
    word_art = el.get("wordArt") or {}
    wa_text = (word_art.get("renderedText") or "").strip()
    if wa_text:
        return wa_text
    return None


def _collect_text_from_elements(elements: list[dict]) -> list[str]:
    """Recursively collect text from page elements (shapes, groups, tables, wordArt)."""
    texts = []
    for el in elements or []:
        # Group: recurse into children
        group = el.get("elementGroup") or {}
        children = group.get("children") or []
        if children:
            texts.extend(_collect_text_from_elements(children))
            continue
        t = _extract_text_from_element(el)
        if t:
            texts.append(t)
    return texts


def _extract_slide_text(slide: dict) -> tuple[str, str]:
    """Extract title and body text from a slide's pageElements. Returns (title, body).
    Handles shapes, groups (recursive), tables, and WordArt."""
    title_parts = []
    body_parts = []
    elements = slide.get("pageElements") or []
    all_texts = _collect_text_from_elements(elements)
    for text in all_texts:
        if not text:
            continue
        # First text box treated as title if we don't have one yet; else body
        if not title_parts:
            first_line = text.split("\n")[0].strip() if "\n" in text else text
            if first_line and len(first_line) < 200:
                title_parts.append(first_line)
                rest = text[len(first_line) :].strip().strip("\n")
                if rest:
                    body_parts.append(rest)
            else:
                body_parts.append(text)
        else:
            body_parts.append(text)
    title = " ".join(title_parts).strip() or "Untitled"
    body = "\n".join(body_parts).strip()
    return title, body


@app.post("/api/extract-presentation")
async def extract_presentation(request: dict):
    """Extract text from each slide of a presentation. Returns slides with title and body per slide."""
    presentation_id = (request.get("presentationId") or request.get("presentation_id") or "").strip()
    if not presentation_id:
        raise HTTPException(status_code=400, detail="presentationId required")
    try:
        pres = presentations_get(presentation_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to get presentation: {e}")
    if not isinstance(pres, dict):
        raise HTTPException(status_code=502, detail="Invalid presentation response")
    slides_raw = pres.get("slides") or []
    out_slides = []
    for i, slide in enumerate(slides_raw):
        if not isinstance(slide, dict):
            continue
        title, body = _extract_slide_text(slide)
        out_slides.append({
            "slideIndex": i + 1,
            "title": title,
            "body": body,
        })
    return {"slides": out_slides, "presentationId": presentation_id}


@app.post("/api/execute-plan")
async def execute_plan(request: dict):
    """Execute a presentation plan: pass plan to agent to build the deck (new or modify existing)."""
    plan = request.get("plan")
    if not plan or not isinstance(plan, dict):
        raise HTTPException(status_code=400, detail="plan object required")

    modify_existing = request.get("modifyExisting") is True
    current_file = request.get("currentFile")
    if modify_existing and (not current_file or not current_file.get("id")):
        raise HTTPException(status_code=400, detail="Modify mode requires currentFile with presentation id")

    session_id = create_session_if_needed(request.get("sessionId"))
    title = plan.get("title", "Untitled Presentation")
    slides = plan.get("slides", [])
    aesthetics = plan.get("aesthetics", {})
    design_settings = request.get("designSettings") or {}

    def _norm(s):
        """Normalize literal \\n to real newlines in plan content."""
        if not isinstance(s, str):
            return s
        return s.replace("\\n", "\n").replace("\\r", "\r")

    def _design_instruction(settings: dict) -> str:
        parts = []
        style = settings.get("style", "minimalist_bw")
        if style == "minimalist_bw":
            parts.append("Design style: Minimalist. White background, black text, clean layout.")
        elif style == "brand_colors":
            parts.append("Design style: Use brand accent color for headers and accents; keep layout professional.")
        elif style == "dark":
            parts.append("Design style: Dark theme. Dark background, light text.")
        if settings.get("printable"):
            parts.append("Printable: Use only white backgrounds with black text. No gradients. Ensure all content is legible in grayscale print.")
        max_lines = settings.get("maxLinesPerSlide")
        if max_lines is not None:
            parts.append(f"Limit body text to at most {max_lines} lines per slide.")
        if not parts:
            return ""
        return "\n\nDesign constraints: " + " ".join(parts)

    design_instruction = _design_instruction(design_settings)
    theme_colors = aesthetics.get("theme_colors") or {}

    # Optional logo placement overrides for this build
    logo_overrides = request.get("logoOverrides") or {}

    if modify_existing:
        plan_text = (
            "Update the EXISTING Google Slides presentation. Do NOT call scaffold_presentation or presentations_create.\n"
            f"The presentation to update has presentationId: {current_file.get('id')} and name: {current_file.get('name', '')}.\n"
            "Use presentations_get to load the current slides and structure, then use presentations_batch_update to update or replace content on each slide according to the plan below.\n\n"
        )
        plan_text += f"Theme/aesthetics: {aesthetics.get('theme', '')}. Primary color: {aesthetics.get('primary_color', '')}. Icon style: {aesthetics.get('suggested_icons_style', '')}.\n\n"
        if theme_colors:
            plan_text += "Theme colors (use these for styling):\n"
            for k, v in theme_colors.items():
                if v:
                    plan_text += f"  {k}: {v}\n"
            plan_text += "\n"
        if design_instruction:
            plan_text += design_instruction.strip() + "\n\n"
        plan_text += "Slides to update (match by slide number / order):\n"
        plan_text += "IMPORTANT: For elements with type process_infographic, grid_infographic, or circular_process_infographic, call the matching add_*_infographic tool—do NOT build them manually with createShape.\n\n"
    else:
        # Deterministically scaffold a new presentation (theme + logos) BEFORE calling the agent,
        # so the LLM never has to handle data URLs and can't forget to add logos.
        from gws import scaffold_presentation

        # Load stored logos (small data URLs) and preferences; allow request overrides.
        prefs = get_logo_prefs()
        my_corner = (logo_overrides.get("myCorner") or prefs.get("myCorner") or "top_left")
        target_corner = (logo_overrides.get("targetCorner") or prefs.get("targetCorner") or "top_right")

        my_w = logo_overrides.get("myWidthEmu") or prefs.get("myWidthEmu") or 600000
        my_h = logo_overrides.get("myHeightEmu") or prefs.get("myHeightEmu") or 600000
        my_m = logo_overrides.get("myMarginEmu") or prefs.get("myMarginEmu") or 250000
        tgt_w = logo_overrides.get("targetWidthEmu") or prefs.get("targetWidthEmu") or 600000
        tgt_h = logo_overrides.get("targetHeightEmu") or prefs.get("targetHeightEmu") or 600000
        tgt_m = logo_overrides.get("targetMarginEmu") or prefs.get("targetMarginEmu") or 250000

        logos = []
        add_logos = logo_overrides.get("addLogosToSlides", False)
        if add_logos:
            base_url = os.environ.get("ICON_BASE_URL", "").strip().rstrip("/")
            my_url = get_logo_url_for_scaffold("my", base_url) if base_url else get_logo_image_url_by_role("my")
            if my_url:
                logos.append({"url": my_url, "corner": my_corner, "idPrefix": "logo_my", "widthEmu": int(my_w), "heightEmu": int(my_h), "marginEmu": int(my_m)})
            tgt_url = get_logo_url_for_scaffold("target", base_url) if base_url else get_logo_image_url_by_role("target")
            if tgt_url:
                logos.append({"url": tgt_url, "corner": target_corner, "idPrefix": "logo_target", "widthEmu": int(tgt_w), "heightEmu": int(tgt_h), "marginEmu": int(tgt_m)})

        scaffolded = scaffold_presentation(
            title=title,
            num_slides=max(1, len(slides) if isinstance(slides, list) else 1),
            theme_colors=theme_colors if isinstance(theme_colors, dict) else {},
            logos=logos if logos else None,
        )
        current_file = {
            "id": scaffolded.get("presentationId"),
            "name": title,
            "mimeType": "application/vnd.google-apps.presentation",
        }
        modify_existing = True

        plan_text = (
            "Update the EXISTING Google Slides presentation. Do NOT call scaffold_presentation or presentations_create.\n"
            f"The presentation to update has presentationId: {current_file.get('id')} and name: {current_file.get('name', '')}.\n"
            "The presentation has already been scaffolded with the correct slide count, theme colors, and logos on every slide.\n"
            "Use presentations_get to load the current slides and structure, then use presentations_batch_update to fill in each slide according to the plan below.\n\n"
        )
        plan_text += f"Theme/aesthetics: {aesthetics.get('theme', '')}. Primary color: {aesthetics.get('primary_color', '')}. Icon style: {aesthetics.get('suggested_icons_style', '')}.\n\n"
        if theme_colors:
            plan_text += "Theme colors (use these for styling):\n"
            for k, v in theme_colors.items():
                if v:
                    plan_text += f"  {k}: {v}\n"
            plan_text += "\n"
        if design_instruction:
            plan_text += design_instruction.strip() + "\n\n"
        plan_text += "Slides to update (match by slide number / order):\n"
        plan_text += "IMPORTANT: For elements with type process_infographic, grid_infographic, or circular_process_infographic, call the matching add_*_infographic tool—do NOT build them manually with createShape.\n\n"

    for s in slides:
        plan_text += f"\n--- Slide {s.get('slide_number', '?')}: {s.get('title', '')} ---\n"
        plan_text += f"Layout: {s.get('layout', '')}\n"
        plan_text += f"Details: {_norm(s.get('details', s.get('content', '')))}\n"
        plan_text += f"Content: {_norm(s.get('content', ''))}\n"
        if s.get("elements"):
            plan_text += f"Elements: {json.dumps(s['elements'])}\n"

    add_message(session_id, "user", f"Build presentation: {title}" if not modify_existing else f"Update presentation: {title}", mode="agent")
    messages = [{"role": "user", "content": plan_text}]

    try:
        result = run_agent(messages, current_file=current_file)
        content = str(result["text"])
        add_message(session_id, "assistant", content, mode="agent")
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
        add_message(session_id, "assistant", err_msg, mode="agent")
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
        add_message(session_id, "user", str(user_content), mode="agent")
        update_session_title(session_id, (str(user_content)[:100]) or "New chat")

    try:
        result = run_agent(messages, current_file=current_file, current_document=current_document)
        content = str(result["text"])
        add_message(session_id, "assistant", content, mode="agent")
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
        add_message(session_id, "assistant", err_msg, mode="agent")
        return {
            "sessionId": session_id,
            "error": str(e),
            "message": {"role": "assistant", "content": err_msg},
            "toolCalls": [],
        }


@app.post("/api/sheets-chat")
async def sheets_chat(request: dict):
    """Sheets assistant chat: messages + optional spreadsheetId (from sidebar selection)."""
    messages = request.get("messages", [])
    if not messages:
        raise HTTPException(status_code=400, detail="messages array required")
    spreadsheet_id = (request.get("spreadsheetId") or "").strip() or None
    session_id = create_session_if_needed(request.get("sessionId"))

    last_user = next((m for m in reversed(messages) if m.get("role") == "user"), None)
    if last_user:
        user_content = last_user.get("content", "")
        if isinstance(user_content, list):
            user_content = user_content[0].get("text", "") if user_content else ""
        add_message(session_id, "user", str(user_content), mode="sheets")
        update_session_title(session_id, (str(user_content)[:100]) or "Sheets chat")

    try:
        result = run_sheets_agent(messages, spreadsheet_id=spreadsheet_id)
        content = str(result.get("text") or "No response")
        add_message(session_id, "assistant", content, mode="sheets")
        return {
            "sessionId": session_id,
            "message": {"role": "assistant", "content": content},
            "toolCalls": [
                {"name": str(t.get("name", "")), "args": _json_safe(t.get("args", {}))}
                for t in result.get("tool_calls", [])
            ],
        }
    except Exception as e:
        err_msg = f"Sheets agent error: {e}"
        add_message(session_id, "assistant", err_msg, mode="sheets")
        return {
            "sessionId": session_id,
            "error": str(e),
            "message": {"role": "assistant", "content": err_msg},
            "toolCalls": [],
        }


@app.get("/api/chat/sessions")
async def get_chat_sessions(limit: int = 50, mode: str | None = None):
    """List chat sessions, most recent first. mode=sheets: only sessions with sheets messages."""
    return {"sessions": list_sessions(limit=limit, mode=mode)}


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


@app.get("/api/slide-templates")
async def slide_templates_list(limit: int = 100):
    """List saved slide templates (presentation types + slide guidance)."""
    return {"templates": list_slide_templates(limit=limit)}


@app.get("/api/branding/logos")
async def branding_logos_list():
    """List stored branding logos (my/target)."""
    return {"logos": list_branding_logos(), "prefs": get_logo_prefs()}


@app.post("/api/branding/logos")
async def branding_logos_upload(
    role: str = Form(...),
    file: UploadFile = File(...),
):
    """Upload a logo PNG/JPG and store a small data URL (<=2KB) for embedding."""
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="empty file")
    from functions.image_data_url import make_small_png_data_url

    # Convert non-PNG to PNG bytes via Pillow if available
    png_bytes = content
    ctype = (file.content_type or "").lower()
    if ctype not in ("image/png", "image/x-png"):
        try:
            from PIL import Image
            from io import BytesIO

            img = Image.open(BytesIO(content)).convert("RGBA")
            buf = BytesIO()
            img.save(buf, format="PNG", optimize=True)
            png_bytes = buf.getvalue()
            ctype = "image/png"
        except Exception:
            # Fall back: treat as bytes; may fail later if not PNG-compatible
            png_bytes = content
            ctype = file.content_type or "application/octet-stream"

    data_url, best_len = make_small_png_data_url(png_bytes, max_url_len=2000, return_best_len=True)
    if not data_url:
        detail = "logo cannot be shrunk under ~2KB for data URL embedding"
        if best_len:
            detail += f" (best achieved length: {best_len} chars)"
        detail += ". Try a simpler/smaller logo PNG or use a tunnel/hosted URL."
        raise HTTPException(status_code=400, detail=detail)

    meta = upsert_branding_logo(role=role, filename=file.filename or "", content_type=ctype, png_bytes=png_bytes, small_data_url=data_url)
    return {"ok": True, "logo": meta, "dataUrlLength": len(data_url)}


@app.get("/api/branding/logo/{role}/image")
async def branding_logo_image(role: str):
    """
    Serve logo PNG by role (my/target). Used when ICON_BASE_URL/tunnel is set
    so Google Slides can fetch logos via public URL instead of data URL.
    """
    role = (role or "").strip().lower()
    if role not in ("my", "target"):
        raise HTTPException(status_code=400, detail="role must be 'my' or 'target'")
    png_bytes = get_logo_png_bytes(role)
    if not png_bytes:
        raise HTTPException(status_code=404, detail=f"No logo uploaded for role '{role}'")
    return Response(content=png_bytes, media_type="image/png")


@app.post("/api/branding/logos/url")
async def branding_logos_set_url(request: dict):
    """Set a logo by public URL (no upload). Role: 'my' or 'target'."""
    role = (request.get("role") or "").strip().lower()
    url = (request.get("url") or "").strip()
    if not role or not url:
        raise HTTPException(status_code=400, detail="role and url required")
    try:
        meta = upsert_branding_logo_url(role=role, url=url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "logo": meta}


@app.post("/api/branding/logo-prefs")
async def branding_logo_prefs_save(request: dict):
    """Save global logo corner preferences."""
    try:
        upsert_logo_prefs(
            my_corner=request.get("myCorner"),
            target_corner=request.get("targetCorner"),
            my_width_emu=request.get("myWidthEmu"),
            my_height_emu=request.get("myHeightEmu"),
            my_margin_emu=request.get("myMarginEmu"),
            target_width_emu=request.get("targetWidthEmu"),
            target_height_emu=request.get("targetHeightEmu"),
            target_margin_emu=request.get("targetMarginEmu"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "prefs": get_logo_prefs()}


@app.post("/api/slide-templates")
async def slide_templates_save(request: dict):
    """
    Save or update a slide template.
    Body: {name: str, slides: [{title, guidance}]}
    """
    name = (request.get("name") or "").strip()
    slides = request.get("slides") or []
    if not name:
        raise HTTPException(status_code=400, detail="name required")
    if not isinstance(slides, list):
        raise HTTPException(status_code=400, detail="slides must be a list")
    try:
        upsert_slide_template(name, slides)
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


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
    Serve icon as full-quality PNG by name. Used by add_icon_to_slide via ICON_BASE_URL (tunnel).
    Requires ICON_BASE_URL to be set to a publicly reachable URL (e.g. localtunnel/ngrok) for Google to fetch.
    """
    icon = get_icon_by_name(name)
    if not icon or not icon.get("svg"):
        raise HTTPException(status_code=404, detail=f"Icon '{name}' not found")
    try:
        png_bytes = svg_to_png_bytes(icon["svg"], output_width=256, output_height=256)
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
