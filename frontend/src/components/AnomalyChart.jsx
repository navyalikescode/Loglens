import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import InfoTooltip from "./InfoTooltip.jsx";
import { useTheme } from "../contexts/ThemeContext.jsx";

function bucketKey(iso) {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  d.setSeconds(0, 0);
  return d.toISOString();
}

export default function AnomalyChart({ result }) {
  const { theme } = useTheme();
  const isDark = theme === "dark";
  const gridColor = isDark ? "#333" : "#e2e8f0";
  const tooltipBg = isDark ? "#111" : "#fff";
  const tooltipBorder = isDark ? "#333" : "#e2e8f0";
  const axisColor = isDark ? "#888" : "#94a3b8";

  const timeline = result?.timeline || [];
  const anomalies = result?.anomalies || [];

  const buckets = {};
  for (const ev of timeline) {
    const k = bucketKey(ev.timestamp);
    if (!k) continue;
    if (!buckets[k]) buckets[k] = { t: k, info: 0, warning: 0, error: 0, total: 0 };
    const sev = (ev.severity || "").toLowerCase();
    buckets[k].total += 1;
    if (sev === "critical" || sev === "high") buckets[k].error += 1;
    else if (sev === "medium") buckets[k].warning += 1;
    else buckets[k].info += 1;
  }

  const chartData = Object.values(buckets).sort((a, b) => a.t.localeCompare(b.t));
  const anomalyTimes = anomalies.map((a) => a.timestamp).filter(Boolean);

  if (chartData.length === 0) {
    const summary = result?.summary || {};
    const dist = [
      { name: "INFO", v: Math.max(0, 1 - (summary.error_rate || 0) - (summary.warning_rate || 0)) },
      { name: "WARN", v: summary.warning_rate || 0 },
      { name: "ERROR", v: summary.error_rate || 0 },
    ];
    return (
      <div className="rounded-xl border border-ll-border/10 bg-ll-card/40 p-4 mx-6">
        <div className="mb-2 flex items-center gap-2">
          <h3 className="font-sans text-sm text-ll-muted">Level distribution</h3>
          <InfoTooltip text="No timestamps were found in your logs, so we're showing the overall distribution of log levels instead of a timeline." />
        </div>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={dist}>
              <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
              <XAxis dataKey="name" stroke={axisColor} />
              <YAxis stroke={axisColor} />
              <Tooltip contentStyle={{ background: tooltipBg, border: `1px solid ${tooltipBorder}`, borderRadius: 8, fontSize: 12 }} />
              <Bar dataKey="v" fill="#00ff88" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-ll-border/10 bg-ll-card/40 p-4 mx-6">
      <div className="mb-2 flex items-center gap-2">
        <h3 className="font-sans text-sm text-ll-muted">Volume / minute</h3>
        <InfoTooltip text="Log events per minute, stacked by severity. Red dashed lines mark detected anomalies — sudden spikes or unusual patterns." />
      </div>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
            <XAxis dataKey="t" tickFormatter={(v) => v.slice(11, 16)} stroke={axisColor} />
            <YAxis stroke={axisColor} />
            <Tooltip contentStyle={{ background: tooltipBg, border: `1px solid ${tooltipBorder}`, borderRadius: 8, fontSize: 12 }} />
            <Area type="monotone" dataKey="info" stackId="1" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.35} />
            <Area type="monotone" dataKey="warning" stackId="1" stroke="#ffaa00" fill="#ffaa00" fillOpacity={0.45} />
            <Area type="monotone" dataKey="error" stackId="1" stroke="#ff4444" fill="#ff4444" fillOpacity={0.5} />
            {anomalyTimes.map((ts) => {
              const k = bucketKey(ts);
              if (!k) return null;
              return <ReferenceLine key={ts} x={k} stroke="#ff4444" strokeDasharray="4 4" />;
            })}
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
