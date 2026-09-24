import re
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "policies.md"

HEADING_PATTERN = re.compile(r"^## (.+)$", re.MULTILINE)

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"

_embedding_model: SentenceTransformer | None = None
_chroma_client: chromadb.ClientAPI | None = None
_collection_cache: dict[str, chromadb.Collection] = {}


def load_policy_text() -> str:
    with open(DATA_PATH) as f:
        return f.read()


def chunk_policies(
    markdown_text: str,
    store_id: str,
    chunk_size: int = 500,
    overlap: int = 50,
) -> list[dict]:
    if HEADING_PATTERN.search(markdown_text):
        chunks = _chunk_by_heading(markdown_text)
    else:
        chunks = _chunk_fixed_size(markdown_text, chunk_size, overlap)

    for chunk in chunks:
        chunk["store_id"] = store_id
    return chunks


def _chunk_by_heading(text: str) -> list[dict]:
    parts = HEADING_PATTERN.split(text)
    chunks = []
    for i in range(1, len(parts), 2):
        title = parts[i].strip()
        content = parts[i + 1].strip() if i + 1 < len(parts) else ""
        chunks.append({"title": title, "content": content})
    return chunks


def _chunk_fixed_size(text: str, chunk_size: int, overlap: int) -> list[dict]:
    assert overlap < chunk_size, "overlap must be smaller than chunk_size"

    text = text.strip()
    chunks = []
    start = 0
    section_number = 1

    while start < len(text):
        piece = text[start : start + chunk_size].strip()
        if piece:
            chunks.append({"title": f"Section {section_number}", "content": piece})
            section_number += 1
        start += chunk_size - overlap

    return chunks


def get_embedding_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _embedding_model


def embed_texts(texts: list[str]) -> list[list[float]]:
    model = get_embedding_model()
    embeddings = model.encode(texts, normalize_embeddings=True)
    return embeddings.tolist()


def get_collection(store_id: str) -> chromadb.Collection:
    global _chroma_client

    if store_id in _collection_cache:
        return _collection_cache[store_id]

    if _chroma_client is None:
        _chroma_client = chromadb.Client()

    collection = _chroma_client.get_or_create_collection(
        name=f"policies_{store_id}",
        metadata={"hnsw:space": "cosine"},
    )

    text = load_policy_text()
    chunks = chunk_policies(text, store_id=store_id)
    embeddings = embed_texts([chunk["content"] for chunk in chunks])

    collection.add(
        ids=[f"{store_id}_{i}" for i in range(len(chunks))],
        embeddings=embeddings,
        documents=[chunk["content"] for chunk in chunks],
        metadatas=[{"title": chunk["title"], "store_id": chunk["store_id"]} for chunk in chunks],
    )

    _collection_cache[store_id] = collection
    return collection


def retrieve_policy(
    query: str,
    store_id: str,
    top_k: int = 3,
    min_similarity: float = 0.3,
) -> list[dict]:
    collection = get_collection(store_id)
    query_embedding = embed_texts([query])[0]

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
    )

    matches = []
    ids = results["ids"][0]
    for i in range(len(ids)):
        distance = results["distances"][0][i]
        similarity = 1 - distance
        if similarity < min_similarity:
            continue
        matches.append(
            {
                "title": results["metadatas"][0][i]["title"],
                "content": results["documents"][0][i],
                "similarity": round(similarity, 3),
            }
        )

    return matches


if __name__ == "__main__":
    text = load_policy_text()
    for chunk in chunk_policies(text, store_id="store_mock_001"):
        print(f"[{chunk['title']}] ({len(chunk['content'])} chars)")
        print(chunk["content"][:80], "...\n")
