from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import FaqChunk
from . import embeddings

CHUNK_MAX_CHARS = 600
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?।])\s+|\n+")


def chunk_answer(answer: str, max_chars: int = CHUNK_MAX_CHARS) -> list[str]:
    """Split an answer into sentence-aligned chunks for embedding."""
    parts = [part.strip() for part in _SENTENCE_SPLIT.split(answer) if part.strip()]
    if not parts:
        return []

    chunks: list[str] = []
    current = ""
    for part in parts:
        if len(part) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_split_long(part, max_chars))
            continue
        if not current:
            current = part
        elif len(current) + 1 + len(part) <= max_chars:
            current = f"{current} {part}"
        else:
            chunks.append(current)
            current = part
    if current:
        chunks.append(current)
    return chunks


def _split_long(text: str, max_chars: int) -> list[str]:
    chunks: list[str] = []
    current = ""
    for word in text.split():
        if not current:
            current = word
        elif len(current) + 1 + len(word) <= max_chars:
            current = f"{current} {word}"
        else:
            chunks.append(current)
            current = word
    if current:
        chunks.append(current)
    return chunks


def shorten_answer(
    answer: str,
    *,
    max_sentences: int = 2,
    max_chars: int | None = None,
) -> str:
    """Return at most two short sentences, suitable for a phone reply."""
    limit = max_chars if max_chars is not None else settings.faq_answer_max_chars
    sentences = [part.strip() for part in _SENTENCE_SPLIT.split(answer) if part.strip()]
    short = " ".join(sentences[:max_sentences]) if sentences else answer.strip()
    if len(short) <= limit:
        return short

    trimmed = short[:limit].rsplit(" ", 1)[0].rstrip(",;:-")
    if not trimmed:
        trimmed = short[:limit]
    if trimmed[-1] not in ".!?।":
        trimmed += "."
    return trimmed


async def delete_faq_chunks(
    session: AsyncSession,
    clinic_id: UUID,
    question: str,
) -> None:
    await session.execute(
        delete(FaqChunk).where(
            FaqChunk.clinic_id == clinic_id,
            FaqChunk.question == question,
        )
    )


async def write_faq(
    session: AsyncSession,
    clinic_id: UUID,
    question: str,
    answer: str,
    *,
    is_active: bool = True,
    faq_id: UUID | None = None,
) -> FaqChunk:
    """Replace all chunks for one clinic FAQ and return its first chunk.

    The question is stored as its own chunk and the answer is split into sentence
    chunks. Searching over both means a terse query like "address" can match the
    question while a detail like "UPI" can match the answer.
    """
    chunks = chunk_answer(answer)
    if not chunks:
        chunks = [answer.strip()]

    contents = [question, *chunks]
    vectors = await embeddings.aembed_documents(contents)

    await delete_faq_chunks(session, clinic_id, question)
    rows = [
        FaqChunk(
            clinic_id=clinic_id,
            question=question,
            answer=answer,
            content=content,
            chunk_index=index,
            embedding=vector,
            is_active=is_active,
        )
        for index, (content, vector) in enumerate(zip(contents, vectors, strict=True))
    ]
    if faq_id is not None:
        rows[0].id = faq_id
    session.add_all(rows)
    await session.commit()
    await session.refresh(rows[0])
    return rows[0]


async def list_faqs(
    session: AsyncSession,
    clinic_id: UUID,
    *,
    include_inactive: bool = False,
) -> list[FaqChunk]:
    statement = select(FaqChunk).where(FaqChunk.clinic_id == clinic_id)
    if not include_inactive:
        statement = statement.where(FaqChunk.is_active.is_(True))
    rows = list(
        (await session.scalars(statement.order_by(FaqChunk.question, FaqChunk.chunk_index))).all()
    )

    seen: set[str] = set()
    unique: list[FaqChunk] = []
    for row in rows:
        if row.question in seen:
            continue
        seen.add(row.question)
        unique.append(row)
    return unique


async def find_faq_answer(
    session: AsyncSession,
    clinic_id: UUID,
    query: str,
) -> tuple[FaqChunk, float] | None:
    """Return the closest active FAQ chunk and its cosine similarity."""
    vector = (await embeddings.aembed_documents([query]))[0]
    distance = FaqChunk.embedding.cosine_distance(vector)
    row = (
        await session.execute(
            select(FaqChunk, distance.label("distance"))
            .where(
                FaqChunk.clinic_id == clinic_id,
                FaqChunk.is_active.is_(True),
            )
            .order_by(distance)
            .limit(1)
        )
    ).first()

    if row is None:
        return None

    chunk, raw_distance = row
    value = float(raw_distance)
    if value > settings.faq_max_distance:
        return None

    score = max(0.0, min(1.0, 1.0 - value))
    if score < settings.faq_high_confidence_similarity and not _keyword_overlap(
        query, f"{chunk.question} {chunk.answer}"
    ):
        return None
    return chunk, score


_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "any",
        "are",
        "at",
        "be",
        "can",
        "could",
        "do",
        "does",
        "for",
        "from",
        "have",
        "how",
        "i",
        "in",
        "is",
        "it",
        "me",
        "my",
        "of",
        "on",
        "or",
        "please",
        "should",
        "the",
        "there",
        "to",
        "we",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "with",
        "you",
        "your",
    }
)
_WORD_RE = re.compile(r"[a-z0-9\u0900-\u097f]+")


def _tokens(text: str) -> set[str]:
    words = _WORD_RE.findall(text.lower())
    return {_stem(word) for word in words if len(word) >= 3 and word not in _STOPWORDS}


def _stem(word: str) -> str:
    if len(word) > 4 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _keyword_overlap(query: str, content: str) -> bool:
    return bool(_tokens(query) & _tokens(content))
