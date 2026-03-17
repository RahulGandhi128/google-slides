"""
Research agent: document-only deep research.
Uses only list_documents and document_search. No Slides/Drive tools.
"""
import json
import logging
import os

import google.generativeai as genai
from google.generativeai.types import FunctionDeclaration, Tool

log = logging.getLogger("agent.research")

RESEARCH_TOOLS = [
    FunctionDeclaration(
        name="list_documents",
        description="List the user's ingested documents (upload_id, filename). Call this ONLY when the user explicitly asks to list their files, see what documents they have, or choose a document to search. Do not call for general questions.",
        parameters={"type": "object", "properties": {}},
    ),
    FunctionDeclaration(
        name="document_search",
        description="Semantic search over one ingested document. Use ONLY when you have upload_id(s) from the attached documents in context (see [[DOCUMENTS TO RESEARCH]] below). Call multiple times with different queries to gather information; synthesize results.",
        parameters={
            "type": "object",
            "properties": {
                "upload_id": {"type": "string", "description": "Document upload_id from the attached documents list in context"},
                "query": {"type": "string", "description": "Search query or aspect to research"},
                "k": {"type": "integer", "description": "Number of chunks to return (default 10, use 15-20 for broader coverage)"},
            },
            "required": ["upload_id", "query"],
        },
    ),
    FunctionDeclaration(
        name="web_search",
        description=(
            "Search the web for up-to-date information beyond the model's own knowledge. "
            "Use when the user explicitly asks to search the web / internet, or when the "
            "question clearly requires current external data (recent news, latest stats, "
            "current product info). Do not use for questions that can be answered from "
            "general knowledge or the user's documents alone."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Web search query string"},
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of search results to retrieve (default 5).",
                },
            },
            "required": ["query"],
        },
    ),
]

RESEARCH_SYSTEM = """You are a deep research assistant for a sell-side investment bank. Your output is used to prepare pitch decks, investor presentations, and equity research. Be factual, precise, and use the same language as the underlying source documents when present; otherwise use standard finance and legal terminology. No fluff, no extravagant or promotional wording—stick to facts and clear analysis.

Content and structure:
- When the user asks for slide content, outlines, or research that will go on slides: aim for at least 10 lines of factual content per slide (or per section) unless they specify otherwise (e.g. "3 bullets per slide"). Each line should be a single, verifiable fact or finding from the documents or your search.
- Use the exact terminology and phrasing from the source documents where possible (e.g. DRHP, offer terms, risk factors). When no document is attached, use standard investment-banking and legal language (e.g. "key risks", "valuation metrics", "regulatory considerations").
- Do not use marketing or flowery language. Avoid superlatives and unsupported claims. Prefer "Revenue grew 12% YoY" over "Strong revenue growth."

Tools (use only when appropriate):
- list_documents: lists the user's ingested documents (upload_id, filename). Use ONLY when the user explicitly asks to list their files, see their documents, or pick a document to search. Do NOT call for general queries.
- document_search(upload_id, query, k): semantic search over one document. Use ONLY when the context below provides attached documents with upload_ids. Do NOT call if no documents are attached.
- web_search(query, max_results): search the web for up-to-date external information when the user asks for web/internet search or the task clearly requires current data beyond these documents.

You SHOULD still use a TWO-PHASE mental model for any non-trivial question (anything longer than 1–2 short paragraphs or that mentions analysis, DRHP, pitch decks, investment, risk analysis, strategy, etc.):

PHASE 1 — GATHER & BUILD CORPUS (NO FINAL ANSWER YET)
- Goal: internally build a rich “research corpus” by calling tools multiple times.
- When there are attached documents:
  - For EACH document that is likely relevant, call document_search several times with different focused queries, such as:
    - "overview and business model"
    - "key metrics, revenue, profitability"
    - "products and services"
    - "risk factors and regulatory issues"
    - "management, ownership, and governance"
  - Use k between 10–20 for broad coverage.
  - If there are at least 2 documents (e.g. company website + DRHP), you SHOULD search EACH of them with several different queries.
- For each document_search call:
  - Read all returned chunks carefully.
  - Add their important facts into your internal mental model/corpus.
  - Do NOT produce a final answer yet.
- You may also call web_search when the user explicitly wants external web data or the task clearly needs current information.
- Continue PHASE 1 until:
  - You have searched every relevant document at least once, AND
  - You have made multiple searches focusing on different aspects (business model, financials, risks, etc.), AND
  - You feel you could write a 2–3 page memo if asked.
- Only when these conditions are met, move on to PHASE 2 mentally.

PHASE 2 — SYNTHESIZE & TRIM FINAL ANSWER
- In this phase, you MUST:
  - Synthesize and organize the corpus from PHASE 1.
  - Structure the answer clearly (headings, bullets) and avoid repetition.
  - If the user did not ask for a long memo, TRIM the final answer to the level they requested (e.g. short summary, key bullets, etc.).
- Very important: Once you start PHASE 2, you normally should NOT call tools again unless you notice a specific factual gap that must be filled.

Handling different document situations:
- When NO documents are attached (see context below): For general questions (e.g. "make an outline for a pitch", "best practices for X", "structure for 5 slides"), answer directly from your knowledge. Do NOT call list_documents or document_search. Do not mention or search the user's files.
- When NO documents are attached and the user explicitly asks to "list my files", "what documents do I have", or "search my documents for X": then call list_documents. Only call document_search if the user then asks to search a specific document (you will have upload_id from list_documents).
- When documents ARE attached: use only the upload_ids from the context below for document_search. Search across them as needed and synthesize. Do not use list_documents to load more; use only the attached list.
- For web/internet information, you MAY use web_search when the user asks for it explicitly or when up-to-date external data is clearly required. You still cannot access Slides/Drive tools—only the user's ingested documents and the web_search tool.

Output:
- Provide only the final synthesized answer for the user. Do NOT include any special markers like [[RESEARCH_CORPUS]] or [[FINAL_ANSWER]].
- For slide-ready content: structure as clear headings and bullets; each bullet or line should be one fact. If the user asked for "slides" or "deck content", ensure sufficient density (e.g. ~10 factual lines per slide topic) unless they asked for fewer."""

MODIFY_RESEARCH_SYSTEM = """You are a slide-replacement research agent. You receive extracted text from an existing presentation (one block per slide with title and body). Your ONLY job is to find replacement content for each slide from the user's attached documents (and optionally web_search). You work slide-by-slide: for each slide, determine its topic from its title/body, then search documents for content that matches THAT slide only. Do not write about other slides or add extra sections.

Rules:
- For each slide in [[EXTRACTED SLIDES]]: use document_search (and web_search if the user asked for web or current data) with queries derived from that slide's title and body (e.g. "business model", "financials", "risk factors") to find relevant content. Use only the upload_ids from [[DOCUMENTS TO RESEARCH]].
- If you find strong, factual content that fits that slide's topic: set "action": "replace", provide "replacementTitle" (optional) and "replacementBody" (slide-ready text, bullets or short paragraphs). Set "confidence" between 0.0 and 1.0.
- If you do NOT find good content for that slide, or content is off-topic: set "action": "no_change", leave "replacementBody" empty or null, and set "confidence" low. Do not invent content.
- Output ONLY valid JSON, no markdown or extra text. Use this exact schema:
{"slides": [{"slideIndex": 1, "topic": "brief topic", "action": "replace"|"no_change", "replacementTitle": "..." or null, "replacementBody": "..." or null, "confidence": 0.0-1.0, "notes": "optional"}]}
- Preserve slide order (slideIndex) from the extracted slides. One entry per slide.
- Use the same language and terminology as the source documents when you replace; no marketing fluff."""


def _execute_research_tool(name: str, args: dict) -> str:
    if name == "list_documents":
        from database.documents import list_documents as _list_documents
        r = _list_documents(limit=args.get("limit", 100))
        return json.dumps(r, indent=2)
    if name == "document_search":
        from functions.document_search import search_document
        k_raw = args.get("k", 10)
        try:
            k = int(k_raw)
        except (TypeError, ValueError):
            k = 10
        if k <= 0:
            k = 10
        chunks = search_document(
            upload_id=args.get("upload_id", ""),
            query=args.get("query", ""),
            k=k,
        )
        return json.dumps({"chunks": chunks, "count": len(chunks)}, indent=2)
    if name == "web_search":
        from functions.web_search import web_search as _web_search

        result = _web_search(
            query=args.get("query", ""),
            max_results=args.get("max_results", 5),
        )
        return json.dumps(result, indent=2)
    return json.dumps({"error": f"Unknown tool: {name}"})


def _to_jsonable(obj):
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    if hasattr(obj, "items") and callable(getattr(obj, "items")):
        try:
            return {str(k): _to_jsonable(v) for k, v in obj.items()}
        except Exception:
            pass
    if hasattr(obj, "__iter__") and not isinstance(obj, (str, bytes)):
        try:
            return [_to_jsonable(v) for v in obj]
        except Exception:
            pass
    return str(obj)


GROUND_RESPONSE_ADDON = (
    "\n\n[[CRITICAL - GROUND RESPONSE MODE]] When using document_search results, you MUST use the exact text, "
    "language, and facts from the retrieved chunks or source documents. Do NOT paraphrase, summarize, or modify "
    "them. Quote or reproduce the source content faithfully."
)

def run_research_agent(
    query: str,
    documents: list[dict] | None = None,
    ground_response: bool = False,
    mode: str = "general",
    extracted_slides: list[dict] | None = None,
) -> dict:
    """
    Run the research agent. Returns {text, tool_calls} and optionally {replacement_slides} when mode="modify".
    documents: list of {"upload_id": str, "filename": str}. May be empty.
    ground_response: if True, adds instruction to use exact text/facts from source documents.
    mode: "general" (default) or "modify". When "modify", uses slide-replacement prompt and may return replacement_slides.
    extracted_slides: for mode="modify", list of {slideIndex, title, body} from the presentation extract.
    """
    api_key = os.environ.get("GOOGLE_GENERATIVE_AI_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {"text": "No LLM configured. Set GOOGLE_GENERATIVE_AI_API_KEY in .env", "tool_calls": []}

    docs = documents or []
    if len(docs) == 0:
        doc_ctx = (
            "\n\n[[NO DOCUMENTS ATTACHED]] The user has not attached any documents. "
            "Do NOT call list_documents or document_search for this request. Answer directly from your knowledge. Only use list_documents when the user explicitly asks to list their files; only use document_search when documents are attached ([[DOCUMENTS TO RESEARCH]]) or after user asked to search and you have upload_ids from list_documents."
        )
    else:
        lines = ["\n\n[[DOCUMENTS TO RESEARCH]] Use these upload_ids for document_search. You may search across multiple documents and synthesize results:"]
        for d in docs:
            uid = d.get("upload_id") or ""
            fn = d.get("filename") or "document"
            lines.append(f"- upload_id={uid} (filename: {fn})")
        doc_ctx = "\n".join(lines)

    if mode == "modify" and extracted_slides:
        ext_lines = ["\n\n[[EXTRACTED SLIDES]] Replace or leave unchanged based on document search. One JSON entry per slide."]
        for s in extracted_slides:
            idx = s.get("slideIndex") or s.get("slide_number") or 0
            title = (s.get("title") or "").strip() or "Untitled"
            body = (s.get("body") or "").strip() or ""
            ext_lines.append(f"\nSlide {idx}: {title}\n{body}")
        ext_ctx = "\n".join(ext_lines)
        system_instruction = MODIFY_RESEARCH_SYSTEM + ext_ctx + doc_ctx
        # Ensure the model is prompted to output JSON only
        if not query.strip():
            query = "Find replacement content for each slide from the documents above. Output only the JSON object with a 'slides' array."
        else:
            query = f"User instructions: {query.strip()}\n\nOutput only the JSON object with a 'slides' array (one entry per extracted slide)."
    else:
        system_instruction = RESEARCH_SYSTEM + doc_ctx
        if ground_response:
            system_instruction = system_instruction + GROUND_RESPONSE_ADDON

    genai.configure(api_key=api_key)
    model_name = (
        os.environ.get("RESEARCH_MODEL")
        or os.environ.get("GEMINI_MODEL")
        or os.environ.get("GOOGLE_GENERATIVE_AI_MODEL")
        or "gemini-2.5-flash"
    )
    model = genai.GenerativeModel(
        model_name=model_name,
        tools=[Tool(function_declarations=RESEARCH_TOOLS)],
        system_instruction=system_instruction,
    )

    from google.generativeai import protos

    chat = model.start_chat(history=[])
    tool_calls_made = []
    max_rounds = int(
        os.environ.get("RESEARCH_MAX_ROUNDS")
        or os.environ.get("AGENT_MAX_ROUNDS", "15")
    )
    round_num = 0

    try:
        response = chat.send_message(query)
    except Exception as e:
        log.warning("Research agent send_message failed: %s", e)
        return {"text": f"Research failed: {e}. Please try again.", "tool_calls": []}

    while response.candidates and round_num < max_rounds:
        round_num += 1
        log.info("Research agent round %d/%d", round_num, max_rounds)
        parts = response.candidates[0].content.parts
        if not parts:
            break

        function_responses = []
        has_text = False
        text_content = ""

        for part in parts:
            fc = getattr(part, "function_call", None)
            if fc:
                name = fc.name
                args = _to_jsonable(dict(fc.args)) if fc.args else {}
                result = _execute_research_tool(name, args)
                tool_calls_made.append({"name": name, "args": args})
                function_responses.append(
                    protos.Part(function_response=protos.FunctionResponse(name=name, response={"result": result}))
                )
            else:
                has_text = True
                text_content = getattr(part, "text", None) or (response.text if hasattr(response, "text") else "")

        if has_text and not function_responses:
            return {"text": text_content, "tool_calls": tool_calls_made}
        if not function_responses:
            break

        try:
            response = chat.send_message(function_responses)
        except Exception as e:
            log.warning("Research agent after tools: %s", e)
            if tool_calls_made:
                return {"text": f"Research partially completed but model returned an error. Tools used: {[t['name'] for t in tool_calls_made]}.", "tool_calls": tool_calls_made}
            return {"text": "Research failed. Please try again.", "tool_calls": []}

    final = getattr(response, "text", "") or ""
    if not final and tool_calls_made:
        final = f"Reached max rounds ({max_rounds}). Some research was gathered. Tools used: {[t['name'] for t in tool_calls_made]}."
    out = {"text": final or "No response", "tool_calls": tool_calls_made}
    if mode == "modify":
        try:
            # Strip markdown code block if present
            text = final.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                text = "\n".join(lines)
            parsed = json.loads(text)
            if isinstance(parsed, dict) and "slides" in parsed and isinstance(parsed["slides"], list):
                out["replacement_slides"] = parsed["slides"]
        except (json.JSONDecodeError, TypeError):
            pass
    return out
