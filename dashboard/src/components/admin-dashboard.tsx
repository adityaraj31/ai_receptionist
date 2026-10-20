"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";

import {
  api,
  type Clinic,
  type Doctor,
  type DoctorInput,
  type Slot,
  type SlotInput,
} from "@/lib/api";

const ADMIN_KEY_STORAGE = "ai-receptionist-admin-key";

const WEEKDAYS = [
  { value: 1, label: "Mon" },
  { value: 2, label: "Tue" },
  { value: 3, label: "Wed" },
  { value: 4, label: "Thu" },
  { value: 5, label: "Fri" },
  { value: 6, label: "Sat" },
  { value: 7, label: "Sun" },
];

const EMPTY_DOCTOR: DoctorInput = {
  name: "",
  specialty: "",
  days: "",
  hours: "",
};

type SlotForm = {
  doctor_id: string;
  slot_date: string;
  start_time: string;
  end_time: string;
  capacity: number;
};

type GenerateForm = {
  doctor_id: string;
  start_date: string;
  end_date: string;
  start_time: string;
  end_time: string;
  duration_minutes: number;
  capacity: number;
  weekdays: number[];
};

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en-IN", {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(`${value}T00:00:00`));
}

function formatTime(value: string): string {
  return value.slice(0, 5);
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
const cardClass = "rounded-2xl border border-slate-200 bg-white p-5 shadow-sm";

export function AdminDashboard() {
  const [adminKey, setAdminKey] = useState("");
  const [keyDraft, setKeyDraft] = useState("");
  const [clinic, setClinic] = useState<Clinic | null>(null);
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [slots, setSlots] = useState<Slot[]>([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [doctorForm, setDoctorForm] = useState<DoctorInput>(EMPTY_DOCTOR);
  const [slotForm, setSlotForm] = useState<SlotForm>({
    doctor_id: "",
    slot_date: today(),
    start_time: "10:00",
    end_time: "10:30",
    capacity: 1,
  });
  const [generateForm, setGenerateForm] = useState<GenerateForm>({
    doctor_id: "",
    start_date: today(),
    end_date: today(),
    start_time: "10:00",
    end_time: "12:00",
    duration_minutes: 30,
    capacity: 1,
    weekdays: [1, 2, 3, 4, 5],
  });

  const refresh = useCallback(async (key: string) => {
    setLoading(true);
    setError("");
    try {
      const [clinicData, doctorsData, slotsData] = await Promise.all([
        api.getClinic(key),
        api.listDoctors(key),
        api.listSlots(key),
      ]);
      setClinic(clinicData);
      setDoctors(doctorsData);
      setSlots(slotsData);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const saved = window.sessionStorage.getItem(ADMIN_KEY_STORAGE);
    if (saved) {
      setAdminKey(saved);
      setKeyDraft(saved);
    }
  }, []);

  useEffect(() => {
    if (adminKey) {
      void refresh(adminKey);
    }
  }, [adminKey, refresh]);

  useEffect(() => {
    if (doctors.length === 0) return;
    const firstDoctor = doctors[0].id;
    const isKnown = (id: string) => doctors.some((doctor) => doctor.id === id);

    setSlotForm((current) =>
      current.doctor_id && isKnown(current.doctor_id)
        ? current
        : { ...current, doctor_id: firstDoctor },
    );
    setGenerateForm((current) =>
      current.doctor_id && isKnown(current.doctor_id)
        ? current
        : { ...current, doctor_id: firstDoctor },
    );
  }, [doctors]);

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  function saveKey(event: FormEvent) {
    event.preventDefault();
    const key = keyDraft.trim();
    if (!key) return;
    window.sessionStorage.setItem(ADMIN_KEY_STORAGE, key);
    setAdminKey(key);
    setNotice("");
  }

  function lockDashboard() {
    window.sessionStorage.removeItem(ADMIN_KEY_STORAGE);
    setAdminKey("");
    setKeyDraft("");
    setClinic(null);
    setDoctors([]);
    setSlots([]);
    setError("");
    setNotice("");
  }

  async function handleCreateDoctor(event: FormEvent) {
    event.preventDefault();
    if (!adminKey) return;
    await run(async () => {
      await api.createDoctor(adminKey, {
        ...doctorForm,
        name: doctorForm.name.trim(),
      });
      setDoctorForm(EMPTY_DOCTOR);
      await refresh(adminKey);
      setNotice("Doctor added.");
    });
  }

  async function handleDeactivateDoctor(doctor: Doctor) {
    if (!adminKey) return;
    if (!window.confirm(`Deactivate ${doctor.name} and their future slots?`)) {
      return;
    }
    await run(async () => {
      await api.deactivateDoctor(adminKey, doctor.id);
      await refresh(adminKey);
      setNotice(`${doctor.name} deactivated.`);
    });
  }

  async function handleCreateSlot(event: FormEvent) {
    event.preventDefault();
    if (!adminKey) return;
    const payload: SlotInput = { ...slotForm, capacity: Number(slotForm.capacity) };
    await run(async () => {
      await api.createSlot(adminKey, payload);
      await refresh(adminKey);
      setNotice("Slot added.");
    });
  }

  async function handleGenerateSlots(event: FormEvent) {
    event.preventDefault();
    if (!adminKey) return;
    if (generateForm.weekdays.length === 0) {
      setError("Pick at least one weekday.");
      return;
    }
    await run(async () => {
      const result = await api.generateSlots(adminKey, generateForm);
      await refresh(adminKey);
      setNotice(
        `Created ${result.created} slots. Skipped ${result.skipped} existing slots.`,
      );
    });
  }

  async function handleDeactivateSlot(slot: Slot) {
    if (!adminKey) return;
    if (!window.confirm("Deactivate this slot?")) return;
    await run(async () => {
      await api.deactivateSlot(adminKey, slot.id);
      await refresh(adminKey);
      setNotice("Slot deactivated.");
    });
  }

  function toggleWeekday(value: number) {
    setGenerateForm((current) => ({
      ...current,
      weekdays: current.weekdays.includes(value)
        ? current.weekdays.filter((day) => day !== value)
        : [...current.weekdays, value].sort((a, b) => a - b),
    }));
  }

  if (!adminKey) {
    return (
      <div className="mx-auto max-w-md">
        <div className="mb-8 text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.25em] text-teal-700">
            AI Receptionist
          </p>
          <h1 className="mt-3 text-3xl font-semibold tracking-tight">
            Clinic admin
          </h1>
          <p className="mt-2 text-sm text-slate-500">
            Enter the admin API key to manage doctors and appointment slots.
          </p>
        </div>

        <form onSubmit={saveKey} className={cardClass}>
          <label className={labelClass} htmlFor="admin-key">
            Admin API key
          </label>
          <input
            id="admin-key"
            type="password"
            autoComplete="off"
            value={keyDraft}
            onChange={(event) => setKeyDraft(event.target.value)}
            className={inputClass}
            placeholder="dev-admin-key"
          />
          <button type="submit" className={`${primaryButton} mt-4 w-full`}>
            Open dashboard
          </button>
          <p className="mt-3 text-xs text-slate-500">
            The key is stored in this browser tab&apos;s session storage and sent
            only to the FastAPI server.
          </p>
        </form>
      </div>
    );
  }

  const totalCapacity = slots.reduce((sum, slot) => sum + slot.capacity, 0);
  const totalBooked = slots.reduce((sum, slot) => sum + slot.booked_count, 0);

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
            {clinic?.address ?? "Manage doctors, availability, and slots."}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="inline-flex items-center gap-2 rounded-full border border-teal-200 bg-teal-50 px-3 py-1 text-xs font-medium text-teal-800">
            <span className="h-2 w-2 rounded-full bg-teal-600" />
            {loading ? "Syncing" : "API connected"}
          </span>
          <button type="button" onClick={lockDashboard} className={secondaryButton}>
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
        <StatCard label="Active slots" value={slots.length} />
        <StatCard label="Total capacity" value={totalCapacity} />
        <StatCard label="Booked" value={totalBooked} />
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className={cardClass}>
          <div className="mb-4">
            <h2 className="text-lg font-semibold">Doctors</h2>
            <p className="text-sm text-slate-500">
              Add a doctor or update their weekly availability.
            </p>
          </div>

          <form onSubmit={handleCreateDoctor} className="space-y-3">
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
                <label className={labelClass} htmlFor="doctor-specialty">
                  Specialty
                </label>
                <input
                  id="doctor-specialty"
                  value={doctorForm.specialty}
                  onChange={(event) =>
                    setDoctorForm({
                      ...doctorForm,
                      specialty: event.target.value,
                    })
                  }
                  className={inputClass}
                  placeholder="General Physician"
                />
              </div>
              <div>
                <label className={labelClass} htmlFor="doctor-days">
                  Days
                </label>
                <input
                  id="doctor-days"
                  value={doctorForm.days}
                  onChange={(event) =>
                    setDoctorForm({ ...doctorForm, days: event.target.value })
                  }
                  className={inputClass}
                  placeholder="Mon, Wed, Fri"
                />
              </div>
            </div>
            <div>
              <label className={labelClass} htmlFor="doctor-hours">
                Hours
              </label>
              <input
                id="doctor-hours"
                value={doctorForm.hours}
                onChange={(event) =>
                  setDoctorForm({ ...doctorForm, hours: event.target.value })
                }
                className={inputClass}
                placeholder="10:00-13:00"
              />
            </div>
            <button type="submit" disabled={busy} className={primaryButton}>
              Add doctor
            </button>
          </form>

          <div className="mt-6 space-y-3">
            {doctors.map((doctor) => (
              <div
                key={doctor.id}
                className="flex items-start justify-between gap-3 rounded-xl border border-slate-200 px-4 py-3"
              >
                <div>
                  <p className="font-medium">{doctor.name}</p>
                  <p className="text-sm text-slate-500">
                    {doctor.specialty || "No specialty"}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    {doctor.days || "Days not set"} · {doctor.hours || "Hours not set"}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => void handleDeactivateDoctor(doctor)}
                  disabled={busy}
                  className="text-xs font-medium text-rose-700 hover:text-rose-800 disabled:opacity-50"
                >
                  Deactivate
                </button>
              </div>
            ))}
            {doctors.length === 0 ? (
              <p className="text-sm text-slate-500">
                No active doctors yet. Add the first one above.
              </p>
            ) : null}
          </div>
        </section>

        <div className="space-y-6">
          <section className={cardClass}>
            <div className="mb-4">
              <h2 className="text-lg font-semibold">Add one slot</h2>
              <p className="text-sm text-slate-500">
                Create a single appointment slot for a doctor.
              </p>
            </div>

            <form onSubmit={handleCreateSlot} className="space-y-3">
              <DoctorSelect
                id="slot-doctor"
                value={slotForm.doctor_id}
                doctors={doctors}
                onChange={(doctorId) =>
                  setSlotForm({ ...slotForm, doctor_id: doctorId })
                }
              />
              <div className="grid gap-3 sm:grid-cols-3">
                <div>
                  <label className={labelClass} htmlFor="slot-date">
                    Date
                  </label>
                  <input
                    id="slot-date"
                    type="date"
                    required
                    value={slotForm.slot_date}
                    onChange={(event) =>
                      setSlotForm({ ...slotForm, slot_date: event.target.value })
                    }
                    className={inputClass}
                  />
                </div>
                <div>
                  <label className={labelClass} htmlFor="slot-start">
                    Start
                  </label>
                  <input
                    id="slot-start"
                    type="time"
                    required
                    value={slotForm.start_time}
                    onChange={(event) =>
                      setSlotForm({ ...slotForm, start_time: event.target.value })
                    }
                    className={inputClass}
                  />
                </div>
                <div>
                  <label className={labelClass} htmlFor="slot-end">
                    End
                  </label>
                  <input
                    id="slot-end"
                    type="time"
                    required
                    value={slotForm.end_time}
                    onChange={(event) =>
                      setSlotForm({ ...slotForm, end_time: event.target.value })
                    }
                    className={inputClass}
                  />
                </div>
              </div>
              <div>
                <label className={labelClass} htmlFor="slot-capacity">
                  Capacity
                </label>
                <input
                  id="slot-capacity"
                  type="number"
                  min={1}
                  max={100}
                  required
                  value={slotForm.capacity}
                  onChange={(event) =>
                    setSlotForm({
                      ...slotForm,
                      capacity: Number(event.target.value),
                    })
                  }
                  className={inputClass}
                />
              </div>
              <button
                type="submit"
                disabled={busy || doctors.length === 0}
                className={primaryButton}
              >
                Add slot
              </button>
            </form>
          </section>

          <section className={cardClass}>
            <div className="mb-4">
              <h2 className="text-lg font-semibold">Generate slots</h2>
              <p className="text-sm text-slate-500">
                Create a date range of fixed-length slots and skip duplicates.
              </p>
            </div>

            <form onSubmit={handleGenerateSlots} className="space-y-3">
              <DoctorSelect
                id="generate-doctor"
                value={generateForm.doctor_id}
                doctors={doctors}
                onChange={(doctorId) =>
                  setGenerateForm({ ...generateForm, doctor_id: doctorId })
                }
              />
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <label className={labelClass} htmlFor="generate-start-date">
                    From date
                  </label>
                  <input
                    id="generate-start-date"
                    type="date"
                    required
                    value={generateForm.start_date}
                    onChange={(event) =>
                      setGenerateForm({
                        ...generateForm,
                        start_date: event.target.value,
                      })
                    }
                    className={inputClass}
                  />
                </div>
                <div>
                  <label className={labelClass} htmlFor="generate-end-date">
                    To date
                  </label>
                  <input
                    id="generate-end-date"
                    type="date"
                    required
                    value={generateForm.end_date}
                    onChange={(event) =>
                      setGenerateForm({
                        ...generateForm,
                        end_date: event.target.value,
                      })
                    }
                    className={inputClass}
                  />
                </div>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <label className={labelClass} htmlFor="generate-start-time">
                    Start time
                  </label>
                  <input
                    id="generate-start-time"
                    type="time"
                    required
                    value={generateForm.start_time}
                    onChange={(event) =>
                      setGenerateForm({
                        ...generateForm,
                        start_time: event.target.value,
                      })
                    }
                    className={inputClass}
                  />
                </div>
                <div>
                  <label className={labelClass} htmlFor="generate-end-time">
                    End time
                  </label>
                  <input
                    id="generate-end-time"
                    type="time"
                    required
                    value={generateForm.end_time}
                    onChange={(event) =>
                      setGenerateForm({
                        ...generateForm,
                        end_time: event.target.value,
                      })
                    }
                    className={inputClass}
                  />
                </div>
              </div>
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <label className={labelClass} htmlFor="generate-duration">
                    Slot length (minutes)
                  </label>
                  <input
                    id="generate-duration"
                    type="number"
                    min={5}
                    max={240}
                    required
                    value={generateForm.duration_minutes}
                    onChange={(event) =>
                      setGenerateForm({
                        ...generateForm,
                        duration_minutes: Number(event.target.value),
                      })
                    }
                    className={inputClass}
                  />
                </div>
                <div>
                  <label className={labelClass} htmlFor="generate-capacity">
                    Capacity per slot
                  </label>
                  <input
                    id="generate-capacity"
                    type="number"
                    min={1}
                    max={100}
                    required
                    value={generateForm.capacity}
                    onChange={(event) =>
                      setGenerateForm({
                        ...generateForm,
                        capacity: Number(event.target.value),
                      })
                    }
                    className={inputClass}
                  />
                </div>
              </div>
              <div>
                <span className={labelClass}>Weekdays</span>
                <div className="mt-2 flex flex-wrap gap-2">
                  {WEEKDAYS.map((day) => (
                    <label
                      key={day.value}
                      className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-slate-300 px-2.5 py-1.5 text-sm text-slate-700"
                    >
                      <input
                        type="checkbox"
                        checked={generateForm.weekdays.includes(day.value)}
                        onChange={() => toggleWeekday(day.value)}
                        className="accent-teal-700"
                      />
                      {day.label}
                    </label>
                  ))}
                </div>
              </div>
              <button
                type="submit"
                disabled={busy || doctors.length === 0}
                className={primaryButton}
              >
                Generate slots
              </button>
            </form>
          </section>
        </div>
      </div>

      <section className={`${cardClass} mt-6`}>
        <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-lg font-semibold">Active slots</h2>
            <p className="text-sm text-slate-500">
              All currently bookable slots across doctors.
            </p>
          </div>
          <button
            type="button"
            onClick={() => void refresh(adminKey)}
            disabled={loading}
            className={secondaryButton}
          >
            Refresh
          </button>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
                <th className="px-3 py-3 font-medium">Doctor</th>
                <th className="px-3 py-3 font-medium">Date</th>
                <th className="px-3 py-3 font-medium">Time</th>
                <th className="px-3 py-3 font-medium">Capacity</th>
                <th className="px-3 py-3 font-medium">Status</th>
                <th className="px-3 py-3 text-right font-medium">Action</th>
              </tr>
            </thead>
            <tbody>
              {slots.map((slot) => (
                <tr key={slot.id} className="border-b border-slate-100">
                  <td className="px-3 py-3">
                    <p className="font-medium">{slot.doctor_name}</p>
                    <p className="text-xs text-slate-500">
                      {slot.doctor_specialty || "No specialty"}
                    </p>
                  </td>
                  <td className="px-3 py-3 text-slate-700">
                    {formatDate(slot.slot_date)}
                  </td>
                  <td className="px-3 py-3 text-slate-700">
                    {formatTime(slot.start_time)}–{formatTime(slot.end_time)}
                  </td>
                  <td className="px-3 py-3 text-slate-700">
                    {slot.booked_count}/{slot.capacity}
                  </td>
                  <td className="px-3 py-3">
                    <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700">
                      Active
                    </span>
                  </td>
                  <td className="px-3 py-3 text-right">
                    <button
                      type="button"
                      onClick={() => void handleDeactivateSlot(slot)}
                      disabled={busy}
                      className="text-xs font-medium text-rose-700 hover:text-rose-800 disabled:opacity-50"
                    >
                      Deactivate
                    </button>
                  </td>
                </tr>
              ))}
              {slots.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-3 py-8 text-center text-slate-500">
                    No active slots. Add one or generate a range above.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
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
            {doctor.specialty ? ` · ${doctor.specialty}` : ""}
          </option>
        ))}
      </select>
    </div>
  );
}
