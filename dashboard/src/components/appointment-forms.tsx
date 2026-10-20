"use client";

import { useEffect, useState } from "react";

import {
  Button,
  EmptyState,
  ErrorPanel,
  Spinner,
  inputClass,
  labelClass,
} from "@/components/ui";
import { api } from "@/lib/api-client";
import type {
  Appointment,
  Doctor,
  FreeSlot,
} from "@/lib/api-types";
import { getErrorMessage } from "@/lib/errors";
import {
  dateInTimeZone,
  formatDate,
  formatTime,
  todayInTimeZone,
} from "@/lib/format";
import { useApi } from "@/lib/use-api";

export function BookingForm({
  doctors,
  timeZone,
  defaultDate,
  defaultDoctorId,
  defaultSlot = null,
  onSaved,
  onCancel,
}: {
  doctors: Doctor[];
  timeZone: string;
  defaultDate: string;
  defaultDoctorId?: string;
  defaultSlot?: FreeSlot | null;
  onSaved: (appointment: Appointment) => void;
  onCancel: () => void;
}) {
  const [doctorId, setDoctorId] = useState(
    defaultDoctorId || doctors[0]?.id || "",
  );
  const [date, setDate] = useState(defaultDate);
  const [slot, setSlot] = useState<FreeSlot | null>(defaultSlot);
  const [patientName, setPatientName] = useState("");
  const [patientPhone, setPatientPhone] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const {
    data: slots,
    loading,
    error: slotsError,
    reload,
  } = useApi(
    () => (doctorId ? api.listFreeSlots(doctorId, date) : Promise.resolve([])),
    [doctorId, date],
  );

  useEffect(() => {
    if (!slot || !slots) return;
    const stillAvailable = slots.some(
      (candidate) => candidate.starts_at === slot.starts_at,
    );
    if (!stillAvailable) setSlot(null);
  }, [slot, slots]);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (!slot) {
      setError("Choose an available time slot.");
      return;
    }
    if (!patientName.trim() || !patientPhone.trim()) {
      setError("Patient name and phone number are required.");
      return;
    }

    setBusy(true);
    try {
      const appointment = await api.bookAppointment({
        doctor_id: doctorId,
        starts_at: slot.starts_at,
        ends_at: slot.ends_at,
        patient_name: patientName.trim(),
        patient_phone: patientPhone.trim(),
        notes: notes.trim(),
      });
      onSaved(appointment);
    } catch (caught) {
      setError(getErrorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="space-y-5" onSubmit={handleSubmit}>
      {error ? <ErrorPanel message={error} /> : null}

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className={labelClass} htmlFor="booking-doctor">
            Doctor
          </label>
          <select
            id="booking-doctor"
            className={inputClass}
            value={doctorId}
            onChange={(event) => {
              setDoctorId(event.target.value);
              setSlot(null);
            }}
          >
            {doctors.map((doctor) => (
              <option key={doctor.id} value={doctor.id}>
                {doctor.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className={labelClass} htmlFor="booking-date">
            Date
          </label>
          <input
            id="booking-date"
            className={inputClass}
            type="date"
            value={date}
            min={todayInTimeZone(timeZone)}
            onChange={(event) => {
              setDate(event.target.value);
              setSlot(null);
            }}
            required
          />
        </div>
      </div>

      <div>
        <div className="mb-2 flex items-center justify-between">
          <span className={labelClass}>Available slots</span>
          <button
            className="text-xs font-semibold text-teal-700 hover:text-teal-900"
            type="button"
            onClick={() => void reload()}
          >
            Refresh
          </button>
        </div>

        {loading ? (
          <div className="flex h-28 items-center justify-center rounded-xl border border-slate-200 bg-slate-50">
            <Spinner className="h-5 w-5 text-teal-700" />
          </div>
        ) : null}

        {!loading && slotsError ? (
          <ErrorPanel message={slotsError} onRetry={reload} />
        ) : null}

        {!loading && !slotsError && slots && slots.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-center text-sm text-slate-500">
            No free slots on {formatDate(date)}. Try another date.
          </div>
        ) : null}

        {!loading && !slotsError && slots && slots.length > 0 ? (
          <div className="grid max-h-52 grid-cols-2 gap-2 overflow-y-auto rounded-xl border border-slate-200 p-3 sm:grid-cols-3">
            {slots.map((candidate) => {
              const selected = slot?.starts_at === candidate.starts_at;
              return (
                <button
                  key={candidate.starts_at}
                  className={`rounded-lg border px-3 py-2 text-sm font-medium transition ${
                    selected
                      ? "border-teal-700 bg-teal-700 text-white"
                      : "border-slate-200 bg-white text-slate-700 hover:border-teal-500 hover:text-teal-800"
                  }`}
                  onClick={() => setSlot(candidate)}
                  type="button"
                >
                  {formatTime(candidate.starts_at, timeZone)}
                </button>
              );
            })}
          </div>
        ) : null}
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className={labelClass} htmlFor="booking-name">
            Patient name
          </label>
          <input
            id="booking-name"
            className={inputClass}
            value={patientName}
            onChange={(event) => setPatientName(event.target.value)}
            required
          />
        </div>
        <div>
          <label className={labelClass} htmlFor="booking-phone">
            Phone number
          </label>
          <input
            id="booking-phone"
            className={inputClass}
            type="tel"
            value={patientPhone}
            onChange={(event) => setPatientPhone(event.target.value)}
            placeholder="+91 90000 00000"
            required
          />
        </div>
      </div>

      <div>
        <label className={labelClass} htmlFor="booking-notes">
          Notes
        </label>
        <textarea
          id="booking-notes"
          className={inputClass}
          rows={2}
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
          placeholder="Optional reason for visit"
        />
      </div>

      <div className="flex flex-col-reverse gap-2 pt-2 sm:flex-row sm:justify-end">
        <Button type="button" variant="secondary" onClick={onCancel} disabled={busy}>
          Cancel
        </Button>
        <Button type="submit" loading={busy} disabled={!slot}>
          Book appointment
        </Button>
      </div>
    </form>
  );
}

export function RescheduleForm({
  appointment,
  timeZone,
  onSaved,
  onCancel,
}: {
  appointment: Appointment;
  timeZone: string;
  onSaved: (appointment: Appointment) => void;
  onCancel: () => void;
}) {
  const [date, setDate] = useState(
    dateInTimeZone(appointment.starts_at, timeZone),
  );
  const [slot, setSlot] = useState<FreeSlot | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const {
    data: slots,
    loading,
    error: slotsError,
    reload,
  } = useApi(
    () => api.listFreeSlots(appointment.doctor_id, date),
    [appointment.doctor_id, date],
  );

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (!slot) {
      setError("Choose a new time slot.");
      return;
    }

    setBusy(true);
    try {
      const updated = await api.rescheduleAppointment(appointment.id, {
        starts_at: slot.starts_at,
        ends_at: slot.ends_at,
      });
      onSaved(updated);
    } catch (caught) {
      setError(getErrorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="space-y-5" onSubmit={handleSubmit}>
      {error ? <ErrorPanel message={error} /> : null}

      <div className="rounded-xl bg-slate-50 p-4 text-sm">
        <p className="font-semibold text-slate-900">
          {appointment.patient_name}
        </p>
        <p className="mt-1 text-slate-500">
          Currently {formatDate(dateInTimeZone(appointment.starts_at, timeZone))}{" "}
          at {formatTime(appointment.starts_at, timeZone)} with{" "}
          {appointment.doctor_name}
        </p>
      </div>

      <div>
        <label className={labelClass} htmlFor="reschedule-date">
          New date
        </label>
        <input
          id="reschedule-date"
          className={inputClass}
          type="date"
          value={date}
          min={todayInTimeZone(timeZone)}
          onChange={(event) => {
            setDate(event.target.value);
            setSlot(null);
          }}
          required
        />
      </div>

      <div>
        <div className="mb-2 flex items-center justify-between">
          <span className={labelClass}>Available slots</span>
          <button
            className="text-xs font-semibold text-teal-700 hover:text-teal-900"
            type="button"
            onClick={() => void reload()}
          >
            Refresh
          </button>
        </div>

        {loading ? (
          <div className="flex h-28 items-center justify-center rounded-xl border border-slate-200 bg-slate-50">
            <Spinner className="h-5 w-5 text-teal-700" />
          </div>
        ) : null}

        {!loading && slotsError ? (
          <ErrorPanel message={slotsError} onRetry={reload} />
        ) : null}

        {!loading && !slotsError && slots && slots.length === 0 ? (
          <EmptyState
            title="No slots for this day"
            description="Try another date or check the doctor's availability."
          />
        ) : null}

        {!loading && !slotsError && slots && slots.length > 0 ? (
          <div className="grid max-h-52 grid-cols-2 gap-2 overflow-y-auto rounded-xl border border-slate-200 p-3 sm:grid-cols-3">
            {slots.map((candidate) => {
              const selected = slot?.starts_at === candidate.starts_at;
              return (
                <button
                  key={candidate.starts_at}
                  className={`rounded-lg border px-3 py-2 text-sm font-medium transition ${
                    selected
                      ? "border-teal-700 bg-teal-700 text-white"
                      : "border-slate-200 bg-white text-slate-700 hover:border-teal-500 hover:text-teal-800"
                  }`}
                  onClick={() => setSlot(candidate)}
                  type="button"
                >
                  {formatTime(candidate.starts_at, timeZone)}
                </button>
              );
            })}
          </div>
        ) : null}
      </div>

      <div className="flex flex-col-reverse gap-2 pt-2 sm:flex-row sm:justify-end">
        <Button type="button" variant="secondary" onClick={onCancel} disabled={busy}>
          Cancel
        </Button>
        <Button type="submit" loading={busy} disabled={!slot}>
          Move appointment
        </Button>
      </div>
    </form>
  );
}
