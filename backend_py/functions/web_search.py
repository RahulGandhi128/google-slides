import logging
import os
from typing import Any, Dict

from google import genai
from google.genai import types

log = logging.getLogger("functions.web_search")


def web_search(query: str, max_results: int = 5) -> Dict[str, Any]:
    """
    Web search using Gemini's built-in Google Search grounding.

    This uses the same Gemini API key you already configure for the app; no
    separate Tavily key is required.
    """
    query = (query or "").strip()
    if not query:
        raise ValueError("query must not be empty")

    api_key = os.getenv("GOOGLE_GENERATIVE_AI_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("No Gemini API key. Set GOOGLE_GENERATIVE_AI_API_KEY in .env")

    client = genai.Client(api_key=api_key)

    model_name = (
        os.getenv("RESEARCH_SEARCH_MODEL")
        or os.getenv("RESEARCH_MODEL")
        or os.getenv("GEMINI_MODEL")
        or os.getenv("GOOGLE_GENERATIVE_AI_MODEL")
        or "gemini-2.5-flash"
    )

    grounding_tool = types.Tool(google_search=types.GoogleSearch())
    config = types.GenerateContentConfig(tools=[grounding_tool])

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=query,
            config=config,
        )
    except Exception as e:
        log.warning("Gemini Google Search grounding failed: %s", e)
        raise RuntimeError(f"Web search failed: {e}") from e

    text = (response.text or "").strip()

    # Try to extract simple citation URLs from grounding metadata if present.
    citations = []
    try:
        cand = response.candidates[0] if response.candidates else None
        gm = getattr(cand, "grounding_metadata", None)
        if gm and getattr(gm, "grounding_chunks", None):
            for chunk in gm.grounding_chunks:
                web = getattr(chunk, "web", None)
                if web and getattr(web, "uri", None):
                    citations.append({"url": web.uri, "title": getattr(web, "title", "")})
    except Exception:
        # Best-effort; ignore citation parsing errors.
        pass

    return {
        "provider": "gemini_google_search",
        "model": model_name,
        "query": query,
        "answer": text,
        "citations": citations,
    }
