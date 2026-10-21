"use client";

import { useState, type ChangeEvent } from "react";

import { FaqForm } from "@/components/faq-form";
import {
  EditIcon,
  PlusIcon,
  RefreshIcon,
  TrashIcon,
  UploadIcon,
} from "@/components/icons";
import {
  Button,
  ConfirmDialog,
  EmptyState,
  ErrorPanel,
  LoadingPanel,
  Modal,
  PageHeader,
  inputClass,
} from "@/components/ui";
import { api } from "@/lib/api-client";
import type { Faq } from "@/lib/api-types";
import { cn } from "@/lib/cn";
import { getErrorMessage } from "@/lib/errors";
import { useApi } from "@/lib/use-api";

type ImportRow = { question: string; answer: string };

export default function FaqsPage() {
  const {
    data: faqs,
    loading,
    error,
    reload,
  } = useApi(() => api.listFaqs(true), []);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Faq | null>(null);
  const [deactivating, setDeactivating] = useState<Faq | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [showInactive, setShowInactive] = useState(true);
  const [busy, setBusy] = useState(false);
  const [togglingId, setTogglingId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  function openAdd() {
    setEditing(null);
    setFormOpen(true);
  }

  function openEdit(faq: Faq) {
    setEditing(faq);
    setFormOpen(true);
  }

  async function confirmDeactivate() {
    if (!deactivating) return;
    setBusy(true);
    setActionError(null);
    try {
      await api.deactivateFaq(deactivating.id);
      setDeactivating(null);
      await reload();
    } catch (caught) {
      setActionError(getErrorMessage(caught));
    } finally {
      setBusy(false);
    }
  }

  async function toggleActive(faq: Faq) {
    setTogglingId(faq.id);
    setActionError(null);
    try {
      await api.updateFaq(faq.id, { is_active: !faq.is_active });
      await reload();
    } catch (caught) {
      setActionError(getErrorMessage(caught));
    } finally {
      setTogglingId(null);
    }
  }

  const activeCount = faqs?.filter((faq) => faq.is_active).length ?? 0;
  const visible = showInactive
    ? faqs
    : faqs?.filter((faq) => faq.is_active);

  return (
    <div>
      <PageHeader
        eyebrow="Clinic knowledge"
        title="FAQs"
        description="The voice agent answers caller questions from this list. Keep answers short and factual. Changes are searchable immediately."
        actions={
          <>
            <Button
              variant="secondary"
              onClick={() => setImportOpen(true)}
            >
              <UploadIcon className="h-4 w-4" />
              Upload
            </Button>
            <Button onClick={openAdd}>
              <PlusIcon className="h-4 w-4" />
              Add FAQ
            </Button>
          </>
        }
      />

      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-slate-500">
          {faqs ? `${activeCount} active of ${faqs.length}` : "Loading FAQs"}
        </p>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-slate-300 text-teal-700 focus:ring-teal-600"
              checked={showInactive}
              onChange={(event) => setShowInactive(event.target.checked)}
            />
            Show inactive
          </label>
          <Button variant="ghost" size="sm" onClick={reload} disabled={loading}>
            <RefreshIcon className="h-4 w-4" />
            Refresh
          </Button>
        </div>
      </div>

      {actionError ? (
        <div className="mb-4">
          <ErrorPanel message={actionError} onRetry={reload} />
        </div>
      ) : null}

      {loading ? <LoadingPanel label="Loading FAQs…" /> : null}

      {!loading && error ? (
        <ErrorPanel message={error} onRetry={reload} />
      ) : null}

      {!loading && !error && !visible?.length ? (
        <EmptyState
          title={faqs?.length ? "No active FAQs" : "No FAQs yet"}
          description={
            faqs?.length
              ? "Turn on “Show inactive” to see hidden answers, or add a new one."
              : "Add the questions callers ask most: timings, address, fees, doctors, parking, and payments."
          }
          action={
            <Button onClick={openAdd}>
              <PlusIcon className="h-4 w-4" />
              Add first FAQ
            </Button>
          }
        />
      ) : null}

      {!loading && !error && visible && visible.length > 0 ? (
        <div className="grid gap-4 lg:grid-cols-2">
          {visible.map((faq) => (
            <article
              key={faq.id}
              className={cn(
                "flex flex-col rounded-2xl border border-slate-200 bg-white p-5 shadow-sm",
                !faq.is_active && "opacity-70",
              )}
            >
              <div className="flex items-start justify-between gap-3">
                <h2 className="text-base font-semibold text-slate-900">
                  {faq.question}
                </h2>
                <span
                  className={cn(
                    "shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold ring-1 ring-inset",
                    faq.is_active
                      ? "bg-teal-50 text-teal-800 ring-teal-600/20"
                      : "bg-slate-100 text-slate-600 ring-slate-500/20",
                  )}
                >
                  {faq.is_active ? "Active" : "Inactive"}
                </span>
              </div>
              <p className="mt-2 line-clamp-4 whitespace-pre-line text-sm leading-6 text-slate-600">
                {faq.answer}
              </p>
              <div className="mt-auto flex gap-2 pt-4">
                <Button variant="secondary" size="sm" onClick={() => openEdit(faq)}>
                  <EditIcon className="h-4 w-4" />
                  Edit
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  loading={togglingId === faq.id}
                  onClick={() => toggleActive(faq)}
                >
                  {faq.is_active ? "Deactivate" : "Activate"}
                </Button>
                {faq.is_active ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-rose-600 hover:bg-rose-50 hover:text-rose-700"
                    onClick={() => setDeactivating(faq)}
                  >
                    <TrashIcon className="h-4 w-4" />
                    Remove
                  </Button>
                ) : null}
              </div>
            </article>
          ))}
        </div>
      ) : null}

      <Modal
        open={formOpen}
        onClose={() => setFormOpen(false)}
        title={editing ? "Edit FAQ" : "Add FAQ"}
        description="The agent embeds your question and answer so callers can ask in their own words, in Hindi or English."
        wide
      >
        <FaqForm
          key={editing?.id ?? "new"}
          faq={editing}
          onSaved={async () => {
            setFormOpen(false);
            await reload();
          }}
          onCancel={() => setFormOpen(false)}
        />
      </Modal>

      <Modal
        open={importOpen}
        onClose={() => setImportOpen(false)}
        title="Upload FAQs"
        description="Import a JSON or CSV file. Existing questions are reported as skipped."
        wide
      >
        <FaqImport
          onImported={reload}
          onClose={() => setImportOpen(false)}
        />
      </Modal>

      <ConfirmDialog
        open={Boolean(deactivating)}
        title="Deactivate FAQ"
        message={
          deactivating
            ? `The voice agent will stop using “${deactivating.question}”. You can activate it again later.`
            : ""
        }
        confirmLabel="Deactivate"
        danger
        busy={busy}
        onCancel={() => setDeactivating(null)}
        onConfirm={confirmDeactivate}
      />
    </div>
  );
}

function FaqImport({
  onImported,
  onClose,
}: {
  onImported: () => Promise<unknown>;
  onClose: () => void;
}) {
  const [rows, setRows] = useState<ImportRow[]>([]);
  const [fileName, setFileName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    setRows([]);
    setResult(null);
    setError(null);
    if (!file) return;

    setFileName(file.name);
    try {
      const text = await file.text();
      const parsed = parseFaqFile(text, file.name);
      if (!parsed.length) {
        throw new Error("No rows found. Expected question and answer columns.");
      }
      setRows(parsed);
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Could not read that file.",
      );
    }
  }

  async function importRows() {
    setBusy(true);
    setError(null);
    setResult(null);
    let imported = 0;
    const failures: string[] = [];

    for (const [index, row] of rows.entries()) {
      try {
        await api.createFaq({
          question: row.question,
          answer: row.answer,
          is_active: true,
        });
        imported += 1;
      } catch (caught) {
        failures.push(`Row ${index + 1}: ${getErrorMessage(caught)}`);
      }
    }

    setBusy(false);
    setResult(
      `${imported} imported, ${failures.length} skipped. ${
        failures.length ? failures.slice(0, 3).join(" ") : ""
      }`.trim(),
    );
    if (imported > 0) {
      await onImported();
      setRows([]);
    }
  }

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-5">
        <label className="block text-sm font-semibold text-slate-800" htmlFor="faq-file">
          Choose a .json or .csv file
        </label>
        <input
          id="faq-file"
          type="file"
          accept=".json,.csv,text/csv,application/json"
          className="mt-3 block w-full text-sm text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-teal-700 file:px-3 file:py-2 file:text-sm file:font-semibold file:text-white hover:file:bg-teal-800"
          onChange={handleFile}
        />
        <p className="mt-2 text-xs text-slate-500">
          JSON: <code>{`[{"question": "...", "answer": "..."}]`}</code> or{" "}
          <code>{`{"faqs": [...]}`}</code>. CSV: a header row with{" "}
          <code>question,answer</code>.
        </p>
      </div>

      {fileName ? (
        <p className="text-sm text-slate-600">
          <span className="font-semibold">{fileName}</span>
          {rows.length ? ` - ${rows.length} FAQ${rows.length === 1 ? "" : "s"} ready` : ""}
        </p>
      ) : null}

      {error ? <ErrorPanel message={error} /> : null}
      {result ? (
        <div className="rounded-xl border border-teal-200 bg-teal-50 px-4 py-3 text-sm text-teal-900">
          {result}
        </div>
      ) : null}

      {rows.length ? (
        <div className="max-h-52 overflow-y-auto rounded-xl border border-slate-200">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-500">
              <tr>
                <th className="px-3 py-2 font-semibold">Question</th>
                <th className="px-3 py-2 font-semibold">Answer</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((row, index) => (
                <tr key={`${row.question}-${index}`}>
                  <td className="px-3 py-2 font-medium text-slate-800">
                    {row.question}
                  </td>
                  <td className="max-w-md px-3 py-2 text-slate-500">
                    <span className="line-clamp-2">{row.answer}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <Button variant="secondary" onClick={onClose} disabled={busy}>
          Close
        </Button>
        <Button onClick={importRows} loading={busy} disabled={!rows.length}>
          Import {rows.length || ""} FAQ{rows.length === 1 ? "" : "s"}
        </Button>
      </div>
    </div>
  );
}

function parseFaqFile(text: string, fileName: string): ImportRow[] {
  const trimmed = text.trim();
  if (
    fileName.toLowerCase().endsWith(".json") ||
    trimmed.startsWith("[") ||
    trimmed.startsWith("{")
  ) {
    const payload: unknown = JSON.parse(trimmed);
    const items =
      Array.isArray(payload)
        ? payload
        : (payload as { faqs?: unknown } | null)?.faqs;
    if (!Array.isArray(items)) {
      throw new Error("JSON must be a list of FAQs or an object with a faqs list.");
    }
    return items.map((item, index) => {
      const record = item as { question?: unknown; answer?: unknown };
      const question = String(record.question ?? "").trim();
      const answer = String(record.answer ?? "").trim();
      if (!question || !answer) {
        throw new Error(`FAQ ${index + 1} is missing a question or answer.`);
      }
      return { question, answer };
    });
  }

  const parsed = parseCsv(text);
  if (!parsed.length) return [];
  const first = parsed[0].map((cell) => cell.trim().toLowerCase());
  const hasHeader = first.includes("question") && first.includes("answer");
  const rows = (hasHeader ? parsed.slice(1) : parsed)
    .map((cells) => ({
      question: (cells[0] ?? "").trim(),
      answer: (cells[1] ?? "").trim(),
    }))
    .filter((row) => row.question && row.answer);
  return rows;
}

function parseCsv(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let quoted = false;

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    if (quoted) {
      if (char === '"') {
        if (text[index + 1] === '"') {
          field += '"';
          index += 1;
        } else {
          quoted = false;
        }
      } else {
        field += char;
      }
      continue;
    }
    if (char === '"') {
      quoted = true;
    } else if (char === ",") {
      row.push(field);
      field = "";
    } else if (char === "\n") {
      row.push(field);
      field = "";
      rows.push(row);
      row = [];
    } else if (char !== "\r") {
      field += char;
    }
  }

  if (field || row.length) {
    row.push(field);
    rows.push(row);
  }
  return rows.filter((cells) => cells.some((cell) => cell.trim()));
}
