export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export type Staff = {
  id: string;
  clinic_id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
};

export type LoginResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
  staff: Staff;
};

export type Clinic = {
  id: string;
  name: string;
  timezone: string;
  address: string | null;
  phone: string | null;
  email: string | null;
  is_active: boolean;
};

export type Doctor = {
  id: string;
  clinic_id: string;
  name: string;
  specialization: string;
  languages: string[];
  fee: string;
  is_active: boolean;
};

export type DoctorInput = {
  name: string;
  specialization: string;
  languages: string[];
  fee: string;
};

export type AvailabilityRule = {
  id: string;
  doctor_id: string;
  weekday: number;
  start_time: string;
  end_time: string;
  slot_minutes: number;
  is_active: boolean;
};

export type AvailabilityRuleInput = {
  weekday: number;
  start_time: string;
  end_time: string;
  slot_minutes: number;
};

export type TimeOff = {
  id: string;
  doctor_id: string;
  starts_at: string;
  ends_at: string;
  reason: string;
};

export type TimeOffInput = {
  starts_at: string;
  ends_at: string;
  reason: string;
};

export type FreeSlot = {
  doctor_id: string;
  slot_date: string;
  starts_at: string;
  ends_at: string;
  slot_minutes: number;
  timezone: string;
};

export type AppointmentStatus =
  | "booked"
  | "cancelled"
  | "completed"
  | "no_show";

export type Appointment = {
  id: string;
  clinic_id: string;
  doctor_id: string;
  doctor_name: string;
  doctor_specialization: string;
  patient_id: string;
  patient_name: string;
  patient_phone: string;
  starts_at: string;
  ends_at: string;
  status: AppointmentStatus;
  source: "staff" | "agent";
  notes: string;
  fee: string;
};

export type AppointmentInput = {
  doctor_id: string;
  starts_at: string;
  ends_at: string;
  patient_name: string;
  patient_phone: string;
  notes?: string;
};

async function request<T>(
  path: string,
  token: string | null,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  if (init.body) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as {
      detail?: unknown;
    } | null;

    let message = `Request failed with status ${response.status}`;
    if (typeof payload?.detail === "string") {
      message = payload.detail;
    } else if (Array.isArray(payload?.detail)) {
      message = payload.detail
        .map((item) =>
          typeof item === "object" && item && "msg" in item
            ? String((item as { msg: unknown }).msg)
            : String(item),
        )
        .join(", ");
    }

    throw new ApiError(message, response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

function jsonBody(body: unknown): RequestInit {
  return { body: JSON.stringify(body) };
}

export const api = {
  login: (email: string, password: string) =>
    request<LoginResponse>("/api/v1/auth/login", null, {
      method: "POST",
      ...jsonBody({ email, password }),
    }),

  me: (token: string) => request<Staff>("/api/v1/auth/me", token),

  getClinic: (token: string) => request<Clinic>("/api/v1/clinic", token),

  listDoctors: (token: string, includeInactive = false) =>
    request<Doctor[]>(
      `/api/v1/doctors${includeInactive ? "?include_inactive=true" : ""}`,
      token,
    ),

  createDoctor: (token: string, input: DoctorInput) =>
    request<Doctor>("/api/v1/doctors", token, {
      method: "POST",
      ...jsonBody(input),
    }),

  updateDoctor: (token: string, doctorId: string, input: DoctorInput) =>
    request<Doctor>(`/api/v1/doctors/${doctorId}`, token, {
      method: "PATCH",
      ...jsonBody(input),
    }),

  deactivateDoctor: (token: string, doctorId: string) =>
    request<void>(`/api/v1/doctors/${doctorId}`, token, {
      method: "DELETE",
    }),

  listAvailability: (token: string, doctorId: string) =>
    request<AvailabilityRule[]>(
      `/api/v1/doctors/${doctorId}/availability`,
      token,
    ),

  createAvailability: (
    token: string,
    doctorId: string,
    input: AvailabilityRuleInput,
  ) =>
    request<AvailabilityRule>(
      `/api/v1/doctors/${doctorId}/availability`,
      token,
      { method: "POST", ...jsonBody(input) },
    ),

  deleteAvailability: (token: string, doctorId: string, ruleId: string) =>
    request<void>(
      `/api/v1/doctors/${doctorId}/availability/${ruleId}`,
      token,
      { method: "DELETE" },
    ),

  listTimeOff: (token: string, doctorId: string) =>
    request<TimeOff[]>(`/api/v1/doctors/${doctorId}/time-off`, token),

  createTimeOff: (token: string, doctorId: string, input: TimeOffInput) =>
    request<TimeOff>(`/api/v1/doctors/${doctorId}/time-off`, token, {
      method: "POST",
      ...jsonBody(input),
    }),

  deleteTimeOff: (token: string, doctorId: string, timeOffId: string) =>
    request<void>(
      `/api/v1/doctors/${doctorId}/time-off/${timeOffId}`,
      token,
      { method: "DELETE" },
    ),

  listFreeSlots: (token: string, doctorId: string, date: string) =>
    request<FreeSlot[]>(
      `/api/v1/doctors/${doctorId}/free-slots?date=${encodeURIComponent(date)}`,
      token,
    ),

  listAppointments: (token: string, date: string, doctorId?: string) => {
    const params = new URLSearchParams({ date });
    if (doctorId) params.set("doctor_id", doctorId);
    return request<Appointment[]>(
      `/api/v1/appointments?${params.toString()}`,
      token,
    );
  },

  bookAppointment: (token: string, input: AppointmentInput) =>
    request<Appointment>("/api/v1/appointments", token, {
      method: "POST",
      ...jsonBody(input),
    }),

  rescheduleAppointment: (
    token: string,
    appointmentId: string,
    input: { starts_at: string; ends_at: string },
  ) =>
    request<Appointment>(
      `/api/v1/appointments/${appointmentId}/reschedule`,
      token,
      { method: "PATCH", ...jsonBody(input) },
    ),

  cancelAppointment: (token: string, appointmentId: string) =>
    request<Appointment>(
      `/api/v1/appointments/${appointmentId}/cancel`,
      token,
      { method: "POST" },
    ),
};
