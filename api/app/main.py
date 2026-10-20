from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routers import (
    agent,
    appointments,
    auth,
    availability,
    clinic,
    doctors,
    health,
    invitations,
    slots,
    staff,
    time_off,
)
from .config import settings
from .db import engine

TAGS_METADATA = [
    {"name": "Health", "description": "Service and database health checks."},
    {"name": "Auth", "description": "Staff login and current-user lookup."},
    {
        "name": "Staff",
        "description": "Clinic admin staff management and invitations.",
    },
    {
        "name": "Invitations",
        "description": "Public staff invitation preview and acceptance.",
    },
    {"name": "Clinic", "description": "Clinic profile for the logged-in staff user."},
    {
        "name": "Doctors",
        "description": "Clinic-scoped doctor management. Requires a staff JWT.",
    },
    {
        "name": "Availability",
        "description": "Weekly availability rules used to generate slots.",
    },
    {"name": "Time Off", "description": "Doctor leave and blocked time."},
    {
        "name": "Slots",
        "description": "Computed free slots. Accepts a staff JWT or service key.",
    },
    {
        "name": "Appointments",
        "description": "Booking, rescheduling, cancellation, and daily lists.",
    },
]


@asynccontextmanager
async def lifespan(_: FastAPI):
    if not settings.secret_key:
        raise RuntimeError("SECRET_KEY must be set before starting the API")
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.api_title,
    version="1.0.0",
    description=(
        "Clinic-scoped API for staff, the voice agent, and appointment booking. "
        "Staff use a JWT from `/api/v1/auth/login`; the agent uses `X-Service-Key`."
    ),
    openapi_tags=TAGS_METADATA,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.dashboard_url, "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_private_network=True,
)

app.include_router(health.router)
app.include_router(auth.router, prefix="/api/v1")
app.include_router(agent.router, prefix="/api/v1")
app.include_router(invitations.router, prefix="/api/v1")
app.include_router(staff.router, prefix="/api/v1")
app.include_router(clinic.router, prefix="/api/v1")
app.include_router(doctors.router, prefix="/api/v1")
app.include_router(availability.router, prefix="/api/v1")
app.include_router(time_off.router, prefix="/api/v1")
app.include_router(slots.router, prefix="/api/v1")
app.include_router(appointments.router, prefix="/api/v1")
