import { useState } from "react";
import { Activity, BarChart3, Clock, Code2, Plus } from "lucide-react";
import AnalysisPipeline from "./components/AnalysisPipeline.jsx";
import AnomalyChart from "./components/AnomalyChart.jsx";
import CustomFormatManager from "./components/CustomFormatManager.jsx";
import Dashboard from "./components/Dashboard.jsx";
import ErrorClusters from "./components/ErrorClusters.jsx";
import HealthIndicator from "./components/HealthIndicator.jsx";
import IncidentReport from "./components/IncidentReport.jsx";
import LogUploader from "./components/LogUploader.jsx";
import ResultsToolbar from "./components/ResultsToolbar.jsx";
import RootCausePanel from "./components/RootCausePanel.jsx";
import ThemeToggle from "./components/ThemeToggle.jsx";
import TimelinePanel from "./components/TimelinePanel.jsx";
import useHistory from "./hooks/useHistory.js";
import { analyseLogs, analyseLogsStream, saveReport } from "./lib/api.js";
import SeverityBadge from "./components/SeverityBadge.jsx";

const VIEWS = [
  { id: "analyse", label: "Analyse", icon: Plus },
  { id: "history", label: "History", icon: Clock },
  { id: "dashboard", label: "Dashboard", icon: BarChart3 },
  { id: "formats", label: "Formats", icon: Code2 },
];

const STEP_MAP = { parsing: 0, anomalies: 1, clustering: 2, timeline: 3, root_cause: 4, report: 5 };

export default function App() {
  const [view, setView] = useState("analyse");
  const [phase, setPhase] = useState("idle");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [pipeDone, setPipeDone] = useState(false);
  const [serverStep, setServerStep] = useState(-1);
  const [filters, setFilters] = useState({ search: "", severities: [] });
  const [clusterBookmarks, setClusterBookmarks] = useState(() => new Set());

  const { history, addEntry, removeEntry, toggleBookmark, clearHistory } = useHistory();

  const reset = () => {
    setPhase("idle");
    setResult(null);
    setError(null);
    setPipeDone(false);
    setServerStep(-1);
    setFilters({ search: "", severities: [] });
    setClusterBookmarks(new Set());
  };

  const handleSubmit = async ({ logText, logFile }) => {
    setError(null);
    setPhase("analysing");
    setPipeDone(false);
    setServerStep(-1);

    try {
      await analyseLogsStream({
        logText,
        logFile,
        onProgress: (data) => {
          const idx = STEP_MAP[data.step];
          if (idx !== undefined) setServerStep(idx);
        },
        onComplete: (data) => {
          setResult(data);
          setPipeDone(true);
          addEntry(data);
          notifyIfCritical(data);
          setTimeout(() => setPhase("complete"), 400);
        },
        onError: (msg) => {
          setError(msg || "Analysis failed");
          setPhase("idle");
        },
      });
    } catch (e) {
      try {
        const data = await analyseLogs({ logText, logFile });
        setResult(data);
        setPipeDone(true);
        addEntry(data);
        notifyIfCritical(data);
        setTimeout(() => setPhase("complete"), 400);
      } catch (e2) {
        setError(e2.message || "Request failed");
        setPhase("idle");
      }
    }
  };

  const loadFromHistory = (entry) => {
    setResult(entry.result);
    setPhase("complete");
    setError(null);
    setPipeDone(true);
    setView("analyse");
    setFilters({ search: "", severities: [] });
  };

  const toggleClusterBookmark = (clusterId) => {
    setClusterBookmarks((prev) => {
      const next = new Set(prev);
      if (next.has(clusterId)) next.delete(clusterId);
      else next.add(clusterId);
      return next;
    });
  };

  const handleShare = async () => {
    if (!result) return;
    try {
      const resp = await saveReport(result);
      const shareUrl = `${window.location.origin}?report=${resp.report_id}`;
      await navigator.clipboard.writeText(shareUrl);
      return shareUrl;
    } catch {
      return null;
    }
  };

  return (
    <div className="min-h-screen bg-ll-bg transition-colors">
      <header className="sticky top-0 z-40 border-b border-ll-border/10 bg-ll-surface/80 px-6 py-3 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl items-center gap-4">
          <button onClick={() => { setView("analyse"); reset(); }} className="flex items-center gap-2.5">
            <Activity className="h-7 w-7 text-ll-accent" />
            <div>
              <h1 className="font-sans text-xl font-bold tracking-tight text-ll-text">LogLens</h1>
              <p className="font-mono text-[10px] text-ll-muted">Ops-grade log intelligence</p>
            </div>
          </button>

          <nav className="ml-6 hidden items-center gap-1 sm:flex">
            {VIEWS.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() => { setView(id); if (id === "analyse" && phase !== "complete") reset(); }}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 font-sans text-sm transition-colors ${
                  view === id
                    ? "bg-ll-accent/10 text-ll-accent"
                    : "text-ll-muted hover:text-ll-text"
                }`}
              >
                <Icon className="h-4 w-4" />
                {label}
                {id === "history" && history.length > 0 && (
                  <span className="rounded-full bg-ll-border/10 px-1.5 py-0.5 font-mono text-[10px]">
                    {history.length}
                  </span>
                )}
              </button>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-2">
            <HealthIndicator />
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl pb-16">
        {error && (
          <div className="mx-6 mt-4 rounded-xl border border-ll-danger/30 bg-ll-danger/10 px-4 py-3 font-mono text-sm text-ll-danger">
            {error}
          </div>
        )}

        {view === "analyse" && (
          <>
            {phase === "idle" && <LogUploader onSubmit={handleSubmit} disabled={false} />}

            {phase === "analysing" && (
              <AnalysisPipeline active finished={pipeDone} serverStep={serverStep >= 0 ? serverStep : undefined} />
            )}

            {phase === "complete" && result && (
              <div className="space-y-8 pt-4">
                <ResultsToolbar filters={filters} onFiltersChange={setFilters} />
                <AnomalyChart result={result} />
                <RootCausePanel rootCauses={result.root_causes} />
                <div className="px-6">
                  <h2 className="mb-4 font-sans text-lg text-ll-muted">Error clusters</h2>
                  <ErrorClusters
                    clusters={result.error_clusters}
                    filters={filters}
                    bookmarks={clusterBookmarks}
                    onToggleBookmark={toggleClusterBookmark}
                  />
                </div>
                <TimelinePanel timeline={result.timeline} />
                <IncidentReport result={result} onReset={reset} onShare={handleShare} />
              </div>
            )}
          </>
        )}

        {view === "history" && (
          <div className="p-6">
            <div className="mb-6 flex items-center justify-between">
              <div>
                <h2 className="font-sans text-xl font-semibold text-ll-text">Analysis History</h2>
                <p className="mt-1 text-sm text-ll-muted">{history.length} past analyses stored locally</p>
              </div>
              {history.length > 0 && (
                <button
                  onClick={clearHistory}
                  className="rounded-lg border border-ll-danger/30 px-3 py-1.5 font-sans text-xs text-ll-danger hover:bg-ll-danger/10"
                >
                  Clear All
                </button>
              )}
            </div>
            {history.length === 0 ? (
              <div className="rounded-xl border border-ll-border/10 bg-ll-card/30 p-12 text-center">
                <Clock className="mx-auto mb-4 h-12 w-12 text-ll-muted/30" />
                <p className="text-sm text-ll-muted">No analyses yet. Run one to see it here.</p>
              </div>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {history.map((entry) => (
                  <HistoryCard
                    key={entry.id}
                    entry={entry}
                    onClick={() => loadFromHistory(entry)}
                    onRemove={() => removeEntry(entry.id)}
                    onToggleBookmark={() => toggleBookmark(entry.id)}
                  />
                ))}
              </div>
            )}
          </div>
        )}

        {view === "dashboard" && <Dashboard history={history} />}
        {view === "formats" && <CustomFormatManager />}
      </main>

      {/* Mobile nav */}
      <nav className="fixed bottom-0 left-0 right-0 z-40 flex border-t border-ll-border/10 bg-ll-surface/95 backdrop-blur-xl sm:hidden">
        {VIEWS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => { setView(id); if (id === "analyse" && phase !== "complete") reset(); }}
            className={`flex flex-1 flex-col items-center gap-0.5 py-2.5 text-[10px] ${
              view === id ? "text-ll-accent" : "text-ll-muted"
            }`}
          >
            <Icon className="h-5 w-5" />
            {label}
          </button>
        ))}
      </nav>
    </div>
  );
}

function HistoryCard({ entry, onClick, onRemove, onToggleBookmark }) {
  return (
    <div
      onClick={onClick}
      className="group cursor-pointer rounded-xl border border-ll-border/10 bg-ll-card/40 p-4 transition-all hover:border-ll-accent/30 hover:shadow-lg"
    >
      <div className="flex items-center justify-between gap-2">
        <SeverityBadge severity={entry.severity} />
        <span className="font-mono text-xs text-ll-muted">{entry.logSource}</span>
      </div>
      <p className="mt-2 truncate font-sans text-sm text-ll-text">{entry.title}</p>
      <div className="mt-2 flex items-center gap-3 text-xs text-ll-muted">
        <span>{entry.totalLines} lines</span>
        <span>{entry.clusterCount} clusters</span>
        <span>{entry.anomalyCount} anomalies</span>
      </div>
      <p className="mt-2 font-mono text-[10px] text-ll-muted/60">
        {new Date(entry.timestamp).toLocaleString()}
      </p>
      <div className="mt-3 flex gap-2 opacity-0 transition-opacity group-hover:opacity-100">
        <button
          onClick={(e) => { e.stopPropagation(); onToggleBookmark(); }}
          className="rounded px-2 py-1 text-xs text-ll-muted hover:text-ll-warn"
        >
          {entry.bookmarked ? "★ Saved" : "☆ Save"}
        </button>
        <button
          onClick={(e) => { e.stopPropagation(); onRemove(); }}
          className="rounded px-2 py-1 text-xs text-ll-muted hover:text-ll-danger"
        >
          Delete
        </button>
      </div>
    </div>
  );
}

function notifyIfCritical(data) {
  if (!data?.severity) return;
  if (data.severity !== "P1" && data.severity !== "P2") return;
  if (!("Notification" in window)) return;
  if (Notification.permission === "granted") {
    new Notification(`LogLens — ${data.severity} Incident Detected`, {
      body: `${data.metadata?.log_source || "Log"} analysis found ${data.error_clusters?.length || 0} error clusters with ${data.anomalies?.length || 0} anomalies.`,
      icon: "/favicon.ico",
    });
  } else if (Notification.permission !== "denied") {
    Notification.requestPermission().then((perm) => {
      if (perm === "granted") notifyIfCritical(data);
    });
  }
}
