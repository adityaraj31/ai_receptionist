"use client";

import Link from "next/link";
import { useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { ArrowUpRightIcon, ChartIcon, RefreshIcon } from "@/components/icons";
import {
  Button,
  EmptyState,
  ErrorPanel,
  LoadingPanel,
  PageHeader,
  Spinner,
  StatusBadge,
} from "@/components/ui";
import { api } from "@/lib/api-client";
import type {
  CallAnalytics,
  CallAnalyticsDay,
  CallListItem,
} from "@/lib/api-types";
import { cn } from "@/lib/cn";
import { formatDateTime } from "@/lib/format";
import { useApi } from "@/lib/use-api";

const ranges = [7, 30, 90];

export default function AnalyticsPage() {
  const { clinic } = useAuth();
  const timeZone = clinic?.timezone ?? "Asia/Kolkata";
  const [days, setDays] = useState(30);
  const { data, loading, error, reload } = useApi(
    () => api.getCallAnalytics(days),
    [days],
  );

  return (
    <div>
      <PageHeader
        eyebrow="Performance"
        title="Call analytics"
        description="How your AI receptionist is handling calls: volume, bookings, handoffs, latency, language, and cost."
        actions={
          <>
            <div className="flex rounded-xl border border-slate-300 bg-white p-1 shadow-sm">
              {ranges.map((range) => (
                <button
                  key={range}
                  className={cn(
                    "rounded-lg px-3 py-1.5 text-xs font-semibold transition",
                    days === range
                      ? "bg-teal-700 text-white"
                      : "text-slate-600 hover:bg-slate-100",
                  )}
                  onClick={() => setDays(range)}
                  type="button"
                >
                  {range}d
                </button>
              ))}
            </div>
            <Button variant="secondary" onClick={() => void reload()}>
              <RefreshIcon className="h-4 w-4" />
              Refresh
            </Button>
          </>
        }
      />

      {loading && !data ? <LoadingPanel label="Loading call analytics…" /> : null}

      {!loading && error ? (
        <ErrorPanel message={error} onRetry={() => void reload()} />
      ) : null}

      {data ? (
        <div className={cn("space-y-6", loading && "opacity-70")}>
          <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-slate-500">
            <p>
              {formatDateRange(data.period_start, data.period_end)} ·{" "}
              {data.totals.calls} calls
            </p>
            {loading ? (
              <span className="inline-flex items-center gap-2">
                <Spinner className="h-4 w-4 text-teal-700" />
                Updating
              </span>
            ) : null}
          </div>

          <MetricGrid data={data} />

          {data.totals.calls === 0 ? (
            <EmptyState
              title="No calls in this period"
              description="Call analytics will appear here after the AI receptionist handles its first call."
            />
          ) : (
            <>
              <div className="grid gap-6 xl:grid-cols-[1.55fr_1fr]">
                <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                  <div className="mb-5 flex items-start justify-between gap-4">
                    <div>
                      <h2 className="text-base font-semibold text-slate-900">
                        Call volume
                      </h2>
                      <p className="mt-1 text-sm text-slate-500">
                        Incoming calls per day, in {timeZone}.
                      </p>
                    </div>
                    <ChartIcon className="h-5 w-5 text-teal-700" />
                  </div>
                  <CallVolumeChart days={data.calls_per_day} />
                </section>

                <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                  <h2 className="text-base font-semibold text-slate-900">
                    Language mix
                  </h2>
                  <p className="mt-1 text-sm text-slate-500">
                    Language detected at the start of each call.
                  </p>
                  <div className="mt-5 space-y-4">
                    {data.languages.length ? (
                      data.languages.map((row) => (
                        <SplitBar
                          key={row.language}
                          label={row.language}
                          value={row.calls}
                          share={row.share}
                          tone="teal"
                        />
                      ))
                    ) : (
                      <p className="text-sm text-slate-500">
                        No language data yet.
                      </p>
                    )}
                  </div>

                  <h2 className="mt-7 text-base font-semibold text-slate-900">
                    Call outcomes
                  </h2>
                  <div className="mt-4 space-y-4">
                    {data.outcomes.length ? (
                      data.outcomes.map((row) => (
                        <SplitBar
                          key={row.outcome}
                          label={humanize(row.outcome)}
                          value={row.calls}
                          share={row.share}
                          tone="slate"
                        />
                      ))
                    ) : (
                      <p className="text-sm text-slate-500">
                        No outcomes recorded yet.
                      </p>
                    )}
                  </div>
                </section>
              </div>

              <RecentCalls calls={data.recent_calls} timeZone={timeZone} />
            </>
          )}
        </div>
      ) : null}
    </div>
  );
}

function MetricGrid({ data }: { data: CallAnalytics }) {
  const totals = data.totals;
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      <Metric
        label="Calls handled"
        value={String(totals.calls)}
        detail={`${formatDuration(totals.average_duration_seconds)} average call`}
      />
      <Metric
        label="Booking conversion"
        value={formatPercent(totals.booking_conversion)}
        detail={`${totals.booked} appointment${totals.booked === 1 ? "" : "s"} booked`}
      />
      <Metric
        label="Average latency"
        value={
          totals.average_latency_ms == null
            ? "—"
            : `${Math.round(totals.average_latency_ms)} ms`
        }
        detail="End of caller speech to agent speech"
      />
      <Metric
        label="Transfer rate"
        value={formatPercent(totals.transfer_rate)}
        detail={`${totals.transferred} call${totals.transferred === 1 ? "" : "s"} handed to staff`}
      />
      <Metric
        label="Cost per minute"
        value={
          totals.cost_per_minute == null
            ? "—"
            : formatCurrency(totals.cost_per_minute)
        }
        detail={`${formatCurrency(totals.total_cost)} total · ${totals.total_minutes} min`}
      />
      <Metric
        label="Talk time"
        value={`${totals.total_minutes} min`}
        detail="Across all calls in this period"
      />
    </div>
  );
}

function Metric({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
        {label}
      </p>
      <p className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">
        {value}
      </p>
      <p className="mt-1 text-xs text-slate-500">{detail}</p>
    </div>
  );
}

function CallVolumeChart({ days }: { days: CallAnalyticsDay[] }) {
  const max = Math.max(1, ...days.map((day) => day.calls));
  const labelCount = days.length <= 10 ? days.length : 6;
  const labels = Array.from({ length: labelCount }, (_, index) =>
    days[Math.round((index * (days.length - 1)) / Math.max(1, labelCount - 1))],
  );

  return (
    <div>
      <div className="flex h-44 items-end gap-[3px] border-b border-slate-200 px-1">
        {days.map((day) => {
          const height = day.calls === 0 ? 2 : Math.max(6, (day.calls / max) * 100);
          return (
            <div
              key={day.date}
              className="group relative flex h-full flex-1 items-end"
              title={`${shortDate(day.date)}: ${day.calls} call${day.calls === 1 ? "" : "s"}`}
            >
              <div
                className="w-full rounded-t bg-teal-600/80 transition group-hover:bg-teal-500"
                style={{ height: `${height}%` }}
              />
            </div>
          );
        })}
      </div>
      <div className="mt-2 flex justify-between px-1 text-[10px] text-slate-400">
        {labels.map((day, index) => (
          <span key={`${day.date}-${index}`}>{shortDate(day.date)}</span>
        ))}
      </div>
    </div>
  );
}

function SplitBar({
  label,
  value,
  share,
  tone,
}: {
  label: string;
  value: number;
  share: number;
  tone: "teal" | "slate";
}) {
  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between gap-3 text-sm">
        <span className="truncate font-medium text-slate-700">{label}</span>
        <span className="shrink-0 text-xs text-slate-500">
          {value} · {formatPercent(share)}
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-slate-100">
        <div
          className={cn(
            "h-full rounded-full",
            tone === "teal" ? "bg-teal-600" : "bg-slate-500",
          )}
          style={{ width: `${Math.max(2, share * 100)}%` }}
        />
      </div>
    </div>
  );
}

function RecentCalls({
  calls,
  timeZone,
}: {
  calls: CallListItem[];
  timeZone: string;
}) {
  return (
    <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center justify-between gap-4 border-b border-slate-200 px-5 py-4">
        <div>
          <h2 className="text-base font-semibold text-slate-900">Recent calls</h2>
          <p className="mt-1 text-sm text-slate-500">
            Open a call for the transcript, recording, summary, and evaluation.
          </p>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-5 py-3 font-semibold">Caller</th>
              <th className="px-4 py-3 font-semibold">When</th>
              <th className="px-4 py-3 font-semibold">Language</th>
              <th className="px-4 py-3 font-semibold">Outcome</th>
              <th className="px-4 py-3 font-semibold">Duration</th>
              <th className="px-4 py-3 font-semibold">Cost</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200">
            {calls.map((call) => (
              <tr key={call.id} className="hover:bg-slate-50">
                <td className="whitespace-nowrap px-5 py-3 font-medium text-slate-900">
                  {call.from_number ?? "Unknown caller"}
                </td>
                <td className="whitespace-nowrap px-4 py-3 text-slate-500">
                  {call.started_at ? formatDateTime(call.started_at, timeZone) : "—"}
                </td>
                <td className="whitespace-nowrap px-4 py-3 text-slate-600">
                  {call.language ?? "—"}
                </td>
                <td className="whitespace-nowrap px-4 py-3">
                  {call.outcome ? (
                    <StatusBadge status={call.outcome} />
                  ) : (
                    <span className="text-slate-400">—</span>
                  )}
                </td>
                <td className="whitespace-nowrap px-4 py-3 text-slate-600">
                  {formatDuration(call.duration_seconds)}
                </td>
                <td className="whitespace-nowrap px-4 py-3 text-slate-600">
                  {call.cost == null ? "—" : formatCurrency(call.cost)}
                </td>
                <td className="whitespace-nowrap px-4 py-3 text-right">
                  <Link
                    href={`/calls/${call.id}`}
                    className="inline-flex items-center gap-1.5 font-semibold text-teal-700 hover:text-teal-800"
                  >
                    View
                    <ArrowUpRightIcon className="h-4 w-4" />
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function formatDuration(seconds: number | null): string {
  if (seconds == null) return "—";
  const rounded = Math.round(seconds);
  if (rounded < 60) return `${rounded}s`;
  return `${Math.floor(rounded / 60)}m ${rounded % 60}s`;
}

function shortDate(date: string): string {
  return new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  }).format(new Date(`${date}T12:00:00Z`));
}

function formatDateRange(start: string, end: string): string {
  const formatter = new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
  return `${formatter.format(new Date(`${start}T12:00:00Z`))} – ${formatter.format(
    new Date(`${end}T12:00:00Z`),
  )}`;
}

function humanize(value: string): string {
  const labels: Record<string, string> = {
    booked: "Appointment booked",
    enquiry: "Enquiry",
    transferred: "Transferred to staff",
    callback: "Callback requested",
    cancelled: "Cancelled",
    no_show: "No show",
    pending: "Pending",
  };
  return labels[value] ?? value.replaceAll("_", " ");
}
