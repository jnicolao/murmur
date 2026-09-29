"use client";

import type { Turn } from "@/lib/useVoice";

export function TurnLog({ turns }: { turns: Turn[] }) {
  return (
    <div className="space-y-3">
      {turns.map((turn) => (
        <article
          key={turn.id}
          className={`rounded-xl border px-5 py-4 ${
            turn.crisis
              ? "border-[var(--color-blush)] bg-[var(--color-blush-soft)]"
              : "border-[var(--color-line)] bg-white"
          }`}
        >
          <p className="mb-1 text-[11px] uppercase tracking-wider text-[var(--color-muted)]">
            You said
          </p>
          <p className="mb-3 text-sm">{turn.said}</p>
          {turn.reply && (
            <p className={turn.crisis ? "text-sm" : "text-sm text-[var(--color-indigo-deep)]"}>
              {turn.reply}
            </p>
          )}

          {turn.resources.length > 0 && (
            <ul className="mt-4 space-y-2">
              {turn.resources.map((resource) => (
                <li key={resource.label} className="border-t border-[var(--color-blush)] pt-2">
                  <b className="block text-sm font-semibold">{resource.label}</b>
                  <span className="text-sm text-[var(--color-muted)]">{resource.detail}</span>
                </li>
              ))}
            </ul>
          )}

          {turn.timings?.ttfa_ms != null && (
            <p className="mt-3 text-xs tabular-nums text-[var(--color-muted)]">
              heard in {turn.timings.asr_ms} ms · checked in {turn.timings.safety_ms} ms · first
              audio at {turn.timings.ttfa_ms} ms
            </p>
          )}
        </article>
      ))}
    </div>
  );
}
