// Cumulative P&L line chart. Recharts is already in the stack.
// Single point: render with a single dot and a "history begins now" caption,
// per the brief.

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { fmtUsdSigned } from "./format";

export default function PnLChart({ history }) {
  const points = (history || []).map((h) => ({
    t:    new Date(h.snapshot_at).getTime(),
    pnl:  h.total_pnl_usd,
    date: h.snapshot_at,
  }));

  return (
    <section className="op-chart-block">
      <p className="op-eyebrow">Cumulative P&amp;L · realized + unrealized</p>
      <div className="op-chart">
        {points.length === 0 ? (
          <p className="op-meta">— no snapshots yet.</p>
        ) : (
          <ResponsiveContainer width="100%" height={280}>
            <LineChart
              data={points}
              margin={{ top: 12, right: 24, bottom: 12, left: 12 }}
            >
              <CartesianGrid stroke="var(--rule)" strokeDasharray="0" vertical={false} />
              <XAxis
                dataKey="t"
                type="number"
                domain={["dataMin", "dataMax"]}
                tickFormatter={(v) => new Date(v).toISOString().slice(5, 10)}
                stroke="var(--graphite-soft)"
                tick={{ fill: "var(--graphite-soft)", fontSize: 11, fontFamily: "var(--font-mono)" }}
                tickLine={false}
                axisLine={{ stroke: "var(--rule)" }}
              />
              <YAxis
                tickFormatter={(v) =>
                  Math.abs(v) >= 1000 ? `${(v / 1000).toFixed(1)}k` : v.toFixed(0)
                }
                stroke="var(--graphite-soft)"
                tick={{ fill: "var(--graphite-soft)", fontSize: 11, fontFamily: "var(--font-mono)" }}
                tickLine={false}
                axisLine={{ stroke: "var(--rule)" }}
                width={56}
              />
              <Tooltip
                contentStyle={{
                  background: "var(--paper-pure)",
                  border: "1px solid var(--rule)",
                  borderRadius: 6,
                  fontFamily: "var(--font-sans)",
                  fontSize: 12,
                  color: "var(--ink)",
                }}
                labelFormatter={(v) => new Date(v).toISOString().replace("T", " ").slice(0, 16) + "Z"}
                formatter={(v) => [fmtUsdSigned(v), "P&L"]}
              />
              <Line
                type="monotone"
                dataKey="pnl"
                stroke="var(--ink)"
                strokeWidth={1.75}
                dot={points.length === 1 ? { r: 3, fill: "var(--flame)" } : false}
                activeDot={{ r: 4, fill: "var(--flame)", stroke: "none" }}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
      {points.length === 1 ? (
        <p className="op-footnote">
          † First snapshot. History begins now — the chart fills in as the
          background refresh runs and you re-open this wallet.
        </p>
      ) : null}
    </section>
  );
}
