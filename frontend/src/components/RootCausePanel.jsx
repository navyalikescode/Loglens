import { useState } from "react";
import { AlertTriangle, ChevronDown, ChevronRight, Lightbulb, Target } from "lucide-react";
import InfoTooltip from "./InfoTooltip.jsx";

const CONFIDENCE_STYLES = {
  high: "bg-ll-danger/20 text-ll-danger border-ll-danger/30",
  medium: "bg-ll-warn/20 text-ll-warn border-ll-warn/30",
  low: "bg-ll-accent/20 text-ll-accent border-ll-accent/30",
};

export default function RootCausePanel({ rootCauses }) {
  if (!rootCauses || rootCauses.length === 0) return null;

  return (
    <div className="px-6">
      <div className="mb-4 flex items-center gap-2">
        <h2 className="font-sans text-lg text-ll-muted">Root Cause Analysis</h2>
        <InfoTooltip text="These are the most likely causes of the issues found in your logs, ranked by confidence. Each includes evidence and recommended actions." />
      </div>
      <div className="space-y-3">
        {rootCauses.map((rc, i) => (
          <RootCauseCard key={i} rc={rc} index={i} />
        ))}
      </div>
    </div>
  );
}

function RootCauseCard({ rc, index }) {
  const [expanded, setExpanded] = useState(index === 0);
  const conf = rc.confidence?.toLowerCase() || "low";
  const style = CONFIDENCE_STYLES[conf] || CONFIDENCE_STYLES.low;

  return (
    <div className="rounded-lg border border-ll-border/10 bg-ll-card/40 overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-start gap-3 p-4 text-left transition-colors hover:bg-ll-border/5"
      >
        <Target className="mt-0.5 h-5 w-5 shrink-0 text-ll-accent" />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className={`rounded border px-2 py-0.5 font-mono text-xs font-semibold ${style}`}>
              {conf}
            </span>
            <span className="rounded bg-ll-border/10 px-2 py-0.5 font-mono text-xs text-ll-muted">
              {rc.category}
            </span>
          </div>
          <p className="mt-2 font-sans text-sm text-ll-text">{rc.hypothesis}</p>
        </div>
        {expanded ? (
          <ChevronDown className="mt-1 h-4 w-4 shrink-0 text-ll-muted" />
        ) : (
          <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-ll-muted" />
        )}
      </button>

      {expanded && (
        <div className="space-y-4 border-t border-ll-border/10 px-4 py-4">
          {rc.evidence?.length > 0 && (
            <div>
              <h4 className="mb-2 flex items-center gap-1.5 font-sans text-xs font-medium text-ll-muted uppercase tracking-wide">
                <AlertTriangle className="h-3.5 w-3.5" /> Evidence
              </h4>
              <ul className="space-y-1">
                {rc.evidence.map((ev, i) => (
                  <li key={i} className="flex items-start gap-2 font-mono text-xs text-ll-text">
                    <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-ll-muted" />
                    {ev}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {rc.recommended_actions?.length > 0 && (
            <div>
              <h4 className="mb-2 flex items-center gap-1.5 font-sans text-xs font-medium text-ll-muted uppercase tracking-wide">
                <Lightbulb className="h-3.5 w-3.5" /> Recommended Actions
              </h4>
              <ul className="space-y-1">
                {rc.recommended_actions.map((action, i) => (
                  <li key={i} className="flex items-start gap-2 font-mono text-xs text-ll-accent">
                    <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-ll-accent" />
                    {action}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {rc.first_signal_at && (
            <p className="font-mono text-xs text-ll-muted">
              First signal: {new Date(rc.first_signal_at).toLocaleString()}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
