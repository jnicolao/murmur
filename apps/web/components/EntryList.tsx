"use client";

import { API, type Entry } from "@/lib/api";

export function EntryList({ entries, onChanged }: { entries: Entry[]; onChanged: () => void }) {
  if (entries.length === 0) {
    return <p className="text-sm text-[var(--color-muted)]">Nothing here yet.</p>;
  }

  const remove = async (id: number) => {
    await fetch(`${API}/entries/${id}`, { method: "DELETE" });
    onChanged();
  };

  return (
    <ul className="space-y-2">
      {entries.map((entry) => (
        <li
          key={entry.id}
          className="flex items-baseline gap-3 rounded-xl border border-[var(--color-line)] bg-white px-4 py-3"
        >
          <span className="shrink-0 text-xs tabular-nums text-[var(--color-muted)]">
            {new Date(entry.started_at).toLocaleDateString(undefined, {
              month: "short",
              day: "numeric",
            })}
          </span>
          <span className="min-w-0 flex-1 truncate text-sm">
            {entry.summary ?? entry.opening ?? `${entry.utterances} turns`}
          </span>
          {entry.safety_triggered && (
            <span
              className="shrink-0 text-xs text-[var(--color-blush)]"
              title="This entry reached the crisis path. It is never used as context and never appears on the timeline."
            >
              held apart
            </span>
          )}
          {entry.self_mood && (
            <span className="shrink-0 text-xs tabular-nums text-[var(--color-muted)]">
              rated {entry.self_mood}
            </span>
          )}
          <button
            onClick={() => remove(entry.id)}
            className="shrink-0 rounded px-2 py-0.5 text-xs text-[var(--color-muted)] hover:text-[var(--color-blush)]"
          >
            Delete
          </button>
        </li>
      ))}
    </ul>
  );
}
