"use client";

import { useState } from "react";

import { Button, ErrorPanel, inputClass, labelClass } from "@/components/ui";
import { api } from "@/lib/api-client";
import type { TimeOff } from "@/lib/api-types";
import { getErrorMessage } from "@/lib/errors";
import { todayInTimeZone, zonedDateTimeToIso } from "@/lib/format";

export function TimeOffForm({
  doctorId,
  timeZone,
  onSaved,
  onCancel,
}: {
  doctorId: string;
  timeZone: string;
  onSaved: (timeOff: TimeOff) => void;
  onCancel: () => void;
}) {
  const today = todayInTimeZone(timeZone);
  const [startDate, setStartDate] = useState(today);
  const [startTime, setStartTime] = useState("09:00");
  const [endDate, setEndDate] = useState(today);
  const [endTime, setEndTime] = useState("18:00");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    const startsAt = zonedDateTimeToIso(
      `${startDate}T${startTime}`,
      timeZone,
    );
    const endsAt = zonedDateTimeToIso(`${endDate}T${endTime}`, timeZone);

    if (new Date(endsAt) <= new Date(startsAt)) {
      setError("The end of the time off must be after the start.");
      return;
    }

    setBusy(true);
    try {
      const saved = await api.createTimeOff(doctorId, {
        starts_at: startsAt,
        ends_at: endsAt,
        reason: reason.trim(),
      });
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

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className={labelClass} htmlFor="timeoff-start-date">
            From date
          </label>
          <input
            id="timeoff-start-date"
            className={inputClass}
            type="date"
            value={startDate}
            onChange={(event) => setStartDate(event.target.value)}
            required
          />
        </div>
        <div>
          <label className={labelClass} htmlFor="timeoff-start-time">
            From time
          </label>
          <input
            id="timeoff-start-time"
            className={inputClass}
            type="time"
            value={startTime}
            onChange={(event) => setStartTime(event.target.value)}
            required
          />
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className={labelClass} htmlFor="timeoff-end-date">
            To date
          </label>
          <input
            id="timeoff-end-date"
            className={inputClass}
            type="date"
            value={endDate}
            onChange={(event) => setEndDate(event.target.value)}
            required
          />
        </div>
        <div>
          <label className={labelClass} htmlFor="timeoff-end-time">
            To time
          </label>
          <input
            id="timeoff-end-time"
            className={inputClass}
            type="time"
            value={endTime}
            onChange={(event) => setEndTime(event.target.value)}
            required
          />
        </div>
      </div>

      <div>
        <label className={labelClass} htmlFor="timeoff-reason">
          Reason
        </label>
        <input
          id="timeoff-reason"
          className={inputClass}
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          placeholder="Public holiday, conference, leave…"
        />
      </div>

      <div className="flex flex-col-reverse gap-2 pt-2 sm:flex-row sm:justify-end">
        <Button type="button" variant="secondary" onClick={onCancel} disabled={busy}>
          Cancel
        </Button>
        <Button type="submit" loading={busy}>
          Add time off
        </Button>
      </div>
    </form>
  );
}
