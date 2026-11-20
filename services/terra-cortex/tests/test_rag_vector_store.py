"""Offline regression tests for the embedded Chroma store behind RAGAdvisor.

chromadb 0.4.22 references ``np.float_``, which NumPy 2.0 removed. With an
unconstrained numpy, ``Chroma(...)`` raised inside ``RAGAdvisor.__init__``,
was logged, and RAG silently stayed disabled. These tests build the real
persistent store through the production ingestion and advisor code paths,
swapping only the HuggingFace model for a deterministic local embedding so
no network or model download is required.
"""
import hashlib
import logging
import math
import re

import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from src import ingest_knowledge, rag_advisor

EMBEDDING_DIMENSIONS = 256
TOKEN_PATTERN = re.compile(r"[a-z]+")


class HashingEmbeddings(Embeddings):
    """Deterministic bag-of-words embedding that runs fully offline."""

    def __init__(self, **kwargs):
        self.init_kwargs = kwargs

    def _embed(self, text):
        vector = [0.0] * EMBEDDING_DIMENSIONS
        for token in TOKEN_PATTERN.findall(text.lower()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            vector[int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSIONS] += 1.0
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0.0:
            return [1.0 / math.sqrt(EMBEDDING_DIMENSIONS)] * EMBEDDING_DIMENSIONS
        return [value / norm for value in vector]

    def embed_documents(self, texts):
        return [self._embed(text) for text in texts]

    def embed_query(self, text):
        return self._embed(text)


KNOWLEDGE_CHUNKS = [
    Document(
        page_content=(
            "Tomato heat stress: when greenhouse temperature exceeds 32C, "
            "open roof vents, run shade screens and increase misting."
        ),
        metadata={"source": "tomato-heat.pdf"},
    ),
    Document(
        page_content=(
            "Lettuce tipburn is linked to low calcium uptake under weak "
            "airflow; keep horizontal fans running during humid nights."
        ),
        metadata={"source": "lettuce-tipburn.pdf"},
    ),
    Document(
        page_content=(
            "Strawberry irrigation: keep substrate moisture between 60 and "
            "70 percent and flush drippers weekly to prevent salt buildup."
        ),
        metadata={"source": "strawberry-irrigation.pdf"},
    ),
]


@pytest.fixture
def offline_embeddings(monkeypatch):
    created = []

    def factory(**kwargs):
        embeddings = HashingEmbeddings(**kwargs)
        created.append(embeddings)
        return embeddings

    monkeypatch.setattr(ingest_knowledge, "HuggingFaceEmbeddings", factory)
    monkeypatch.setattr(rag_advisor, "HuggingFaceEmbeddings", factory)
    yield created
    # Imported lazily so a broken chromadb install fails the tests, not collection.
    try:
        from chromadb.api.client import SharedSystemClient
    except (AttributeError, ImportError):
        return  # chromadb never loaded, so there is no cached client to release.
    SharedSystemClient.clear_system_cache()


def test_rag_advisor_retrieves_context_from_ingested_chroma_store(
    tmp_path, offline_embeddings, caplog
):
    chroma_db_path = tmp_path / "chroma_db"
    ingester = ingest_knowledge.KnowledgeBaseIngester(
        knowledge_base_path=str(tmp_path / "knowledge_base"),
        chroma_db_path=str(chroma_db_path),
    )
    assert ingester.create_vector_db(KNOWLEDGE_CHUNKS) is not None

    with caplog.at_level(logging.ERROR, logger=rag_advisor.__name__):
        advisor = rag_advisor.RAGAdvisor(chroma_db_path=str(chroma_db_path), top_k=2)

    assert advisor.enabled, caplog.text
    assert advisor.get_stats()["document_count"] == len(KNOWLEDGE_CHUNKS)
    # Ingestion and retrieval must embed with the same configured model.
    assert [e.init_kwargs["model_name"] for e in offline_embeddings] == [
        "all-MiniLM-L6-v2",
        "all-MiniLM-L6-v2",
    ]

    contexts = advisor.retrieve_context("tomato greenhouse temperature heat stress")

    assert len(contexts) == 2
    assert contexts[0] == KNOWLEDGE_CHUNKS[0].page_content


def test_rag_advisor_stays_disabled_for_empty_chroma_store(
    tmp_path, offline_embeddings, caplog
):
    chroma_db_path = tmp_path / "chroma_db"
    chroma_db_path.mkdir()

    with caplog.at_level(logging.ERROR, logger=rag_advisor.__name__):
        advisor = rag_advisor.RAGAdvisor(chroma_db_path=str(chroma_db_path))

    # The store itself must open cleanly; only the empty collection disables RAG.
    assert advisor.vector_db is not None, caplog.text
    assert "Failed to initialize RAG Advisor" not in caplog.text
    assert advisor.enabled is False
    assert advisor.retrieve_context("tomato heat") == []
