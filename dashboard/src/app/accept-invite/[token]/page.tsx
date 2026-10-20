"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { StethoscopeIcon } from "@/components/icons";
import {
  Button,
  ErrorPanel,
  inputClass,
  labelClass,
  LoadingPanel,
} from "@/components/ui";
import { api } from "@/lib/api-client";
import { getErrorMessage } from "@/lib/errors";
import { useApi } from "@/lib/use-api";

export default function AcceptInvitePage() {
  const params = useParams<{ token: string }>();
  const token = typeof params.token === "string" ? params.token : "";
  const router = useRouter();
  const { staff, establishSession } = useAuth();
  const { data, loading, error } = useApi(
    () => api.previewInvitation(token),
    [token],
  );

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);

    if (password.length < 12) {
      setFormError("Use at least 12 characters for your password.");
      return;
    }
    if (password !== confirmPassword) {
      setFormError("The passwords do not match.");
      return;
    }

    setBusy(true);
    try {
      const response = await api.acceptInvitation(token, password);
      await establishSession(response);
      router.replace("/appointments");
    } catch (caught) {
      setFormError(getErrorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="grid min-h-screen bg-slate-50 lg:grid-cols-[1fr_1.1fr]">
      <section className="relative hidden overflow-hidden bg-slate-900 p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <div
          className="absolute inset-0 opacity-40"
          style={{
            backgroundImage:
              "radial-gradient(circle at 20% 10%, #0f766e 0, transparent 42%), radial-gradient(circle at 80% 80%, #115e59 0, transparent 38%)",
          }}
        />
        <div className="relative">
          <div className="flex items-center gap-3">
            <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-white/10 text-teal-200 ring-1 ring-inset ring-white/20">
              <StethoscopeIcon className="h-6 w-6" />
            </span>
            <span className="text-lg font-semibold">AI Receptionist</span>
          </div>
          <h1 className="mt-16 max-w-lg text-4xl font-semibold leading-tight tracking-tight">
            Join your clinic&apos;s front desk.
          </h1>
          <p className="mt-4 max-w-md text-base leading-7 text-slate-300">
            Set a password to start managing appointments, doctors, and clinic
            hours.
          </p>
        </div>
        <p className="relative text-sm text-slate-400">
          This invitation is tied to one email address and expires after 7 days.
        </p>
      </section>

      <section className="flex items-center justify-center px-5 py-12 sm:px-8">
        <div className="w-full max-w-md">
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-teal-700 text-white">
              <StethoscopeIcon className="h-6 w-6" />
            </span>
            <span className="text-lg font-semibold text-slate-900">
              AI Receptionist
            </span>
          </div>

          {loading ? <LoadingPanel label="Checking your invitation…" /> : null}

          {!loading && error ? (
            <div className="space-y-5">
              <ErrorPanel message={error} />
              <p className="text-sm text-slate-500">
                Ask your clinic admin for a new invitation, or{" "}
                <Link
                  className="font-semibold text-teal-700 hover:text-teal-800"
                  href="/login"
                >
                  sign in
                </Link>{" "}
                if you already have an account.
              </p>
            </div>
          ) : null}

          {!loading && !error && data ? (
            <>
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-teal-700">
                {data.clinic_name}
              </p>
              <h2 className="mt-2 text-3xl font-semibold tracking-tight text-slate-900">
                Create your account
              </h2>
              <p className="mt-2 text-sm text-slate-500">
                You&apos;re joining as{" "}
                <span className="font-medium text-slate-700">
                  {data.full_name}
                </span>{" "}
                ({data.email}) with{" "}
                {data.role === "admin" ? "admin" : "staff"} access.
              </p>

              {staff ? (
                <p className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
                  You are currently signed in as {staff.email}. Accepting this
                  invitation will switch this browser to the new account.
                </p>
              ) : null}

              <form className="mt-8 space-y-5" onSubmit={handleSubmit}>
                {formError ? <ErrorPanel message={formError} /> : null}

                <div>
                  <label className={labelClass} htmlFor="new-password">
                    New password
                  </label>
                  <input
                    id="new-password"
                    className={inputClass}
                    type="password"
                    autoComplete="new-password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    minLength={12}
                    maxLength={128}
                    required
                  />
                  <p className="mt-1 text-xs text-slate-500">
                    At least 12 characters.
                  </p>
                </div>

                <div>
                  <label className={labelClass} htmlFor="confirm-password">
                    Confirm password
                  </label>
                  <input
                    id="confirm-password"
                    className={inputClass}
                    type="password"
                    autoComplete="new-password"
                    value={confirmPassword}
                    onChange={(event) =>
                      setConfirmPassword(event.target.value)
                    }
                    minLength={12}
                    maxLength={128}
                    required
                  />
                </div>

                <Button className="w-full" type="submit" loading={busy}>
                  Create account
                </Button>
              </form>
            </>
          ) : null}

          <p className="mt-8 text-center text-xs text-slate-400">
            Already have an account?{" "}
            <Link
              className="font-medium text-slate-600 hover:text-slate-900"
              href="/login"
            >
              Sign in
            </Link>
          </p>
        </div>
      </section>
    </main>
  );
}
