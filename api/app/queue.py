from __future__ import annotations

import logging
from datetime import datetime

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from .config import settings

logger = logging.getLogger(__name__)

_pool: ArqRedis | None = None


async def init_queue() -> None:
    global _pool
    if not settings.reminder_jobs_enabled or _pool is not None:
        return
    try:
        _pool = await create_pool(
            RedisSettings.from_dsn(settings.redis_url),
            default_queue_name=settings.arq_queue_name,
        )
    except Exception:
        logger.warning("Redis unavailable; reminder jobs will not be enqueued", exc_info=True)


async def close_queue() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_queue() -> ArqRedis | None:
    return _pool


async def enqueue_reminder(
    appointment_id: str,
    kind: str,
    run_at: datetime,
    expected_start: datetime,
) -> bool:
    pool = get_queue()
    if pool is None:
        return False
    job_id = f"reminder:{appointment_id}:{kind}:{int(expected_start.timestamp())}"
    try:
        await pool.enqueue_job(
            "send_appointment_reminder",
            appointment_id,
            kind,
            expected_start.isoformat(),
            _job_id=job_id,
            _defer_until=run_at,
        )
    except Exception:
        logger.warning("Could not enqueue reminder job %s", job_id, exc_info=True)
        return False
    return True
