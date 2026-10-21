from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import func, select

from ...db import SessionDep
from ...models import FaqChunk
from ...schemas import FaqCreate, FaqRead, FaqUpdate
from ...services.faq import delete_faq_chunks, list_faqs, write_faq
from ..deps import CurrentStaff

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/faqs", tags=["FAQs"])


async def _first_chunk(
    session,
    clinic_id: UUID,
    faq_id: UUID,
) -> FaqChunk:
    chunk = await session.scalar(
        select(FaqChunk)
        .where(
            FaqChunk.id == faq_id,
            FaqChunk.clinic_id == clinic_id,
        )
        .limit(1)
    )
    if chunk is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="FAQ not found",
        )
    return chunk


async def _question_exists(
    session,
    clinic_id: UUID,
    question: str,
    *,
    exclude_question: str | None = None,
) -> bool:
    statement = select(FaqChunk.id).where(
        FaqChunk.clinic_id == clinic_id,
        FaqChunk.question == question,
    )
    if exclude_question is not None:
        statement = statement.where(FaqChunk.question != exclude_question)
    return await session.scalar(statement.limit(1)) is not None


@router.get(
    "",
    response_model=list[FaqRead],
    summary="List clinic FAQs",
)
async def list_clinic_faqs(
    staff: CurrentStaff,
    session: SessionDep,
    include_inactive: bool = False,
) -> list[FaqChunk]:
    return await list_faqs(
        session,
        staff.clinic_id,
        include_inactive=include_inactive,
    )


@router.post(
    "",
    response_model=FaqRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add an FAQ",
    responses={
        409: {"description": "An FAQ with this question already exists"},
        503: {"description": "Embedding service unavailable"},
    },
)
async def create_faq(
    payload: FaqCreate,
    staff: CurrentStaff,
    session: SessionDep,
) -> FaqChunk:
    if await _question_exists(session, staff.clinic_id, payload.question):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An FAQ with this question already exists.",
        )
    try:
        return await write_faq(
            session,
            staff.clinic_id,
            payload.question,
            payload.answer,
            is_active=payload.is_active,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to index FAQ for clinic %s", staff.clinic_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not index the FAQ right now. Please try again.",
        ) from exc


@router.patch(
    "/{faq_id}",
    response_model=FaqRead,
    summary="Edit an FAQ",
    responses={
        404: {"description": "FAQ not found"},
        409: {"description": "An FAQ with this question already exists"},
        503: {"description": "Embedding service unavailable"},
    },
)
async def update_faq(
    faq_id: UUID,
    payload: FaqUpdate,
    staff: CurrentStaff,
    session: SessionDep,
) -> FaqChunk:
    current = await _first_chunk(session, staff.clinic_id, faq_id)
    question = payload.question or current.question
    answer = payload.answer or current.answer
    is_active = payload.is_active if payload.is_active is not None else current.is_active

    if question != current.question and await _question_exists(
        session,
        staff.clinic_id,
        question,
        exclude_question=current.question,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An FAQ with this question already exists.",
        )

    if question == current.question and answer == current.answer:
        await session.execute(
            FaqChunk.__table__.update()
            .where(
                FaqChunk.clinic_id == staff.clinic_id,
                FaqChunk.question == current.question,
            )
            .values(is_active=is_active, updated_at=func.now())
        )
        await session.commit()
        await session.refresh(current)
        return current

    try:
        faq_id = current.id
        old_question = current.question
        session.expunge(current)
        if old_question != question:
            await delete_faq_chunks(session, staff.clinic_id, old_question)
        return await write_faq(
            session,
            staff.clinic_id,
            question,
            answer,
            is_active=is_active,
            faq_id=faq_id,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to reindex FAQ %s", faq_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not index the FAQ right now. Please try again.",
        ) from exc


@router.delete(
    "/{faq_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate an FAQ",
    responses={404: {"description": "FAQ not found"}},
)
async def deactivate_faq(
    faq_id: UUID,
    staff: CurrentStaff,
    session: SessionDep,
) -> Response:
    current = await _first_chunk(session, staff.clinic_id, faq_id)
    await session.execute(
        FaqChunk.__table__.update()
        .where(
            FaqChunk.clinic_id == staff.clinic_id,
            FaqChunk.question == current.question,
        )
        .values(is_active=False, updated_at=func.now())
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
