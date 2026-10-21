"use client";

import { useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { PhoneIcon, RefreshIcon } from "@/components/icons";
import {
  Button,
  EmptyState,
  ErrorPanel,
  LoadingPanel,
  PageHeader,
  StatusBadge,
} from "@/components/ui";
import { api } from "@/lib/api-client";
import type { Callback, CallbackStatus } from "@/lib/api-types";
import { getErrorMessage } from "@/lib/errors";
import { formatDateTime } from "@/lib/format";
import { useApi } from "@/lib/use-api";

export default function CallbacksPage() {
  const { clinic } = useAuth();
  const timeZone = clinic?.timezone ?? "Asia/Kolkata";
  const [showAll, setShowAll] = useState(false);
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const {
    data: callbacks,
    loading,
    error,
    reload,
  } = useApi(
    () => api.listCallbacks(showAll ? undefined : "pending"),
    [showAll],
  );

  async function setStatus(callback: Callback, status: CallbackStatus) {
    setUpdatingId(callback.id);
    setActionError(null);
    try {
      await api.updateCallback(callback.id, { status });
      await reload();
    } catch (caught) {
      setActionError(getErrorMessage(caught));
    } finally {
      setUpdatingId(null);
    }
  }

  const pendingCount =
    callbacks?.filter((callback) => callback.status === "pending").length ?? 0;

  return (
    <div>
      <PageHeader
        eyebrow="Follow up"
        title="Callbacks"
        description="Callers who could not be transferred, or who asked the AI for a callback. Call them back from the front desk."
        actions={
          <>
            <Button
              variant="secondary"
              onClick={() => setShowAll((value) => !value)}
            >
              {showAll ? "Show pending only" : "Show all"}
            </Button>
            <Button variant="secondary" onClick={() => void reload()}>
              <RefreshIcon className="h-4 w-4" />
              Refresh
            </Button>
          </>
        }
      />

      <p className="mb-4 text-sm text-slate-500">
        {callbacks
          ? `${pendingCount} pending${showAll ? ` of ${callbacks.length}` : ""}`
          : "Loading callback tasks"}
      </p>

      {actionError ? (
        <div className="mb-4">
          <ErrorPanel message={actionError} onRetry={() => void reload()} />
        </div>
      ) : null}

      {loading ? <LoadingPanel label="Loading callbacks…" /> : null}

      {!loading && error ? (
        <ErrorPanel message={error} onRetry={() => void reload()} />
      ) : null}

      {!loading && !error && callbacks && callbacks.length === 0 ? (
        <EmptyState
          title="No pending callbacks"
          description="When a caller cannot reach the front desk, the AI takes their details and adds a task here."
        />
      ) : null}

      {!loading && !error && callbacks && callbacks.length > 0 ? (
        <div className="space-y-3">
          {callbacks.map((callback) => (
            <article
              key={callback.id}
              className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5"
            >
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="text-base font-semibold text-slate-900">
                      {callback.caller_name}
                    </h2>
                    <StatusBadge status={callback.status} />
                  </div>
                  <a
                    href={`tel:${callback.phone}`}
                    className="mt-1 inline-flex items-center gap-1.5 text-sm font-medium text-teal-700 hover:text-teal-800"
                  >
                    <PhoneIcon className="h-4 w-4" />
                    {callback.phone}
                  </a>
                  <p className="mt-2 text-sm text-slate-600">
                    <span className="font-medium text-slate-700">Reason:</span>{" "}
                    {callback.reason || "Callback requested"}
                  </p>
                  {callback.message ? (
                    <p className="mt-1 text-sm text-slate-600">
                      {callback.message}
                    </p>
                  ) : null}
                  <p className="mt-3 text-xs text-slate-400">
                    {formatDateTime(callback.created_at, timeZone)}
                  </p>
                </div>

                <div className="flex shrink-0 flex-wrap gap-2">
                  {callback.status === "pending" ? (
                    <Button
                      size="sm"
                      variant="secondary"
                      loading={updatingId === callback.id}
                      onClick={() => void setStatus(callback, "contacted")}
                    >
                      Mark contacted
                    </Button>
                  ) : null}
                  {callback.status === "pending" ||
                  callback.status === "contacted" ? (
                    <Button
                      size="sm"
                      loading={updatingId === callback.id}
                      onClick={() => void setStatus(callback, "done")}
                    >
                      Mark done
                    </Button>
                  ) : null}
                </div>
              </div>
            </article>
          ))}
        </div>
      ) : null}
    </div>
  );
}
