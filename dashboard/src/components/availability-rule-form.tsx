"use client";

import { useState } from "react";

import { Button, ErrorPanel, inputClass, labelClass } from "@/components/ui";
import { api } from "@/lib/api-client";
import type { AvailabilityRule } from "@/lib/api-types";
import { getErrorMessage } from "@/lib/errors";
import { formatWeekday } from "@/lib/format";

const weekdays = [1, 2, 3, 4, 5, 6, 7];

export function AvailabilityRuleForm({
  doctorId,
  rule,
  onSaved,
  onCancel,
  submitLabel,
  cancelLabel = "Cancel",
}: {
  doctorId: string;
  rule?: AvailabilityRule | null;
  onSaved: (rule: AvailabilityRule) => void;
  onCancel: () => void;
  submitLabel?: string;
  cancelLabel?: string;
}) {
  const [weekday, setWeekday] = useState(rule?.weekday ?? 1);
  const [startTime, setStartTime] = useState(
    rule?.start_time.slice(0, 5) ?? "09:00",
  );
  const [endTime, setEndTime] = useState(
    rule?.end_time.slice(0, 5) ?? "17:00",
  );
  const [slotMinutes, setSlotMinutes] = useState(
    String(rule?.slot_minutes ?? 15),
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    const minutes = Number(slotMinutes);
    if (endTime <= startTime) {
      setError("End time must be after start time.");
      return;
    }
    if (!Number.isInteger(minutes) || minutes < 5 || minutes > 240) {
      setError("Slot length must be between 5 and 240 minutes.");
      return;
    }

    const payload = {
      weekday,
      start_time: startTime,
      end_time: endTime,
      slot_minutes: minutes,
      is_active: rule?.is_active ?? true,
    };

    setBusy(true);
    try {
      const saved = rule
        ? await api.updateAvailability(doctorId, rule.id, payload)
        : await api.createAvailability(doctorId, payload);
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
        <label className={labelClass} htmlFor="rule-weekday">
          Day of week
        </label>
        <select
          id="rule-weekday"
          className={inputClass}
          value={weekday}
          onChange={(event) => setWeekday(Number(event.target.value))}
        >
          {weekdays.map((day) => (
            <option key={day} value={day}>
              {formatWeekday(day)}
            </option>
          ))}
        </select>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className={labelClass} htmlFor="rule-start">
            Start time
          </label>
          <input
            id="rule-start"
            className={inputClass}
            type="time"
            value={startTime}
            onChange={(event) => setStartTime(event.target.value)}
            required
          />
        </div>
        <div>
          <label className={labelClass} htmlFor="rule-end">
            End time
          </label>
          <input
            id="rule-end"
            className={inputClass}
            type="time"
            value={endTime}
            onChange={(event) => setEndTime(event.target.value)}
            required
          />
        </div>
      </div>

      <div>
        <label className={labelClass} htmlFor="rule-slot">
          Slot length (minutes)
        </label>
        <input
          id="rule-slot"
          className={inputClass}
          type="number"
          min="5"
          max="240"
          step="5"
          value={slotMinutes}
          onChange={(event) => setSlotMinutes(event.target.value)}
          required
        />
        <p className="mt-1 text-xs text-slate-500">
          Each appointment will use this length inside the working hours.
        </p>
      </div>

      <div className="flex flex-col-reverse gap-2 pt-2 sm:flex-row sm:justify-end">
        <Button type="button" variant="secondary" onClick={onCancel} disabled={busy}>
          {cancelLabel}
        </Button>
        <Button type="submit" loading={busy}>
          {submitLabel ?? (rule ? "Save hours" : "Add working hours")}
        </Button>
      </div>
    </form>
  );
}
