from fastapi import APIRouter

from ...db import SessionDep
from ...schemas import ClinicRead
from ...services.common import get_clinic_or_404
from ..deps import CurrentStaff

router = APIRouter(prefix="/clinic", tags=["Clinic"])


@router.get(
    "",
    response_model=ClinicRead,
    summary="Get the authenticated staff member's clinic",
)
async def get_clinic(staff: CurrentStaff, session: SessionDep) -> ClinicRead:
    clinic = await get_clinic_or_404(session, staff.clinic_id)
    return ClinicRead.model_validate(clinic)
