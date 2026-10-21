"""Ingest clinic FAQs into pgvector.

Run from the api directory:
    uv run python -m scripts.ingest_faqs --clinic-id <uuid>
    uv run python -m scripts.ingest_faqs --clinic-name "Demo Family Clinic"
    uv run python -m scripts.ingest_faqs --replace --dry-run

The input is JSON: either a list of ``{"question", "answer"}`` objects or an object
with a ``faqs`` list. Long answers are split into sentence-aligned chunks, each chunk is
embedded locally, and existing chunks for the same clinic/question are replaced.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from uuid import UUID

from dotenv import load_dotenv
from sqlalchemy import delete, select

API_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = API_DIR.parent
load_dotenv(ROOT_DIR / ".env")
load_dotenv(API_DIR / ".env")
sys.path.insert(0, str(API_DIR))

from app.db import SessionLocal  # noqa: E402
from app.models import Clinic, FaqChunk  # noqa: E402
from app.services.faq import chunk_answer, write_faq  # noqa: E402

DEFAULT_FILE = ROOT_DIR / "evals" / "faq_corpus.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=DEFAULT_FILE)
    parser.add_argument("--clinic-id", type=UUID)
    parser.add_argument("--clinic-name")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Delete all existing FAQ chunks for the clinic before ingesting.",
    )
    parser.add_argument(
        "--inactive",
        action="store_true",
        help="Import the FAQs as inactive (staff can activate them in the dashboard).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and chunk the file without touching the database.",
    )
    return parser.parse_args()


def load_faqs(path: Path) -> list[dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload.get("faqs") if isinstance(payload, dict) else payload
    if not isinstance(items, list) or not items:
        raise SystemExit(f"{path} must contain a non-empty list of FAQs")

    faqs: list[dict[str, object]] = []
    seen: set[str] = set()
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise SystemExit(f"FAQ #{index} must be an object")
        question = str(item.get("question", "")).strip()
        answer = str(item.get("answer", "")).strip()
        if len(question) < 3 or len(answer) < 3:
            raise SystemExit(f"FAQ #{index} needs a question and an answer")
        if question in seen:
            raise SystemExit(f"Duplicate question in {path}: {question}")
        seen.add(question)
        faqs.append(
            {
                "question": question,
                "answer": answer,
                "is_active": bool(item.get("is_active", True)),
            }
        )
    return faqs


async def resolve_clinic(session, args: argparse.Namespace) -> Clinic:
    if args.clinic_id:
        clinic = await session.get(Clinic, args.clinic_id)
        if clinic is None:
            raise SystemExit(f"No clinic with id {args.clinic_id}")
        return clinic

    if not args.clinic_name:
        raise SystemExit("Pass --clinic-id or --clinic-name")

    clinics = list(
        (await session.scalars(select(Clinic).where(Clinic.name == args.clinic_name))).all()
    )
    if not clinics:
        raise SystemExit(f"No clinic named {args.clinic_name!r}")
    if len(clinics) > 1:
        raise SystemExit("Clinic name is ambiguous; pass --clinic-id instead")
    return clinics[0]


async def ingest(args: argparse.Namespace) -> int:
    faqs = load_faqs(args.file)
    total_chunks = sum(len(chunk_answer(str(faq["answer"]))) + 1 for faq in faqs)

    if args.dry_run:
        print(f"{len(faqs)} FAQs, {total_chunks} chunks from {args.file}")
        for faq in faqs:
            chunks = chunk_answer(str(faq["answer"]))
            print(f"- {faq['question']} ({len(chunks)} chunk(s))")
        return 0

    async with SessionLocal() as session:
        clinic = await resolve_clinic(session, args)
        if args.replace:
            await session.execute(delete(FaqChunk).where(FaqChunk.clinic_id == clinic.id))
            await session.commit()

        imported = 0
        for faq in faqs:
            is_active = bool(faq["is_active"]) and not args.inactive
            await write_faq(
                session,
                clinic.id,
                str(faq["question"]),
                str(faq["answer"]),
                is_active=is_active,
            )
            imported += 1

        stored = await session.scalar(
            select(FaqChunk.question).where(FaqChunk.clinic_id == clinic.id).limit(1)
        )

    print(f"Ingested {imported} FAQs ({total_chunks} chunks) for {clinic.name} ({clinic.id})")
    if stored is None:
        raise SystemExit("Ingestion finished but no FAQ chunks were stored")
    return 0


def main() -> None:
    args = parse_args()
    raise SystemExit(asyncio.run(ingest(args)))


if __name__ == "__main__":
    main()
