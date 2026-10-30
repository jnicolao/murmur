// Empty in production, because the API serves this page from the same origin.
export const API = process.env.NEXT_PUBLIC_API ?? "";

export function socketUrl(): string {
  if (API) return API.replace(/^http/, "ws") + "/ws";
  const scheme = location.protocol === "https:" ? "wss" : "ws";
  return `${scheme}://${location.host}/ws`;
}

export async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${API}${path}`);
  if (!response.ok) throw new Error(`${path} returned ${response.status}`);
  return response.json();
}

export type Entry = {
  id: number;
  started_at: string;
  self_mood: number | null;
  summary: string | null;
  opening: string | null;
  utterances: number;
  safety_triggered: boolean | null;
};

export type TimelinePoint = {
  day: string;
  self_mood: number | null;
  est_valence: number | null;
  entries: number;
  utterances: number;
};

export type Timeline = {
  points: TimelinePoint[];
  trend: { text: string | null; reason: string };
};

export type Resource = { label: string; detail: string };
