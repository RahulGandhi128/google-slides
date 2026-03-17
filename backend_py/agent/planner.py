"""
planner.py

Single-call planner LLM: one Gemini request, no tools. Returns a structured JSON plan
(title, slides, aesthetics) for the whole presentation.

Used when the frontend sends to POST /api/plan (Plan mode toggle).
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

PLANNER_MODEL: str = (
    os.getenv("PLANNER_MODEL")
    or os.getenv("GEMINI_MODEL")
    or os.getenv("GOOGLE_GENERATIVE_AI_MODEL")
    or "gemini-2.5-flash"
)

PLAN_PROMPT_TEMPLATE = """You are a slide-design planner. Your ONLY role is to produce a single, execution-ready presentation plan (slide layout and content). Do not answer general questions, summarize documents, or do anything other than output a plan when the user explicitly asks for one.

WHEN TO OUTPUT A PLAN:
- Only when the user explicitly asks for a presentation plan, slide outline, or deck (e.g. "create a plan", "make a deck", "outline slides", "design slides for this").
- If the user is just asking a question (e.g. what is this about, summarize, explain) or not asking for a plan, respond in natural language and do NOT output any JSON.

PRESERVE DOCUMENT CONTENT VERBATIM:
- The "Document content" / outline you receive is the research or outline text to base the plan on. You MUST preserve it verbatim.
- Do NOT paraphrase, summarize, or rewrite that text. Copy the exact wording from the document into slide titles, bullets, and content fields.
- Your job is layout and structure only: take the given text and place it on slides without changing wording.

CONSISTENT TYPOGRAPHY:
- Use a single typography system across all slides. Example: slide titles 24pt (or 28pt), body text 14pt (or 16pt) everywhere.
- Do NOT vary body font size arbitrarily (no mixing 12pt, 14pt, 16pt across slides). Pick one body size and use it in every text_box that is body content.
- Specify font_size in elements: e.g. title text_box font_size 24 or 28, body text_box font_size 14 or 16 consistently.

LAYOUT VARIETY (do not use "title + bullets" on every slide):
- Vary layouts per slide. Use: two-column layouts, split layout (text left / visual or image right, or vice versa), stat or data grids, accent bars or colored strips, title-only slides, section divider slides, full-bleed title with subtitle.
- Not every slide should be "title centered + bullet list below". Include at least 2–3 different layout types in the deck (e.g. split, columns, accent bar, grid).
- "layout" and "details" should describe the actual visual structure (e.g. "Two columns: left column 3 stat cards, right column key message"; "Split: title top, image left 50%, body text right 50%").

WHEN PRODUCING A PLAN:
- Output exactly one JSON object (no markdown, no code fence, no other text before or after).
- Your job is slide design only: define title, slides, layout, text content, and element positions. Do not generate images, fetch URLs, or do anything beyond describing what goes on each slide.
- Where a slide needs a picture or visual, leave a reserved space by adding an "image" element with left, top, width, height, and image_description. The builder will fill that space later; you only reserve the slot and describe what should go there.

Slide dimensions: 960 points wide × 540 points tall (16:9). All positions and sizes are in points (1 inch = 72 points).

JSON structure (output only this, nothing else):
{
  "title": "Short presentation title",
  "slides": [
    {
      "slide_number": 1,
      "title": "Slide title",
      "layout": "One-line description of visual layout (e.g. 'Split: title top; image placeholder right; body text left')",
      "details": "Concrete instructions: exact title text, subtitle, bullet points, icon placement, colors. What should appear on this slide.",
      "content": "Main body text or bullet points. Use actual newline characters between lines (each line becomes one bullet). Copy from document verbatim. Do not use escaped backslash-n.",
      "elements": [
        { "type": "text_box", "left": 72, "top": 80, "width": 816, "height": 56, "content": "Title text here", "font_size": 24 },
        { "type": "text_box", "left": 72, "top": 160, "width": 816, "height": 320, "content": "Body or bullets - one line per bullet", "font_size": 14 },
        { "type": "icon", "left": 872, "top": 40, "width": 48, "height": 48, "query": "chart" },
        { "type": "image", "left": 600, "top": 180, "width": 320, "height": 200, "image_description": "Placeholder: hero image (space reserved)" }
      ]
    }
  ],
  "aesthetics": {
    "theme": "e.g. Professional blue, Modern minimal",
    "primary_color": "#hex or null",
    "suggested_icons_style": "outline or fill",
    "theme_colors": {
      "heading_color": "#hex",
      "body_text_color": "#hex",
      "background_color": "#hex",
      "accent_color": "#hex",
      "shapes_color": "#hex",
      "charts_color": "#hex"
    }
  }
}

You MUST include "theme_colors" in aesthetics with all six keys: heading_color, body_text_color, background_color, accent_color, shapes_color, charts_color. Use hex values (e.g. "#1a1a2e"). When a color palette is provided in the request, use those colors to fill theme_colors (dominant for headings/accents, palette entries for shapes/charts/background as appropriate). Otherwise choose a coherent theme and set all six.

Element types:
- text_box: left, top, width, height (numbers), content (string). Optional: font_size (number). Use font_size 24 or 28 for titles, 14 or 16 for body—consistently.
- icon: left, top, width, height, query (e.g. "chart", "people"). Add only where an icon adds value.
- image: left, top, width, height, image_description (string). Use to reserve space for an image; describe what should go there. Do not generate or fetch images—only leave the slot.
- shape: left, top, width, height, shape_type (e.g. "rectangle"), optional fill.

Requirements:
- For each slide: "layout", "details", "content", and "elements" with exact coordinates.
- Content must be copied from the document verbatim; do not rewrite.
- Where a slide needs a visual, add one image element with image_description; the plan only reserves space.
- Coordinates within 0–960 (width) and 0–540 (height). Margins: left ≥ 72, right ≤ 888.
- Order elements: background shape first, then text, then icons, then image placeholders.
- Include theme and theme_colors (all six keys) in aesthetics.
- Output only the JSON object, no other text before or after."""


def _design_prompt_addon(design_settings: dict | None) -> str:
    """Build addon string for design constraints (style, max lines, printable)."""
    if not design_settings:
        return ""
    parts = []
    style = design_settings.get("style", "minimalist_bw")
    if style == "minimalist_bw":
        parts.append("Use a minimalist style: white background, black text only. Aesthetics: theme 'Minimalist B&W', no decorative colors.")
    elif style == "brand_colors":
        parts.append("Use brand accent color for headers and accents; keep layout professional. Aesthetics: theme aligned with brand.")
    elif style == "dark":
        parts.append("Use a dark theme: dark background, light text. Aesthetics: theme 'Dark'.")
    max_lines = design_settings.get("maxLinesPerSlide")
    if max_lines is not None:
        parts.append(f"Limit body text to at most {max_lines} lines per slide.")
    if design_settings.get("printable"):
        parts.append("Printable: white backgrounds, black text, no gradients. All content must be legible in grayscale print.")
    if not parts:
        return ""
    return "\n\nDesign constraints (follow these in the plan and aesthetics): " + "; ".join(parts)


def _color_palette_prompt_addon(color_palette: dict | None) -> str:
    """Build addon that gives the LLM the extracted logo color palette to use for theme_colors."""
    if not color_palette:
        return ""
    dominant = color_palette.get("dominant")
    palette = color_palette.get("palette") or []
    if not dominant and not palette:
        return ""
    parts = [
        "The user uploaded a logo; use these extracted colors for the presentation theme."
    ]
    if dominant:
        parts.append(f"Dominant color (use for headings, accent, primary): {dominant}")
    if palette:
        hex_list = ", ".join(palette[:8])  # cap for prompt length
        parts.append(f"Palette (use for shapes, charts, backgrounds, variety): {hex_list}")
    parts.append(
        "Set aesthetics.theme_colors using these hex values: heading_color and accent_color from dominant; "
        "body_text_color and background_color for readability (e.g. dark text on light or light on dark); "
        "shapes_color and charts_color from the palette. Output all six theme_colors."
    )
    return "\n\n" + " ".join(parts)


def generate_plan(
    topic: str,
    document_context: str | None = None,
    design_settings: dict | None = None,
    color_palette: dict | None = None,
) -> tuple[dict[str, Any] | None, str]:
    """
    Run the planner LLM. Returns (plan, text). Plan is non-None only when the user
    explicitly asked for a plan and the model output valid plan JSON; otherwise
    returns (None, raw response text) for RAG-style answers.
    If document_context is provided (from an ingested document), it is prepended so the plan is based on that content.
    design_settings: optional dict with style, maxLinesPerSlide, printable for design constraints.
    color_palette: optional { "dominant": "#hex", "palette": ["#hex", ...] } from logo extraction; used to set theme_colors.
    """
    topic = topic.strip()
    if not topic:
        raise ValueError("Topic must not be empty.")
    if document_context and document_context.strip():
        prompt = (
            "Document content (use this to create the presentation plan; copy its text verbatim into slides, do not paraphrase):\n\n"
            f"{document_context.strip()}\n\nUser request:\n\n{topic}"
        )
    else:
        prompt = f"User request:\n\n{topic}"
    prompt += _design_prompt_addon(design_settings)
    prompt += _color_palette_prompt_addon(color_palette)

    logger.info("Planner: generating for topic=%r", topic[:80])

    api_key = os.environ.get("GOOGLE_GENERATIVE_AI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None, "No API key. Set GOOGLE_GENERATIVE_AI_API_KEY in .env"

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=PLANNER_MODEL,
        system_instruction=PLAN_PROMPT_TEMPLATE,
        generation_config={"temperature": 0.3},
    )
    response = model.generate_content(prompt)

    raw = (response.text or "").strip()
    if not raw:
        return None, "The model returned no response."

    # Try to parse as plan JSON (only when user asked for a plan)
    text = raw
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if json_match:
        text = json_match.group(1).strip()
    try:
        plan = json.loads(text)
    except json.JSONDecodeError:
        logger.info("Planner: response is not JSON (likely natural-language answer)")
        return None, raw

    if not isinstance(plan, dict) or "slides" not in plan or "title" not in plan:
        return None, raw

    # Normalize structure
    plan.setdefault("title", "Presentation")
    plan.setdefault("slides", [])
    plan.setdefault("aesthetics", {})
    aesthetics = plan["aesthetics"]
    if not isinstance(aesthetics, dict):
        aesthetics = {}
        plan["aesthetics"] = aesthetics
    theme_colors = aesthetics.get("theme_colors")
    if not isinstance(theme_colors, dict):
        theme_colors = {}
    for key in ("heading_color", "body_text_color", "background_color", "accent_color", "shapes_color", "charts_color"):
        theme_colors.setdefault(key, aesthetics.get("primary_color") or "#333333")
    plan["aesthetics"]["theme_colors"] = theme_colors
    if not isinstance(plan["slides"], list):
        plan["slides"] = []
    for i, s in enumerate(plan["slides"]):
        if not isinstance(s, dict):
            plan["slides"][i] = {"slide_number": i + 1, "title": "Slide", "layout": "", "content": "", "elements": []}
        else:
            s.setdefault("slide_number", i + 1)
            s.setdefault("title", "Slide")
            s.setdefault("layout", "")
            s.setdefault("details", s.get("content", ""))
            s.setdefault("content", "")
            s.setdefault("elements", [])
            if not isinstance(s["elements"], list):
                s["elements"] = []
            for j, el in enumerate(s["elements"]):
                if not isinstance(el, dict):
                    s["elements"][j] = {"type": "text_box", "left": 72, "top": 80, "width": 400, "height": 40, "content": ""}
                else:
                    el.setdefault("left", 72)
                    el.setdefault("top", 80)
                    el.setdefault("width", 200)
                    el.setdefault("height", 40)
            # Keep legacy fields for backward compatibility
            s.setdefault("icons", [])
            s.setdefault("theme_note", None)
            s.setdefault("image_description", None)
            s.setdefault("chart_or_table", None)

    logger.info("Planner: plan generated with title=%r, %d slides", plan.get("title"), len(plan.get("slides", [])))
    return plan, raw