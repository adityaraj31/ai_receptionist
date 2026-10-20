"use client";

import { useState } from "react";

import { useAuth } from "@/components/auth-provider";
import {
  CheckIcon,
  CopyIcon,
  PlusIcon,
  RefreshIcon,
  TrashIcon,
  UsersIcon,
} from "@/components/icons";
import {
  Button,
  ConfirmDialog,
  EmptyState,
  ErrorPanel,
  inputClass,
  labelClass,
  LoadingPanel,
  Modal,
  PageHeader,
} from "@/components/ui";
import { api } from "@/lib/api-client";
import type {
  Staff,
  StaffInvitation,
  StaffInvitationCreated,
} from "@/lib/api-types";
import { getErrorMessage } from "@/lib/errors";
import { formatDateTime } from "@/lib/format";
import { useApi } from "@/lib/use-api";

export default function StaffPage() {
  const { staff, loading } = useAuth();

  if (loading) {
    return <LoadingPanel label="Loading clinic access…" />;
  }

  if (!staff) return null;

  if (staff.role !== "admin") {
    return (
      <div>
        <PageHeader
          eyebrow="Clinic access"
          title="Staff access"
          description="Only clinic admins can manage staff accounts."
        />
        <EmptyState
          title="Admin access required"
          description="Ask a clinic admin if you need an account created, deactivated, or promoted."
        />
      </div>
    );
  }

  return <StaffAdmin currentStaff={staff} />;
}

function StaffAdmin({ currentStaff }: { currentStaff: Staff }) {
  const { clinic } = useAuth();
  const timeZone = clinic?.timezone ?? "Asia/Kolkata";
  const {
    data,
    loading,
    error,
    reload,
  } = useApi(
    async () => {
      const [members, invitations] = await Promise.all([
        api.listStaff(),
        api.listStaffInvitations(),
      ]);
      return { members, invitations };
    },
    [],
  );

  const [inviteOpen, setInviteOpen] = useState(false);
  const [createdInvite, setCreatedInvite] =
    useState<StaffInvitationCreated | null>(null);
  const [copied, setCopied] = useState(false);
  const [confirming, setConfirming] = useState<{
    member: Staff;
    action: "deactivate" | "activate" | "promote" | "demote";
  } | null>(null);
  const [revoking, setRevoking] = useState<StaffInvitation | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  function openInvite() {
    setCreatedInvite(null);
    setCopied(false);
    setInviteOpen(true);
  }

  function closeInvite() {
    setInviteOpen(false);
    setCreatedInvite(null);
    setCopied(false);
  }

  async function copyLink() {
    if (!createdInvite) return;
    try {
      await navigator.clipboard.writeText(createdInvite.invite_url);
      setCopied(true);
    } catch {
      setActionError(
        "Could not copy automatically. Select the link and copy it manually.",
      );
    }
  }

  async function confirmMemberAction() {
    if (!confirming) return;
    const { member, action } = confirming;
    setBusy(true);
    setActionError(null);

    try {
      await api.updateStaff(member.id, {
        is_active:
          action === "deactivate"
            ? false
            : action === "activate"
              ? true
              : undefined,
        role:
          action === "promote"
            ? "admin"
            : action === "demote"
              ? "staff"
              : undefined,
      });
      setConfirming(null);
      await reload();
    } catch (caught) {
      setActionError(getErrorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function confirmRevoke() {
    if (!revoking) return;
    setBusy(true);
    setActionError(null);
    try {
      await api.revokeStaffInvitation(revoking.id);
      setRevoking(null);
      await reload();
    } catch (caught) {
      setActionError(getErrorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  const dialog = confirming ? memberDialog(confirming) : null;

  return (
    <div>
      <PageHeader
        eyebrow="Clinic access"
        title="Staff"
        description="Invite receptionists, promote admins, and turn access off when someone leaves. Every account is limited to this clinic."
        actions={
          <>
            <Button variant="secondary" onClick={reload} disabled={loading}>
              <RefreshIcon className="h-4 w-4" />
              Refresh
            </Button>
            <Button onClick={openInvite}>
              <PlusIcon className="h-4 w-4" />
              Invite staff
            </Button>
          </>
        }
      />

      {actionError ? (
        <div className="mb-4">
          <ErrorPanel message={actionError} />
        </div>
      ) : null}

      {loading ? <LoadingPanel label="Loading clinic access…" /> : null}

      {!loading && error ? (
        <ErrorPanel message={error} onRetry={reload} />
      ) : null}

      {!loading && !error && data ? (
        <div className="space-y-8">
          <section>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-base font-semibold text-slate-900">
                Staff accounts
              </h2>
              <span className="text-xs font-medium text-slate-500">
                {data.members.length}{" "}
                {data.members.length === 1 ? "account" : "accounts"}
              </span>
            </div>

            <ul className="divide-y divide-slate-100 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
              {data.members.map((member) => {
                const isSelf = member.id === currentStaff.id;
                return (
                  <li
                    key={member.id}
                    className="flex flex-col gap-4 p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5"
                  >
                    <div className="flex min-w-0 items-center gap-3">
                      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-teal-50 text-sm font-semibold text-teal-700">
                        {initials(member.full_name)}
                      </span>
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="truncate text-sm font-semibold text-slate-900">
                            {member.full_name}
                          </p>
                          {isSelf ? (
                            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-600">
                              You
                            </span>
                          ) : null}
                          <RoleBadge role={member.role} />
                          {!member.is_active ? (
                            <span className="rounded-full bg-rose-50 px-2 py-0.5 text-[11px] font-semibold text-rose-700 ring-1 ring-inset ring-rose-600/20">
                              Inactive
                            </span>
                          ) : null}
                        </div>
                        <p className="mt-1 truncate text-xs text-slate-500">
                          {member.email}
                        </p>
                      </div>
                    </div>

                    {!isSelf ? (
                      <div className="flex flex-wrap gap-2 sm:justify-end">
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() =>
                            setConfirming({
                              member,
                              action:
                                member.role === "admin" ? "demote" : "promote",
                            })
                          }
                        >
                          {member.role === "admin" ? "Make staff" : "Make admin"}
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className={
                            member.is_active
                              ? "text-rose-600 hover:bg-rose-50 hover:text-rose-700"
                              : "text-teal-700 hover:bg-teal-50 hover:text-teal-800"
                          }
                          onClick={() =>
                            setConfirming({
                              member,
                              action: member.is_active
                                ? "deactivate"
                                : "activate",
                            })
                          }
                        >
                          {member.is_active ? "Deactivate" : "Reactivate"}
                        </Button>
                      </div>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          </section>

          <section>
            <div className="mb-3 flex items-center justify-between">
              <div>
                <h2 className="text-base font-semibold text-slate-900">
                  Pending invitations
                </h2>
                <p className="mt-1 text-xs text-slate-500">
                  Invite links expire after 7 days. Email delivery is not
                  connected yet, so copy each link after creating it.
                </p>
              </div>
            </div>

            {data.invitations.length === 0 ? (
              <EmptyState
                title="No pending invitations"
                description="Invite a receptionist or another clinic admin. You will get a one-time link to share with them."
                action={
                  <Button onClick={openInvite}>
                    <PlusIcon className="h-4 w-4" />
                    Invite staff
                  </Button>
                }
              />
            ) : (
              <ul className="divide-y divide-slate-100 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
                {data.invitations.map((invitation) => (
                  <li
                    key={invitation.id}
                    className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5"
                  >
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="truncate text-sm font-semibold text-slate-900">
                          {invitation.full_name}
                        </p>
                        <RoleBadge role={invitation.role} />
                        <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-semibold text-amber-800 ring-1 ring-inset ring-amber-600/20">
                          Pending
                        </span>
                      </div>
                      <p className="mt-1 truncate text-xs text-slate-500">
                        {invitation.email} · Expires{" "}
                        {formatDateTime(invitation.expires_at, timeZone)}
                      </p>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="self-start text-rose-600 hover:bg-rose-50 hover:text-rose-700 sm:self-auto"
                      onClick={() => setRevoking(invitation)}
                    >
                      <TrashIcon className="h-4 w-4" />
                      Revoke
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      ) : null}

      <Modal
        open={inviteOpen || Boolean(createdInvite)}
        onClose={closeInvite}
        title={createdInvite ? "Invitation ready" : "Invite staff"}
        description={
          createdInvite
            ? "Share this one-time link with the new staff member."
            : "Create an account for a receptionist or another clinic admin."
        }
        footer={
          createdInvite ? (
            <Button onClick={closeInvite}>Done</Button>
          ) : undefined
        }
      >
        {createdInvite ? (
          <div className="space-y-4">
            <div className="rounded-xl border border-teal-200 bg-teal-50 p-4">
              <p className="text-sm font-semibold text-teal-900">
                {createdInvite.full_name}
              </p>
              <p className="mt-0.5 text-xs text-teal-800">
                {createdInvite.email} ·{" "}
                {createdInvite.role === "admin" ? "Admin" : "Staff"}
              </p>
              <p className="mt-2 text-xs text-teal-800">
                Expires {formatDateTime(createdInvite.expires_at, timeZone)}
              </p>
            </div>

            <div>
              <label className={labelClass} htmlFor="invite-url">
                Invitation link
              </label>
              <div className="flex flex-col gap-2 sm:flex-row">
                <input
                  id="invite-url"
                  className={inputClass}
                  value={createdInvite.invite_url}
                  readOnly
                  onFocus={(event) => event.currentTarget.select()}
                />
                <Button
                  variant="secondary"
                  onClick={copyLink}
                  className="shrink-0"
                >
                  {copied ? (
                    <CheckIcon className="h-4 w-4 text-teal-700" />
                  ) : (
                    <CopyIcon className="h-4 w-4" />
                  )}
                  {copied ? "Copied" : "Copy link"}
                </Button>
              </div>
              <p className="mt-2 text-xs text-slate-500">
                The link works once and can only be used to create this
                account. Send it over WhatsApp, SMS, or email manually.
              </p>
            </div>
          </div>
        ) : (
          <InviteForm
            onCancel={closeInvite}
            onCreated={(invitation) => {
              setCreatedInvite(invitation);
              setCopied(false);
              void reload();
            }}
          />
        )}
      </Modal>

      <ConfirmDialog
        open={Boolean(confirming)}
        title={dialog?.title ?? ""}
        message={dialog?.message ?? ""}
        confirmLabel={dialog?.confirmLabel ?? "Confirm"}
        danger={
          confirming?.action === "deactivate" ||
          confirming?.action === "demote"
        }
        busy={busy}
        onCancel={() => setConfirming(null)}
        onConfirm={confirmMemberAction}
      />

      <ConfirmDialog
        open={Boolean(revoking)}
        title="Revoke invitation?"
        message={`${revoking?.email ?? "This invitation"} will no longer be able to create an account. You can send a new invitation later.`}
        confirmLabel="Revoke"
        danger
        busy={busy}
        onCancel={() => setRevoking(null)}
        onConfirm={confirmRevoke}
      />
    </div>
  );
}

function InviteForm({
  onCancel,
  onCreated,
}: {
  onCancel: () => void;
  onCreated: (invitation: StaffInvitationCreated) => void;
}) {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"staff" | "admin">("staff");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);

    try {
      const invitation = await api.createStaffInvitation({
        full_name: fullName.trim(),
        email: email.trim(),
        role,
      });
      onCreated(invitation);
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
        <label className={labelClass} htmlFor="staff-name">
          Full name
        </label>
        <input
          id="staff-name"
          className={inputClass}
          value={fullName}
          onChange={(event) => setFullName(event.target.value)}
          placeholder="Anita Sharma"
          autoComplete="name"
          required
          maxLength={160}
        />
      </div>

      <div>
        <label className={labelClass} htmlFor="staff-email">
          Email
        </label>
        <input
          id="staff-email"
          className={inputClass}
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="anita@yourclinic.com"
          autoComplete="email"
          required
        />
      </div>

      <div>
        <label className={labelClass} htmlFor="staff-role">
          Access level
        </label>
        <select
          id="staff-role"
          className={inputClass}
          value={role}
          onChange={(event) =>
            setRole(event.target.value === "admin" ? "admin" : "staff")
          }
        >
          <option value="staff">Staff — appointments and schedules</option>
          <option value="admin">Admin — staff and clinic settings too</option>
        </select>
        <p className="mt-1 text-xs text-slate-500">
          Admins can invite staff, deactivate accounts, and change clinic
          details. Staff can manage doctors, availability, and appointments.
        </p>
      </div>

      <div className="flex flex-col-reverse gap-2 pt-2 sm:flex-row sm:justify-end">
        <Button variant="secondary" type="button" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" loading={busy}>
          <UsersIcon className="h-4 w-4" />
          Create invitation
        </Button>
      </div>
    </form>
  );
}

function RoleBadge({ role }: { role: string }) {
  return (
    <span
      className={
        role === "admin"
          ? "rounded-full bg-teal-50 px-2 py-0.5 text-[11px] font-semibold text-teal-800 ring-1 ring-inset ring-teal-600/20"
          : "rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-600"
      }
    >
      {role === "admin" ? "Admin" : "Staff"}
    </span>
  );
}

function memberDialog({
  member,
  action,
}: {
  member: Staff;
  action: "deactivate" | "activate" | "promote" | "demote";
}) {
  if (action === "deactivate") {
    return {
      title: "Deactivate access?",
      message: `${member.full_name} will be signed out and will not be able to sign in again until reactivated. Their appointment history stays intact.`,
      confirmLabel: "Deactivate",
    };
  }
  if (action === "activate") {
    return {
      title: "Reactivate access?",
      message: `${member.full_name} will be able to sign in to the clinic dashboard again.`,
      confirmLabel: "Reactivate",
    };
  }
  if (action === "promote") {
    return {
      title: "Make clinic admin?",
      message: `${member.full_name} will be able to invite staff, deactivate accounts, and change clinic settings.`,
      confirmLabel: "Make admin",
    };
  }
  return {
    title: "Change to staff access?",
    message: `${member.full_name} will lose access to staff management and clinic settings. Their other work is unchanged.`,
    confirmLabel: "Make staff",
  };
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}
