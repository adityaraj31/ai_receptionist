from uuid import UUID

from .common import ORMModel


class ClinicRead(ORMModel):
    id: UUID
    name: str
    timezone: str
    address: str | None
    phone: str | None
    email: str | None
    is_active: bool
