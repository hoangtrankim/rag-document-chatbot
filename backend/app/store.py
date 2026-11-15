"""Vector store: embeds chunks and finds the most relevant ones for a question."""

from functools import lru_cache

from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings

from .config import get_settings


class FastEmbedEmbeddings(Embeddings):
    """LangChain wrapper around FastEmbed, which runs locally (ONNX): no API key or cost."""

    def __init__(self, model_name: str, cache_dir: str | None = None):
        from fastembed import TextEmbedding

        self._model = TextEmbedding(model_name, cache_dir=cache_dir)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [v.tolist() for v in self._model.passage_embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        return next(iter(self._model.query_embed(text))).tolist()


@lru_cache
def get_embeddings() -> Embeddings:
    s = get_settings()
    return FastEmbedEmbeddings(s.embedding_model, s.embedding_cache_dir)


@lru_cache
def get_store() -> Chroma:
    s = get_settings()
    return Chroma(
        collection_name=s.collection_name,
        embedding_function=get_embeddings(),
        persist_directory=s.chroma_dir,
        collection_metadata={"hnsw:space": "cosine"},
    )
