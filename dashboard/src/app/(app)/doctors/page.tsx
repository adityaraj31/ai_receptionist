"use client";

import { useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { DoctorForm } from "@/components/doctor-form";
import { EditIcon, PlusIcon, TrashIcon } from "@/components/icons";
import {
  Button,
  ConfirmDialog,
  EmptyState,
  ErrorPanel,
  LoadingPanel,
  Modal,
  PageHeader,
} from "@/components/ui";
import { api } from "@/lib/api-client";
import type { Doctor } from "@/lib/api-types";
import { getErrorMessage } from "@/lib/errors";
import { formatFee } from "@/lib/format";
import { useApi } from "@/lib/use-api";

export default function DoctorsPage() {
  const { clinic } = useAuth();
  const {
    data: doctors,
    loading,
    error,
    reload,
  } = useApi(() => api.listDoctors(), []);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Doctor | null>(null);
  const [deactivating, setDeactivating] = useState<Doctor | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  function openAdd() {
    setEditing(null);
    setFormOpen(true);
  }

  function openEdit(doctor: Doctor) {
    setEditing(doctor);
    setFormOpen(true);
  }

  async function confirmDeactivate() {
    if (!deactivating) return;
    setBusy(true);
    setActionError(null);
    try {
      await api.deactivateDoctor(deactivating.id);
      setDeactivating(null);
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
        eyebrow="Your team"
        title="Doctors"
        description="Manage the clinicians patients can book with. Deactivating a doctor keeps their appointment history."
        actions={
          <Button onClick={openAdd}>
            <PlusIcon className="h-4 w-4" />
            Add doctor
          </Button>
        }
      />

      {actionError ? (
        <div className="mb-4">
          <ErrorPanel message={actionError} onRetry={reload} />
        </div>
      ) : null}

      {loading ? <LoadingPanel label="Loading doctors…" /> : null}

      {!loading && error ? (
        <ErrorPanel message={error} onRetry={reload} />
      ) : null}

      {!loading && !error && doctors?.length === 0 ? (
        <EmptyState
          title="No doctors yet"
          description="Add your first doctor so the clinic can start taking appointments."
          action={
            <Button onClick={openAdd}>
              <PlusIcon className="h-4 w-4" />
              Add first doctor
            </Button>
          }
        />
      ) : null}

      {!loading && !error && doctors && doctors.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {doctors.map((doctor) => (
            <article
              key={doctor.id}
              className="flex flex-col rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h2 className="truncate text-base font-semibold text-slate-900">
                    {doctor.name}
                  </h2>
                  <p className="mt-1 text-sm text-slate-500">
                    {doctor.specialization}
                  </p>
                </div>
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-teal-50 text-sm font-semibold text-teal-700">
                  {doctor.name
                    .replace(/^Dr\.?\s*/i, "")
                    .split(/\s+/)
                    .slice(0, 2)
                    .map((part) => part[0]?.toUpperCase())
                    .join("")}
                </span>
              </div>

              <div className="mt-4 flex flex-wrap gap-1.5">
                {doctor.languages.length > 0 ? (
                  doctor.languages.map((language) => (
                    <span
                      key={language}
                      className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600"
                    >
                      {language}
                    </span>
                  ))
                ) : (
                  <span className="text-xs text-slate-400">
                    No languages listed
                  </span>
                )}
              </div>

              <p className="mt-5 text-sm text-slate-500">
                Consultation fee{" "}
                <span className="font-semibold text-slate-900">
                  {formatFee(doctor.fee)}
                </span>
              </p>

              <div className="mt-5 flex gap-2 border-t border-slate-100 pt-4">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => openEdit(doctor)}
                >
                  <EditIcon className="h-4 w-4" />
                  Edit
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-rose-600 hover:bg-rose-50 hover:text-rose-700"
                  onClick={() => setDeactivating(doctor)}
                >
                  <TrashIcon className="h-4 w-4" />
                  Deactivate
                </Button>
              </div>
            </article>
          ))}
        </div>
      ) : null}

      <Modal
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={editing ? "Edit doctor" : "Add doctor"}
        description={
          editing
            ? "Update the details patients and staff will see."
            : "Add a clinician to your clinic."
        }
      >
        <DoctorForm
          doctor={editing}
          onCancel={() => setFormOpen(false)}
          onSaved={async () => {
            setFormOpen(false);
            await reload();
          }}
        />
      </Modal>

      <ConfirmDialog
        open={Boolean(deactivating)}
        title="Deactivate doctor?"
        message={`${deactivating?.name ?? "This doctor"} will no longer appear for new bookings. Existing appointments remain in the clinic history.`}
        confirmLabel="Deactivate"
        danger
        busy={busy}
        onCancel={() => setDeactivating(null)}
        onConfirm={confirmDeactivate}
      />

      {clinic ? (
        <p className="mt-8 text-xs text-slate-400">
          All times use {clinic.timezone}.
        </p>
      ) : null}
    </div>
  );
}
