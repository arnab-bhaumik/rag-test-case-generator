"""CRUD for the design_docs Chroma collection — chunks from ingested design
docs and Jira tickets, used by retrieval for requirement context (plan.md §5
step 4)."""

from __future__ import annotations

from src.embeddings.embedder import get_embedding_function
from src.ingestion.chunker import Chunk
from src.vectorstore.chroma_client import get_client

COLLECTION_NAME = "design_docs"


def _collection():
    return get_client().get_or_create_collection(COLLECTION_NAME, embedding_function=get_embedding_function())


def upsert(chunks: list[Chunk]) -> None:
    if not chunks:
        return
    _collection().upsert(
        ids=[c.id for c in chunks],
        documents=[c.text for c in chunks],
        metadatas=[
            {
                "section": c.section or "",
                "source_type": c.source_type,
                "source_id": c.source_id,
                "order": c.order,
                "module": c.module or "",
            }
            for c in chunks
        ],
    )


def query_similar(
    text: str,
    n_results: int = 5,
    source_id: str | None = None,
    source_type: str | None = None,
    module: str | None = None,
) -> list[dict]:
    conditions = []
    if source_id:
        conditions.append({"source_id": source_id})
    if source_type:
        conditions.append({"source_type": source_type})
    if module:
        conditions.append({"module": module})
    where = conditions[0] if len(conditions) == 1 else ({"$and": conditions} if conditions else None)

    result = _collection().query(query_texts=[text], n_results=n_results, where=where)
    return [
        {
            "id": result["ids"][0][i],
            "document": result["documents"][0][i],
            "metadata": result["metadatas"][0][i],
            "distance": result["distances"][0][i],
        }
        for i in range(len(result["ids"][0]))
    ]


def count() -> int:
    return _collection().count()
