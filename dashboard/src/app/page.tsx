"use client";

import Link from "next/link";

import { useAuth } from "@/components/auth-provider";
import { ChevronRightIcon, StethoscopeIcon } from "@/components/icons";
import { OnboardingOverview } from "@/components/onboarding-overview";
import { ThemeToggle } from "@/components/theme-toggle";

export default function PublicHomePage() {
  const { staff, clinic } = useAuth();
  const isSignedIn = Boolean(staff);
  const dashboardHref = isSignedIn ? "/appointments" : "/login";
  const dashboardLabel = isSignedIn ? "Open dashboard" : "Sign in";

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="sticky top-0 z-30 border-b border-slate-200/80 bg-slate-50/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-5 sm:px-8">
          <Link
            className="flex items-center gap-3 rounded-xl focus:outline-none focus-visible:ring-4 focus-visible:ring-teal-600/15"
            href="/"
          >
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-900 text-teal-200 ring-1 ring-inset ring-slate-900/10">
              <StethoscopeIcon className="h-5 w-5" />
            </span>
            <span>
              <span className="block text-sm font-semibold tracking-tight text-slate-900">
                AI Receptionist
              </span>
              <span className="block text-[11px] text-slate-500">
                For modern clinics
              </span>
            </span>
          </Link>

          <nav className="hidden items-center gap-6 text-sm font-medium text-slate-600 md:flex">
            <a className="transition hover:text-slate-950" href="#features">
              Features
            </a>
            <a className="transition hover:text-slate-950" href="#how-it-works">
              How it works
            </a>
            <a className="transition hover:text-slate-950" href="#security">
              Security
            </a>
          </nav>

          <div className="flex items-center gap-2">
            <ThemeToggle />
            <Link
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-slate-800 focus:outline-none focus-visible:ring-4 focus-visible:ring-slate-900/15 dark:bg-teal-400 dark:text-slate-950 dark:hover:bg-teal-300"
              href={dashboardHref}
            >
              {dashboardLabel}
              <ChevronRightIcon className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-5 py-8 sm:px-8 sm:py-12">
        <OnboardingOverview
          clinicName={clinic?.name}
          mode="public"
          staffName={staff?.full_name}
        />
      </main>

      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 px-5 py-8 text-sm text-slate-500 sm:flex-row sm:items-center sm:justify-between sm:px-8">
          <div className="flex items-center gap-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-900 text-teal-200">
              <StethoscopeIcon className="h-[18px] w-[18px]" />
            </span>
            <div>
              <p className="font-semibold text-slate-900">AI Receptionist</p>
              <p className="text-xs">A calm front desk for every clinic.</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-4">
            <span className="text-xs">Built for Indian clinics</span>
            <Link
              className="font-semibold text-teal-700 transition hover:text-teal-800"
              href={dashboardHref}
            >
              {dashboardLabel}
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
