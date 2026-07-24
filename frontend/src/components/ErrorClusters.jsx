import { useState } from "react";
import { Bookmark, BookmarkCheck, Check, ChevronDown, ChevronRight } from "lucide-react";
import SeverityBadge from "./SeverityBadge.jsx";
import InfoTooltip from "./InfoTooltip.jsx";

function sevToP(c) {
  const s = (c.severity || "").toLowerCase();
  if (s === "critical") return "P1";
  if (s === "high") return "P2";
  if (s === "medium") return "P3";
  return "P4";
}

export default function ErrorClusters({ clusters, filters, bookmarks, onToggleBookmark }) {
  const { search = "", severities = [] } = filters || {};

  const sorted = [...(clusters || [])].sort((a, b) => (b.count || 0) - (a.count || 0));

  const filtered = sorted.filter((c) => {
    const p = sevToP(c);
    if (severities.length > 0 && !severities.includes(p)) return false;
    if (search) {
      const q = search.toLowerCase();
      return (
        (c.representative_message || "").toLowerCase().includes(q) ||
        (c.sample_messages || []).some((s) => s.toLowerCase().includes(q)) ||
        (c.affected_services || []).some((s) => s.toLowerCase().includes(q))
      );
    }
    return true;
  });

  if (!sorted.length) {
    return (
      <div className="flex items-center gap-2 rounded-xl border border-ll-accent/30 bg-ll-accent/5 p-6 text-ll-accent">
        <Check className="h-6 w-6" />
        <span className="font-sans">No error clusters detected</span>
      </div>
    );
  }

  if (filtered.length === 0) {
    return (
      <div className="rounded-xl border border-ll-border/10 bg-ll-card/30 p-8 text-center">
        <p className="text-sm text-ll-muted">No clusters match your filters</p>
      </div>
    );
  }

  return (
    <div className="grid gap-4 md:grid-cols-2">
      {filtered.map((c) => (
        <ClusterCard
          key={c.cluster_id + c.representative_message}
          c={c}
          bookmarked={bookmarks?.has(c.cluster_id)}
          onToggleBookmark={() => onToggleBookmark?.(c.cluster_id)}
        />
      ))}
    </div>
  );
}

function ClusterCard({ c, bookmarked, onToggleBookmark }) {
  const [open, setOpen] = useState(false);
  const msg = c.representative_message || "";
  const short = msg.length > 80 ? `${msg.slice(0, 80)}…` : msg;

  return (
    <div className="rounded-xl border border-ll-border/10 bg-ll-card/40 p-4 transition-all hover:border-ll-border/20">
      <div className="flex items-start justify-between gap-2">
        <p className="font-mono text-sm text-ll-text">{short}</p>
        <div className="flex shrink-0 items-center gap-1.5">
          <button
            onClick={onToggleBookmark}
            className="rounded p-0.5 text-ll-muted transition-colors hover:text-ll-warn"
            title={bookmarked ? "Remove bookmark" : "Bookmark this cluster"}
          >
            {bookmarked ? (
              <BookmarkCheck className="h-4 w-4 text-ll-warn" />
            ) : (
              <Bookmark className="h-4 w-4" />
            )}
          </button>
          <SeverityBadge severity={sevToP(c)} />
        </div>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-ll-muted">
        <span className="rounded bg-ll-accent/10 px-2 py-0.5 font-mono text-ll-accent">
          {c.count} occurrences
        </span>
        <span className="font-mono">
          {c.first_seen?.slice(11, 19) || "?"} → {c.last_seen?.slice(11, 19) || "?"}
        </span>
        {c.affected_services?.length > 0 && (
          <span className="rounded bg-ll-border/10 px-2 py-0.5 font-mono">
            {c.affected_services.join(", ")}
          </span>
        )}
      </div>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="mt-3 flex items-center gap-1 text-sm text-ll-warn transition-colors hover:text-ll-text"
      >
        {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        Samples ({(c.sample_messages || []).length})
      </button>
      {open && (
        <ul className="mt-2 space-y-1 border-t border-ll-border/10 pt-2 font-mono text-xs text-ll-muted">
          {(c.sample_messages || []).map((s, i) => (
            <li key={i} className="break-all">{s}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
