"""
AI Agent with Gemini + Slides/Drive tools
"""
import json
import logging
import os

import google.generativeai as genai

log = logging.getLogger("agent")
from google.generativeai.types import FunctionDeclaration, Tool

from gws import (
    drive_files_list,
    pages_get_thumbnail,
    presentations_batch_update,
    presentations_create,
    presentations_get,
    scaffold_presentation,
)
from icon.icons import search_icon, svg_to_png_bytes

TOOL_DECLARATIONS = [
    FunctionDeclaration(
        name="presentations_create",
        description="Create a new Google Slides presentation",
        parameters={
            "type": "object",
            "properties": {"title": {"type": "string", "description": "Presentation title"}},
        },
    ),
    FunctionDeclaration(
        name="presentations_get",
        description="Get full content of a presentation including slides and placeholder objectIds",
        parameters={
            "type": "object",
            "properties": {"presentationId": {"type": "string"}},
            "required": ["presentationId"],
        },
    ),
    FunctionDeclaration(
        name="presentations_batch_update",
        description="Powerful container tool for 50+ slide actions. Pass requests array with: createSlide (use placeholderIdMappings), insertText, updateTextStyle, createImage, createShape, createTable, deleteObject, updatePageProperties (background color via pageBackgroundFill), updatePageElementTransform (precise alignment and affine transforms). Use for content, colors, themes, aesthetics, and layout.",
        parameters={
            "type": "object",
            "properties": {
                "presentationId": {"type": "string"},
                "requests": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "createSlide, insertText, updateTextStyle, createImage, createShape, createTable, deleteObject, etc.",
                },
            },
            "required": ["presentationId", "requests"],
        },
    ),
    FunctionDeclaration(
        name="pages_get_thumbnail",
        description="Get thumbnail for a slide",
        parameters={
            "type": "object",
            "properties": {
                "presentationId": {"type": "string"},
                "pageObjectId": {"type": "string"},
            },
            "required": ["presentationId", "pageObjectId"],
        },
    ),
    FunctionDeclaration(
        name="drive_files_list",
        description="List files in Google Drive",
        parameters={
            "type": "object",
            "properties": {
                "pageSize": {"type": "integer"},
                "q": {"type": "string"},
            },
        },
    ),
    FunctionDeclaration(
        name="add_icon_to_slide",
        description="Search for an icon by meaning (e.g. rocket, lightbulb, checkmark) and add it to a slide. Use when the user asks for icons, decorative icons, or visual symbols on slides. Combines semantic icon search with createImage in one call.",
        parameters={
            "type": "object",
            "properties": {
                "presentationId": {"type": "string", "description": "The presentation ID"},
                "pageObjectId": {"type": "string", "description": "The slide's page object ID (e.g. p, slide_geo)"},
                "query": {"type": "string", "description": "Natural-language icon description, e.g. 'rocket', 'lightbulb idea', 'checkmark'"},
                "objectId": {"type": "string", "description": "Optional unique ID for the image element"},
                "translateX": {"type": "number", "description": "Optional X position in EMU (slide width ~9144000)"},
                "translateY": {"type": "number", "description": "Optional Y position in EMU (slide height ~6858000)"},
            },
            "required": ["presentationId", "pageObjectId", "query"],
        },
    ),
    FunctionDeclaration(
        name="scaffold_presentation",
        description="Create a new presentation with a global theme color scheme (Theme Builder-like), then scaffold a fixed number of slides with a shared background and optional logo on every slide. Returns presentationId and slide objectIds to fill content next.",
        parameters={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Presentation title"},
                "numSlides": {"type": "integer", "description": "Total number of slides to scaffold (>=1)"},
                "themeColors": {
                    "type": "object",
                    "description": "Theme colors as hex strings (e.g. #RRGGBB). Used to set master color scheme and slide backgrounds.",
                    "properties": {
                        "heading_color": {"type": "string"},
                        "body_text_color": {"type": "string"},
                        "background_color": {"type": "string"},
                        "accent_color": {"type": "string"},
                        "shapes_color": {"type": "string"},
                        "charts_color": {"type": "string"},
                    },
                },
                "logoUrl": {"type": "string", "description": "Optional logo image URL (or data URL) to place on every slide"},
            },
            "required": ["title", "numSlides"],
        },
    ),
]

SYSTEM_INSTRUCTION = """You are a Google Workspace assistant for Slides and Drive, acting as a professional designer and content creator. Work step-by-step until the task is complete.

PERSONA - Professional Designer/Editor:
- Create polished, well-designed presentations with attention to visual hierarchy and consistency.
- Use a design grid mindset: align elements precisely, maintain consistent spacing, avoid random placement.
- Apply professional design principles: contrast, repetition, alignment, proximity.
- When adding shapes or elements, position them intentionally—not arbitrarily.

When the user asks to create a presentation WITH content:
1. Call presentations_create with the title
2. Get presentationId from the response
3. Call presentations_get to see slide structure and placeholder objectIds
4. Call presentations_batch_update with createSlide and insertText requests

When building a presentation FROM A PLAN (title + N slides + theme colors):
- First call scaffold_presentation(title, numSlides=N, themeColors from the plan, logoUrl if provided).
- Use the returned presentationId and slide objectIds to fill content with presentations_batch_update (insertText, updateTextStyle, createShape, createImage, etc.).
- Do NOT call presentations_create again and do NOT create extra slides beyond the plan count unless explicitly requested.

BULLETED LISTS - For body text with bullets:
- Use insertText with actual newline characters (U+000A) between items. Do NOT use literal backslash-n (\\n) in the text.
- After insertText on a body text box, add createParagraphBullets in the SAME requests array:

{"createParagraphBullets": {"objectId": "body_box_id", "textRange": {"type": "ALL"}, "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"}}

- Use this for any multi-line bullet content. Never use "•" or "\\n" as literal characters in insertText—use real newlines and createParagraphBullets.

CRITICAL - Object IDs for insertText:
- Use objectIds from the SLIDES array only (slides[].pageElements[].objectId). These are editable.
- NEVER use objectIds from the LAYOUTS array (layouts[].pageElements). Layout placeholders (e.g. p2_i0, p2_i1) are read-only templates—the API will reject insertText on them.

CRITICAL - presentations_batch_update:
- requests MUST be a valid JSON array of objects, never a string.
- Use INTEGERS only for insertionIndex (e.g. 1, 2, 3). Do NOT use decimals like 1.0.

PLACEHOLDER TRICK - Use placeholderIdMappings when creating slides so you know the text box IDs immediately. You can then use insertText in the SAME batch without calling presentations_get again:

{"createSlide": {"objectId": "slide_geo", "insertionIndex": 1, "slideLayoutReference": {"predefinedLayout": "TITLE_AND_BODY"}, "placeholderIdMappings": [{"layoutPlaceholder": {"type": "TITLE", "index": 0}, "objectId": "title_box_geo"}, {"layoutPlaceholder": {"type": "BODY", "index": 0}, "objectId": "body_box_geo"}]}}

For TITLE_AND_TWO_COLUMNS layout use type "BODY" with index 0 and index 1 (NOT BODY_1 or BODY_2): [{"layoutPlaceholder": {"type": "BODY", "index": 0}, "objectId": "body_left"}, {"layoutPlaceholder": {"type": "BODY", "index": 1}, "objectId": "body_right"}]. Valid layoutPlaceholder types are only: NONE, BODY, CHART, CLIP_ART, CENTERED_TITLE, DIAGRAM, DATE_AND_TIME, FOOTER, HEADER, MEDIA, OBJECT, PICTURE, SLIDE_NUMBER, SUBTITLE, TABLE, TITLE, SLIDE_IMAGE.

Then use insertText with objectId "title_box_geo" and "body_box_geo" in the same requests array. Never guess IDs like slide_2_i0 - they do not exist until you assign them via placeholderIdMappings.

AESTHETICS - You CAN add colors, themes, and styling. Use presentations_batch_update with these requests:
- Background color: updatePageProperties with pageBackgroundFill. Example: {"updatePageProperties": {"objectId": "slide_id", "pageProperties": {"pageBackgroundFill": {"solidFill": {"color": {"rgbColor": {"red": 0.0, "green": 0.1, "blue": 0.2}}}}}, "fields": "pageBackgroundFill"}}
- Decorative shapes: createShape must use elementProperties for pageObjectId, size, transform. Example: {"createShape": {"objectId": "bar_id", "shapeType": "RECTANGLE", "elementProperties": {"pageObjectId": "slide_id", "size": {"width": {"magnitude": 9144000, "unit": "EMU"}, "height": {"magnitude": 95250, "unit": "EMU"}}, "transform": {"scaleX": 1, "scaleY": 1, "translateX": 0, "translateY": 0, "unit": "EMU"}}}}
- Text styling: updateTextStyle for color must use foregroundColor.opaqueColor (NOT solidFill). Example: {"updateTextStyle": {"objectId": "text_id", "textRange": {"type": "ALL"}, "style": {"foregroundColor": {"opaqueColor": {"rgbColor": {"red": 0.04, "green": 0.33, "blue": 0.45}}}, "fontSize": {"magnitude": 16, "unit": "PT"}, "bold": true}, "fields": "foregroundColor,fontSize,bold"}}
- CRITICAL - Colors in updateTextStyle: use "foregroundColor": {"opaqueColor": {"rgbColor": {"red": r, "green": g, "blue": b}}} with 0-1 floats. Never use foregroundColor.solidFill.

updatePageElementTransform - Use for precise alignment and affine transformations (moving, scaling, shearing). Ensures elements follow a design grid instead of random placement:
- applyMode: "ABSOLUTE" replaces the transform; "RELATIVE" multiplies with existing.
- transform: {scaleX, scaleY, shearX, shearY, translateX, translateY, unit: "EMU"}.
- Example: {"updatePageElementTransform": {"objectId": "shape_id", "transform": {"scaleX": 1, "scaleY": 1, "translateX": 914400, "translateY": 457200, "unit": "EMU"}, "applyMode": "ABSOLUTE"}}
- Slide dimensions: ~9144000 EMU width, ~6858000 EMU height. Use translateX/translateY for positioning (e.g. center: translateX ~4572000, translateY ~3429000).

When users ask for "pretty slides," "colors," "theme," or "aesthetics," use updatePageProperties, createShape, updateTextStyle, and updatePageElementTransform—they are all inside batch_update. Do not say you cannot do it.

ICONS - When users ask for icons, decorative icons, or visual symbols on slides:
- Use add_icon_to_slide with presentationId, pageObjectId, and a descriptive query (e.g. "rocket", "lightbulb", "checkmark").
- The tool handles search + createImage internally. Do not call search_icon separately.

You may make up to 40 tool-call rounds (configurable via AGENT_MAX_ROUNDS). Use the full context from each tool result. Do not stop until the user's request is fully satisfied, then respond with a clear summary."""


def _preview(s: str, max_len: int = 300) -> str:
    s = str(s)
    return s[:max_len] + "..." if len(s) > max_len else s


def _normalize_text_newlines(text: str) -> str:
    """Replace literal \\u000A and \\n with real newlines in insertText."""
    if not isinstance(text, str):
        return text
    return text.replace("\\u000A", "\n").replace("\u000A", "\n").replace("\\n", "\n").replace("\\r", "\r")


def _normalize_batch_requests(obj):
    """Recursively convert whole-number floats to ints, and normalize insertText text (\\u000A -> newline)."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k == "insertText" and isinstance(v, dict) and "text" in v:
                out[k] = {**v, "text": _normalize_text_newlines(v["text"])}
            else:
                out[k] = _normalize_batch_requests(v)
        return out
    if isinstance(obj, list):
        return [_normalize_batch_requests(v) for v in obj]
    if isinstance(obj, float) and obj == int(obj):
        return int(obj)
    return obj


def _to_jsonable(obj):
    """Convert protobuf MapComposite/RepeatedComposite to plain JSON-serializable types."""
    if obj is None or isinstance(obj, (bool, int, float)):
        return obj
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    # Protobuf MapComposite (dict-like) - check before list-like
    if hasattr(obj, "items") and callable(getattr(obj, "items")):
        try:
            return {str(k): _to_jsonable(v) for k, v in obj.items()}
        except Exception:
            pass
    # Protobuf RepeatedComposite (list-like)
    if hasattr(obj, "__iter__") and not isinstance(obj, (str, bytes)):
        try:
            return [_to_jsonable(v) for v in obj]
        except Exception:
            pass
    return str(obj)


def _make_small_icon_data_url(svg: str, max_url_len: int = 2000) -> str | None:
    """
    Render SVG → PNG, aggressively shrink until the data URL is under max_url_len characters.
    Returns data URL or None if it cannot be made small enough.
    """
    import base64
    from io import BytesIO

    try:
        from PIL import Image
    except ImportError:
        # Pillow not available; fall back to single-size render.
        png_bytes = svg_to_png_bytes(svg, output_width=32, output_height=32)
        b64 = base64.b64encode(png_bytes).decode("ascii")
        data_url = f"data:image/png;base64,{b64}"
        return data_url if len(data_url) <= max_url_len else None

    width, height = 32, 32  # start small

    for _attempt in range(6):
        png_bytes = svg_to_png_bytes(svg, output_width=width, output_height=height)
        try:
            img = Image.open(BytesIO(png_bytes))
            img = img.convert("RGBA")
            img_p = img.quantize(colors=16, method=Image.MEDIANCUT)
            buf = BytesIO()
            img_p.save(buf, format="PNG", optimize=True, compress_level=9)
            png_bytes = buf.getvalue()
        except Exception:
            pass

        b64 = base64.b64encode(png_bytes).decode("ascii")
        data_url = f"data:image/png;base64,{b64}"
        if len(data_url) <= max_url_len:
            return data_url

        width = max(8, width // 2)
        height = max(8, height // 2)

    return None


def _execute_add_icon_to_slide(args: dict) -> dict:
    """Search icon, convert to PNG, add to slide via createImage. Keeps SVG/URL handling internal."""
    presentation_id = args.get("presentationId")
    page_object_id = args.get("pageObjectId")
    query = args.get("query", "").strip()
    object_id = args.get("objectId") or f"icon_{args.get('query', 'icon').replace(' ', '_')}_{id(args) % 10000}"

    if not presentation_id or not page_object_id or not query:
        return {"success": False, "error": "presentationId, pageObjectId, and query are required"}

    try:
        results = search_icon(query, k=1)
        if not results:
            return {"success": False, "error": f"No icon found for query: {query}"}

        icon = results[0]
        name = icon["name"]
        svg = icon.get("svg", "")
        if not svg:
            return {"success": False, "error": f"Icon '{name}' has no SVG content"}

        data_url = _make_small_icon_data_url(svg, max_url_len=2000)
        if not data_url:
            # As a fallback, if ICON_BASE_URL is set, use HTTP endpoint; otherwise return error.
            icon_base_url = os.environ.get("ICON_BASE_URL", "").rstrip("/")
            if icon_base_url:
                image_url = f"{icon_base_url}/api/icon/png?name={name}"
            else:
                return {
                    "success": False,
                    "error": "Icon SVG cannot be embedded under 2KB and no ICON_BASE_URL is configured.",
                }
        else:
            image_url = data_url

        tx = args.get("translateX")
        ty = args.get("translateY")
        if tx is None:
            tx = 4345200  # ~center X (9144000/2 - 457200/2)
        if ty is None:
            ty = 3200400   # ~center Y (6858000/2 - 457200/2)

        size_emu = 457200  # 0.5 inch
        create_image = {
            "objectId": object_id,
            "url": image_url,
            "elementProperties": {
                "pageObjectId": page_object_id,
                "size": {
                    "width": {"magnitude": size_emu, "unit": "EMU"},
                    "height": {"magnitude": size_emu, "unit": "EMU"},
                },
                "transform": {
                    "scaleX": 1,
                    "scaleY": 1,
                    "translateX": int(tx),
                    "translateY": int(ty),
                    "unit": "EMU",
                },
            },
        }

        reqs = [{"createImage": create_image}]
        reqs = _normalize_batch_requests(reqs)
        presentations_batch_update(presentation_id, reqs)

        return {"success": True, "objectId": object_id, "icon": name}
    except RuntimeError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        log.warning("add_icon_to_slide failed: %s", e)
        return {"success": False, "error": str(e)}


def _execute_tool(name: str, args: dict) -> str:
    try:
        log.info("Tool called: %s | args: %s", name, args)
        if name == "presentations_create":
            r = presentations_create(title=args.get("title", "Untitled Presentation"))
        elif name == "presentations_get":
            r = presentations_get(args["presentationId"])
        elif name == "presentations_batch_update":
            reqs = args.get("requests")
            if isinstance(reqs, str):
                reqs = json.loads(reqs) if reqs.strip().startswith("[") else []
            if not isinstance(reqs, list):
                reqs = [reqs] if reqs else []
            reqs = _normalize_batch_requests(reqs)
            r = presentations_batch_update(args["presentationId"], reqs)
        elif name == "pages_get_thumbnail":
            r = pages_get_thumbnail(args["presentationId"], args["pageObjectId"])
        elif name == "drive_files_list":
            r = drive_files_list(
                page_size=args.get("pageSize", 10),
                q=args.get("q"),
            )
        elif name == "add_icon_to_slide":
            r = _execute_add_icon_to_slide(args)
        elif name == "scaffold_presentation":
            r = scaffold_presentation(
                title=args.get("title", "Untitled Presentation"),
                num_slides=args.get("numSlides", 1),
                theme_colors=args.get("themeColors") or {},
                logo_url=args.get("logoUrl"),
            )
        else:
            return f"Unknown tool: {name}"
        out = json.dumps(r, indent=2) if isinstance(r, dict) else str(r)
        log.info("Tool %s response preview: %s", name, _preview(out))
        return out
    except Exception as e:
        log.warning("Tool %s failed: %s", name, e)
        return f"Error: {e}"


def run_agent(
    messages: list[dict],
    current_file: dict | None = None,
    current_document: dict | None = None,
) -> dict:
    api_key = os.environ.get("GOOGLE_GENERATIVE_AI_API_KEY")
    if not api_key:
        return {"text": "No LLM configured. Set GOOGLE_GENERATIVE_AI_API_KEY in .env", "tool_calls": []}

    system_instruction = SYSTEM_INSTRUCTION
    if current_file and current_file.get("id") and current_file.get("name"):
        file_ctx = (
            f"\n\n[[CURRENT FILE CONTEXT]] The user is currently working on: \"{current_file.get('name')}\" "
            f"(presentationId/fileId: {current_file.get('id')}). For Slides operations (presentations_get, "
            "presentations_batch_update, pages_get_thumbnail), use this presentationId unless the user "
            "explicitly requests a different file. Do not search Drive for this file—use the id above."
        )
        system_instruction = system_instruction + file_ctx

    genai.configure(api_key=api_key)
    # Prefer per-agent model, then global fallbacks.
    model_name = (
        os.environ.get("AGENT_MODEL")
        or os.environ.get("GEMINI_MODEL")
        or os.environ.get("GOOGLE_GENERATIVE_AI_MODEL")
        or "gemini-2.5-flash"
    )
    model = genai.GenerativeModel(
        model_name=model_name,
        tools=[Tool(function_declarations=TOOL_DECLARATIONS)],
        system_instruction=system_instruction,
    )

    # Build history and last user message
    history = []
    for m in messages[:-1]:
        role = m.get("role")
        content = m.get("content", "")
        if isinstance(content, list):
            content = content[0].get("text", "") if content else ""
        if role == "user":
            history.append({"role": "user", "parts": [content]})
        elif role == "assistant":
            history.append({"role": "model", "parts": [content]})

    last = messages[-1] if messages else {}
    user_content = last.get("content", "")
    if isinstance(user_content, list):
        user_content = user_content[0].get("text", "") if user_content else ""

    from google.generativeai import protos

    chat = model.start_chat(history=history)
    tool_calls_made = []
    max_rounds = int(os.environ.get("AGENT_MAX_ROUNDS", "40"))
    round_num = 0

    try:
        response = chat.send_message(user_content)
    except Exception as e:
        err = str(e).lower()
        if "malformed_function_call" in err or "finish_reason" in err:
            log.warning("Model returned malformed response: %s", e)
            return {"text": "The model returned an unexpected response. Please try your request again.", "tool_calls": []}
        raise

    while response.candidates and round_num < max_rounds:
        round_num += 1
        log.info("Agent round %d/%d", round_num, max_rounds)
        parts = response.candidates[0].content.parts
        if not parts:
            break

        # Collect all function calls from this response
        function_responses = []
        has_text = False
        text_content = ""

        for part in parts:
            fc = getattr(part, "function_call", None)
            if fc:
                name = fc.name
                args = _to_jsonable(dict(fc.args)) if fc.args else {}
                result = _execute_tool(name, args)
                tool_calls_made.append({"name": name, "args": args})
                function_responses.append(
                    protos.Part(function_response=protos.FunctionResponse(name=name, response={"result": result})))
            else:
                has_text = True
                text_content = getattr(part, "text", None) or (response.text if hasattr(response, "text") else "")

        if has_text and not function_responses:
            return {"text": text_content, "tool_calls": tool_calls_made}

        if not function_responses:
            break

        # Send all tool results in one message for full context; model continues the loop
        try:
            response = chat.send_message(function_responses)
        except Exception as e:
            err = str(e).lower()
            if "malformed_function_call" in err or "finish_reason" in err:
                log.warning("Model returned malformed response after tools: %s", e)
                if tool_calls_made:
                    return {"text": f"Some actions completed, but the model returned an unexpected response. Tools used: {[t['name'] for t in tool_calls_made]}. You may check your presentation.", "tool_calls": tool_calls_made}
                return {"text": "The model returned an unexpected response. Please try again.", "tool_calls": []}
            raise

    # Check for malformed finish reason (e.g. MALFORMED_FUNCTION_CALL)
    if response.candidates:
        cand = response.candidates[0]
        fr = str(getattr(cand, "finish_reason", "") or "")
        if "MALFORMED" in fr or "SAFETY" in fr:
            log.warning("Unexpected finish_reason: %s", fr)
            if tool_calls_made:
                return {"text": f"Some actions completed. Tools used: {[t['name'] for t in tool_calls_made]}. Check your presentation.", "tool_calls": tool_calls_made}
            return {"text": "The model returned an unexpected response. Please try again.", "tool_calls": []}

    final = getattr(response, "text", "") or ""
    if not final and tool_calls_made:
        final = f"Reached max rounds ({max_rounds}). Tools used: {[t['name'] for t in tool_calls_made]}. Task may be incomplete."
    return {"text": final or "No response", "tool_calls": tool_calls_made}
