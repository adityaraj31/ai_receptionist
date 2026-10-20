"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AvailabilityRuleForm } from "@/components/availability-rule-form";
import { useAuth } from "@/components/auth-provider";
import { DoctorForm } from "@/components/doctor-form";
import { ChevronRightIcon, StethoscopeIcon } from "@/components/icons";
import {
  Button,
  ErrorPanel,
  PageHeader,
  Spinner,
  inputClass,
  labelClass,
} from "@/components/ui";
import { api } from "@/lib/api-client";
import { getErrorMessage } from "@/lib/errors";
import { clearSetupSkip, skipSetupForSession } from "@/lib/session";
import { useApi } from "@/lib/use-api";

const commonTimeZones = [
  "Asia/Kolkata",
  "Asia/Dubai",
  "Asia/Karachi",
  "Asia/Dhaka",
  "Asia/Singapore",
  "Asia/Tokyo",
  "Europe/London",
  "Europe/Berlin",
  "America/New_York",
  "America/Los_Angeles",
  "Australia/Sydney",
  "UTC",
];

const steps = [
  { number: 1, label: "Clinic details" },
  { number: 2, label: "First doctor" },
  { number: 3, label: "Working hours" },
];

export default function SetupPage() {
  const { clinic, setClinic } = useAuth();
  const router = useRouter();

  const [step, setStep] = useState(1);
  const [doctorId, setDoctorId] = useState("");
  const [name, setName] = useState("");
  const [timezone, setTimezone] = useState("Asia/Kolkata");
  const [address, setAddress] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const {
    data: doctors,
    loading: doctorsLoading,
    error: doctorsError,
    reload: reloadDoctors,
  } = useApi(() => api.listDoctors(), []);

  useEffect(() => {
    if (!clinic) return;
    setName(clinic.name);
    setTimezone(clinic.timezone);
    setAddress(clinic.address ?? "");
    setPhone(clinic.phone ?? "");
    setEmail(clinic.email ?? "");
  }, [clinic]);

  useEffect(() => {
    if (!doctorId && doctors && doctors.length > 0) {
      setDoctorId(doctors[0].id);
    }
  }, [doctorId, doctors]);

  const timeZones = clinic?.timezone && !commonTimeZones.includes(clinic.timezone)
    ? [clinic.timezone, ...commonTimeZones]
    : commonTimeZones;

  function skip() {
    skipSetupForSession();
    router.push("/appointments");
  }

  async function saveClinic(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (!name.trim()) {
      setError("Clinic name is required.");
      return;
    }

    setBusy(true);
    try {
      const updated = await api.updateClinic({
        name: name.trim(),
        timezone,
        address: address.trim() || null,
        phone: phone.trim() || null,
        email: email.trim() || null,
      });
      setClinic(updated);
      setStep(2);
    } catch (caught) {
      setError(getErrorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  function finish() {
    clearSetupSkip();
    router.push("/appointments");
  }

  if (!clinic) {
    return (
      <div className="flex min-h-64 items-center justify-center">
        <Spinner className="h-6 w-6 text-teal-700" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader
        eyebrow="First run"
        title="Set up your clinic"
        description="Add the essentials once. You can refine doctors and hours any time."
        actions={
          <Button variant="ghost" onClick={skip}>
            Skip for now
          </Button>
        }
      />

      <div className="mb-6 grid grid-cols-3 gap-2">
        {steps.map((item) => {
          const active = step === item.number;
          const complete = step > item.number;
          return (
            <div
              key={item.number}
              className={`rounded-xl border px-3 py-3 text-center ${
                active
                  ? "border-teal-600 bg-teal-50"
                  : complete
                    ? "border-teal-200 bg-white"
                    : "border-slate-200 bg-white"
              }`}
            >
              <span
                className={`mx-auto flex h-7 w-7 items-center justify-center rounded-full text-xs font-semibold ${
                  active || complete
                    ? "bg-teal-700 text-white"
                    : "bg-slate-100 text-slate-500"
                }`}
              >
                {complete ? "✓" : item.number}
              </span>
              <span
                className={`mt-2 block text-xs font-semibold ${
                  active ? "text-teal-900" : "text-slate-600"
                }`}
              >
                {item.label}
              </span>
            </div>
          );
        })}
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7">
        {step === 1 ? (
          <form className="space-y-5" onSubmit={saveClinic}>
            {error ? <ErrorPanel message={error} /> : null}
            <div>
              <h2 className="text-lg font-semibold text-slate-900">
                Tell us about the clinic
              </h2>
              <p className="mt-1 text-sm text-slate-500">
                This appears in the dashboard and helps the AI receptionist
                answer questions about your clinic.
              </p>
            </div>

            <div>
              <label className={labelClass} htmlFor="setup-clinic-name">
                Clinic name
              </label>
              <input
                id="setup-clinic-name"
                className={inputClass}
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Demo Family Clinic"
                required
              />
            </div>

            <div>
              <label className={labelClass} htmlFor="setup-timezone">
                Timezone
              </label>
              <select
                id="setup-timezone"
                className={inputClass}
                value={timezone}
                onChange={(event) => setTimezone(event.target.value)}
              >
                {timeZones.map((zone) => (
                  <option key={zone} value={zone}>
                    {zone}
                  </option>
                ))}
              </select>
              <p className="mt-1 text-xs text-slate-500">
                Appointments and working hours use this timezone.
              </p>
            </div>

            <div>
              <label className={labelClass} htmlFor="setup-address">
                Address
              </label>
              <input
                id="setup-address"
                className={inputClass}
                value={address}
                onChange={(event) => setAddress(event.target.value)}
                placeholder="Street, area, city"
              />
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className={labelClass} htmlFor="setup-phone">
                  Phone
                </label>
                <input
                  id="setup-phone"
                  className={inputClass}
                  type="tel"
                  value={phone}
                  onChange={(event) => setPhone(event.target.value)}
                  placeholder="+91 90000 00000"
                />
              </div>
              <div>
                <label className={labelClass} htmlFor="setup-email">
                  Email
                </label>
                <input
                  id="setup-email"
                  className={inputClass}
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="hello@clinic.com"
                />
              </div>
            </div>

            <div className="flex justify-end">
              <Button type="submit" loading={busy}>
                Save and continue
                <ChevronRightIcon className="h-4 w-4" />
              </Button>
            </div>
          </form>
        ) : null}

        {step === 2 ? (
          <div className="space-y-6">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">
                Add your first doctor
              </h2>
              <p className="mt-1 text-sm text-slate-500">
                Patients will choose this doctor when booking by phone.
              </p>
            </div>

            {doctorsLoading ? (
              <div className="flex h-24 items-center justify-center">
                <Spinner className="h-5 w-5 text-teal-700" />
              </div>
            ) : null}

            {!doctorsLoading && doctorsError ? (
              <ErrorPanel message={doctorsError} onRetry={reloadDoctors} />
            ) : null}

            {!doctorsLoading && !doctorsError && doctors && doctors.length > 0 ? (
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Existing doctors
                </p>
                <div className="mt-3 space-y-2">
                  {doctors.map((doctor) => (
                    <button
                      key={doctor.id}
                      className={`flex w-full items-center justify-between gap-3 rounded-xl border bg-white px-4 py-3 text-left transition ${
                        doctorId === doctor.id
                          ? "border-teal-600 ring-2 ring-teal-600/10"
                          : "border-slate-200 hover:border-teal-400"
                      }`}
                      onClick={() => setDoctorId(doctor.id)}
                      type="button"
                    >
                      <span>
                        <span className="block text-sm font-semibold text-slate-900">
                          {doctor.name}
                        </span>
                        <span className="block text-xs text-slate-500">
                          {doctor.specialization}
                        </span>
                      </span>
                      <span className="text-xs font-semibold text-teal-700">
                        {doctorId === doctor.id ? "Selected" : "Select"}
                      </span>
                    </button>
                  ))}
                </div>
                <div className="mt-4 flex justify-end">
                  <Button
                    onClick={() => setStep(3)}
                    disabled={!doctorId}
                  >
                    Continue with doctor
                    <ChevronRightIcon className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ) : null}

            {!doctorsLoading ? (
              <>
                <div className="flex items-center gap-3 text-xs font-semibold uppercase tracking-wide text-slate-400">
                  <span className="h-px flex-1 bg-slate-200" />
                  Or add a doctor
                  <span className="h-px flex-1 bg-slate-200" />
                </div>
                <DoctorForm
                  submitLabel="Add doctor and continue"
                  cancelLabel="Back"
                  onCancel={() => setStep(1)}
                  onSaved={(doctor) => {
                    setDoctorId(doctor.id);
                    void reloadDoctors();
                    setStep(3);
                  }}
                />
              </>
            ) : null}
          </div>
        ) : null}

        {step === 3 ? (
          <div className="space-y-6">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">
                Set weekly working hours
              </h2>
              <p className="mt-1 text-sm text-slate-500">
                Add one regular window now. You can add more days and time off
                from Availability.
              </p>
            </div>

            {!doctorId ? (
              <ErrorPanel
                message="Choose a doctor before setting hours."
                onRetry={() => setStep(2)}
              />
            ) : (
              <>
                <div className="flex items-center gap-3 rounded-xl bg-slate-50 px-4 py-3">
                  <span className="flex h-9 w-9 items-center justify-center rounded-full bg-white text-teal-700 shadow-sm">
                    <StethoscopeIcon className="h-5 w-5" />
                  </span>
                  <div>
                    <p className="text-xs uppercase tracking-wide text-slate-500">
                      Doctor
                    </p>
                    <p className="text-sm font-semibold text-slate-900">
                      {doctors?.find((doctor) => doctor.id === doctorId)?.name ??
                        "Selected doctor"}
                    </p>
                  </div>
                </div>
                <AvailabilityRuleForm
                  doctorId={doctorId}
                  submitLabel="Finish setup"
                  cancelLabel="Back"
                  onCancel={() => setStep(2)}
                  onSaved={() => {
                    clearSetupSkip();
                    setStep(4);
                  }}
                />
              </>
            )}
          </div>
        ) : null}

        {step === 4 ? (
          <div className="py-8 text-center">
            <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-teal-50 text-2xl font-semibold text-teal-700">
              ✓
            </span>
            <h2 className="mt-4 text-xl font-semibold text-slate-900">
              Your clinic is ready
            </h2>
            <p className="mx-auto mt-2 max-w-md text-sm text-slate-500">
              The first doctor and working hours are set. You can add more
              doctors, adjust availability, or book a patient now.
            </p>
            <div className="mt-6 flex flex-col justify-center gap-2 sm:flex-row">
              <Link
                href="/availability"
                className="inline-flex items-center justify-center rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
              >
                Review availability
              </Link>
              <Button onClick={finish}>Go to appointments</Button>
            </div>
          </div>
        ) : null}
      </div>

      <p className="mt-4 text-center text-xs text-slate-400">
        You can change every detail later from Doctors, Availability, and
        Clinic setup.
      </p>
    </div>
  );
}
