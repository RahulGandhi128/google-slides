# Document ingestion and RAG — import from functions.datapipeline or functions.document_search directly
# (No top-level imports here to avoid circular/partial load when database.documents imports datapipeline.)
__all__ = [
    "extract_text",
    "extract_text_with_metadata",
    "chunk_document",
    "BIG_DOC_PAGE_THRESHOLD",
    "BIG_DOC_CHAR_THRESHOLD",
    "build_index_from_chunks",
    "save_index_to_db",
    "load_index_from_db",
    "search_document",
]
