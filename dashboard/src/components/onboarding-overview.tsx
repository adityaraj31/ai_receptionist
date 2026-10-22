"use client";

import Link from "next/link";

import {
  ArrowUpRightIcon,
  CalendarIcon,
  ChartIcon,
  CheckIcon,
  ChevronRightIcon,
  ClockIcon,
  FaqIcon,
  MessageIcon,
  PhoneIcon,
  ShieldIcon,
  SparklesIcon,
  StethoscopeIcon,
  UsersIcon,
} from "@/components/icons";
import { cn } from "@/lib/cn";

const highlights = [
  {
    title: "Books the appointment",
    description:
      "Checks live doctor availability, books, reschedules, or cancels without double-booking.",
    href: "/appointments",
    icon: CalendarIcon,
    tone: "bg-teal-50 text-teal-700 ring-teal-600/15",
  },
  {
    title: "Answers clinic questions",
    description:
      "Uses your clinic FAQ knowledge base for timings, fees, doctors, location, and policies.",
    href: "/faqs",
    icon: FaqIcon,
    tone: "bg-indigo-50 text-indigo-700 ring-indigo-600/15",
  },
  {
    title: "Sends confirmations",
    description:
      "WhatsApp or SMS confirmations after booking, plus 24-hour and 2-hour reminders.",
    href: "/messaging",
    icon: MessageIcon,
    tone: "bg-amber-50 text-amber-700 ring-amber-600/15",
  },
  {
    title: "Hands off when it matters",
    description:
      "Warm-transfers urgent or complex calls, and takes a callback when the front desk is busy.",
    href: "/callbacks",
    icon: PhoneIcon,
    tone: "bg-rose-50 text-rose-700 ring-rose-600/15",
  },
  {
    title: "Speaks your caller’s language",
    description:
      "Detects Hindi, English, and Hinglish, then replies in the language the caller is using.",
    href: "/setup",
    icon: MessageIcon,
    tone: "bg-sky-50 text-sky-700 ring-sky-600/15",
  },
  {
    title: "Keeps every call visible",
    description:
      "Transcript, summary, outcome, language, duration, and cost land in one clinic workspace.",
    href: "/appointments",
    icon: ChartIcon,
    tone: "bg-violet-50 text-violet-700 ring-violet-600/15",
  },
];

const workflow = [
  {
    title: "A patient calls",
    description: "Your clinic number rings through LiveKit SIP, day or night.",
    icon: PhoneIcon,
  },
  {
    title: "The AI answers",
    description:
      "A natural voice greets the caller, discloses AI, and detects Hindi or English.",
    icon: StethoscopeIcon,
  },
  {
    title: "The work gets done",
    description:
      "The receptionist books, answers, takes a message, or transfers to your front desk.",
    icon: SparklesIcon,
  },
  {
    title: "You see the result",
    description:
      "Appointments, confirmations, transcripts, and post-call analytics update automatically.",
    icon: ChartIcon,
  },
];

const checklist = [
  {
    title: "Complete your clinic profile",
    description: "Name, timezone, address, phone, and front-desk number.",
    href: "/setup",
    icon: StethoscopeIcon,
  },
  {
    title: "Add doctors and working hours",
    description: "Set who patients can book and when slots are generated.",
    href: "/doctors",
    icon: UsersIcon,
  },
  {
    title: "Load your clinic FAQs",
    description: "Give the receptionist trusted answers about fees, timing, and policies.",
    href: "/faqs",
    icon: FaqIcon,
  },
  {
    title: "Turn on confirmations",
    description: "Choose WhatsApp or SMS, then review Hindi and English templates.",
    href: "/messaging",
    icon: MessageIcon,
  },
];

type OnboardingOverviewProps = {
  mode?: "app" | "public";
  staffName?: string | null;
  clinicName?: string | null;
};

export function OnboardingOverview({
  mode = "app",
  staffName,
  clinicName,
}: OnboardingOverviewProps) {
  const isPublic = mode === "public";
  const firstName = staffName?.split(/\s+/)[0] ?? "there";

  return (
    <div className="space-y-8">
      <section className="relative overflow-hidden rounded-[2rem] bg-slate-950 text-white shadow-xl shadow-slate-900/10">
        <div
          className="absolute inset-0"
          style={{
            backgroundImage:
              "radial-gradient(circle at 15% 12%, rgba(13,148,136,0.55) 0, transparent 34%), radial-gradient(circle at 85% 78%, rgba(15,118,110,0.35) 0, transparent 38%)",
          }}
        />
        <div
          className="absolute inset-0 opacity-[0.08]"
          style={{
            backgroundImage:
              "linear-gradient(rgba(255,255,255,0.6) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.6) 1px, transparent 1px)",
            backgroundSize: "44px 44px",
          }}
        />

        <div className="relative grid gap-10 px-6 py-10 sm:px-10 sm:py-12 lg:grid-cols-[1.05fr_0.95fr] lg:items-center lg:px-12 lg:py-14">
          <div>
            <p className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.16em] text-teal-200">
              <SparklesIcon className="h-3.5 w-3.5" />
              Product overview
            </p>
            <h1 className="mt-6 max-w-2xl text-4xl font-semibold leading-[1.05] tracking-tight sm:text-5xl">
              Your clinic, answered.
            </h1>
            <p className="mt-5 max-w-xl text-base leading-7 text-slate-300">
              {isPublic ? (
                <>
                  A voice-first front desk for modern clinics. The receptionist
                  answers every call in Hindi or English, books appointments,
                  and hands your team a clean record of the conversation.
                </>
              ) : (
                <>
                  Welcome{firstName !== "there" ? `, ${firstName}` : ""}. Meet
                  the AI receptionist for {clinicName ?? "your clinic"} — a
                  calm, always-on front desk that answers calls, books
                  appointments, and keeps your team in the loop.
                </>
              )}
            </p>

            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                className="inline-flex items-center justify-center gap-2 rounded-xl bg-teal-400 px-4 py-2.5 text-sm font-semibold text-slate-950 shadow-sm transition hover:bg-teal-300 focus:outline-none focus-visible:ring-4 focus-visible:ring-teal-300/40"
                href={isPublic ? "/login" : "/appointments"}
              >
                {isPublic ? "Sign in to your clinic" : "Go to appointments"}
                <ChevronRightIcon className="h-4 w-4" />
              </Link>
              <Link
                className="inline-flex items-center justify-center gap-2 rounded-xl border border-white/20 bg-white/5 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-white/10 focus:outline-none focus-visible:ring-4 focus-visible:ring-white/20"
                href={isPublic ? "#features" : "/setup"}
              >
                {isPublic ? "Explore the product" : "Review clinic setup"}
              </Link>
            </div>

            <div className="mt-8 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-slate-400">
              <span className="inline-flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-teal-400" />
                Built for Indian clinics
              </span>
              <span className="inline-flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-teal-400" />
                Hindi + English
              </span>
              <span className="inline-flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-teal-400" />
                Every call logged
              </span>
            </div>
          </div>

          <div className="relative">
            <div className="rounded-[1.75rem] border border-white/10 bg-white/[0.07] p-3 shadow-2xl backdrop-blur">
              <div className="rounded-[1.35rem] bg-slate-900/85 p-5 ring-1 ring-inset ring-white/10">
                <div className="flex items-center justify-between gap-4">
                  <div className="flex items-center gap-3">
                    <span className="relative flex h-10 w-10 items-center justify-center rounded-full bg-teal-400/15 text-teal-300 ring-1 ring-inset ring-teal-300/25">
                      <PhoneIcon className="h-5 w-5" />
                      <span className="absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full border-2 border-slate-900 bg-emerald-400" />
                    </span>
                    <div>
                      <p className="text-sm font-semibold text-white">
                        Incoming call
                      </p>
                      <p className="text-xs text-slate-400">Live receptionist</p>
                    </div>
                  </div>
                  <span className="rounded-full bg-white/5 px-2.5 py-1 text-[11px] font-medium text-slate-300 ring-1 ring-inset ring-white/10">
                    00:42
                  </span>
                </div>

                <div className="mt-5 rounded-2xl bg-slate-950/60 p-4 ring-1 ring-inset ring-white/10">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2.5">
                      <span className="flex h-8 w-8 items-center justify-center rounded-full bg-amber-400/15 text-[11px] font-semibold text-amber-200">
                        AS
                      </span>
                      <div>
                        <p className="text-xs font-medium text-white">
                          +91 ••••• ••210
                        </p>
                        <p className="text-[11px] text-slate-500">New caller</p>
                      </div>
                    </div>
                    <span className="rounded-full bg-teal-400/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide text-teal-300 ring-1 ring-inset ring-teal-400/20">
                      Hindi / English
                    </span>
                  </div>

                  <div className="mt-4 space-y-2.5">
                    <div className="max-w-[85%] rounded-2xl rounded-tl-md bg-white/10 px-3.5 py-2.5 text-xs leading-5 text-slate-200">
                      Kal subah appointment milega?
                    </div>
                    <div className="ml-auto max-w-[88%] rounded-2xl rounded-tr-md bg-teal-500/15 px-3.5 py-2.5 text-xs leading-5 text-teal-50 ring-1 ring-inset ring-teal-400/15">
                      Ji, 10:30 baje Dr. Rao available hain. Book kar doon?
                    </div>
                    <div className="max-w-[70%] rounded-2xl rounded-tl-md bg-white/10 px-3.5 py-2.5 text-xs leading-5 text-slate-200">
                      Haan, please.
                    </div>
                  </div>

                  <div className="mt-4 flex items-center gap-2 rounded-xl border border-teal-400/15 bg-teal-400/10 px-3 py-2 text-[11px] font-medium text-teal-200">
                    <CheckIcon className="h-3.5 w-3.5" />
                    Appointment booked · WhatsApp confirmation queued
                  </div>
                </div>

                <div className="mt-4 flex items-end justify-between gap-3">
                  <div className="flex items-end gap-1" aria-hidden="true">
                    {[10, 18, 26, 16, 32, 22, 14, 28, 20, 12, 24, 18].map(
                      (height, index) => (
                        <span
                          className="w-1 rounded-full bg-teal-400/50"
                          key={index}
                          style={{ height }}
                        />
                      ),
                    )}
                  </div>
                  <span className="text-[10px] uppercase tracking-[0.16em] text-slate-500">
                    Voice pipeline live
                  </span>
                </div>
              </div>
            </div>

            <div className="absolute -bottom-4 -left-4 hidden rounded-2xl border border-white/10 bg-slate-900/90 px-4 py-3 shadow-xl backdrop-blur sm:block">
              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">
                After the call
              </p>
              <p className="mt-1 text-sm font-semibold text-white">
                Transcript + summary ready
              </p>
            </div>
          </div>
        </div>
      </section>

      <section
        aria-label="Product at a glance"
        className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"
      >
        {[
          { value: "24×7", label: "Always answering", icon: ClockIcon },
          { value: "2", label: "Hindi + English", icon: MessageIcon },
          { value: "<1s", label: "Voice latency target", icon: SparklesIcon },
          { value: "1", label: "Clinic workspace", icon: StethoscopeIcon },
        ].map((item) => (
          <div
            className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-4 py-4 shadow-sm"
            key={item.label}
          >
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-50 text-slate-600 ring-1 ring-inset ring-slate-200">
              <item.icon className="h-5 w-5" />
            </span>
            <div>
              <p className="text-lg font-semibold tracking-tight text-slate-900">
                {item.value}
              </p>
              <p className="text-xs text-slate-500">{item.label}</p>
            </div>
          </div>
        ))}
      </section>

      <section className="scroll-mt-24" id="features">
        <div className="mb-5 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-teal-700">
              One front desk
            </p>
            <h2 className="mt-1 text-2xl font-semibold tracking-tight text-slate-900">
              Everything the receptionist handles
            </h2>
          </div>
          <p className="max-w-md text-sm text-slate-500">
            A voice-first workflow, backed by the same clinic data your staff
            already manages.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {highlights.map((feature) => (
            <Link
              className="group flex flex-col rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-md focus:outline-none focus-visible:ring-4 focus-visible:ring-teal-600/15"
              href={feature.href}
              key={feature.title}
            >
              <div className="flex items-start justify-between gap-3">
                <span
                  className={cn(
                    "flex h-10 w-10 items-center justify-center rounded-xl ring-1 ring-inset",
                    feature.tone,
                  )}
                >
                  <feature.icon className="h-5 w-5" />
                </span>
                <ArrowUpRightIcon className="h-4 w-4 text-slate-300 transition group-hover:text-teal-700" />
              </div>
              <h3 className="mt-4 text-sm font-semibold text-slate-900">
                {feature.title}
              </h3>
              <p className="mt-1.5 text-sm leading-6 text-slate-500">
                {feature.description}
              </p>
            </Link>
          ))}
        </div>
      </section>

      <section className="overflow-hidden rounded-[2rem] bg-gradient-to-br from-teal-950 via-slate-950 to-slate-900 text-white shadow-xl shadow-slate-900/10">
        <div className="grid gap-8 p-6 sm:p-10 lg:grid-cols-[0.95fr_1.05fr] lg:items-center lg:p-12">
          <div>
            <p className="inline-flex items-center gap-2 rounded-full border border-teal-300/20 bg-teal-300/10 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.16em] text-teal-200">
              <SparklesIcon className="h-3.5 w-3.5" />
              Highlighted feature
            </p>
            <h2 className="mt-5 max-w-xl text-3xl font-semibold tracking-tight sm:text-4xl">
              Every call becomes a coaching moment.
            </h2>
            <p className="mt-4 max-w-xl text-sm leading-7 text-slate-300">
              After the caller hangs up, the receptionist turns the conversation
              into structured clinic intelligence: a readable summary, a clear
              outcome, provider cost, and an automated quality review.
            </p>
            <ul className="mt-6 space-y-3 text-sm text-slate-200">
              {[
                "Transcript stored against the right clinic and call",
                "LLM summary with a safe heuristic fallback",
                "Correctness, politeness, and missed-handoff scoring",
                "Recording, usage, and cost in one post-call record",
              ].map((item) => (
                <li className="flex items-start gap-3" key={item}>
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-teal-400/15 text-teal-300">
                    <CheckIcon className="h-3 w-3" />
                  </span>
                  {item}
                </li>
              ))}
            </ul>
          </div>

          <div className="rounded-[1.5rem] border border-white/10 bg-white/[0.06] p-3 backdrop-blur">
            <div className="rounded-[1.15rem] bg-slate-950/70 p-5 ring-1 ring-inset ring-white/10">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-teal-400/15 text-teal-300 ring-1 ring-inset ring-teal-300/20">
                    <ChartIcon className="h-[18px] w-[18px]" />
                  </span>
                  <div>
                    <p className="text-sm font-semibold text-white">
                      Sample call report
                    </p>
                    <p className="text-[11px] text-slate-500">
                      Illustrative post-call view
                    </p>
                  </div>
                </div>
                <span className="rounded-full bg-teal-400/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide text-teal-300 ring-1 ring-inset ring-teal-400/20">
                  Booked
                </span>
              </div>

              <div className="mt-5 rounded-xl border border-white/10 bg-white/[0.04] p-3.5">
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                  Summary
                </p>
                <p className="mt-1.5 text-xs leading-5 text-slate-300">
                  Caller asked for a morning appointment and booked with Dr.
                  Rao. A WhatsApp confirmation was sent.
                </p>
              </div>

              <div className="mt-3 grid grid-cols-3 gap-2">
                {[
                  { label: "Correctness", value: "92%" },
                  { label: "Politeness", value: "98%" },
                  { label: "Handoffs", value: "0" },
                ].map((metric) => (
                  <div
                    className="rounded-xl border border-white/10 bg-white/[0.04] px-3 py-3"
                    key={metric.label}
                  >
                    <p className="text-base font-semibold text-white">
                      {metric.value}
                    </p>
                    <p className="mt-0.5 text-[10px] text-slate-500">
                      {metric.label}
                    </p>
                  </div>
                ))}
              </div>

              <div className="mt-3 flex items-center justify-between rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2.5 text-[11px]">
                <span className="text-slate-400">Estimated provider cost</span>
                <span className="font-semibold text-teal-200">₹4.82</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="scroll-mt-24" id="how-it-works">
        <div className="mb-5">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-teal-700">
            How it works
          </p>
          <h2 className="mt-1 text-2xl font-semibold tracking-tight text-slate-900">
            From ring to record
          </h2>
        </div>

        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {workflow.map((step, index) => (
            <div
              className="relative rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
              key={step.title}
            >
              <div className="flex items-center justify-between">
                <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-900 text-white">
                  <step.icon className="h-[18px] w-[18px]" />
                </span>
                <span className="text-xs font-semibold text-slate-300">
                  0{index + 1}
                </span>
              </div>
              <h3 className="mt-4 text-sm font-semibold text-slate-900">
                {step.title}
              </h3>
              <p className="mt-1.5 text-sm leading-6 text-slate-500">
                {step.description}
              </p>
            </div>
          ))}
        </div>
      </section>

      <section
        className="scroll-mt-24 grid gap-6 lg:grid-cols-[1.05fr_0.95fr]"
        id="security"
      >
        <div className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-teal-700">
            {isPublic ? "Inside the dashboard" : "Launch checklist"}
          </p>
          <h2 className="mt-1 text-2xl font-semibold tracking-tight text-slate-900">
            {isPublic
              ? "Set up once, answer every call"
              : "Make the receptionist yours"}
          </h2>
          <p className="mt-2 text-sm text-slate-500">
            {isPublic
              ? "Sign in to connect your doctors, hours, FAQs, and confirmations. The receptionist starts using them immediately."
              : "Four short steps turn a generic assistant into your clinic&apos;s front desk."}
          </p>

          <div className="mt-6 space-y-2">
            {checklist.map((item) => (
              <Link
                className="group flex items-center gap-3 rounded-xl border border-transparent px-2 py-3 transition hover:border-slate-200 hover:bg-slate-50 focus:outline-none focus-visible:ring-4 focus-visible:ring-teal-600/15"
                href={isPublic ? "/login" : item.href}
                key={item.title}
              >
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-teal-50 text-teal-700 ring-1 ring-inset ring-teal-600/15">
                  <item.icon className="h-[18px] w-[18px]" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-semibold text-slate-900">
                    {item.title}
                  </span>
                  <span className="mt-0.5 block text-xs leading-5 text-slate-500">
                    {item.description}
                  </span>
                </span>
                <ChevronRightIcon className="h-4 w-4 text-slate-300 transition group-hover:translate-x-0.5 group-hover:text-teal-700" />
              </Link>
            ))}
          </div>
        </div>

        <div className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-teal-700">
            Under the hood
          </p>
          <h2 className="mt-1 text-2xl font-semibold tracking-tight text-slate-900">
            Clinic-first by design
          </h2>
          <p className="mt-2 text-sm text-slate-500">
            A production-minded stack built for real phone calls, not a demo
            chat window.
          </p>

          <div className="mt-6 space-y-4">
            {[
              {
                icon: SparklesIcon,
                title: "Live voice pipeline",
                description:
                  "SIP to LiveKit, streaming STT, an LLM with tools, and natural TTS — tuned for barge-in and short spoken replies.",
              },
              {
                icon: ShieldIcon,
                title: "Clinic-scoped access",
                description:
                  "Staff use JWT sessions; the voice agent uses a clinic-scoped service key. Every query stays inside the clinic.",
              },
              {
                icon: ChartIcon,
                title: "Operational records",
                description:
                  "Appointments, messages, callbacks, transcripts, costs, and evaluations share one Postgres source of truth.",
              },
            ].map((item) => (
              <div className="flex gap-3" key={item.title}>
                <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-slate-900 text-white">
                  <item.icon className="h-[18px] w-[18px]" />
                </span>
                <div>
                  <h3 className="text-sm font-semibold text-slate-900">
                    {item.title}
                  </h3>
                  <p className="mt-1 text-xs leading-5 text-slate-500">
                    {item.description}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="rounded-[2rem] border border-teal-200 bg-teal-50 px-6 py-8 text-center sm:px-10">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-teal-700">
          {isPublic ? "Your front desk, always on" : "Ready when you are"}
        </p>
        <h2 className="mt-2 text-2xl font-semibold tracking-tight text-teal-950 sm:text-3xl">
          Let the next call take care of itself.
        </h2>
        <p className="mx-auto mt-3 max-w-xl text-sm leading-6 text-teal-900/70">
          {isPublic
            ? "Sign in to your clinic workspace, or explore how the receptionist handles a call from ring to record."
            : "Start with today&apos;s appointments, or tighten the setup so every answer sounds like your clinic."}
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-3">
          <Link
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-teal-700 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-teal-800 focus:outline-none focus-visible:ring-4 focus-visible:ring-teal-600/25"
            href={isPublic ? "/login" : "/appointments"}
          >
            {isPublic ? "Sign in to your clinic" : "View appointments"}
            <ChevronRightIcon className="h-4 w-4" />
          </Link>
          <Link
            className="inline-flex items-center justify-center gap-2 rounded-xl border border-teal-300 bg-white px-4 py-2.5 text-sm font-semibold text-teal-800 shadow-sm transition hover:bg-teal-100 focus:outline-none focus-visible:ring-4 focus-visible:ring-teal-600/15"
            href={isPublic ? "#how-it-works" : "/setup"}
          >
            {isPublic ? "See how it works" : "Open clinic setup"}
          </Link>
        </div>
      </section>
    </div>
  );
}
