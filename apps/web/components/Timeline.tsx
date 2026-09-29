"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Timeline as TimelineData } from "@/lib/api";

const INDIGO = "#3D437A";
const LAVENDER = "#9B8CE0";

export function Timeline({ data }: { data: TimelineData | null }) {
  const points = data?.points ?? [];
  const withMood = points.filter((p) => p.self_mood !== null).length;

  if (withMood < 2) {
    return (
      <p className="text-sm text-[var(--color-muted)]">
        The timeline needs a few days of entries before it shows anything. Rate how a session
        felt when it ends and it will start filling in.
      </p>
    );
  }

  const shaped = points.map((point) => ({
    day: point.day.slice(5),
    "How you rated it": point.self_mood,
    "How you sounded": point.est_valence,
  }));

  return (
    <div>
      <div className="h-56 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={shaped} margin={{ top: 8, right: 8, bottom: 0, left: -18 }}>
            <CartesianGrid stroke="#E2E0EC" vertical={false} />
            <XAxis
              dataKey="day"
              tick={{ fontSize: 11, fill: "#6B6C80" }}
              tickLine={false}
              axisLine={{ stroke: "#E2E0EC" }}
            />
            <YAxis
              yAxisId="mood"
              domain={[1, 5]}
              ticks={[1, 2, 3, 4, 5]}
              tick={{ fontSize: 11, fill: "#6B6C80" }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis yAxisId="valence" orientation="right" domain={[-1, 1]} hide />
            <Tooltip
              contentStyle={{
                border: "1px solid #E2E0EC",
                borderRadius: 10,
                fontSize: 13,
              }}
              formatter={(value, name) => [
                typeof value === "number" ? value.toFixed(2) : "no reading",
                String(name),
              ]}
            />
            <Line
              yAxisId="mood"
              type="monotone"
              dataKey="How you rated it"
              stroke={INDIGO}
              strokeWidth={2}
              dot={{ r: 3, fill: INDIGO }}
              connectNulls
            />
            <Line
              yAxisId="valence"
              type="monotone"
              dataKey="How you sounded"
              stroke={LAVENDER}
              strokeWidth={2}
              strokeDasharray="4 3"
              dot={false}
              connectNulls
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1 text-xs text-[var(--color-muted)]">
        <span className="flex items-center gap-2">
          <span className="h-0.5 w-5" style={{ background: INDIGO }} />
          How you rated it, 1 to 5
        </span>
        <span className="flex items-center gap-2">
          <span
            className="h-0.5 w-5"
            style={{ background: `repeating-linear-gradient(90deg, ${LAVENDER} 0 4px, transparent 4px 7px)` }}
          />
          How you sounded, estimated
        </span>
      </div>

      <p className="mt-4 text-sm">
        {data?.trend.text ? (
          <span className="text-[var(--color-ink)]">{data.trend.text}</span>
        ) : (
          <span className="text-[var(--color-muted)]">
            Both lines are here to read yourself. Nothing to add this week
            {data?.trend.reason ? `: ${data.trend.reason}` : ""}.
          </span>
        )}
      </p>
    </div>
  );
}
