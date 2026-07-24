import { useState } from "react";
import { Bookmark, BookmarkCheck, Clock, Search, Trash2, X } from "lucide-react";
import SeverityBadge from "./SeverityBadge.jsx";

export default function HistorySidebar({ history, onSelect, onClose, onRemove, onToggleBookmark, onClear }) {
  const [search, setSearch] = useState("");
  const [filterSev, setFilterSev] = useState(null);
  const [showBookmarked, setShowBookmarked] = useState(false);

  const filtered = history.filter((e) => {
    if (showBookmarked && !e.bookmarked) return false;
    if (filterSev && e.severity !== filterSev) return false;
    if (search) {
      const q = search.toLowerCase();
      return (
        e.title.toLowerCase().includes(q) ||
        e.logSource.toLowerCase().includes(q) ||
        e.severity.toLowerCase().includes(q)
      );
    }
    return true;
  });

  return (
    <div className="fixed inset-0 z-50 flex">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative ml-auto flex h-full w-full max-w-md flex-col border-l border-ll-border/10 bg-ll-bg shadow-2xl">
        <div className="flex items-center justify-between border-b border-ll-border/10 p-4">
          <h2 className="font-sans text-lg font-semibold text-ll-text">Analysis History</h2>
          <button onClick={onClose} className="rounded p-1 text-ll-muted hover:text-ll-text">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-3 border-b border-ll-border/10 p-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ll-muted" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search history…"
              className="w-full rounded-lg border border-ll-border/10 bg-ll-input/60 py-2 pl-10 pr-3 font-mono text-sm text-ll-text placeholder:text-ll-muted focus:border-ll-accent focus:outline-none"
            />
          </div>
          <div className="flex flex-wrap gap-2">
            {["P1", "P2", "P3", "P4"].map((sev) => (
              <button
                key={sev}
                onClick={() => setFilterSev(filterSev === sev ? null : sev)}
                className={`rounded px-2.5 py-1 font-mono text-xs transition-colors ${
                  filterSev === sev
                    ? "bg-ll-accent text-black"
                    : "bg-ll-border/10 text-ll-muted hover:text-ll-text"
                }`}
              >
                {sev}
              </button>
            ))}
            <button
              onClick={() => setShowBookmarked(!showBookmarked)}
              className={`flex items-center gap-1 rounded px-2.5 py-1 font-mono text-xs transition-colors ${
                showBookmarked
                  ? "bg-ll-warn text-black"
                  : "bg-ll-border/10 text-ll-muted hover:text-ll-text"
              }`}
            >
              <Bookmark className="h-3 w-3" /> Saved
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto scrollbar-thin">
          {filtered.length === 0 ? (
            <div className="p-8 text-center text-ll-muted">
              <Clock className="mx-auto mb-3 h-10 w-10 opacity-40" />
              <p className="font-sans text-sm">
                {history.length === 0 ? "No analyses yet" : "No matches found"}
              </p>
            </div>
          ) : (
            <div className="divide-y divide-ll-border/5">
              {filtered.map((entry) => (
                <div
                  key={entry.id}
                  className="group flex cursor-pointer items-start gap-3 p-4 transition-colors hover:bg-ll-border/5"
                  onClick={() => onSelect(entry)}
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <SeverityBadge severity={entry.severity} />
                      <span className="truncate font-mono text-xs text-ll-muted">
                        {entry.logSource}
                      </span>
                    </div>
                    <p className="mt-1 truncate font-sans text-sm text-ll-text">
                      {entry.title}
                    </p>
                    <div className="mt-1 flex items-center gap-3 text-xs text-ll-muted">
                      <span>{entry.totalLines} lines</span>
                      <span>{entry.clusterCount} clusters</span>
                      <span>{entry.anomalyCount} anomalies</span>
                    </div>
                    <p className="mt-1 font-mono text-xs text-ll-muted/60">
                      {new Date(entry.timestamp).toLocaleString()}
                    </p>
                  </div>
                  <div className="flex shrink-0 flex-col gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                    <button
                      onClick={(e) => { e.stopPropagation(); onToggleBookmark(entry.id); }}
                      className="rounded p-1 text-ll-muted hover:text-ll-warn"
                      title={entry.bookmarked ? "Remove bookmark" : "Bookmark"}
                    >
                      {entry.bookmarked ? (
                        <BookmarkCheck className="h-4 w-4 text-ll-warn" />
                      ) : (
                        <Bookmark className="h-4 w-4" />
                      )}
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); onRemove(entry.id); }}
                      className="rounded p-1 text-ll-muted hover:text-ll-danger"
                      title="Delete"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {history.length > 0 && (
          <div className="border-t border-ll-border/10 p-3">
            <button
              onClick={onClear}
              className="w-full rounded-lg border border-ll-danger/30 px-3 py-2 font-sans text-xs text-ll-danger transition-colors hover:bg-ll-danger/10"
            >
              Clear All History ({history.length} entries)
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
