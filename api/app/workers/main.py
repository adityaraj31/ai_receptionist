from __future__ import annotations

from arq.connections import RedisSettings

from ..config import settings
from ..db import engine
from ..services.reminders import send_appointment_reminder


async def on_shutdown(_ctx: dict) -> None:
    await engine.dispose()


class WorkerSettings:
    functions = [send_appointment_reminder]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    queue_name = settings.arq_queue_name
    job_timeout = 60
    max_tries = 3
    on_shutdown = on_shutdown
