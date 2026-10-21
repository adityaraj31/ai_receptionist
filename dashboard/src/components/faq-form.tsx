"use client";

import { useState, type FormEvent } from "react";

import { Button, ErrorPanel, inputClass, labelClass } from "@/components/ui";
import { api } from "@/lib/api-client";
import type { Faq } from "@/lib/api-types";
import { getErrorMessage } from "@/lib/errors";

export function FaqForm({
  faq,
  onSaved,
  onCancel,
}: {
  faq?: Faq | null;
  onSaved: (faq: Faq) => void;
  onCancel: () => void;
}) {
  const [question, setQuestion] = useState(faq?.question ?? "");
  const [answer, setAnswer] = useState(faq?.answer ?? "");
  const [isActive, setIsActive] = useState(faq?.is_active ?? true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    const trimmedQuestion = question.trim();
    const trimmedAnswer = answer.trim();
    if (trimmedQuestion.length < 3) {
      setError("Enter the question callers are likely to ask.");
      return;
    }
    if (trimmedAnswer.length < 3) {
      setError("Enter the answer the voice agent should give.");
      return;
    }

    setBusy(true);
    try {
      const saved = faq
        ? await api.updateFaq(faq.id, {
            question: trimmedQuestion,
            answer: trimmedAnswer,
            is_active: isActive,
          })
        : await api.createFaq({
            question: trimmedQuestion,
            answer: trimmedAnswer,
            is_active: isActive,
          });
      onSaved(saved);
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
        <label className={labelClass} htmlFor="faq-question">
          Question
        </label>
        <input
          id="faq-question"
          className={inputClass}
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="What are the clinic timings?"
          maxLength={300}
          autoFocus
          required
        />
        <p className="mt-1 text-xs text-slate-500">
          Use the words callers use, such as timings, address, fees, UPI, or parking.
        </p>
      </div>

      <div>
        <label className={labelClass} htmlFor="faq-answer">
          Answer
        </label>
        <textarea
          id="faq-answer"
          className={`${inputClass} min-h-32 resize-y`}
          value={answer}
          onChange={(event) => setAnswer(event.target.value)}
          placeholder="We are open Monday to Saturday, 9 AM to 6 PM."
          maxLength={4000}
          required
        />
        <p className="mt-1 text-xs text-slate-500">
          Keep it factual. The voice agent reads the first two sentences on a call.
        </p>
      </div>

      <label className="flex items-center gap-2 text-sm text-slate-700">
        <input
          type="checkbox"
          className="h-4 w-4 rounded border-slate-300 text-teal-700 focus:ring-teal-600"
          checked={isActive}
          onChange={(event) => setIsActive(event.target.checked)}
        />
        Active - the voice agent can use this answer
      </label>

      <div className="flex flex-col-reverse gap-2 pt-2 sm:flex-row sm:justify-end">
        <Button type="button" variant="secondary" onClick={onCancel} disabled={busy}>
          Cancel
        </Button>
        <Button type="submit" loading={busy}>
          {faq ? "Save changes" : "Add FAQ"}
        </Button>
      </div>
    </form>
  );
}
