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

RESEARCH_SYSTEM = """You are a deep research assistant. You can answer general questions from your knowledge, or search the user's ingested documents (PDF/DOCX) when they attach files or explicitly ask to search.

Tools (use only when appropriate):
- list_documents: lists the user's ingested documents (upload_id, filename). Use ONLY when the user explicitly asks to list their files, see their documents, or pick a document to search. Do NOT call for general queries.
- document_search(upload_id, query, k): semantic search over one document. Use ONLY when the context below provides attached documents with upload_ids. Do NOT call if no documents are attached.
 - web_search(query, max_results): search the web for up-to-date external information when the user asks for web/internet search or the task clearly requires current data beyond these documents.

Critical rules:
1. When NO documents are attached (see context below): For general questions (e.g. "make an outline for a pitch", "best practices for X", "structure for 5 slides"), answer directly from your knowledge. Do NOT call list_documents or document_search. Do not mention or search the user's files.
2. When NO documents are attached and the user explicitly asks to "list my files", "what documents do I have", or "search my documents for X": then call list_documents. Only call document_search if the user then asks to search a specific document (you will have upload_id from list_documents).
3. When documents ARE attached: use only the upload_ids from the context below for document_search. Search across them as needed and synthesize. Do not use list_documents to load more; use only the attached list.
4. For web/internet information, you MAY use web_search when the user asks for it explicitly or when up-to-date external data is clearly required. You still cannot access Slides/Drive tools—only the user's ingested documents and the web_search tool."""


def _execute_research_tool(name: str, args: dict) -> str:
    if name == "list_documents":
        from database.documents import list_documents as _list_documents
        r = _list_documents(limit=args.get("limit", 100))
        return json.dumps(r, indent=2)
    if name == "document_search":
        from functions.document_search import search_document
        chunks = search_document(
            upload_id=args.get("upload_id", ""),
            query=args.get("query", ""),
            k=args.get("k", 10),
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


def run_research_agent(query: str, documents: list[dict] | None = None) -> dict:
    """
    Run the research agent. Returns {text, tool_calls}.
    documents: list of {"upload_id": str, "filename": str}. May be empty (agent can list_documents and ask user to attach).
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
    system_instruction = RESEARCH_SYSTEM + doc_ctx

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
    return {"text": final or "No response", "tool_calls": tool_calls_made}
