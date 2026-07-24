import { Filter, Search, X } from "lucide-react";

const SEVERITIES = ["P1", "P2", "P3", "P4"];

export default function ResultsToolbar({ filters, onFiltersChange }) {
  const { search = "", severities = [] } = filters;

  const toggleSeverity = (sev) => {
    const next = severities.includes(sev)
      ? severities.filter((s) => s !== sev)
      : [...severities, sev];
    onFiltersChange({ ...filters, severities: next });
  };

  const hasFilters = search || severities.length > 0;

  return (
    <div className="mx-6 mb-6 flex flex-wrap items-center gap-3 rounded-xl border border-ll-border/10 bg-ll-card/40 p-3">
      <Filter className="h-4 w-4 text-ll-muted" />

      <div className="relative flex-1 min-w-[200px]">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ll-muted" />
        <input
          type="text"
          value={search}
          onChange={(e) => onFiltersChange({ ...filters, search: e.target.value })}
          placeholder="Search errors, messages…"
          className="w-full rounded-lg border border-ll-border/10 bg-ll-input/60 py-1.5 pl-10 pr-3 font-mono text-sm text-ll-text placeholder:text-ll-muted focus:border-ll-accent focus:outline-none"
        />
      </div>

      <div className="flex gap-1.5">
        {SEVERITIES.map((sev) => (
          <button
            key={sev}
            onClick={() => toggleSeverity(sev)}
            className={`rounded px-2.5 py-1 font-mono text-xs font-semibold transition-all ${
              severities.includes(sev)
                ? sev === "P1"
                  ? "bg-ll-danger text-white"
                  : sev === "P2"
                    ? "bg-orange-600 text-white"
                    : sev === "P3"
                      ? "bg-ll-warn text-black"
                      : "bg-ll-accent text-black"
                : "bg-ll-border/10 text-ll-muted hover:text-ll-text"
            }`}
          >
            {sev}
          </button>
        ))}
      </div>

      {hasFilters && (
        <button
          onClick={() => onFiltersChange({ search: "", severities: [] })}
          className="flex items-center gap-1 rounded px-2 py-1 text-xs text-ll-muted hover:text-ll-text"
        >
          <X className="h-3 w-3" /> Clear
        </button>
      )}
    </div>
  );
}
