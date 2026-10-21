from datetime import time
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class AgentClinicRead(BaseModel):
    id: UUID
    name: str
    timezone: str
    address: str | None
    phone: str | None
    email: str | None
    front_desk_number: str | None


class AgentDoctorRead(BaseModel):
    id: UUID
    name: str
    specialization: str
    languages: list[str]
    fee: Decimal


class AgentAvailabilityRead(BaseModel):
    doctor_id: UUID
    weekday: int
    start_time: time
    end_time: time
    slot_minutes: int


class AgentClinicConfigRead(BaseModel):
    clinic: AgentClinicRead
    doctors: list[AgentDoctorRead]
    availability: list[AgentAvailabilityRead]
