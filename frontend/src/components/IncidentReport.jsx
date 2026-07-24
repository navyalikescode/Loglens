import { useState } from "react";
import { Check, ClipboardCopy, Download, FileJson, FileSpreadsheet, FileText, RotateCcw, Share2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import SeverityBadge from "./SeverityBadge.jsx";

export default function IncidentReport({ result, onReset, onShare }) {
  const md = result?.incident_report_markdown || "";
  const severity = result?.severity || "P4";
  const [copied, setCopied] = useState(false);
  const [showShare, setShowShare] = useState(false);

  const downloadJson = () => {
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
    triggerDownload(blob, "loglens-report.json");
  };

  const downloadMd = () => {
    const blob = new Blob([md], { type: "text/markdown" });
    triggerDownload(blob, "loglens-report.md");
  };

  const downloadCsv = () => {
    const clusters = result?.error_clusters || [];
    const rows = [["Cluster ID", "Severity", "Count", "Message", "First Seen", "Last Seen", "Services"]];
    clusters.forEach((c) => {
      rows.push([
        c.cluster_id,
        c.severity || "",
        c.count,
        `"${(c.representative_message || "").replace(/"/g, '""')}"`,
        c.first_seen || "",
        c.last_seen || "",
        (c.affected_services || []).join("; "),
      ]);
    });
    const csv = rows.map((r) => r.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    triggerDownload(blob, "loglens-clusters.csv");
  };

  const copyMd = async () => {
    await navigator.clipboard.writeText(md);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const shareReport = async () => {
    if (onShare) {
      const url = await onShare();
      if (url) {
        setShowShare(true);
        setTimeout(() => setShowShare(false), 3000);
        return;
      }
    }
    const shareData = {
      title: `LogLens Report — ${severity}`,
      text: `Log analysis report: ${result?.metadata?.log_source || "unknown"} (${result?.metadata?.total_lines || 0} lines)`,
    };
    if (navigator.share) {
      try { await navigator.share(shareData); } catch { /* cancelled */ }
    } else {
      await navigator.clipboard.writeText(md);
      setShowShare(true);
      setTimeout(() => setShowShare(false), 2000);
    }
  };

  return (
    <div className="space-y-6 p-6">
      <div className="flex flex-wrap items-center gap-4">
        <h2 className="font-sans text-xl font-semibold text-ll-text">Incident report</h2>
        <SeverityBadge severity={severity} />
        {result?.metadata && (
          <span className="font-mono text-xs text-ll-muted">
            {result.metadata.log_source} · {result.metadata.total_lines} lines · {result.summary?.processing_time_ms?.toFixed(0)}ms
          </span>
        )}
      </div>

      <div className="prose prose-invert max-w-none rounded-xl border border-ll-border/10 bg-ll-card/40 p-6 prose-headings:font-sans prose-headings:text-ll-text prose-p:font-mono prose-p:text-sm prose-p:text-ll-text prose-li:font-mono prose-li:text-ll-text prose-strong:text-ll-accent prose-a:text-ll-accent">
        <ReactMarkdown>{md}</ReactMarkdown>
      </div>

      <div className="flex flex-wrap gap-3">
        <ActionButton onClick={copyMd} icon={copied ? Check : ClipboardCopy} label={copied ? "Copied!" : "Copy Markdown"} />
        <ActionButton onClick={downloadJson} icon={FileJson} label="Download JSON" />
        <ActionButton onClick={downloadMd} icon={FileText} label="Download MD" />
        <ActionButton onClick={downloadCsv} icon={FileSpreadsheet} label="Export CSV" />
        <ActionButton onClick={shareReport} icon={Share2} label={showShare ? "Copied to clipboard!" : "Share"} />
        <button
          type="button"
          onClick={onReset}
          className="flex items-center gap-2 rounded-xl bg-ll-accent px-4 py-2 font-sans text-sm font-semibold text-black transition-all hover:brightness-110"
        >
          <RotateCcw className="h-4 w-4" />
          Analyse Another
        </button>
      </div>
    </div>
  );
}

function ActionButton({ onClick, icon: Icon, label }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex items-center gap-2 rounded-xl border border-ll-border/10 px-4 py-2 font-sans text-sm text-ll-text transition-colors hover:border-ll-accent hover:text-ll-accent"
    >
      <Icon className="h-4 w-4" />
      {label}
    </button>
  );
}

function triggerDownload(blob, filename) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}
