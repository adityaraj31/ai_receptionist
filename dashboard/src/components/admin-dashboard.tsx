"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type FormEvent,
} from "react";

import {
  ApiError,
  api,
  type Appointment,
  type AvailabilityRule,
  type AvailabilityRuleInput,
  type Clinic,
  type Doctor,
  type DoctorInput,
  type FreeSlot,
  type Staff,
  type TimeOff,
} from "@/lib/api";

const TOKEN_STORAGE = "ai-receptionist-token";

const WEEKDAYS = [
  { value: 1, label: "Monday" },
  { value: 2, label: "Tuesday" },
  { value: 3, label: "Wednesday" },
  { value: 4, label: "Thursday" },
  { value: 5, label: "Friday" },
  { value: 6, label: "Saturday" },
  { value: 7, label: "Sunday" },
];

type Tab = "doctors" | "availability" | "timeoff" | "appointments";

type DoctorForm = Omit<DoctorInput, "languages"> & {
  id?: string;
  languages: string;
};

type TimeOffForm = {
  starts_at: string;
  ends_at: string;
  reason: string;
};

type BookingForm = {
  patient_name: string;
  patient_phone: string;
  notes: string;
};

const EMPTY_DOCTOR: DoctorForm = {
  name: "",
  specialization: "",
  languages: "",
  fee: "500",
};

const EMPTY_RULE: AvailabilityRuleInput = {
  weekday: 1,
  start_time: "09:00",
  end_time: "13:00",
  slot_minutes: 15,
};

const EMPTY_TIME_OFF: TimeOffForm = {
  starts_at: "",
  ends_at: "",
  reason: "",
};

const EMPTY_BOOKING: BookingForm = {
  patient_name: "",
  patient_phone: "",
  notes: "",
};

function today(): string {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60_000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-IN", {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(`${value}T00:00:00`));
}

function formatDateTime(value: string, timeZone?: string): string {
  return new Intl.DateTimeFormat("en-IN", {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
    timeZone,
  }).format(new Date(value));
}

function formatSlotTime(value: string, timeZone?: string): string {
  return new Intl.DateTimeFormat("en-IN", {
    hour: "numeric",
    minute: "2-digit",
    timeZone,
  }).format(new Date(value));
}

function formatRuleTime(value: string): string {
  return value.slice(0, 5);
}

function localToClinicIso(localValue: string, timeZone?: string): string {
  if (!timeZone) {
    return new Date(localValue).toISOString();
  }

  const [datePart, timePart] = localValue.split("T");
  const [year, month, day] = datePart.split("-").map(Number);
  const [hour, minute] = timePart.split(":").map(Number);
  const utcGuess = Date.UTC(year, month - 1, day, hour, minute);
  const formatter = new Intl.DateTimeFormat("en-US", {
    timeZone,
    hourCycle: "h23",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  const values: Record<string, string> = {};
  for (const part of formatter.formatToParts(new Date(utcGuess))) {
    if (part.type !== "literal") values[part.type] = part.value;
  }
  const asZone = Date.UTC(
    Number(values.year),
    Number(values.month) - 1,
    Number(values.day),
    Number(values.hour),
    Number(values.minute),
    Number(values.second),
  );
  return new Date(utcGuess - (asZone - utcGuess)).toISOString();
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong";
}

const inputClass =
  "mt-1 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-100";
const labelClass = "text-sm font-medium text-slate-700";
const primaryButton =
  "inline-flex items-center justify-center rounded-xl bg-teal-700 px-4 py-2 text-sm font-semibold text-white transition hover:bg-teal-800 disabled:cursor-not-allowed disabled:opacity-50";
const secondaryButton =
  "inline-flex items-center justify-center rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-400 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50";
const dangerButton =
  "text-xs font-medium text-rose-700 hover:text-rose-800 disabled:opacity-50";
const cardClass =
  "rounded-2xl border border-slate-200 bg-white p-5 shadow-sm";

export function AdminDashboard() {
  const [token, setToken] = useState("");
  const [staff, setStaff] = useState<Staff | null>(null);
  const [clinic, setClinic] = useState<Clinic | null>(null);
  const [email, setEmail] = useState("admin@demo-clinic.example.com");
  const [password, setPassword] = useState("");
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [selectedDoctorId, setSelectedDoctorId] = useState("");
  const [rules, setRules] = useState<AvailabilityRule[]>([]);
  const [timeOff, setTimeOff] = useState<TimeOff[]>([]);
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [freeSlots, setFreeSlots] = useState<FreeSlot[]>([]);
  const [date, setDate] = useState(today());
  const [tab, setTab] = useState<Tab>("doctors");
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const [doctorForm, setDoctorForm] = useState<DoctorForm>(EMPTY_DOCTOR);
  const [ruleForm, setRuleForm] =
    useState<AvailabilityRuleInput>(EMPTY_RULE);
  const [timeOffForm, setTimeOffForm] = useState<TimeOffForm>(EMPTY_TIME_OFF);
  const [bookingForm, setBookingForm] = useState<BookingForm>(EMPTY_BOOKING);
  const [selectedSlot, setSelectedSlot] = useState<FreeSlot | null>(null);

  const selectedDoctor = useMemo(
    () => doctors.find((doctor) => doctor.id === selectedDoctorId) ?? null,
    [doctors, selectedDoctorId],
  );

  const reload = useCallback(() => setRefreshKey((value) => value + 1), []);

  const resetSession = useCallback((message = "") => {
    window.sessionStorage.removeItem(TOKEN_STORAGE);
    setToken("");
    setStaff(null);
    setClinic(null);
    setDoctors([]);
    setSelectedDoctorId("");
    setRules([]);
    setTimeOff([]);
    setAppointments([]);
    setFreeSlots([]);
    setSelectedSlot(null);
    setDoctorForm(EMPTY_DOCTOR);
    setRuleForm(EMPTY_RULE);
    setTimeOffForm(EMPTY_TIME_OFF);
    setBookingForm(EMPTY_BOOKING);
    setError(message);
    setNotice("");
    setTab("doctors");
  }, []);

  const handleApiError = useCallback(
    (err: unknown) => {
      if (err instanceof ApiError && err.status === 401) {
        resetSession("Session expired. Please log in again.");
        return;
      }
      setError(errorMessage(err));
    },
    [resetSession],
  );

  useEffect(() => {
    const saved = window.sessionStorage.getItem(TOKEN_STORAGE);
    if (saved) setToken(saved);
  }, []);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    setLoading(true);
    setError("");

    Promise.all([api.me(token), api.getClinic(token), api.listDoctors(token)])
      .then(([staffData, clinicData, doctorData]) => {
        if (cancelled) return;
        setStaff(staffData);
        setClinic(clinicData);
        setDoctors(doctorData);
        setSelectedDoctorId((current) =>
          doctorData.some((doctor) => doctor.id === current)
            ? current
            : (doctorData[0]?.id ?? ""),
        );
      })
      .catch((err) => {
        if (!cancelled) handleApiError(err);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [token, refreshKey, handleApiError]);

  useEffect(() => {
    if (!token || !selectedDoctorId) {
      setRules([]);
      setTimeOff([]);
      return;
    }
    let cancelled = false;

    Promise.all([
      api.listAvailability(token, selectedDoctorId),
      api.listTimeOff(token, selectedDoctorId),
    ])
      .then(([ruleData, timeOffData]) => {
        if (cancelled) return;
        setRules(ruleData);
        setTimeOff(timeOffData);
      })
      .catch((err) => {
        if (!cancelled) handleApiError(err);
      });

    return () => {
      cancelled = true;
    };
  }, [token, selectedDoctorId, refreshKey, handleApiError]);

  useEffect(() => {
    if (!token || !date) return;
    let cancelled = false;
    const doctorId = selectedDoctorId || undefined;

    Promise.all([
      api.listAppointments(token, date, doctorId),
      doctorId
        ? api.listFreeSlots(token, doctorId, date)
        : Promise.resolve<FreeSlot[]>([]),
    ])
      .then(([appointmentData, slotData]) => {
        if (cancelled) return;
        setAppointments(appointmentData);
        setFreeSlots(slotData);
        setSelectedSlot((current) =>
          current &&
          slotData.some(
            (slot) =>
              slot.doctor_id === current.doctor_id &&
              slot.starts_at === current.starts_at,
          )
            ? current
            : null,
        );
      })
      .catch((err) => {
        if (!cancelled) handleApiError(err);
      });

    return () => {
      cancelled = true;
    };
  }, [token, selectedDoctorId, date, refreshKey, handleApiError]);

  async function run(action: () => Promise<unknown>, success: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
      setNotice(success);
      reload();
    } catch (err) {
      handleApiError(err);
    } finally {
      setBusy(false);
    }
  }

  async function handleLogin(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const response = await api.login(email.trim(), password);
      window.sessionStorage.setItem(TOKEN_STORAGE, response.access_token);
      setToken(response.access_token);
      setStaff(response.staff);
      setPassword("");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  function lock() {
    resetSession();
  }

  async function handleDoctorSubmit(event: FormEvent) {
    event.preventDefault();
    if (!token) return;
    const input: DoctorInput = {
      name: doctorForm.name.trim(),
      specialization: doctorForm.specialization.trim(),
      languages: doctorForm.languages
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
      fee: doctorForm.fee || "0",
    };
    if (!input.name) {
      setError("Doctor name is required.");
      return;
    }

    const editingId = doctorForm.id;
    await run(async () => {
      if (editingId) {
        await api.updateDoctor(token, editingId, input);
      } else {
        await api.createDoctor(token, input);
      }
      setDoctorForm(EMPTY_DOCTOR);
    }, editingId ? "Doctor updated." : "Doctor added.");
  }

  function editDoctor(doctor: Doctor) {
    setDoctorForm({
      id: doctor.id,
      name: doctor.name,
      specialization: doctor.specialization,
      languages: doctor.languages.join(", "),
      fee: doctor.fee,
    });
    setError("");
    setNotice("");
  }

  async function deactivateDoctor(doctor: Doctor) {
    if (!token) return;
    if (!window.confirm(`Deactivate ${doctor.name}?`)) return;
    await run(
      () => api.deactivateDoctor(token, doctor.id),
      `${doctor.name} deactivated.`,
    );
  }

  async function handleRuleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!token || !selectedDoctorId) return;
    await run(async () => {
      await api.createAvailability(token, selectedDoctorId, {
        weekday: Number(ruleForm.weekday),
        start_time: ruleForm.start_time,
        end_time: ruleForm.end_time,
        slot_minutes: Number(ruleForm.slot_minutes),
      });
      setRuleForm(EMPTY_RULE);
    }, "Availability rule added.");
  }

  async function deleteRule(rule: AvailabilityRule) {
    if (!token || !selectedDoctorId) return;
    await run(
      () => api.deleteAvailability(token, selectedDoctorId, rule.id),
      "Availability rule deleted.",
    );
  }

  async function handleTimeOffSubmit(event: FormEvent) {
    event.preventDefault();
    if (!token || !selectedDoctorId) return;
    if (!timeOffForm.starts_at || !timeOffForm.ends_at) {
      setError("Start and end times are required.");
      return;
    }
    const startsAt = localToClinicIso(
      timeOffForm.starts_at,
      clinic?.timezone,
    );
    const endsAt = localToClinicIso(timeOffForm.ends_at, clinic?.timezone);

    await run(async () => {
      await api.createTimeOff(token, selectedDoctorId, {
        starts_at: startsAt,
        ends_at: endsAt,
        reason: timeOffForm.reason.trim(),
      });
      setTimeOffForm(EMPTY_TIME_OFF);
    }, "Time off added.");
  }

  async function deleteTimeOff(entry: TimeOff) {
    if (!token || !selectedDoctorId) return;
    await run(
      () => api.deleteTimeOff(token, selectedDoctorId, entry.id),
      "Time off deleted.",
    );
  }

  async function handleBook(event: FormEvent) {
    event.preventDefault();
    if (!token || !selectedDoctorId || !selectedSlot) return;
    await run(async () => {
      await api.bookAppointment(token, {
        doctor_id: selectedDoctorId,
        starts_at: selectedSlot.starts_at,
        ends_at: selectedSlot.ends_at,
        patient_name: bookingForm.patient_name.trim(),
        patient_phone: bookingForm.patient_phone.trim(),
        notes: bookingForm.notes.trim(),
      });
      setBookingForm(EMPTY_BOOKING);
      setSelectedSlot(null);
    }, "Appointment booked.");
  }

  async function cancelAppointment(appointment: Appointment) {
    if (!token) return;
    if (
      !window.confirm(
        `Cancel ${appointment.patient_name}'s appointment at ${formatSlotTime(
          appointment.starts_at,
          clinic?.timezone,
        )}?`,
      )
    ) {
      return;
    }
    await run(
      () => api.cancelAppointment(token, appointment.id),
      "Appointment cancelled.",
    );
  }

  if (!token) {
    return (
      <div className="mx-auto max-w-md">
        <div className="mb-8 text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.25em] text-teal-700">
            AI Receptionist
          </p>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight">
            Staff login
          </h1>
          <p className="mt-2 text-sm text-slate-500">
            Sign in to manage doctors, availability, and appointments.
          </p>
        </div>

        <form onSubmit={handleLogin} className={cardClass}>
          <div>
            <label className={labelClass} htmlFor="email">
              Email
            </label>
            <input
              id="email"
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className={inputClass}
            />
          </div>
          <div className="mt-3">
            <label className={labelClass} htmlFor="password">
              Password
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className={inputClass}
            />
          </div>
          <button
            type="submit"
            disabled={busy}
            className={`${primaryButton} mt-4 w-full`}
          >
            {busy ? "Signing in…" : "Open dashboard"}
          </button>
          <p className="mt-3 text-xs text-slate-500">
            Demo: admin@demo-clinic.example.com / DemoClinic123!
          </p>
        </form>

        {error ? (
          <div className="mt-4 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
            {error}
          </div>
        ) : null}
      </div>
    );
  }

  const bookedCount = appointments.filter(
    (appointment) => appointment.status === "booked",
  ).length;

  return (
    <div>
      <header className="mb-8 flex flex-col gap-4 border-b border-slate-200 pb-6 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.25em] text-teal-700">
            Clinic admin
          </p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight">
            {clinic?.name ?? "AI Receptionist"}
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            {clinic?.address ??
              "Manage doctors, weekly availability, and appointments."}
            {clinic?.timezone ? ` · ${clinic.timezone}` : ""}
          </p>
          {staff ? (
            <p className="mt-1 text-xs text-slate-500">
              Signed in as {staff.full_name || staff.email} · {staff.role}
            </p>
          ) : null}
        </div>
        <div className="flex items-center gap-3">
          <span className="inline-flex items-center gap-2 rounded-full border border-teal-200 bg-teal-50 px-3 py-1 text-xs font-medium text-teal-800">
            <span className="h-2 w-2 rounded-full bg-teal-600" />
            {loading ? "Syncing" : "API connected"}
          </span>
          <button
            type="button"
            onClick={reload}
            disabled={loading}
            className={secondaryButton}
          >
            Refresh
          </button>
          <button type="button" onClick={lock} className={secondaryButton}>
            Lock
          </button>
        </div>
      </header>

      {error ? (
        <div className="mb-6 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
          {error}
        </div>
      ) : null}

      {notice ? (
        <div className="mb-6 rounded-xl border border-teal-200 bg-teal-50 px-4 py-3 text-sm text-teal-800">
          {notice}
        </div>
      ) : null}

      <section className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Doctors" value={doctors.length} />
        <StatCard label="Weekly rules" value={rules.length} />
        <StatCard label="Booked on date" value={bookedCount} />
        <StatCard label="Free slots" value={freeSlots.length} />
      </section>

      <nav className="mb-6 flex flex-wrap gap-2">
        {(
          [
            ["doctors", "Doctors"],
            ["availability", "Availability"],
            ["timeoff", "Time off"],
            ["appointments", "Appointments"],
          ] as const
        ).map(([value, label]) => (
          <button
            key={value}
            type="button"
            onClick={() => setTab(value)}
            className={
              tab === value
                ? "rounded-xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white"
                : secondaryButton
            }
          >
            {label}
          </button>
        ))}
      </nav>

      {tab === "doctors" ? (
        <div className="grid gap-6 lg:grid-cols-2">
          <section className={cardClass}>
            <div className="mb-4">
              <h2 className="text-lg font-semibold">
                {doctorForm.id ? "Edit doctor" : "Add doctor"}
              </h2>
              <p className="text-sm text-slate-500">
                Fee is in INR. Languages are comma separated.
              </p>
            </div>

            <form onSubmit={handleDoctorSubmit} className="space-y-3">
              <div>
                <label className={labelClass} htmlFor="doctor-name">
                  Name
                </label>
                <input
                  id="doctor-name"
                  required
                  value={doctorForm.name}
                  onChange={(event) =>
                    setDoctorForm({ ...doctorForm, name: event.target.value })
                  }
                  className={inputClass}
                  placeholder="Dr. Asha Rao"
                />
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <label className={labelClass} htmlFor="doctor-specialization">
                    Specialization
                  </label>
                  <input
                    id="doctor-specialization"
                    value={doctorForm.specialization}
                    onChange={(event) =>
                      setDoctorForm({
                        ...doctorForm,
                        specialization: event.target.value,
                      })
                    }
                    className={inputClass}
                    placeholder="General Medicine"
                  />
                </div>
                <div>
                  <label className={labelClass} htmlFor="doctor-fee">
                    Fee (INR)
                  </label>
                  <input
                    id="doctor-fee"
                    type="number"
                    min={0}
                    step="0.01"
                    value={doctorForm.fee}
                    onChange={(event) =>
                      setDoctorForm({ ...doctorForm, fee: event.target.value })
                    }
                    className={inputClass}
                  />
                </div>
              </div>
              <div>
                <label className={labelClass} htmlFor="doctor-languages">
                  Languages
                </label>
                <input
                  id="doctor-languages"
                  value={doctorForm.languages}
                  onChange={(event) =>
                    setDoctorForm({
                      ...doctorForm,
                      languages: event.target.value,
                    })
                  }
                  className={inputClass}
                  placeholder="English, Hindi"
                />
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="submit"
                  disabled={busy}
                  className={primaryButton}
                >
                  {doctorForm.id ? "Update doctor" : "Add doctor"}
                </button>
                {doctorForm.id ? (
                  <button
                    type="button"
                    onClick={() => setDoctorForm(EMPTY_DOCTOR)}
                    className={secondaryButton}
                  >
                    Cancel
                  </button>
                ) : null}
              </div>
            </form>
          </section>

          <section className={cardClass}>
            <div className="mb-4">
              <h2 className="text-lg font-semibold">Doctors</h2>
              <p className="text-sm text-slate-500">
                Active doctors for this clinic.
              </p>
            </div>

            <div className="space-y-3">
              {doctors.map((doctor) => (
                <div
                  key={doctor.id}
                  className={
                    doctor.id === selectedDoctorId
                      ? "rounded-xl border border-teal-300 bg-teal-50/50 px-4 py-3"
                      : "rounded-xl border border-slate-200 px-4 py-3"
                  }
                >
                  <div className="flex items-start justify-between gap-3">
                    <button
                      type="button"
                      onClick={() => setSelectedDoctorId(doctor.id)}
                      className="text-left"
                    >
                      <p className="font-medium">{doctor.name}</p>
                      <p className="text-sm text-slate-500">
                        {doctor.specialization || "No specialization"}
                      </p>
                      <p className="mt-1 text-xs text-slate-500">
                        {doctor.languages.length
                          ? doctor.languages.join(", ")
                          : "No languages set"}{" "}
                        · ₹{doctor.fee}
                      </p>
                    </button>
                    <div className="flex flex-col items-end gap-2">
                      <button
                        type="button"
                        onClick={() => editDoctor(doctor)}
                        className="text-xs font-medium text-teal-700 hover:text-teal-800"
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setSelectedDoctorId(doctor.id);
                          setTab("availability");
                        }}
                        className="text-xs font-medium text-slate-600 hover:text-slate-800"
                      >
                        Availability
                      </button>
                      <button
                        type="button"
                        onClick={() => void deactivateDoctor(doctor)}
                        disabled={busy}
                        className={dangerButton}
                      >
                        Deactivate
                      </button>
                    </div>
                  </div>
                </div>
              ))}
              {doctors.length === 0 ? (
                <p className="text-sm text-slate-500">
                  No active doctors yet. Add the first one.
                </p>
              ) : null}
            </div>
          </section>
        </div>
      ) : null}

      {tab === "availability" ? (
        <div className="grid gap-6 lg:grid-cols-2">
          <section className={cardClass}>
            <div className="mb-4">
              <h2 className="text-lg font-semibold">Weekly availability</h2>
              <p className="text-sm text-slate-500">
                Slots are generated from these windows.
              </p>
            </div>

            <DoctorSelect
              id="availability-doctor"
              value={selectedDoctorId}
              doctors={doctors}
              onChange={setSelectedDoctorId}
            />

            <form onSubmit={handleRuleSubmit} className="mt-4 space-y-3">
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <label className={labelClass} htmlFor="rule-weekday">
                    Weekday
                  </label>
                  <select
                    id="rule-weekday"
                    value={ruleForm.weekday}
                    onChange={(event) =>
                      setRuleForm({
                        ...ruleForm,
                        weekday: Number(event.target.value),
                      })
                    }
                    className={inputClass}
                  >
                    {WEEKDAYS.map((day) => (
                      <option key={day.value} value={day.value}>
                        {day.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className={labelClass} htmlFor="rule-slot">
                    Slot length (minutes)
                  </label>
                  <input
                    id="rule-slot"
                    type="number"
                    min={5}
                    max={240}
                    required
                    value={ruleForm.slot_minutes}
                    onChange={(event) =>
                      setRuleForm({
                        ...ruleForm,
                        slot_minutes: Number(event.target.value),
                      })
                    }
                    className={inputClass}
                  />
                </div>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <label className={labelClass} htmlFor="rule-start">
                    Start time
                  </label>
                  <input
                    id="rule-start"
                    type="time"
                    required
                    value={ruleForm.start_time}
                    onChange={(event) =>
                      setRuleForm({
                        ...ruleForm,
                        start_time: event.target.value,
                      })
                    }
                    className={inputClass}
                  />
                </div>
                <div>
                  <label className={labelClass} htmlFor="rule-end">
                    End time
                  </label>
                  <input
                    id="rule-end"
                    type="time"
                    required
                    value={ruleForm.end_time}
                    onChange={(event) =>
                      setRuleForm({
                        ...ruleForm,
                        end_time: event.target.value,
                      })
                    }
                    className={inputClass}
                  />
                </div>
              </div>
              <button
                type="submit"
                disabled={busy || !selectedDoctorId}
                className={primaryButton}
              >
                Add availability
              </button>
            </form>
          </section>

          <section className={cardClass}>
            <div className="mb-4">
              <h2 className="text-lg font-semibold">
                {selectedDoctor
                  ? `${selectedDoctor.name}'s rules`
                  : "Availability rules"}
              </h2>
              <p className="text-sm text-slate-500">
                Overlapping active windows are rejected.
              </p>
            </div>

            <div className="space-y-2">
              {rules.map((rule) => (
                <div
                  key={rule.id}
                  className="flex items-center justify-between gap-3 rounded-xl border border-slate-200 px-4 py-3"
                >
                  <div>
                    <p className="font-medium">
                      {WEEKDAYS.find((day) => day.value === rule.weekday)
                        ?.label ?? `Day ${rule.weekday}`}
                    </p>
                    <p className="text-sm text-slate-500">
                      {formatRuleTime(rule.start_time)}–
                      {formatRuleTime(rule.end_time)} · {rule.slot_minutes} min
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => void deleteRule(rule)}
                    disabled={busy}
                    className={dangerButton}
                  >
                    Delete
                  </button>
                </div>
              ))}
              {rules.length === 0 ? (
                <p className="text-sm text-slate-500">
                  {selectedDoctorId
                    ? "No availability rules yet."
                    : "Add a doctor first."}
                </p>
              ) : null}
            </div>
          </section>
        </div>
      ) : null}

      {tab === "timeoff" ? (
        <div className="grid gap-6 lg:grid-cols-2">
          <section className={cardClass}>
            <div className="mb-4">
              <h2 className="text-lg font-semibold">Add time off</h2>
              <p className="text-sm text-slate-500">
                Times are entered in {clinic?.timezone ?? "clinic"} time.
              </p>
            </div>

            <DoctorSelect
              id="timeoff-doctor"
              value={selectedDoctorId}
              doctors={doctors}
              onChange={setSelectedDoctorId}
            />

            <form onSubmit={handleTimeOffSubmit} className="mt-4 space-y-3">
              <div>
                <label className={labelClass} htmlFor="timeoff-start">
                  Starts
                </label>
                <input
                  id="timeoff-start"
                  type="datetime-local"
                  required
                  value={timeOffForm.starts_at}
                  onChange={(event) =>
                    setTimeOffForm({
                      ...timeOffForm,
                      starts_at: event.target.value,
                    })
                  }
                  className={inputClass}
                />
              </div>
              <div>
                <label className={labelClass} htmlFor="timeoff-end">
                  Ends
                </label>
                <input
                  id="timeoff-end"
                  type="datetime-local"
                  required
                  value={timeOffForm.ends_at}
                  onChange={(event) =>
                    setTimeOffForm({
                      ...timeOffForm,
                      ends_at: event.target.value,
                    })
                  }
                  className={inputClass}
                />
              </div>
              <div>
                <label className={labelClass} htmlFor="timeoff-reason">
                  Reason
                </label>
                <input
                  id="timeoff-reason"
                  value={timeOffForm.reason}
                  onChange={(event) =>
                    setTimeOffForm({
                      ...timeOffForm,
                      reason: event.target.value,
                    })
                  }
                  className={inputClass}
                  placeholder="Break, leave, training"
                />
              </div>
              <button
                type="submit"
                disabled={busy || !selectedDoctorId}
                className={primaryButton}
              >
                Add time off
              </button>
            </form>
          </section>

          <section className={cardClass}>
            <div className="mb-4">
              <h2 className="text-lg font-semibold">
                {selectedDoctor
                  ? `${selectedDoctor.name}'s time off`
                  : "Time off"}
              </h2>
              <p className="text-sm text-slate-500">
                Overlapping entries are rejected by the database.
              </p>
            </div>

            <div className="space-y-2">
              {timeOff.map((entry) => (
                <div
                  key={entry.id}
                  className="flex items-start justify-between gap-3 rounded-xl border border-slate-200 px-4 py-3"
                >
                  <div>
                    <p className="font-medium">
                      {formatDateTime(entry.starts_at, clinic?.timezone)}
                    </p>
                    <p className="text-sm text-slate-500">
                      to {formatDateTime(entry.ends_at, clinic?.timezone)}
                    </p>
                    {entry.reason ? (
                      <p className="mt-1 text-xs text-slate-500">
                        {entry.reason}
                      </p>
                    ) : null}
                  </div>
                  <button
                    type="button"
                    onClick={() => void deleteTimeOff(entry)}
                    disabled={busy}
                    className={dangerButton}
                  >
                    Delete
                  </button>
                </div>
              ))}
              {timeOff.length === 0 ? (
                <p className="text-sm text-slate-500">
                  {selectedDoctorId
                    ? "No time off scheduled."
                    : "Add a doctor first."}
                </p>
              ) : null}
            </div>
          </section>
        </div>
      ) : null}

      {tab === "appointments" ? (
        <div className="space-y-6">
          <section className={cardClass}>
            <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <h2 className="text-lg font-semibold">Day schedule</h2>
                <p className="text-sm text-slate-500">
                  {formatDate(date)} · {clinic?.timezone ?? "clinic time"}
                </p>
              </div>
              <div className="w-full sm:w-64">
                <label className={labelClass} htmlFor="schedule-date">
                  Date
                </label>
                <input
                  id="schedule-date"
                  type="date"
                  required
                  value={date}
                  onChange={(event) => setDate(event.target.value)}
                  className={inputClass}
                />
              </div>
            </div>

            <DoctorSelect
              id="schedule-doctor"
              value={selectedDoctorId}
              doctors={doctors}
              onChange={setSelectedDoctorId}
            />
          </section>

          <div className="grid gap-6 lg:grid-cols-2">
            <section className={cardClass}>
              <div className="mb-4">
                <h2 className="text-lg font-semibold">Free slots</h2>
                <p className="text-sm text-slate-500">
                  Pick a slot, then enter the patient details.
                </p>
              </div>

              <div className="flex flex-wrap gap-2">
                {freeSlots.map((slot) => (
                  <button
                    key={`${slot.doctor_id}-${slot.starts_at}`}
                    type="button"
                    onClick={() => {
                      setSelectedSlot(slot);
                      setError("");
                      setNotice("");
                    }}
                    className={
                      selectedSlot?.starts_at === slot.starts_at
                        ? "rounded-xl bg-teal-700 px-3 py-2 text-sm font-semibold text-white"
                        : secondaryButton
                    }
                  >
                    {formatSlotTime(slot.starts_at, clinic?.timezone)}
                  </button>
                ))}
                {freeSlots.length === 0 ? (
                  <p className="text-sm text-slate-500">
                    No free slots for this doctor and date.
                  </p>
                ) : null}
              </div>

              {selectedSlot ? (
                <form
                  onSubmit={handleBook}
                  className="mt-5 border-t border-slate-200 pt-5"
                >
                  <p className="mb-3 text-sm font-medium text-slate-700">
                    Book {formatSlotTime(selectedSlot.starts_at, clinic?.timezone)}
                    –{formatSlotTime(selectedSlot.ends_at, clinic?.timezone)}
                  </p>
                  <div className="space-y-3">
                    <div>
                      <label className={labelClass} htmlFor="patient-name">
                        Patient name
                      </label>
                      <input
                        id="patient-name"
                        required
                        value={bookingForm.patient_name}
                        onChange={(event) =>
                          setBookingForm({
                            ...bookingForm,
                            patient_name: event.target.value,
                          })
                        }
                        className={inputClass}
                        placeholder="Ravi Kumar"
                      />
                    </div>
                    <div>
                      <label className={labelClass} htmlFor="patient-phone">
                        Phone
                      </label>
                      <input
                        id="patient-phone"
                        required
                        value={bookingForm.patient_phone}
                        onChange={(event) =>
                          setBookingForm({
                            ...bookingForm,
                            patient_phone: event.target.value,
                          })
                        }
                        className={inputClass}
                        placeholder="+91 98765 43210"
                      />
                    </div>
                    <div>
                      <label className={labelClass} htmlFor="patient-notes">
                        Notes
                      </label>
                      <input
                        id="patient-notes"
                        value={bookingForm.notes}
                        onChange={(event) =>
                          setBookingForm({
                            ...bookingForm,
                            notes: event.target.value,
                          })
                        }
                        className={inputClass}
                        placeholder="Optional"
                      />
                    </div>
                  </div>
                  <div className="mt-4 flex gap-2">
                    <button
                      type="submit"
                      disabled={busy}
                      className={primaryButton}
                    >
                      Book appointment
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedSlot(null);
                        setBookingForm(EMPTY_BOOKING);
                      }}
                      className={secondaryButton}
                    >
                      Clear
                    </button>
                  </div>
                </form>
              ) : null}
            </section>

            <section className={cardClass}>
              <div className="mb-4">
                <h2 className="text-lg font-semibold">Appointments</h2>
                <p className="text-sm text-slate-500">
                  All appointments for the selected day.
                </p>
              </div>

              <div className="space-y-2">
                {appointments.map((appointment) => (
                  <div
                    key={appointment.id}
                    className="rounded-xl border border-slate-200 px-4 py-3"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-medium">
                          {formatSlotTime(
                            appointment.starts_at,
                            clinic?.timezone,
                          )}
                          –{formatSlotTime(appointment.ends_at, clinic?.timezone)}
                        </p>
                        <p className="text-sm text-slate-700">
                          {appointment.patient_name} · {appointment.patient_phone}
                        </p>
                        <p className="mt-1 text-xs text-slate-500">
                          {appointment.doctor_name} · {appointment.source} · ₹
                          {appointment.fee}
                        </p>
                      </div>
                      <div className="flex flex-col items-end gap-2">
                        <StatusBadge status={appointment.status} />
                        {appointment.status === "booked" ? (
                          <button
                            type="button"
                            onClick={() => void cancelAppointment(appointment)}
                            disabled={busy}
                            className={dangerButton}
                          >
                            Cancel
                          </button>
                        ) : null}
                      </div>
                    </div>
                  </div>
                ))}
                {appointments.length === 0 ? (
                  <p className="text-sm text-slate-500">
                    No appointments on this date.
                  </p>
                ) : null}
              </div>
            </section>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white px-5 py-4 shadow-sm">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
        {label}
      </p>
      <p className="mt-2 text-2xl font-semibold tracking-tight">{value}</p>
    </div>
  );
}

function StatusBadge({ status }: { status: Appointment["status"] }) {
  const classes: Record<Appointment["status"], string> = {
    booked: "bg-emerald-50 text-emerald-700",
    cancelled: "bg-rose-50 text-rose-700",
    completed: "bg-sky-50 text-sky-700",
    no_show: "bg-amber-50 text-amber-700",
  };
  return (
    <span
      className={`rounded-full px-2.5 py-1 text-xs font-medium ${classes[status]}`}
    >
      {status.replace("_", " ")}
    </span>
  );
}

function DoctorSelect({
  id,
  value,
  doctors,
  onChange,
}: {
  id: string;
  value: string;
  doctors: Doctor[];
  onChange: (doctorId: string) => void;
}) {
  return (
    <div>
      <label className={labelClass} htmlFor={id}>
        Doctor
      </label>
      <select
        id={id}
        required
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={inputClass}
        disabled={doctors.length === 0}
      >
        {doctors.length === 0 ? (
          <option value="">Add a doctor first</option>
        ) : null}
        {doctors.map((doctor) => (
          <option key={doctor.id} value={doctor.id}>
            {doctor.name}
            {doctor.specialization ? ` · ${doctor.specialization}` : ""}
          </option>
        ))}
      </select>
    </div>
  );
}
