"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import {
  CalendarIcon,
  ClockIcon,
  FaqIcon,
  LogoutIcon,
  MenuIcon,
  MessageIcon,
  PhoneIcon,
  SettingsIcon,
  StethoscopeIcon,
  UsersIcon,
} from "@/components/icons";
import { cn } from "@/lib/cn";
import { api } from "@/lib/api-client";
import { isSetupSkipped } from "@/lib/session";
import { Spinner } from "@/components/ui";

const navigation: {
  href: string;
  label: string;
  icon: (props: { className?: string }) => React.ReactNode;
  adminOnly?: boolean;
}[] = [
  { href: "/appointments", label: "Appointments", icon: CalendarIcon },
  { href: "/callbacks", label: "Callbacks", icon: PhoneIcon },
  { href: "/doctors", label: "Doctors", icon: StethoscopeIcon },
  { href: "/availability", label: "Availability", icon: ClockIcon },
  { href: "/faqs", label: "FAQs", icon: FaqIcon },
  { href: "/messaging", label: "Messaging", icon: MessageIcon },
  { href: "/staff", label: "Staff access", icon: UsersIcon, adminOnly: true },
  { href: "/setup", label: "Clinic setup", icon: SettingsIcon },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const { staff, clinic, loading, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const setupChecked = useRef(false);

  useEffect(() => {
    if (!loading && !staff) {
      router.replace("/login");
    }
  }, [loading, staff, router]);

  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!staff || setupChecked.current) return;
    setupChecked.current = true;

    void api
      .listDoctors()
      .then((doctors) => {
        if (doctors.length === 0 && !isSetupSkipped()) {
          router.replace("/setup");
        }
      })
      .catch(() => {
        setupChecked.current = false;
      });
  }, [staff, router]);

  if (loading || !staff) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50">
        <div className="flex items-center gap-3 text-sm font-medium text-slate-500">
          <Spinner className="h-5 w-5 text-teal-700" />
          Loading your clinic…
        </div>
      </div>
    );
  }

  const sidebar = (
    <div className="flex h-full flex-col bg-slate-900 text-slate-300">
      <div className="border-b border-white/10 px-5 py-5">
        <Link href="/appointments" className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-teal-500/15 text-teal-300 ring-1 ring-inset ring-teal-400/25">
            <StethoscopeIcon className="h-5 w-5" />
          </span>
          <span>
            <span className="block text-sm font-semibold text-white">
              AI Receptionist
            </span>
            <span className="block truncate text-xs text-slate-400">
              {clinic?.name ?? "Clinic admin"}
            </span>
          </span>
        </Link>
      </div>

      <nav className="flex-1 space-y-1 px-3 py-4" aria-label="Main">
        {navigation
          .filter((item) => !item.adminOnly || staff.role === "admin")
          .map((item) => {
            const Icon = item.icon;
            const active =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);

            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition",
                  active
                    ? "bg-white/10 text-white shadow-sm"
                    : "text-slate-400 hover:bg-white/5 hover:text-white",
                )}
              >
                <Icon className="h-5 w-5" />
                {item.label}
              </Link>
            );
          })}
      </nav>

      <div className="border-t border-white/10 p-3">
        <div className="mb-2 flex items-center gap-3 rounded-xl px-3 py-2">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-teal-500/15 text-sm font-semibold text-teal-200">
            {initials(staff.full_name)}
          </span>
          <span className="min-w-0">
            <span className="block truncate text-sm font-medium text-white">
              {staff.full_name}
            </span>
            <span className="block truncate text-xs text-slate-400">
              {staff.role}
            </span>
          </span>
        </div>
        <button
          className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium text-slate-400 transition hover:bg-white/5 hover:text-white"
          onClick={logout}
          type="button"
        >
          <LogoutIcon className="h-5 w-5" />
          Sign out
        </button>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-slate-50">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 lg:block">
        {sidebar}
      </aside>

      {mobileOpen ? (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            className="absolute inset-0 bg-slate-950/50"
            onClick={() => setMobileOpen(false)}
            aria-label="Close navigation"
            type="button"
          />
          <aside className="relative h-full w-72 max-w-[85vw] shadow-2xl">
            {sidebar}
          </aside>
        </div>
      ) : null}

      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/90 backdrop-blur">
          <div className="flex h-16 items-center gap-3 px-4 sm:px-6 lg:px-8">
            <button
              className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 lg:hidden"
              onClick={() => setMobileOpen(true)}
              aria-label="Open navigation"
              type="button"
            >
              <MenuIcon className="h-5 w-5" />
            </button>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold text-slate-900">
                {clinic?.name ?? "Clinic"}
              </p>
              <p className="truncate text-xs text-slate-500">
                {clinic?.timezone ?? "Clinic timezone"}
              </p>
            </div>
            <span className="hidden rounded-full bg-slate-100 px-3 py-1.5 text-xs font-medium text-slate-600 sm:inline">
              {staff.full_name}
            </span>
          </div>
        </header>

        <main className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 sm:py-8 lg:px-8">
          {children}
        </main>
      </div>
    </div>
  );
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
}

