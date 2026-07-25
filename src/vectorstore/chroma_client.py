"""Shared persistent Chroma client — one instance per process."""

import chromadb

from src import config

_client: chromadb.ClientAPI | None = None


def get_client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=config.CHROMA_DB_DIR)
    return _client
