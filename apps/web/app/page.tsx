"use client";

import { useCallback, useEffect, useState } from "react";
import { EntryList } from "@/components/EntryList";
import { Timeline } from "@/components/Timeline";
import { TurnLog } from "@/components/TurnLog";
import { API, get, type Entry, type Timeline as TimelineData } from "@/lib/api";
import { useVoice } from "@/lib/useVoice";

const BUTTON_LABEL: Record<string, string> = {
  loading: "Loading",
  idle: "Talk",
  recording: "Stop",
  thinking: "Thinking",
  speaking: "Interrupt",
};

const BUTTON_STYLE: Record<string, string> = {
  idle: "bg-[var(--color-indigo-deep)] text-white",
  recording: "bg-[var(--color-blush)] text-[var(--color-ink)]",
  thinking: "bg-[var(--color-lavender)] text-[var(--color-ink)] cursor-wait",
  speaking: "bg-[var(--color-indigo-deep)] text-white",
  loading: "bg-[var(--color-indigo-deep)] text-white opacity-60",
};

export default function Page() {
  const [entries, setEntries] = useState<Entry[]>([]);
  const [timeline, setTimeline] = useState<TimelineData | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [rows, chart] = await Promise.all([
        get<Entry[]>("/entries"),
        get<TimelineData>("/timeline"),
      ]);
      setEntries(rows);
      setTimeline(chart);
    } catch {
      // The server is still waking up; the voice hook reports that.
    }
  }, []);

  const { state, status, turns, press, askMood, setMood, clearTurns } = useVoice(refresh);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const forget = async () => {
    const typed = window.prompt(
      'This deletes every entry and every recording on this machine. There is no undo.\n\nType "forget everything" to confirm.',
    );
    if (typed !== "forget everything") return;
    await fetch(`${API}/forget`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirm: typed }),
    });
    clearTurns();
    void refresh();
  };

  return (
    <main className="mx-auto w-full max-w-2xl px-5 pb-16 pt-10">
      <header className="mb-8 text-center">
        <h1 className="text-[28px] font-semibold tracking-[0.03em] text-[var(--color-indigo-deep)]">
          murmur
        </h1>
        <p className="text-sm text-[var(--color-muted)]">A space for your inner voice.</p>
      </header>

      <div className="flex flex-col items-center">
        <button
          onClick={press}
          disabled={state === "thinking" || state === "loading"}
          className={`h-32 w-32 rounded-full text-[15px] font-medium transition ${BUTTON_STYLE[state]}`}
        >
          {BUTTON_LABEL[state]}
        </button>
        <p className="mt-4 h-5 text-[13px] text-[var(--color-muted)]">{status}</p>

        {askMood && (
          <div className="mt-2 flex items-center gap-2">
            <span className="text-[11px] uppercase tracking-wider text-[var(--color-muted)]">
              How was that?
            </span>
            {[1, 2, 3, 4, 5].map((value) => (
              <button
                key={value}
                onClick={() => {
                  setMood(value);
                  setTimeout(() => void refresh(), 200);
                }}
                className="h-8 w-8 rounded-lg border border-[var(--color-line)] bg-white text-sm hover:border-[var(--color-indigo-deep)]"
              >
                {value}
              </button>
            ))}
          </div>
        )}
      </div>

      {turns.length > 0 && (
        <section className="mt-8">
          <TurnLog turns={turns} />
        </section>
      )}

      <section className="mt-10">
        <h2 className="mb-3 text-[13px] font-semibold uppercase tracking-wider text-[var(--color-muted)]">
          How it has been going
        </h2>
        <Timeline data={timeline} />
      </section>

      <section className="mt-10">
        <h2 className="mb-3 text-[13px] font-semibold uppercase tracking-wider text-[var(--color-muted)]">
          Earlier
        </h2>
        <EntryList entries={entries} onChanged={refresh} />
      </section>

      <footer className="mt-12 border-t border-[var(--color-line)] pt-5 text-[13px] text-[var(--color-muted)]">
        <p className="mb-3">
          Murmur is a journal, not therapy. It is not a substitute for a professional, and no
          person reads or listens to what you record here. Everything stays on this machine.
        </p>
        <button
          onClick={forget}
          className="rounded-lg border border-[var(--color-line)] px-3 py-1.5 text-[13px] hover:border-[var(--color-blush)] hover:text-[var(--color-blush)]"
        >
          Forget everything
        </button>
      </footer>
    </main>
  );
}
