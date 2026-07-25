"""Wraps Chroma's default local embedding function (all-MiniLM-L6-v2 via ONNX,
runs on CPU, no API key). Centralized here so stores/retrievers depend on this
module instead of chromadb.utils directly — swap the implementation later
without touching callers."""

from chromadb.utils.embedding_functions import DefaultEmbeddingFunction


def get_embedding_function():
    return DefaultEmbeddingFunction()
