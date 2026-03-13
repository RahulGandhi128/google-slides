# RAG (Document) Flow

## Ingestion

- **Every** uploaded PDF/DOCX is chunked and indexed with FAISS (no page or size limit).
- Flow: `POST /api/documents/ingest` → extract text → chunk → build FAISS index → save to `document_indexes` + `documents` (metadata, `has_faiss=1`).
- Frontend: upload via chat bar paperclip, or type `@` and pick a saved file.

## Plan mode (RAG)

1. User attaches a document (upload or `@filename`) and asks for a plan (e.g. “Create a plan from this doc”).
2. Frontend sends `topic` + `documentId` (upload_id) to `POST /api/plan`.
3. Backend calls `search_document(upload_id, "main content key points summary", k=15)` and passes the concatenated chunks as `document_context` into the planner LLM.
4. Planner sees that context and returns a JSON plan (or natural-language answer) based on the document.

## Chat mode (RAG)

1. User attaches a document and asks questions in chat.
2. Frontend sends `messages` + `documentId` to `POST /api/chat`.
3. Backend passes `current_document: { upload_id, filename }` into the agent. The system instruction tells the model to use the document tools for that upload_id.
4. The agent can call:
   - `list_documents` – list ingested docs;
   - `document_search(upload_id, query, k)` – semantic search over the attached doc;
   - `get_document_text(upload_id)` – not used for RAG anymore (all docs are FAISS-only).
5. The model uses `document_search` to pull relevant chunks and answers from them.

## Tools (agent)

- **list_documents** – list ingested documents (upload_id, filename, page_count, has_faiss).
- **document_search** – `(upload_id, query, k)` → top-k chunk texts for the query (FAISS similarity search).
- **get_document_text** – returns full text only when `full_text` is stored; for current ingestion (all FAISS) it returns “use document_search”.
