import createClient from "openapi-fetch";

import type { paths } from "./api-schema";
import {
  type Appointment,
  type AppointmentInput,
  type AppointmentReschedule,
  type AvailabilityRule,
  type AvailabilityRuleInput,
  type AvailabilityRuleUpdate,
  type CallAnalytics,
  type CallDetail,
  type Callback,
  type CallbackStatus,
  type CallbackUpdate,
  type Clinic,
  type ClinicInput,
  type Doctor,
  type DoctorInput,
  type DoctorUpdate,
  type Faq,
  type FaqInput,
  type FaqUpdate,
  type FreeSlot,
  type InvitationPreview,
  type LoginInput,
  type LoginResponse,
  type MessagingSettings,
  type MessagingSettingsInput,
  type Staff,
  type StaffInvitation,
  type StaffInvitationCreate,
  type StaffInvitationCreated,
  type StaffUpdate,
  type TimeOff,
  type TimeOffInput,
} from "./api-types";
import { notifyAuthExpired } from "./auth-events";
import { parseApiError } from "./errors";
import { getToken } from "./session";

export const API_URL = (
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

const noStoreFetch: typeof fetch = (input, init) =>
  fetch(input, { ...init, cache: "no-store" });

const client = createClient<paths>({
  baseUrl: API_URL,
  fetch: noStoreFetch,
});

client.use({
  onRequest({ request }) {
    const token = getToken();
    if (token) {
      request.headers.set("Authorization", `Bearer ${token}`);
    }
    return request;
  },
  onResponse({ request, response }) {
    const isLogin = new URL(request.url).pathname.endsWith("/auth/login");
    if (response.status === 401 && !isLogin) {
      notifyAuthExpired();
    }
    return response;
  },
});

type ApiResult<T> = {
  data?: T;
  error?: unknown;
  response: Response;
};

export async function unwrap<T>(
  resultOrPromise: ApiResult<T> | Promise<ApiResult<T>>,
): Promise<T> {
  const result = await resultOrPromise;
  if (!result.response.ok) {
    throw parseApiError(result.response.status, result.error);
  }
  return result.data as T;
}

export type DoctorPayload = {
  name: string;
  specialization: string;
  languages: string[];
  fee: string;
  is_active?: boolean;
};

export const api = {
  login: (body: LoginInput) =>
    unwrap<LoginResponse>(client.POST("/api/v1/auth/login", { body })),

  me: () => unwrap<Staff>(client.GET("/api/v1/auth/me")),

  getClinic: () => unwrap<Clinic>(client.GET("/api/v1/clinic")),

  getCallAnalytics: (days = 30) =>
    unwrap<CallAnalytics>(
      client.GET("/api/v1/analytics/calls", {
        params: { query: { days } },
      }),
    ),

  getCall: (callId: string) =>
    unwrap<CallDetail>(
      client.GET("/api/v1/calls/{call_id}", {
        params: { path: { call_id: callId } },
      }),
    ),

  getCallRecording: async (callId: string): Promise<Blob> => {
    const token = getToken();
    const response = await fetch(
      `${API_URL}/api/v1/calls/${callId}/recording`,
      {
        cache: "no-store",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      },
    );
    if (!response.ok) {
      let error: unknown = null;
      try {
        error = await response.json();
      } catch {
        error = null;
      }
      throw parseApiError(response.status, error);
    }
    return response.blob();
  },

  listStaff: () => unwrap<Staff[]>(client.GET("/api/v1/staff")),

  updateStaff: (staffId: string, body: StaffUpdate) =>
    unwrap<Staff>(
      client.PATCH("/api/v1/staff/{staff_id}", {
        params: { path: { staff_id: staffId } },
        body,
      }),
    ),

  listStaffInvitations: () =>
    unwrap<StaffInvitation[]>(client.GET("/api/v1/staff/invitations")),

  createStaffInvitation: (body: StaffInvitationCreate) =>
    unwrap<StaffInvitationCreated>(
      client.POST("/api/v1/staff/invitations", { body }),
    ),

  revokeStaffInvitation: (invitationId: string) =>
    unwrap<void>(
      client.DELETE("/api/v1/staff/invitations/{invitation_id}", {
        params: { path: { invitation_id: invitationId } },
      }),
    ),

  previewInvitation: (token: string) =>
    unwrap<InvitationPreview>(
      client.GET("/api/v1/invitations/{token}", {
        params: { path: { token } },
      }),
    ),

  acceptInvitation: (token: string, password: string) =>
    unwrap<LoginResponse>(
      client.POST("/api/v1/invitations/{token}/accept", {
        params: { path: { token } },
        body: { password },
      }),
    ),

  updateClinic: (body: ClinicInput) =>
    unwrap<Clinic>(client.PATCH("/api/v1/clinic", { body })),

  getMessagingSettings: () =>
    unwrap<MessagingSettings>(client.GET("/api/v1/messaging-settings")),

  updateMessagingSettings: (body: MessagingSettingsInput) =>
    unwrap<MessagingSettings>(
      client.PATCH("/api/v1/messaging-settings", { body }),
    ),

  listCallbacks: (status?: CallbackStatus) =>
    unwrap<Callback[]>(
      client.GET("/api/v1/callbacks", {
        params: { query: status ? { status } : {} },
      }),
    ),

  updateCallback: (callbackId: string, body: CallbackUpdate) =>
    unwrap<Callback>(
      client.PATCH("/api/v1/callbacks/{callback_id}", {
        params: { path: { callback_id: callbackId } },
        body,
      }),
    ),

  listDoctors: (includeInactive = false) =>
    unwrap<Doctor[]>(
      client.GET("/api/v1/doctors", {
        params: { query: { include_inactive: includeInactive } },
      }),
    ),

  createDoctor: (body: DoctorPayload) =>
    unwrap<Doctor>(
      client.POST("/api/v1/doctors", {
        body: { ...body, is_active: body.is_active ?? true } as DoctorInput,
      }),
    ),

  updateDoctor: (doctorId: string, body: DoctorPayload) =>
    unwrap<Doctor>(
      client.PATCH("/api/v1/doctors/{doctor_id}", {
        params: { path: { doctor_id: doctorId } },
        body: body as DoctorUpdate,
      }),
    ),

  deactivateDoctor: (doctorId: string) =>
    unwrap<void>(
      client.DELETE("/api/v1/doctors/{doctor_id}", {
        params: { path: { doctor_id: doctorId } },
      }),
    ),

  listFaqs: (includeInactive = false) =>
    unwrap<Faq[]>(
      client.GET("/api/v1/faqs", {
        params: { query: { include_inactive: includeInactive } },
      }),
    ),

  createFaq: (body: FaqInput) =>
    unwrap<Faq>(client.POST("/api/v1/faqs", { body })),

  updateFaq: (faqId: string, body: FaqUpdate) =>
    unwrap<Faq>(
      client.PATCH("/api/v1/faqs/{faq_id}", {
        params: { path: { faq_id: faqId } },
        body,
      }),
    ),

  deactivateFaq: (faqId: string) =>
    unwrap<void>(
      client.DELETE("/api/v1/faqs/{faq_id}", {
        params: { path: { faq_id: faqId } },
      }),
    ),

  listAvailability: (doctorId: string, includeInactive = false) =>
    unwrap<AvailabilityRule[]>(
      client.GET("/api/v1/doctors/{doctor_id}/availability", {
        params: {
          path: { doctor_id: doctorId },
          query: { include_inactive: includeInactive },
        },
      }),
    ),

  createAvailability: (doctorId: string, body: AvailabilityRuleInput) =>
    unwrap<AvailabilityRule>(
      client.POST("/api/v1/doctors/{doctor_id}/availability", {
        params: { path: { doctor_id: doctorId } },
        body: { ...body, is_active: body.is_active ?? true },
      }),
    ),

  updateAvailability: (
    doctorId: string,
    ruleId: string,
    body: AvailabilityRuleUpdate,
  ) =>
    unwrap<AvailabilityRule>(
      client.PATCH(
        "/api/v1/doctors/{doctor_id}/availability/{rule_id}",
        {
          params: { path: { doctor_id: doctorId, rule_id: ruleId } },
          body,
        },
      ),
    ),

  deleteAvailability: (doctorId: string, ruleId: string) =>
    unwrap<void>(
      client.DELETE(
        "/api/v1/doctors/{doctor_id}/availability/{rule_id}",
        {
          params: { path: { doctor_id: doctorId, rule_id: ruleId } },
        },
      ),
    ),

  listTimeOff: (doctorId: string) =>
    unwrap<TimeOff[]>(
      client.GET("/api/v1/doctors/{doctor_id}/time-off", {
        params: { path: { doctor_id: doctorId } },
      }),
    ),

  createTimeOff: (doctorId: string, body: TimeOffInput) =>
    unwrap<TimeOff>(
      client.POST("/api/v1/doctors/{doctor_id}/time-off", {
        params: { path: { doctor_id: doctorId } },
        body,
      }),
    ),

  deleteTimeOff: (doctorId: string, timeOffId: string) =>
    unwrap<void>(
      client.DELETE(
        "/api/v1/doctors/{doctor_id}/time-off/{time_off_id}",
        {
          params: {
            path: { doctor_id: doctorId, time_off_id: timeOffId },
          },
        },
      ),
    ),

  listFreeSlots: (doctorId: string, date: string) =>
    unwrap<FreeSlot[]>(
      client.GET("/api/v1/doctors/{doctor_id}/free-slots", {
        params: { path: { doctor_id: doctorId }, query: { date } },
      }),
    ),

  listAppointments: (date: string, doctorId?: string) =>
    unwrap<Appointment[]>(
      client.GET("/api/v1/appointments", {
        params: {
          query: {
            date,
            doctor_id: doctorId || undefined,
            status: undefined,
          },
        },
      }),
    ),

  bookAppointment: (body: AppointmentInput) =>
    unwrap<Appointment>(
      client.POST("/api/v1/appointments", { body }),
    ),

  rescheduleAppointment: (
    appointmentId: string,
    body: AppointmentReschedule,
  ) =>
    unwrap<Appointment>(
      client.PATCH("/api/v1/appointments/{appointment_id}/reschedule", {
        params: { path: { appointment_id: appointmentId } },
        body,
      }),
    ),

  cancelAppointment: (appointmentId: string) =>
    unwrap<Appointment>(
      client.POST("/api/v1/appointments/{appointment_id}/cancel", {
        params: { path: { appointment_id: appointmentId } },
      }),
    ),
};
