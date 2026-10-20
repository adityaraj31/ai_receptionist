import type { components } from "./api-schema";

export type Staff = components["schemas"]["StaffRead"];
export type Clinic = components["schemas"]["ClinicRead"];
export type ClinicInput = components["schemas"]["ClinicUpdate"];
export type Doctor = components["schemas"]["DoctorRead"];
export type DoctorInput = components["schemas"]["DoctorCreate"];
export type DoctorUpdate = components["schemas"]["DoctorUpdate"];
export type AvailabilityRule = components["schemas"]["AvailabilityRuleRead"];
export type AvailabilityRuleInput = components["schemas"]["AvailabilityRuleCreate"];
export type AvailabilityRuleUpdate = components["schemas"]["AvailabilityRuleUpdate"];
export type TimeOff = components["schemas"]["TimeOffRead"];
export type TimeOffInput = components["schemas"]["TimeOffCreate"];
export type FreeSlot = components["schemas"]["FreeSlotRead"];
export type Appointment = components["schemas"]["AppointmentRead"];
export type AppointmentInput = components["schemas"]["AppointmentCreate"];
export type AppointmentReschedule = components["schemas"]["AppointmentReschedule"];
export type LoginInput = components["schemas"]["LoginRequest"];
export type LoginResponse = components["schemas"]["TokenResponse"];
export type StaffUpdate = components["schemas"]["StaffUpdate"];
export type StaffInvitation = components["schemas"]["StaffInvitationRead"];
export type StaffInvitationCreate = components["schemas"]["StaffInvitationCreate"];
export type StaffInvitationCreated = components["schemas"]["StaffInvitationCreated"];
export type InvitationPreview = components["schemas"]["InvitationPreview"];

export type AppointmentStatus =
  | "booked"
  | "cancelled"
  | "completed"
  | "no_show";
