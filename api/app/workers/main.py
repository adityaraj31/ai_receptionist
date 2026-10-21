from __future__ import annotations

from arq.connections import RedisSettings

from ..config import settings
from ..db import engine
from ..queue import close_queue, init_queue
from ..services.post_call import evaluate_call, process_call
from ..services.reminders import send_appointment_reminder


async def on_startup(_ctx: dict) -> None:
    await init_queue()


async def on_shutdown(_ctx: dict) -> None:
    await close_queue()
    await engine.dispose()


class WorkerSettings:
    functions = [process_call, evaluate_call, send_appointment_reminder]
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    queue_name = settings.arq_queue_name
    job_timeout = 120
    max_tries = 3
    on_startup = on_startup
    on_shutdown = on_shutdown
