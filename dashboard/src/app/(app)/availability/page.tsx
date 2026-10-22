"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { AvailabilityRuleForm } from "@/components/availability-rule-form";
import {
  ClockIcon,
  EditIcon,
  PlusIcon,
  TrashIcon,
} from "@/components/icons";
import { TimeOffForm } from "@/components/time-off-form";
import {
  Button,
  ConfirmDialog,
  EmptyState,
  ErrorPanel,
  LoadingPanel,
  Modal,
  PageHeader,
  inputClass,
  labelClass,
} from "@/components/ui";
import { api } from "@/lib/api-client";
import type { AvailabilityRule, TimeOff } from "@/lib/api-types";
import { getErrorMessage } from "@/lib/errors";
import {
  formatDateTime,
  formatNextWeekday,
  formatTimeValue,
  formatWeekday,
} from "@/lib/format";
import { useApi } from "@/lib/use-api";

type DoctorAvailability = {
  rules: AvailabilityRule[];
  timeOff: TimeOff[];
};

export default function AvailabilityPage() {
  const { clinic } = useAuth();
  const {
    data: doctors,
    loading: doctorsLoading,
    error: doctorsError,
    reload: reloadDoctors,
  } = useApi(() => api.listDoctors(), []);

  const [doctorId, setDoctorId] = useState("");
  const [ruleOpen, setRuleOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<AvailabilityRule | null>(null);
  const [timeOffOpen, setTimeOffOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<{
    type: "rule" | "timeoff";
    id: string;
    label: string;
  } | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    if (!doctorId && doctors && doctors.length > 0) {
      setDoctorId(doctors[0].id);
    }
  }, [doctorId, doctors]);

  const {
    data,
    loading,
    error,
    reload,
  } = useApi<DoctorAvailability>(
    async () => {
      if (!doctorId) return { rules: [], timeOff: [] };
      const [rules, timeOff] = await Promise.all([
        api.listAvailability(doctorId),
        api.listTimeOff(doctorId),
      ]);
      return { rules, timeOff };
    },
    [doctorId],
  );

  const selectedDoctor = doctors?.find((doctor) => doctor.id === doctorId);
  const timeZone = clinic?.timezone ?? "Asia/Kolkata";
  const rules = [...(data?.rules ?? [])].sort(
    (a, b) =>
      a.weekday - b.weekday || a.start_time.localeCompare(b.start_time),
  );
  const timeOff = [...(data?.timeOff ?? [])].sort(
    (a, b) => new Date(a.starts_at).getTime() - new Date(b.starts_at).getTime(),
  );

  function openAddRule() {
    setEditingRule(null);
    setRuleOpen(true);
  }

  function openEditRule(rule: AvailabilityRule) {
    setEditingRule(rule);
    setRuleOpen(true);
  }

  async function confirmDelete() {
    if (!deleteTarget || !doctorId) return;
    setBusy(true);
    setActionError(null);
    try {
      if (deleteTarget.type === "rule") {
        await api.deleteAvailability(doctorId, deleteTarget.id);
      } else {
        await api.deleteTimeOff(doctorId, deleteTarget.id);
      }
      setDeleteTarget(null);
      await reload();
    } catch (caught) {
      setActionError(getErrorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Weekly schedule"
        title="Availability"
        description="Set the hours each doctor takes appointments, choose slot lengths, and block days off."
      />

      {actionError ? (
        <div className="mb-4">
          <ErrorPanel
            message={actionError}
            onRetry={() => {
              setActionError(null);
              void reload();
            }}
          />
        </div>
      ) : null}

      {doctorsLoading ? <LoadingPanel label="Loading doctors…" /> : null}

      {!doctorsLoading && doctorsError ? (
        <ErrorPanel message={doctorsError} onRetry={reloadDoctors} />
      ) : null}

      {!doctorsLoading && !doctorsError && doctors?.length === 0 ? (
        <EmptyState
          title="Add a doctor first"
          description="Availability is configured per doctor. Add a clinician, then set their weekly hours here."
          action={
            <Link
              href="/doctors"
              className="inline-flex items-center justify-center rounded-xl bg-teal-700 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-teal-800"
            >
              Go to doctors
            </Link>
          }
        />
      ) : null}

      {!doctorsLoading && !doctorsError && doctors && doctors.length > 0 ? (
        <div className="space-y-5">
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <label className={labelClass} htmlFor="availability-doctor">
              Doctor
            </label>
            <select
              id="availability-doctor"
              className={`${inputClass} max-w-md`}
              value={doctorId}
              onChange={(event) => setDoctorId(event.target.value)}
            >
              {doctors.map((doctor) => (
                <option key={doctor.id} value={doctor.id}>
                  {doctor.name} · {doctor.specialization}
                </option>
              ))}
            </select>
            {selectedDoctor ? (
              <p className="mt-2 text-xs text-slate-500">
                {selectedDoctor.languages.length > 0
                  ? `Speaks ${selectedDoctor.languages.join(", ")} · `
                  : ""}
                Availability is calculated in {timeZone}.
              </p>
            ) : null}
          </div>

          {loading ? <LoadingPanel label="Loading availability…" /> : null}

          {!loading && error ? (
            <ErrorPanel message={error} onRetry={reload} />
          ) : null}

          {!loading && !error ? (
            <div className="grid gap-5 xl:grid-cols-[1.2fr_1fr]">
              <section className="rounded-2xl border border-slate-200 bg-white shadow-sm">
                <div className="flex items-center justify-between gap-3 border-b border-slate-200 px-5 py-4">
                  <div>
                    <h2 className="text-base font-semibold text-slate-900">
                      Weekly working hours
                    </h2>
                    <p className="mt-0.5 text-xs text-slate-500">
                      These windows repeat weekly. Each date shows the next
                      occurrence in {timeZone}.
                    </p>
                  </div>
                  <Button size="sm" onClick={openAddRule} disabled={!doctorId}>
                    <PlusIcon className="h-4 w-4" />
                    Add hours
                  </Button>
                </div>

                {rules.length === 0 ? (
                  <div className="px-5 py-10 text-center">
                    <ClockIcon className="mx-auto h-8 w-8 text-slate-300" />
                    <p className="mt-3 text-sm font-medium text-slate-700">
                      No working hours yet
                    </p>
                    <p className="mt-1 text-xs text-slate-500">
                      Add at least one weekly window before appointments can be
                      booked.
                    </p>
                  </div>
                ) : (
                  <ul className="divide-y divide-slate-100">
                    {rules.map((rule) => (
                      <li
                        key={rule.id}
                        className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:justify-between"
                      >
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="text-sm font-semibold text-slate-900">
                              {formatWeekday(rule.weekday)}
                            </p>
                            <span className="rounded-full bg-teal-50 px-2.5 py-1 text-[11px] font-semibold text-teal-700 ring-1 ring-inset ring-teal-600/15">
                              Next: {formatNextWeekday(rule.weekday, timeZone)}
                            </span>
                          </div>
                          <p className="mt-1 text-sm text-slate-500">
                            {formatTimeValue(rule.start_time)} –{" "}
                            {formatTimeValue(rule.end_time)}
                            <span className="mx-2 text-slate-300">·</span>
                            {rule.slot_minutes} min slots
                          </p>
                        </div>
                        <div className="flex gap-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openEditRule(rule)}
                          >
                            <EditIcon className="h-4 w-4" />
                            Edit
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-rose-600 hover:bg-rose-50 hover:text-rose-700"
                            onClick={() =>
                              setDeleteTarget({
                                type: "rule",
                                id: rule.id,
                                label: `${formatWeekday(rule.weekday)} working hours`,
                              })
                            }
                          >
                            <TrashIcon className="h-4 w-4" />
                            Delete
                          </Button>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              <section className="rounded-2xl border border-slate-200 bg-white shadow-sm">
                <div className="flex items-center justify-between gap-3 border-b border-slate-200 px-5 py-4">
                  <div>
                    <h2 className="text-base font-semibold text-slate-900">
                      Days off
                    </h2>
                    <p className="mt-0.5 text-xs text-slate-500">
                      Block holidays, leave, or part of a day.
                    </p>
                  </div>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => setTimeOffOpen(true)}
                    disabled={!doctorId}
                  >
                    <PlusIcon className="h-4 w-4" />
                    Add
                  </Button>
                </div>

                {timeOff.length === 0 ? (
                  <div className="px-5 py-10 text-center">
                    <p className="text-sm font-medium text-slate-700">
                      No days off scheduled
                    </p>
                    <p className="mt-1 text-xs text-slate-500">
                      The doctor is available during their weekly hours.
                    </p>
                  </div>
                ) : (
                  <ul className="divide-y divide-slate-100">
                    {timeOff.map((entry) => (
                      <li
                        key={entry.id}
                        className="flex items-start justify-between gap-3 px-5 py-4"
                      >
                        <div>
                          <p className="text-sm font-semibold text-slate-900">
                            {formatDateTime(entry.starts_at, timeZone)}
                          </p>
                          <p className="mt-1 text-sm text-slate-500">
                            to {formatDateTime(entry.ends_at, timeZone)}
                          </p>
                          {entry.reason ? (
                            <p className="mt-1 text-xs text-slate-500">
                              {entry.reason}
                            </p>
                          ) : null}
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="shrink-0 text-rose-600 hover:bg-rose-50 hover:text-rose-700"
                          onClick={() =>
                            setDeleteTarget({
                              type: "timeoff",
                              id: entry.id,
                              label: "this time off",
                            })
                          }
                        >
                          <TrashIcon className="h-4 w-4" />
                          Remove
                        </Button>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </div>
          ) : null}
        </div>
      ) : null}

      <Modal
        open={ruleOpen}
        onClose={() => setRuleOpen(false)}
        title={editingRule ? "Edit working hours" : "Add working hours"}
        description="The clinic will offer slots inside this window."
      >
        {doctorId ? (
          <AvailabilityRuleForm
            doctorId={doctorId}
            rule={editingRule}
            onCancel={() => setRuleOpen(false)}
            timeZone={timeZone}
            onSaved={async () => {
              setRuleOpen(false);
              await reload();
            }}
          />
        ) : null}
      </Modal>

      <Modal
        open={timeOffOpen}
        onClose={() => setTimeOffOpen(false)}
        title="Add time off"
        description="Blocked time is removed from the doctor's free slots."
      >
        {doctorId ? (
          <TimeOffForm
            doctorId={doctorId}
            timeZone={timeZone}
            onCancel={() => setTimeOffOpen(false)}
            onSaved={async () => {
              setTimeOffOpen(false);
              await reload();
            }}
          />
        ) : null}
      </Modal>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title={
          deleteTarget?.type === "rule"
            ? "Delete working hours?"
            : "Remove time off?"
        }
        message={`${deleteTarget?.label ?? "This item"} will be removed from the schedule. Existing appointments are not changed.`}
        confirmLabel="Delete"
        danger
        busy={busy}
        onCancel={() => setDeleteTarget(null)}
        onConfirm={confirmDelete}
      />
    </div>
  );
}
