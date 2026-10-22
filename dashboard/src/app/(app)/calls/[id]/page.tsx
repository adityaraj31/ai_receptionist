"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { ArrowUpRightIcon, PhoneIcon } from "@/components/icons";
import {
  Button,
  ErrorPanel,
  LoadingPanel,
  PageHeader,
  StatusBadge,
} from "@/components/ui";
import { api } from "@/lib/api-client";
import type { CallDetail, CallEvaluation } from "@/lib/api-types";
import { cn } from "@/lib/cn";
import { formatDateTime, formatTime } from "@/lib/format";
import { getErrorMessage } from "@/lib/errors";
import { useApi } from "@/lib/use-api";

export default function CallDetailPage() {
  const params = useParams<{ id: string }>();
  const { clinic } = useAuth();
  const timeZone = clinic?.timezone ?? "Asia/Kolkata";
  const { data: call, loading, error, reload } = useApi(
    () => api.getCall(params.id),
    [params.id],
  );

  return (
    <div>
      <PageHeader
        eyebrow="Call detail"
        title={call?.from_number ?? "Call"}
        description={
          call
            ? `${call.started_at ? formatDateTime(call.started_at, timeZone) : "Unknown time"} · ${formatDuration(call.duration_seconds)}`
            : "Transcript, recording, and quality evaluation."
        }
        actions={
          <Link
            href="/analytics"
            className="inline-flex items-center gap-2 rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50"
          >
            Back to analytics
          </Link>
        }
      />

      {loading ? <LoadingPanel label="Loading call detail…" /> : null}
      {!loading && error ? (
        <ErrorPanel message={error} onRetry={() => void reload()} />
      ) : null}

      {call ? (
        <div className="grid gap-6 xl:grid-cols-[1.5fr_1fr]">
          <div className="space-y-6">
            <SummaryCard call={call} />
            <RecordingCard call={call} />
            <TranscriptCard call={call} />
          </div>
          <div className="space-y-6">
            <CallFacts call={call} timeZone={timeZone} />
            <EvaluationCard evaluations={call.evaluations} />
            <UsageCard call={call} />
          </div>
        </div>
      ) : null}
    </div>
  );
}

function SummaryCard({ call }: { call: CallDetail }) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-base font-semibold text-slate-900">Call summary</h2>
        <div className="flex flex-wrap gap-2">
          {call.outcome ? <StatusBadge status={call.outcome} /> : null}
          <StatusBadge status={call.post_call_status} />
        </div>
      </div>
      <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-600">
        {call.summary || "No summary was generated for this call."}
      </p>
      {call.post_call_error ? (
        <p className="mt-3 rounded-xl bg-rose-50 px-3 py-2 text-xs text-rose-800">
          Post-call processing: {call.post_call_error}
        </p>
      ) : null}
    </section>
  );
}

function RecordingCard({ call }: { call: CallDetail }) {
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const urlRef = useRef<string | null>(null);

  useEffect(() => {
    return () => {
      if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    };
  }, []);

  async function loadRecording() {
    setLoading(true);
    setError(null);
    try {
      const blob = await api.getCallRecording(call.id);
      const url = URL.createObjectURL(blob);
      if (urlRef.current) URL.revokeObjectURL(urlRef.current);
      urlRef.current = url;
      setAudioUrl(url);
    } catch (caught) {
      setError(getErrorMessage(caught));
    } finally {
      setLoading(false);
    }
  }

  if (!call.recording_available) {
    return (
      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="text-base font-semibold text-slate-900">Recording</h2>
        <p className="mt-2 text-sm text-slate-500">
          Recording was not enabled for this call, or the audio is still being
          uploaded.
        </p>
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-slate-900">Recording</h2>
          <p className="mt-1 text-sm text-slate-500">
            Audio is fetched with clinic access and expires automatically.
          </p>
        </div>
        {audioUrl ? (
          <a
            href={audioUrl}
            download={`call-${call.id}.ogg`}
            className="inline-flex items-center gap-1.5 text-sm font-semibold text-teal-700 hover:text-teal-800"
          >
            Download
            <ArrowUpRightIcon className="h-4 w-4" />
          </a>
        ) : null}
      </div>

      {error ? (
        <div className="mt-4">
          <ErrorPanel message={error} onRetry={() => void loadRecording()} />
        </div>
      ) : null}

      {audioUrl ? (
        <audio className="mt-4 w-full" controls src={audioUrl} />
      ) : (
        <Button
          className="mt-4"
          variant="secondary"
          loading={loading}
          onClick={() => void loadRecording()}
        >
          <PhoneIcon className="h-4 w-4" />
          Load recording
        </Button>
      )}
    </section>
  );
}

function TranscriptCard({ call }: { call: CallDetail }) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-base font-semibold text-slate-900">Transcript</h2>
        <span className="text-xs text-slate-500">
          {call.transcript.length} turn{call.transcript.length === 1 ? "" : "s"}
        </span>
      </div>
      {call.transcript.length === 0 ? (
        <p className="mt-3 text-sm text-slate-500">
          No transcript was stored for this call.
        </p>
      ) : (
        <ol className="mt-4 space-y-4">
          {call.transcript.map((turn) => {
            const isAgent = turn.role === "assistant";
            return (
              <li
                key={turn.id}
                className={cn(
                  "flex",
                  isAgent ? "justify-start" : "justify-end",
                )}
              >
                <div
                  className={cn(
                    "max-w-[85%] rounded-2xl px-4 py-2.5 text-sm",
                    isAgent
                      ? "rounded-tl-sm bg-slate-100 text-slate-800"
                      : "rounded-tr-sm bg-teal-700 text-white",
                  )}
                >
                  <p
                    className={cn(
                      "mb-1 text-[10px] font-semibold uppercase tracking-wide",
                      isAgent ? "text-slate-500" : "text-teal-100",
                    )}
                  >
                    {roleLabel(turn.role)}
                    {turn.language ? ` · ${turn.language}` : ""} ·{" "}
                    {formatTime(turn.created_at, "Asia/Kolkata")}
                  </p>
                  <p className="whitespace-pre-wrap leading-6">{turn.text}</p>
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}

function CallFacts({ call, timeZone }: { call: CallDetail; timeZone: string }) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-base font-semibold text-slate-900">Call facts</h2>
      <dl className="mt-4 space-y-3 text-sm">
        <Fact label="From" value={call.from_number ?? "—"} />
        <Fact label="To" value={call.to_number ?? "—"} />
        <Fact
          label="Started"
          value={call.started_at ? formatDateTime(call.started_at, timeZone) : "—"}
        />
        <Fact
          label="Ended"
          value={call.ended_at ? formatDateTime(call.ended_at, timeZone) : "—"}
        />
        <Fact label="Language" value={call.language ?? "—"} />
        <Fact label="Duration" value={formatDuration(call.duration_seconds)} />
        <Fact label="Outcome" value={call.outcome ?? "—"} />
        <Fact
          label="Post-call"
          value={call.post_call_status.replaceAll("_", " ")}
        />
        <Fact
          label="Evaluation"
          value={call.evaluation_status.replaceAll("_", " ")}
        />
        {call.evaluation_error ? (
          <Fact label="Evaluation error" value={call.evaluation_error} />
        ) : null}
      </dl>
    </section>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <dt className="shrink-0 text-slate-500">{label}</dt>
      <dd className="text-right font-medium capitalize text-slate-800">
        {value}
      </dd>
    </div>
  );
}

function EvaluationCard({
  evaluations,
}: {
  evaluations: CallEvaluation[];
}) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-base font-semibold text-slate-900">
        Quality evaluation
      </h2>
      {evaluations.length === 0 ? (
        <p className="mt-3 text-sm text-slate-500">
          Evaluation has not completed for this call yet.
        </p>
      ) : (
        <div className="mt-4 space-y-4">
          {evaluations.map((evaluation) => (
            <div key={evaluation.id}>
              <div className="mb-1.5 flex items-center justify-between gap-3">
                <span className="text-sm font-medium capitalize text-slate-700">
                  {evaluation.metric.replaceAll("_", " ")}
                </span>
                <span
                  className={cn(
                    "rounded-full px-2.5 py-0.5 text-xs font-semibold",
                    scoreTone(evaluation),
                  )}
                >
                  {formatScore(evaluation.score)}
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                <div
                  className={cn("h-full rounded-full", scoreBar(evaluation))}
                  style={{ width: `${Math.min(100, (evaluation.score ?? 0) * 100)}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
      <p className="mt-4 text-xs text-slate-400">
        Scores are 0–100%. For missed handoffs, a lower score is better.
      </p>
    </section>
  );
}

function UsageCard({ call }: { call: CallDetail }) {
  const usage = call.usage_metrics ?? {};
  const latency =
    typeof usage.average_latency_ms === "number"
      ? `${Math.round(usage.average_latency_ms)} ms`
      : "—";
  const breakdown = call.cost_breakdown ?? {};

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 className="text-base font-semibold text-slate-900">Usage & cost</h2>
      <dl className="mt-4 space-y-3 text-sm">
        <Fact
          label="STT audio"
          value={`${round(usage.stt_audio_seconds)} sec`}
        />
        <Fact
          label="LLM tokens"
          value={`${round(usage.llm_prompt_tokens)} in / ${round(usage.llm_completion_tokens)} out`}
        />
        <Fact label="TTS" value={`${round(usage.tts_characters)} chars`} />
        <Fact
          label="Avg latency"
          value={
            typeof usage.latency_samples === "number" && usage.latency_samples > 0
              ? `${latency} · ${usage.latency_samples} turns`
              : latency
          }
        />
        <Fact
          label="Call cost"
          value={call.cost == null ? "—" : formatCurrency(call.cost)}
        />
      </dl>

      {Object.keys(breakdown).length ? (
        <div className="mt-5 border-t border-slate-200 pt-4">
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
            Cost breakdown
          </p>
          <dl className="space-y-2 text-sm">
            {Object.entries(breakdown)
              .filter(([, value]) => typeof value === "number")
              .map(([key, value]) => (
                <Fact
                  key={key}
                  label={key.replaceAll("_", " ")}
                  value={formatCurrency(value as number)}
                />
              ))}
          </dl>
        </div>
      ) : null}
    </section>
  );
}

function roleLabel(role: string): string {
  if (role === "assistant") return "AI receptionist";
  if (role === "user") return "Caller";
  return role;
}

function formatScore(score: number | null): string {
  if (score == null) return "—";
  return `${Math.round(score * 100)}%`;
}

function scoreTone(evaluation: CallEvaluation): string {
  if (evaluation.score == null) return "bg-slate-100 text-slate-600";
  const good =
    evaluation.metric === "missed_handoffs"
      ? evaluation.score <= 0
      : evaluation.score >= 0.75;
  if (good) return "bg-teal-50 text-teal-800";
  return "bg-amber-50 text-amber-800";
}

function scoreBar(evaluation: CallEvaluation): string {
  if (evaluation.score == null) return "bg-slate-400";
  return evaluation.metric === "missed_handoffs"
    ? "bg-amber-500"
    : "bg-teal-600";
}

function formatDuration(seconds: number | null): string {
  if (seconds == null) return "—";
  const rounded = Math.round(seconds);
  if (rounded < 60) return `${rounded}s`;
  return `${Math.floor(rounded / 60)}m ${rounded % 60}s`;
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  }).format(value);
}

function round(value: unknown): string {
  if (typeof value !== "number") return "0";
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits: 1 }).format(
    value,
  );
}
