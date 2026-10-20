"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { BookingForm, RescheduleForm } from "@/components/appointment-forms";
import {
  CalendarIcon,
  ChevronRightIcon,
  PlusIcon,
  RefreshIcon,
} from "@/components/icons";
import {
  Button,
  ConfirmDialog,
  EmptyState,
  ErrorPanel,
  LoadingPanel,
  Modal,
  PageHeader,
  Spinner,
  StatusBadge,
  inputClass,
  labelClass,
} from "@/components/ui";
import { api } from "@/lib/api-client";
import type { Appointment, FreeSlot } from "@/lib/api-types";
import { getErrorMessage } from "@/lib/errors";
import {
  formatDate,
  formatFee,
  formatTime,
  todayInTimeZone,
} from "@/lib/format";
import { useApi } from "@/lib/use-api";

export default function AppointmentsPage() {
  const { clinic } = useAuth();
  const timeZone = clinic?.timezone ?? "Asia/Kolkata";

  const [date, setDate] = useState(() => todayInTimeZone("Asia/Kolkata"));
  const [doctorId, setDoctorId] = useState("");
  const [bookingOpen, setBookingOpen] = useState(false);
  const [bookingSlot, setBookingSlot] = useState<FreeSlot | null>(null);
  const [rescheduleTarget, setRescheduleTarget] =
    useState<Appointment | null>(null);
  const [cancelTarget, setCancelTarget] = useState<Appointment | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const dateSynced = useRef(false);

  useEffect(() => {
    if (!clinic || dateSynced.current) return;
    dateSynced.current = true;
    setDate(todayInTimeZone(clinic.timezone));
  }, [clinic]);

  const {
    data: doctors,
    loading: doctorsLoading,
    error: doctorsError,
    reload: reloadDoctors,
  } = useApi(() => api.listDoctors(), []);

  const {
    data: appointments,
    loading,
    error,
    reload,
  } = useApi(
    () => api.listAppointments(date, doctorId || undefined),
    [date, doctorId],
  );

  const {
    data: slots,
    loading: slotsLoading,
    error: slotsError,
    reload: reloadSlots,
  } = useApi(
    () =>
      doctorId ? api.listFreeSlots(doctorId, date) : Promise.resolve([]),
    [doctorId, date, refreshKey],
  );

  const selectedDoctor = doctors?.find((doctor) => doctor.id === doctorId);
  const sortedAppointments = [...(appointments ?? [])].sort(
    (a, b) =>
      new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime(),
  );
  const bookedCount = sortedAppointments.filter(
    (appointment) => appointment.status === "booked",
  ).length;
  const cancelledCount = sortedAppointments.filter(
    (appointment) => appointment.status === "cancelled",
  ).length;

  async function afterMutation() {
    setRefreshKey((key) => key + 1);
    await reload();
  }

  async function confirmCancel() {
    if (!cancelTarget) return;
    setBusy(true);
    setActionError(null);
    try {
      await api.cancelAppointment(cancelTarget.id);
      setCancelTarget(null);
      await afterMutation();
    } catch (caught) {
      setActionError(getErrorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  function shiftDate(delta: number) {
    const shifted = new Date(`${date}T12:00:00Z`);
    shifted.setUTCDate(shifted.getUTCDate() + delta);
    setDate(shifted.toISOString().slice(0, 10));
  }

  return (
    <div>
      <PageHeader
        eyebrow="Front desk"
        title="Appointments"
        description="Review the day, find free slots, and keep the schedule moving."
        actions={
          <Button
            onClick={() => {
              setBookingSlot(null);
              setBookingOpen(true);
            }}
            disabled={!doctors || doctors.length === 0}
          >
            <PlusIcon className="h-4 w-4" />
            Book appointment
          </Button>
        }
      />

      {actionError ? (
        <div className="mb-4">
          <ErrorPanel
            message={actionError}
            onRetry={() => {
              setActionError(null);
              void afterMutation();
            }}
          />
        </div>
      ) : null}

      <section className="mb-5 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <label className={labelClass} htmlFor="appointments-date">
              Day
            </label>
            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => shiftDate(-1)}
                aria-label="Previous day"
              >
                <ChevronRightIcon className="h-4 w-4 rotate-180" />
              </Button>
              <input
                id="appointments-date"
                className={`${inputClass} w-auto`}
                type="date"
                value={date}
                onChange={(event) => setDate(event.target.value)}
              />
              <Button
                variant="secondary"
                size="sm"
                onClick={() => shiftDate(1)}
                aria-label="Next day"
              >
                <ChevronRightIcon className="h-4 w-4" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setDate(todayInTimeZone(timeZone))}
              >
                Today
              </Button>
            </div>
            <p className="mt-2 text-sm font-medium text-slate-700">
              {formatDate(date)}
            </p>
          </div>

          <div className="w-full lg:w-72">
            <label className={labelClass} htmlFor="appointments-doctor">
              Filter by doctor
            </label>
            <select
              id="appointments-doctor"
              className={inputClass}
              value={doctorId}
              onChange={(event) => setDoctorId(event.target.value)}
              disabled={doctorsLoading}
            >
              <option value="">All doctors</option>
              {doctors?.map((doctor) => (
                <option key={doctor.id} value={doctor.id}>
                  {doctor.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap gap-2 border-t border-slate-100 pt-4 text-xs">
          <span className="rounded-full bg-teal-50 px-2.5 py-1 font-semibold text-teal-800">
            {bookedCount} booked
          </span>
          <span className="rounded-full bg-slate-100 px-2.5 py-1 font-semibold text-slate-600">
            {sortedAppointments.length} total
          </span>
          {cancelledCount > 0 ? (
            <span className="rounded-full bg-rose-50 px-2.5 py-1 font-semibold text-rose-700">
              {cancelledCount} cancelled
            </span>
          ) : null}
          <button
            className="ml-auto inline-flex items-center gap-1.5 font-semibold text-slate-500 hover:text-slate-800"
            type="button"
            onClick={() => {
              void reload();
              setRefreshKey((key) => key + 1);
            }}
          >
            <RefreshIcon className="h-3.5 w-3.5" />
            Refresh
          </button>
        </div>
      </section>

      {doctorsLoading ? <LoadingPanel label="Loading doctors…" /> : null}

      {!doctorsLoading && doctorsError ? (
        <ErrorPanel message={doctorsError} onRetry={reloadDoctors} />
      ) : null}

      {!doctorsLoading && !doctorsError && doctors?.length === 0 ? (
        <EmptyState
          title="Add a doctor to start booking"
          description="Appointments need at least one active doctor with weekly availability."
          action={
            <Link
              href="/doctors"
              className="inline-flex items-center justify-center rounded-xl bg-teal-700 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-teal-800"
            >
              Add a doctor
            </Link>
          }
        />
      ) : null}

      {!doctorsLoading && doctors && doctors.length > 0 ? (
        <div className="grid gap-5 xl:grid-cols-[1.55fr_1fr]">
          <section>
            {loading ? <LoadingPanel label="Loading appointments…" /> : null}

            {!loading && error ? (
              <ErrorPanel message={error} onRetry={reload} />
            ) : null}

            {!loading && !error && sortedAppointments.length === 0 ? (
              <EmptyState
                title="No appointments this day"
                description={
                  selectedDoctor
                    ? `${selectedDoctor.name} has no appointments on ${formatDate(date)}.`
                    : `Nothing is booked for ${formatDate(date)} yet.`
                }
                action={
                  <Button
                    onClick={() => {
                      setBookingSlot(null);
                      setBookingOpen(true);
                    }}
                  >
                    <PlusIcon className="h-4 w-4" />
                    Book a patient
                  </Button>
                }
              />
            ) : null}

            {!loading && !error && sortedAppointments.length > 0 ? (
              <div className="space-y-3">
                {sortedAppointments.map((appointment) => (
                  <article
                    key={appointment.id}
                    className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5"
                  >
                    <div className="flex items-start gap-4">
                      <div className="min-w-20 rounded-xl bg-slate-50 px-3 py-2 text-center">
                        <p className="text-sm font-semibold text-slate-900">
                          {formatTime(appointment.starts_at, timeZone)}
                        </p>
                        <p className="mt-0.5 text-[11px] text-slate-500">
                          {formatTime(appointment.ends_at, timeZone)}
                        </p>
                      </div>

                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <h2 className="truncate text-base font-semibold text-slate-900">
                            {appointment.patient_name}
                          </h2>
                          <StatusBadge status={appointment.status} />
                        </div>
                        <p className="mt-1 text-sm text-slate-500">
                          {appointment.doctor_name} ·{" "}
                          {appointment.doctor_specialization}
                        </p>
                        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
                          <a
                            className="font-medium text-slate-600 hover:text-teal-700"
                            href={`tel:${appointment.patient_phone}`}
                          >
                            {appointment.patient_phone}
                          </a>
                          <span>{formatFee(appointment.fee)}</span>
                          <span className="capitalize">
                            via {appointment.source}
                          </span>
                        </div>
                        {appointment.notes ? (
                          <p className="mt-2 text-xs text-slate-500">
                            {appointment.notes}
                          </p>
                        ) : null}
                      </div>
                    </div>

                    {appointment.status === "booked" ? (
                      <div className="mt-4 flex flex-wrap gap-2 border-t border-slate-100 pt-3">
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => setRescheduleTarget(appointment)}
                        >
                          Reschedule
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-rose-600 hover:bg-rose-50 hover:text-rose-700"
                          onClick={() => setCancelTarget(appointment)}
                        >
                          Cancel appointment
                        </Button>
                      </div>
                    ) : null}
                  </article>
                ))}
              </div>
            ) : null}
          </section>

          <aside className="h-fit rounded-2xl border border-slate-200 bg-white shadow-sm xl:sticky xl:top-24">
            <div className="border-b border-slate-200 px-5 py-4">
              <h2 className="text-base font-semibold text-slate-900">
                Free slots
              </h2>
              <p className="mt-0.5 text-xs text-slate-500">
                {selectedDoctor
                  ? `${selectedDoctor.name} on ${formatDate(date)}`
                  : "Choose a doctor in the filter to see open times."}
              </p>
            </div>

            <div className="p-5">
              {!doctorId ? (
                <div className="rounded-xl border border-dashed border-slate-300 px-4 py-8 text-center">
                  <CalendarIcon className="mx-auto h-7 w-7 text-slate-300" />
                  <p className="mt-2 text-sm text-slate-500">
                    Select a doctor above.
                  </p>
                </div>
              ) : null}

              {doctorId && slotsLoading ? (
                <div className="flex h-28 items-center justify-center">
                  <Spinner className="h-5 w-5 text-teal-700" />
                </div>
              ) : null}

              {doctorId && !slotsLoading && slotsError ? (
                <ErrorPanel message={slotsError} onRetry={reloadSlots} />
              ) : null}

              {doctorId && !slotsLoading && !slotsError && slots?.length === 0 ? (
                <div className="rounded-xl border border-dashed border-slate-300 px-4 py-8 text-center text-sm text-slate-500">
                  No open slots for this day.
                </div>
              ) : null}

              {doctorId && !slotsLoading && !slotsError && slots && slots.length > 0 ? (
                <div className="grid grid-cols-2 gap-2">
                  {slots.map((slot) => (
                    <button
                      key={slot.starts_at}
                      className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 transition hover:border-teal-500 hover:bg-teal-50 hover:text-teal-800"
                      onClick={() => {
                        setBookingSlot(slot);
                        setBookingOpen(true);
                      }}
                      type="button"
                    >
                      {formatTime(slot.starts_at, timeZone)}
                    </button>
                  ))}
                </div>
              ) : null}
            </div>
          </aside>
        </div>
      ) : null}

      {bookingOpen ? (
        <Modal
          open
          wide
          onClose={() => {
            setBookingOpen(false);
            setBookingSlot(null);
          }}
          title="Book appointment"
          description={`Times shown in ${timeZone}.`}
        >
          <BookingForm
            doctors={doctors ?? []}
            timeZone={timeZone}
            defaultDate={date}
            defaultDoctorId={doctorId || undefined}
            defaultSlot={bookingSlot}
            onCancel={() => {
              setBookingOpen(false);
              setBookingSlot(null);
            }}
            onSaved={async () => {
              setBookingOpen(false);
              setBookingSlot(null);
              await afterMutation();
            }}
          />
        </Modal>
      ) : null}

      {rescheduleTarget ? (
        <Modal
          open
          wide
          onClose={() => setRescheduleTarget(null)}
          title="Reschedule appointment"
          description="Choose a new free slot for this patient."
        >
          <RescheduleForm
            appointment={rescheduleTarget}
            timeZone={timeZone}
            onCancel={() => setRescheduleTarget(null)}
            onSaved={async () => {
              setRescheduleTarget(null);
              await afterMutation();
            }}
          />
        </Modal>
      ) : null}

      <ConfirmDialog
        open={Boolean(cancelTarget)}
        title="Cancel appointment?"
        message={`Cancel ${cancelTarget?.patient_name ?? "this appointment"} at ${cancelTarget ? formatTime(cancelTarget.starts_at, timeZone) : ""} on ${formatDate(date)}? The slot will become available again.`}
        confirmLabel="Cancel appointment"
        danger
        busy={busy}
        onCancel={() => setCancelTarget(null)}
        onConfirm={confirmCancel}
      />
    </div>
  );
}
