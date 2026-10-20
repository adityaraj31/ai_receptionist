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

export type Clinic = {
  id: string;
  name: string;
  timezone: string;
  address: string | null;
  phone: string | null;
  fees: string | null;
  emergency_number: string;
  is_active: boolean;
};

export type Doctor = {
  id: string;
  clinic_id: string;
  name: string;
  specialty: string;
  days: string;
  hours: string;
  is_active: boolean;
};

export type DoctorInput = {
  name: string;
  specialty: string;
  days: string;
  hours: string;
};

export type Slot = {
  id: string;
  doctor_id: string;
  doctor_name: string;
  doctor_specialty: string;
  slot_date: string;
  start_time: string;
  end_time: string;
  capacity: number;
  booked_count: number;
  is_active: boolean;
};

export type SlotInput = {
  doctor_id: string;
  slot_date: string;
  start_time: string;
  end_time: string;
  capacity: number;
};

export type SlotGenerateInput = {
  doctor_id: string;
  start_date: string;
  end_date: string;
  start_time: string;
  end_time: string;
  duration_minutes: number;
  capacity: number;
  weekdays: number[];
};

export type SlotGenerateResult = {
  created: number;
  skipped: number;
  slots: Slot[];
};

async function request<T>(
  path: string,
  adminKey: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("X-Admin-Key", adminKey);
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
      detail?: string;
    } | null;
    throw new ApiError(
      payload?.detail ?? `Request failed with status ${response.status}`,
      response.status,
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export const api = {
  getClinic: (adminKey: string) =>
    request<Clinic>("/api/v1/admin/clinic", adminKey),

  listDoctors: (adminKey: string) =>
    request<Doctor[]>("/api/v1/admin/doctors", adminKey),

  createDoctor: (adminKey: string, input: DoctorInput) =>
    request<Doctor>("/api/v1/admin/doctors", adminKey, {
      method: "POST",
      body: JSON.stringify(input),
    }),

  deactivateDoctor: (adminKey: string, doctorId: string) =>
    request<void>(`/api/v1/admin/doctors/${doctorId}`, adminKey, {
      method: "DELETE",
    }),

  listSlots: (
    adminKey: string,
    filters: { doctorId?: string; dateFrom?: string; dateTo?: string } = {},
  ) => {
    const params = new URLSearchParams();
    if (filters.doctorId) params.set("doctor_id", filters.doctorId);
    if (filters.dateFrom) params.set("date_from", filters.dateFrom);
    if (filters.dateTo) params.set("date_to", filters.dateTo);
    const query = params.toString();
    return request<Slot[]>(
      `/api/v1/admin/slots${query ? `?${query}` : ""}`,
      adminKey,
    );
  },

  createSlot: (adminKey: string, input: SlotInput) =>
    request<Slot>("/api/v1/admin/slots", adminKey, {
      method: "POST",
      body: JSON.stringify(input),
    }),

  generateSlots: (adminKey: string, input: SlotGenerateInput) =>
    request<SlotGenerateResult>("/api/v1/admin/slots/generate", adminKey, {
      method: "POST",
      body: JSON.stringify(input),
    }),

  deactivateSlot: (adminKey: string, slotId: string) =>
    request<void>(`/api/v1/admin/slots/${slotId}`, adminKey, {
      method: "DELETE",
    }),
};
