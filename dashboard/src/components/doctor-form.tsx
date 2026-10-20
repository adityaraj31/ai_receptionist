"use client";

import { useState } from "react";

import { Button, ErrorPanel, inputClass, labelClass } from "@/components/ui";
import { api, type DoctorPayload } from "@/lib/api-client";
import type { Doctor } from "@/lib/api-types";
import { getErrorMessage } from "@/lib/errors";

export function DoctorForm({
  doctor,
  onSaved,
  onCancel,
  submitLabel,
  cancelLabel = "Cancel",
}: {
  doctor?: Doctor | null;
  onSaved: (doctor: Doctor) => void;
  onCancel: () => void;
  submitLabel?: string;
  cancelLabel?: string;
}) {
  const [name, setName] = useState(doctor?.name ?? "");
  const [specialization, setSpecialization] = useState(
    doctor?.specialization ?? "",
  );
  const [languages, setLanguages] = useState(
    doctor?.languages.join(", ") ?? "English, Hindi",
  );
  const [fee, setFee] = useState(doctor?.fee ?? "500");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    const trimmedName = name.trim();
    const trimmedSpecialization = specialization.trim();
    const feeNumber = Number(fee);

    if (!trimmedName) {
      setError("Doctor name is required.");
      return;
    }

    if (!trimmedSpecialization) {
      setError("Specialization is required.");
      return;
    }

    if (!Number.isFinite(feeNumber) || feeNumber < 0) {
      setError("Fee must be a valid amount of zero or more.");
      return;
    }

    const payload: DoctorPayload = {
      name: trimmedName,
      specialization: trimmedSpecialization,
      languages: languages
        .split(",")
        .map((language) => language.trim())
        .filter(Boolean),
      fee: feeNumber.toFixed(2),
      is_active: doctor?.is_active ?? true,
    };

    setBusy(true);
    try {
      const saved = doctor
        ? await api.updateDoctor(doctor.id, payload)
        : await api.createDoctor(payload);
      onSaved(saved);
    } catch (caught) {
      setError(getErrorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="space-y-4" onSubmit={handleSubmit}>
      {error ? <ErrorPanel message={error} /> : null}

      <div>
        <label className={labelClass} htmlFor="doctor-name">
          Full name
        </label>
        <input
          id="doctor-name"
          className={inputClass}
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="Dr. Asha Rao"
          autoFocus
          required
        />
      </div>

      <div>
        <label className={labelClass} htmlFor="doctor-specialization">
          Specialization
        </label>
        <input
          id="doctor-specialization"
          className={inputClass}
          value={specialization}
          onChange={(event) => setSpecialization(event.target.value)}
          placeholder="General Medicine"
          required
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className={labelClass} htmlFor="doctor-languages">
            Languages
          </label>
          <input
            id="doctor-languages"
            className={inputClass}
            value={languages}
            onChange={(event) => setLanguages(event.target.value)}
            placeholder="English, Hindi"
          />
          <p className="mt-1 text-xs text-slate-500">
            Separate languages with commas.
          </p>
        </div>

        <div>
          <label className={labelClass} htmlFor="doctor-fee">
            Consultation fee (INR)
          </label>
          <input
            id="doctor-fee"
            className={inputClass}
            type="number"
            min="0"
            step="0.01"
            value={fee}
            onChange={(event) => setFee(event.target.value)}
            required
          />
        </div>
      </div>

      <div className="flex flex-col-reverse gap-2 pt-2 sm:flex-row sm:justify-end">
        <Button type="button" variant="secondary" onClick={onCancel} disabled={busy}>
          {cancelLabel}
        </Button>
        <Button type="submit" loading={busy}>
          {submitLabel ?? (doctor ? "Save changes" : "Add doctor")}
        </Button>
      </div>
    </form>
  );
}
