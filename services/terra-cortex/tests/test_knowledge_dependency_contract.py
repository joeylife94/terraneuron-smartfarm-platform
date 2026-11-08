"""Offline contract tests for the PDF-ingestion and local-embedding dependencies.

These tests pin the behavior Terra-Cortex relies on from pypdf (through
langchain's PyPDFLoader) and sentence-transformers (through langchain's
HuggingFaceEmbeddings) without network access: PDFs are generated in-test and
the embedding model is a deterministic tiny BERT saved in the same module
layout as the public all-MiniLM-L6-v2 repository (Transformer -> mean
Pooling -> Normalize).
"""

import json
import math
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).resolve().parents[1] / "src"


def _minimal_pdf(pages):
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        None,
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    kids = []
    for text in pages:
        stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET"
        objects.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
        content_ref = len(objects)
        objects.append(
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Contents {content_ref} 0 R /Resources << /Font << /F1 3 0 R >> >> >>"
        )
        kids.append(f"{len(objects)} 0 R")
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>"

    body = b"%PDF-1.4\n"
    offsets = []
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(body))
        body += f"{number} 0 obj\n{obj}\nendobj\n".encode("latin-1")
    xref_offset = len(body)
    body += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("latin-1")
    body += "".join(f"{offset:010d} 00000 n \n" for offset in offsets).encode("latin-1")
    body += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    ).encode("latin-1")
    return body


PAGES = [
    "High humidity increases fungal disease risk for tomato.",
    "Reduce irrigation when soil moisture is high.",
]


def test_pdf_loader_extracts_text_and_page_metadata(tmp_path):
    from langchain_community.document_loaders import PyPDFLoader

    pdf = tmp_path / "guide.pdf"
    pdf.write_bytes(_minimal_pdf(PAGES))

    documents = PyPDFLoader(str(pdf)).load()

    assert [doc.page_content.strip() for doc in documents] == PAGES
    assert [doc.metadata["page"] for doc in documents] == [0, 1]
    assert all(doc.metadata["source"] == str(pdf) for doc in documents)


def test_ingester_skips_malformed_pdfs_and_keeps_valid_pages(tmp_path, monkeypatch):
    from src import ingest_knowledge

    class NoModelEmbeddings:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    monkeypatch.setattr(ingest_knowledge, "HuggingFaceEmbeddings", NoModelEmbeddings)
    knowledge_base = tmp_path / "knowledge_base"
    knowledge_base.mkdir()
    valid = _minimal_pdf(PAGES)
    (knowledge_base / "guide.pdf").write_bytes(valid)
    (knowledge_base / "truncated.pdf").write_bytes(valid[: len(valid) // 3])
    (knowledge_base / "not-a-pdf.pdf").write_bytes(b"not a pdf\x00\xff" * 64)

    ingester = ingest_knowledge.KnowledgeBaseIngester(
        knowledge_base_path=str(knowledge_base),
        chroma_db_path=str(tmp_path / "chroma_db"),
        embedding_model="all-MiniLM-L6-v2",
    )
    documents = ingester.load_pdfs()
    chunks = ingester.chunk_documents(documents)

    assert [doc.page_content.strip() for doc in documents] == PAGES
    assert {Path(doc.metadata["source"]).name for doc in documents} == {"guide.pdf"}
    assert [chunk.page_content.strip() for chunk in chunks] == PAGES
    assert ingester.embeddings.kwargs == {
        "model_name": "all-MiniLM-L6-v2",
        "model_kwargs": {"device": "cpu"},
        "encode_kwargs": {"normalize_embeddings": True},
    }


@pytest.fixture(scope="module")
def tiny_minilm_layout_model(tmp_path_factory):
    import torch
    from transformers import BertConfig, BertModel, BertTokenizerFast

    model_dir = tmp_path_factory.mktemp("tiny-minilm-layout")
    words = (
        "high humidity increases fungal disease risk for tomato reduce irrigation "
        "when soil moisture is greenhouse heater night temperature low"
    ).split()
    vocab = ["[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]"] + words + list("abcdefghijklmnopqrstuvwxyz.")
    (model_dir / "vocab.txt").write_text("\n".join(vocab) + "\n", encoding="utf-8")
    BertTokenizerFast(vocab_file=str(model_dir / "vocab.txt"), do_lower_case=True).save_pretrained(model_dir)

    torch.manual_seed(1234)
    config = BertConfig(
        vocab_size=len(vocab),
        hidden_size=32,
        num_hidden_layers=2,
        num_attention_heads=2,
        intermediate_size=64,
        max_position_embeddings=128,
    )
    BertModel(config).save_pretrained(model_dir, safe_serialization=True)

    (model_dir / "modules.json").write_text(json.dumps([
        {"idx": 0, "name": "0", "path": "", "type": "sentence_transformers.models.Transformer"},
        {"idx": 1, "name": "1", "path": "1_Pooling", "type": "sentence_transformers.models.Pooling"},
        {"idx": 2, "name": "2", "path": "2_Normalize", "type": "sentence_transformers.models.Normalize"},
    ]), encoding="utf-8")
    (model_dir / "sentence_bert_config.json").write_text(
        json.dumps({"max_seq_length": 64, "do_lower_case": False}), encoding="utf-8"
    )
    (model_dir / "1_Pooling").mkdir()
    (model_dir / "1_Pooling" / "config.json").write_text(json.dumps({
        "word_embedding_dimension": 32,
        "pooling_mode_cls_token": False,
        "pooling_mode_mean_tokens": True,
        "pooling_mode_max_tokens": False,
        "pooling_mode_mean_sqrt_len_tokens": False,
    }), encoding="utf-8")
    (model_dir / "2_Normalize").mkdir()
    return model_dir


def test_repository_embedding_configuration_returns_normalized_deterministic_vectors(
    tiny_minilm_layout_model,
):
    from langchain_community.embeddings import HuggingFaceEmbeddings

    # Same constructor arguments as rag_advisor, ingest_knowledge and knowledge_collector.
    embeddings = HuggingFaceEmbeddings(
        model_name=str(tiny_minilm_layout_model),
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )

    first = embeddings.embed_documents(PAGES)
    second = embeddings.embed_documents(PAGES)
    query = embeddings.embed_query(PAGES[0])

    assert len(first) == len(PAGES)
    assert all(len(vector) == 32 for vector in first)
    assert all(math.isclose(math.sqrt(sum(x * x for x in v)), 1.0, abs_tol=1e-5) for v in first)
    assert first == second
    assert query == pytest.approx(first[0], abs=1e-6)
    assert first[0] != pytest.approx(first[1], abs=1e-3)


HUB_REPO_CACHE_DIR = "models--sentence-transformers--all-MiniLM-L6-v2"


def _hub_cache_with(model_dir, cache_root, plant_custom_module=None):
    """Lay out model_dir as a cached Hub snapshot of sentence-transformers/all-MiniLM-L6-v2."""
    import shutil

    revision = "0" * 40
    snapshot = cache_root / HUB_REPO_CACHE_DIR / "snapshots" / revision
    shutil.copytree(model_dir, snapshot)
    (cache_root / HUB_REPO_CACHE_DIR / "refs").mkdir(parents=True)
    (cache_root / HUB_REPO_CACHE_DIR / "refs" / "main").write_text(revision, encoding="utf-8")
    if plant_custom_module is not None:
        (snapshot / "modeling_planted.py").write_text(
            "import pathlib\n"
            f"pathlib.Path({str(plant_custom_module)!r}).write_text('executed')\n"
            "from sentence_transformers.models import Normalize\n"
            "class PlantedNormalize(Normalize):\n"
            "    pass\n",
            encoding="utf-8",
        )
        modules = json.loads((snapshot / "modules.json").read_text(encoding="utf-8"))
        modules[-1]["type"] = "modeling_planted.PlantedNormalize"
        (snapshot / "modules.json").write_text(json.dumps(modules), encoding="utf-8")
    return cache_root


def test_bare_embedding_model_name_resolves_to_sentence_transformers_hub_repo(
    tiny_minilm_layout_model, tmp_path, monkeypatch
):
    from sentence_transformers import SentenceTransformer

    # rag_advisor/ingest_knowledge/knowledge_collector load the bare name
    # "all-MiniLM-L6-v2"; it must resolve to the cached Hub repository
    # sentence-transformers/all-MiniLM-L6-v2 (offline: local_files_only).
    cache = _hub_cache_with(tiny_minilm_layout_model, tmp_path / "hf-cache")
    monkeypatch.chdir(tmp_path)

    model = SentenceTransformer(
        "all-MiniLM-L6-v2", cache_folder=str(cache), local_files_only=True, device="cpu"
    )

    assert [type(module).__name__ for module in model] == ["Transformer", "Pooling", "Normalize"]
    assert len(model.encode(PAGES[0])) == 32


def test_hub_model_custom_module_is_not_executed_without_trust_remote_code(
    tiny_minilm_layout_model, tmp_path, monkeypatch
):
    from sentence_transformers import SentenceTransformer

    marker = tmp_path / "planted-code-executed"
    cache = _hub_cache_with(tiny_minilm_layout_model, tmp_path / "hf-cache", plant_custom_module=marker)
    monkeypatch.chdir(tmp_path)

    try:
        model = SentenceTransformer(
            "all-MiniLM-L6-v2", cache_folder=str(cache), local_files_only=True, device="cpu"
        )
    except (ImportError, ValueError, OSError):
        model = None

    assert not marker.exists()
    if model is not None:
        assert "PlantedNormalize" not in [type(module).__name__ for module in model]


def test_repository_code_never_opts_into_remote_code():
    for source in SRC_DIR.glob("*.py"):
        assert "trust_remote_code" not in source.read_text(encoding="utf-8"), source.name
