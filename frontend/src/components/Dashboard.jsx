import { BarChart3, Clock, Shield, TrendingUp } from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useTheme } from "../contexts/ThemeContext.jsx";

const SEV_COLORS = { P1: "#ff4444", P2: "#f97316", P3: "#ffaa00", P4: "#00ff88" };

export default function Dashboard({ history }) {
  const { theme } = useTheme();
  const isDark = theme === "dark";
  const gridColor = isDark ? "#333" : "#e2e8f0";
  const tooltipBg = isDark ? "#111" : "#fff";
  const tooltipBorder = isDark ? "#333" : "#e2e8f0";
  const axisColor = isDark ? "#888" : "#94a3b8";

  if (history.length === 0) {
    return (
      <div className="mx-auto max-w-4xl p-12 text-center">
        <BarChart3 className="mx-auto mb-4 h-16 w-16 text-ll-muted/30" />
        <h2 className="font-sans text-xl font-semibold text-ll-text">No data yet</h2>
        <p className="mt-2 text-sm text-ll-muted">
          Run some analyses and your trends will appear here.
        </p>
      </div>
    );
  }

  const sevDist = { P1: 0, P2: 0, P3: 0, P4: 0 };
  const sourceDist = {};
  let totalClusters = 0;
  let totalAnomalies = 0;
  let totalLines = 0;

  history.forEach((e) => {
    sevDist[e.severity] = (sevDist[e.severity] || 0) + 1;
    sourceDist[e.logSource] = (sourceDist[e.logSource] || 0) + 1;
    totalClusters += e.clusterCount;
    totalAnomalies += e.anomalyCount;
    totalLines += e.totalLines;
  });

  const pieData = Object.entries(sevDist)
    .filter(([, v]) => v > 0)
    .map(([name, value]) => ({ name, value }));

  const sourceData = Object.entries(sourceDist)
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value);

  const daily = {};
  history.forEach((e) => {
    const day = e.timestamp.slice(0, 10);
    if (!daily[day]) daily[day] = { day, count: 0, errors: 0 };
    daily[day].count += 1;
    if (e.severity === "P1" || e.severity === "P2") daily[day].errors += 1;
  });
  const trendData = Object.values(daily).sort((a, b) => a.day.localeCompare(b.day));

  const stats = [
    { icon: BarChart3, label: "Total Analyses", value: history.length },
    { icon: Shield, label: "Avg Severity", value: calcAvgSeverity(sevDist) },
    { icon: TrendingUp, label: "Total Lines Analysed", value: totalLines.toLocaleString() },
    { icon: Clock, label: "Last Analysis", value: timeAgo(history[0]?.timestamp) },
  ];

  return (
    <div className="mx-auto max-w-6xl space-y-8 p-6">
      <div>
        <h2 className="font-sans text-xl font-semibold text-ll-text">Dashboard</h2>
        <p className="mt-1 text-sm text-ll-muted">Overview of your log analysis activity</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((s) => (
          <div key={s.label} className="rounded-xl border border-ll-border/10 bg-ll-card/40 p-4">
            <div className="flex items-center gap-2 text-ll-muted">
              <s.icon className="h-4 w-4" />
              <span className="font-sans text-xs">{s.label}</span>
            </div>
            <p className="mt-2 font-mono text-2xl font-bold text-ll-text">{s.value}</p>
          </div>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {trendData.length > 1 && (
          <div className="rounded-xl border border-ll-border/10 bg-ll-card/40 p-4">
            <h3 className="mb-3 font-sans text-sm text-ll-muted">Analysis Trend</h3>
            <div className="h-52">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={trendData}>
                  <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
                  <XAxis dataKey="day" tickFormatter={(v) => v.slice(5)} stroke={axisColor} tick={{ fontSize: 11 }} />
                  <YAxis stroke={axisColor} tick={{ fontSize: 11 }} />
                  <Tooltip contentStyle={{ background: tooltipBg, border: `1px solid ${tooltipBorder}`, borderRadius: 8, fontSize: 12 }} />
                  <Area type="monotone" dataKey="count" name="Analyses" stroke="#00ff88" fill="#00ff88" fillOpacity={0.2} />
                  <Area type="monotone" dataKey="errors" name="P1/P2" stroke="#ff4444" fill="#ff4444" fillOpacity={0.15} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        <div className="rounded-xl border border-ll-border/10 bg-ll-card/40 p-4">
          <h3 className="mb-3 font-sans text-sm text-ll-muted">Severity Distribution</h3>
          <div className="h-52 flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={pieData} cx="50%" cy="50%" innerRadius={50} outerRadius={80} dataKey="value" label={({ name, value }) => `${name}: ${value}`}>
                  {pieData.map((entry) => (
                    <Cell key={entry.name} fill={SEV_COLORS[entry.name]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ background: tooltipBg, border: `1px solid ${tooltipBorder}`, borderRadius: 8, fontSize: 12 }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {sourceData.length > 0 && (
          <div className="rounded-xl border border-ll-border/10 bg-ll-card/40 p-4 lg:col-span-2">
            <h3 className="mb-3 font-sans text-sm text-ll-muted">Log Sources</h3>
            <div className="h-44">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={sourceData} layout="vertical">
                  <CartesianGrid strokeDasharray="3 3" stroke={gridColor} />
                  <XAxis type="number" stroke={axisColor} tick={{ fontSize: 11 }} />
                  <YAxis dataKey="name" type="category" stroke={axisColor} width={80} tick={{ fontSize: 11 }} />
                  <Tooltip contentStyle={{ background: tooltipBg, border: `1px solid ${tooltipBorder}`, borderRadius: 8, fontSize: 12 }} />
                  <Bar dataKey="value" name="Analyses" fill="#00ff88" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function calcAvgSeverity(dist) {
  const scores = { P1: 4, P2: 3, P3: 2, P4: 1 };
  let total = 0, count = 0;
  for (const [sev, n] of Object.entries(dist)) {
    total += (scores[sev] || 1) * n;
    count += n;
  }
  if (count === 0) return "—";
  const avg = total / count;
  if (avg >= 3.5) return "P1";
  if (avg >= 2.5) return "P2";
  if (avg >= 1.5) return "P3";
  return "P4";
}

function timeAgo(iso) {
  if (!iso) return "—";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}
