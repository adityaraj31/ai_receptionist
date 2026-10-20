"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { StethoscopeIcon } from "@/components/icons";
import {
  Button,
  ErrorPanel,
  inputClass,
  labelClass,
  Spinner,
} from "@/components/ui";
import { getErrorMessage } from "@/lib/errors";

export default function LoginPage() {
  const { staff, loading, login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && staff) {
      router.replace("/appointments");
    }
  }, [loading, staff, router]);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);

    try {
      await login(email.trim(), password);
      router.replace("/appointments");
    } catch (caught) {
      setError(getErrorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50">
        <Spinner className="h-6 w-6 text-teal-700" />
      </div>
    );
  }

  return (
    <main className="grid min-h-screen bg-slate-50 lg:grid-cols-[1.1fr_1fr]">
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
            Your clinic desk, without the busywork.
          </h1>
          <p className="mt-4 max-w-md text-base leading-7 text-slate-300">
            Manage doctors, weekly hours, days off, and the day&apos;s
            appointments from one calm workspace.
          </p>
        </div>
        <p className="relative text-sm text-slate-400">
          Clinic staff access only. Calls are handled by your clinic&apos;s AI
          receptionist.
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

          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-teal-700">
            Clinic admin
          </p>
          <h2 className="mt-2 text-3xl font-semibold tracking-tight text-slate-900">
            Sign in
          </h2>
          <p className="mt-2 text-sm text-slate-500">
            Use the staff email and password provided for your clinic.
          </p>

          <form className="mt-8 space-y-5" onSubmit={handleSubmit}>
            {error ? <ErrorPanel message={error} /> : null}

            <div>
              <label className={labelClass} htmlFor="email">
                Email
              </label>
              <input
                id="email"
                className={inputClass}
                type="email"
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="staff@yourclinic.com"
                required
              />
            </div>

            <div>
              <label className={labelClass} htmlFor="password">
                Password
              </label>
              <input
                id="password"
                className={inputClass}
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
            </div>

            <Button className="w-full" type="submit" loading={busy}>
              Sign in
            </Button>
          </form>
        </div>
      </section>
    </main>
  );
}
