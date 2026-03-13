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

GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", os.getenv("GOOGLE_GENERATIVE_AI_MODEL", "gemini-2.5-flash"))

PLAN_PROMPT_TEMPLATE = """You are a presentation planning expert. Plan only when the user explicitly asks for a presentation plan, slide outline, or deck (e.g. "create a plan", "make a deck", "outline slides"). If the user is just asking a question (e.g. what is this about, summarize, explain), answer in natural language and do NOT output any JSON.

When the user explicitly asks for a plan, create a detailed, execution-ready plan that describes exactly how each slide will look and where every element goes.

Slide dimensions: 960 points wide × 540 points tall (16:9). All positions and sizes are in points (1 inch = 72 points).

When producing a plan, output a single JSON object (no markdown, no code fence) with this exact structure.
IMPORTANT: For each slide, include "details" — a 2-4 sentence description of exactly what to add: specific text, bullet points, visuals, icons, and layout instructions. Be concrete so the agent can build it.
{
  "title": "Short presentation title",
  "slides": [
    {
      "slide_number": 1,
      "title": "Slide title",
      "layout": "One-line description of visual layout (e.g. 'Title centered at top; single icon top-right; body text left-aligned below')",
      "details": "Concrete instructions: exact title text, subtitle, bullet points to add, icon placement, colors. What should appear on this slide.",
      "content": "Main body text or bullet points. Use actual newline characters between lines (each line becomes one bullet when createParagraphBullets is applied). Do not use escaped backslash-n.",
      "elements": [
        { "type": "text_box", "left": 72, "top": 80, "width": 816, "height": 56, "content": "Title text here", "font_size": 36 },
        { "type": "text_box", "left": 72, "top": 160, "width": 816, "height": 320, "content": "Body or bullets - one line per bullet" },
        { "type": "icon", "left": 872, "top": 40, "width": 48, "height": 48, "query": "chart" },
        { "type": "image", "left": 600, "top": 180, "width": 320, "height": 200, "image_description": "Hero image of team" }
      ]
    }
  ],
  "aesthetics": {
    "theme": "e.g. Professional blue, Modern minimal",
    "primary_color": "#hex or null",
    "suggested_icons_style": "outline or fill"
  }
}

Element types and required fields:
- text_box: left, top, width, height (numbers), content (string). Optional: font_size (number).
- icon: left, top, width, height, query (e.g. "chart", "people", "checkmark"). Add ONLY where an icon adds real value — not on every slide.
- image: left, top, width, height, image_description (string for AI image gen). Add only when the slide needs a visual.
- shape: left, top, width, height, shape_type (e.g. "rectangle"), optional fill or use for dividers/backgrounds.

Requirements:
- For each slide, provide "layout" (how the slide looks: where title, body, icons, images sit) and "elements" with exact coordinates.
- Only add icon elements where they add value (e.g. one icon for "key metric" slide, none for a plain title slide). Do not add icons in bulk to every slide.
- Only add image elements when the slide needs a visual; include exact left, top, width, height and image_description.
- Coordinates must be within 0–960 (width) and 0–540 (height). Leave margins (e.g. left ≥ 72, right ≤ 888).
- Order elements in a logical draw order (e.g. background shape first, then text, then icons).
- Include theme and color in aesthetics.
- When producing a plan, output only the JSON object, no other text before or after."""


def generate_plan(topic: str, document_context: str | None = None) -> tuple[dict[str, Any] | None, str]:
    """
    Run the planner LLM. Returns (plan, text). Plan is non-None only when the user
    explicitly asked for a plan and the model output valid plan JSON; otherwise
    returns (None, raw response text) for RAG-style answers.
    If document_context is provided (from an ingested document), it is prepended so the plan is based on that content.
    """
    topic = topic.strip()
    if not topic:
        raise ValueError("Topic must not be empty.")
    if document_context and document_context.strip():
        prompt = f"Document content (use this to create the presentation plan):\n\n{document_context.strip()}\n\nUser request:\n\n{topic}"
    else:
        prompt = f"User request:\n\n{topic}"

    logger.info("Planner: generating for topic=%r", topic[:80])

    api_key = os.environ.get("GOOGLE_GENERATIVE_AI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None, "No API key. Set GOOGLE_GENERATIVE_AI_API_KEY in .env"

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
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