"""Local embedding model for FAQ retrieval.

Uses fastembed (ONNX, CPU) instead of a hosted embeddings API so a query never pays a
network round trip. A warm query takes roughly 5 ms, which keeps retrieval within the
300 ms budget even when the database is remote. The model is multilingual so Hindi,
English, and Hinglish queries hit the same vector space.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import TYPE_CHECKING, Any

from ..config import settings

if TYPE_CHECKING:
    from fastembed import TextEmbedding

logger = logging.getLogger(__name__)

_model: TextEmbedding | None = None
_model_lock = threading.Lock()
_infer_lock = threading.Lock()


def _build_model() -> TextEmbedding:
    from fastembed import TextEmbedding

    kwargs: dict[str, Any] = {}
    if settings.fastembed_cache_path:
        kwargs["cache_dir"] = settings.fastembed_cache_path
    return TextEmbedding(settings.embedding_model, **kwargs)


def get_model() -> TextEmbedding:
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                _model = _build_model()
    return _model


def embed_documents(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    model = get_model()
    with _infer_lock:
        vectors = list(model.embed(texts))
    result = [[float(value) for value in vector] for vector in vectors]
    if result and len(result[0]) != settings.embedding_dimensions:
        raise RuntimeError(
            f"Embedding model {settings.embedding_model!r} returned "
            f"{len(result[0])} dimensions, expected {settings.embedding_dimensions}. "
            "Update EMBEDDING_DIMENSIONS and the faq_chunks vector column together."
        )
    return result


async def aembed_documents(texts: list[str]) -> list[list[float]]:
    return await asyncio.to_thread(embed_documents, texts)


def warm() -> None:
    """Load the model and run one embedding so the first caller does not pay for it."""
    embed_documents(["warmup"])


async def awarm() -> None:
    try:
        await asyncio.to_thread(warm)
    except Exception:
        logger.exception("FAQ embedding warmup failed; the first search will be slower")
