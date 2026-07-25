"""Sprint 0 check: confirm a local persistent Chroma client initializes and
writes to chroma_db/. Run with: python -m scripts.verify_chroma
"""

import chromadb

from src import config


def main():
    client = chromadb.PersistentClient(path=config.CHROMA_DB_DIR)
    collection = client.get_or_create_collection("sprint0_smoke_test")
    collection.upsert(ids=["1"], documents=["hello world"])
    result = collection.get(ids=["1"])
    assert result["documents"] == ["hello world"], "round-trip failed"
    client.delete_collection("sprint0_smoke_test")
    print(f"OK: Chroma persistent client works, data dir = {config.CHROMA_DB_DIR}")


if __name__ == "__main__":
    main()
