"use client";

import { useEffect, useState } from "react";

import {
  Button,
  ErrorPanel,
  LoadingPanel,
  PageHeader,
  inputClass,
  labelClass,
} from "@/components/ui";
import { api } from "@/lib/api-client";
import type { MessagingSettings, MessagingSettingsInput } from "@/lib/api-types";
import { getErrorMessage } from "@/lib/errors";
import { useApi } from "@/lib/use-api";

type TemplateKey =
  | "confirmation_template_en"
  | "confirmation_template_hi"
  | "reminder_24h_template_en"
  | "reminder_24h_template_hi"
  | "reminder_2h_template_en"
  | "reminder_2h_template_hi";

const templateFields: { key: TemplateKey; label: string }[] = [
  { key: "confirmation_template_en", label: "Confirmation · English" },
  { key: "confirmation_template_hi", label: "Confirmation · हिंदी" },
  { key: "reminder_24h_template_en", label: "24-hour reminder · English" },
  { key: "reminder_24h_template_hi", label: "24-hour reminder · हिंदी" },
  { key: "reminder_2h_template_en", label: "2-hour reminder · English" },
  { key: "reminder_2h_template_hi", label: "2-hour reminder · हिंदी" },
];

const variableHelp =
  "{patient_name}, {doctor_name}, {clinic_name}, {clinic_phone}, {appointment_time}";

export default function MessagingPage() {
  const { data, loading, error, reload, setData } = useApi(
    () => api.getMessagingSettings(),
    [],
  );
  const [form, setForm] = useState<MessagingSettings | null>(null);
  const [busy, setBusy] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (data) setForm(data);
  }, [data]);

  function setField<K extends keyof MessagingSettings>(
    key: K,
    value: MessagingSettings[K],
  ) {
    setForm((current) => (current ? { ...current, [key]: value } : current));
    setSaved(false);
  }

  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!form) return;
    setBusy(true);
    setSaveError(null);
    setSaved(false);
    try {
      const { clinic_id: _clinicId, ...values } = form;
      const updated = await api.updateMessagingSettings(
        values as MessagingSettingsInput,
      );
      setForm(updated);
      setData(updated);
      setSaved(true);
    } catch (caught) {
      setSaveError(getErrorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <LoadingPanel label="Loading messaging settings…" />;
  if (error) return <ErrorPanel message={error} onRetry={() => void reload()} />;
  if (!form) return null;

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader
        eyebrow="Patient messages"
        title="Messaging"
        description="Choose which confirmations and reminders go out, and edit the Hindi and English wording. Changes apply to new messages."
      />

      <form className="space-y-5" onSubmit={save}>
        {saveError ? <ErrorPanel message={saveError} /> : null}
        {saved ? (
          <div className="rounded-2xl border border-teal-200 bg-teal-50 p-4 text-sm text-teal-900">
            Messaging settings saved.
          </div>
        ) : null}

        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
          <h2 className="text-lg font-semibold text-slate-900">Confirmations</h2>
          <p className="mt-1 text-sm text-slate-500">
            Sent only when the caller asks, after a booking. The agent offers the
            enabled channels.
          </p>
          <div className="mt-4 space-y-3">
            <CheckRow
              checked={form.confirmation_whatsapp_enabled}
              onChange={(checked) =>
                setField("confirmation_whatsapp_enabled", checked)
              }
              label="WhatsApp confirmations"
              description="Uses the clinic's WhatsApp Business provider."
            />
            <CheckRow
              checked={form.confirmation_sms_enabled}
              onChange={(checked) => setField("confirmation_sms_enabled", checked)}
              label="SMS confirmations"
              description="Uses the clinic's Exotel or Plivo SMS sender."
            />
          </div>
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
          <h2 className="text-lg font-semibold text-slate-900">Reminders</h2>
          <p className="mt-1 text-sm text-slate-500">
            Queued when an appointment is booked or moved. A cancelled or
            rescheduled appointment does not receive an old reminder.
          </p>
          <div className="mt-4 space-y-3">
            <CheckRow
              checked={form.reminders_enabled}
              onChange={(checked) => setField("reminders_enabled", checked)}
              label="Send appointment reminders"
              description="Master switch for both reminder jobs."
            />
            <div className="grid gap-4 sm:grid-cols-2">
              <CheckRow
                checked={form.reminder_24h_enabled}
                onChange={(checked) => setField("reminder_24h_enabled", checked)}
                label="24 hours before"
                description="Sent the day before the visit."
              />
              <CheckRow
                checked={form.reminder_2h_enabled}
                onChange={(checked) => setField("reminder_2h_enabled", checked)}
                label="2 hours before"
                description="Sent on the day of the visit."
              />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className={labelClass} htmlFor="reminder-channel">
                  Reminder channel
                </label>
                <select
                  id="reminder-channel"
                  className={inputClass}
                  value={form.reminder_channel}
                  onChange={(event) =>
                    setField(
                      "reminder_channel",
                      event.target.value as MessagingSettings["reminder_channel"],
                    )
                  }
                >
                  <option value="whatsapp">WhatsApp</option>
                  <option value="sms">SMS</option>
                </select>
              </div>
              <div>
                <label className={labelClass} htmlFor="default-language">
                  Default language
                </label>
                <select
                  id="default-language"
                  className={inputClass}
                  value={form.default_language}
                  onChange={(event) =>
                    setField(
                      "default_language",
                      event.target.value as MessagingSettings["default_language"],
                    )
                  }
                >
                  <option value="en">English</option>
                  <option value="hi">हिंदी</option>
                </select>
              </div>
            </div>
          </div>
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
          <h2 className="text-lg font-semibold text-slate-900">Templates</h2>
          <p className="mt-1 text-sm text-slate-500">
            Keep messages short. Available variables: {variableHelp}.
          </p>
          <div className="mt-4 space-y-4">
            {templateFields.map((field) => (
              <div key={field.key}>
                <label className={labelClass} htmlFor={field.key}>
                  {field.label}
                </label>
                <textarea
                  id={field.key}
                  className={`${inputClass} min-h-24 font-mono text-xs leading-6`}
                  value={form[field.key]}
                  maxLength={1200}
                  onChange={(event) => setField(field.key, event.target.value)}
                />
              </div>
            ))}
          </div>
        </section>

        <div className="flex justify-end">
          <Button type="submit" loading={busy}>
            Save messaging settings
          </Button>
        </div>
      </form>
    </div>
  );
}

function CheckRow({
  checked,
  onChange,
  label,
  description,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
  description: string;
}) {
  return (
    <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-slate-200 p-3.5 transition hover:bg-slate-50">
      <input
        type="checkbox"
        className="mt-0.5 h-4 w-4 rounded border-slate-300 accent-teal-700"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
      />
      <span>
        <span className="block text-sm font-medium text-slate-800">{label}</span>
        <span className="mt-0.5 block text-xs text-slate-500">{description}</span>
      </span>
    </label>
  );
}
