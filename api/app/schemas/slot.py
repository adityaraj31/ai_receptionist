from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class FreeSlotRead(BaseModel):
    doctor_id: UUID
    slot_date: date
    starts_at: datetime
    ends_at: datetime
    slot_minutes: int
    timezone: str
