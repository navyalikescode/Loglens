import { Clock } from "lucide-react";
import InfoTooltip from "./InfoTooltip.jsx";

const EVENT_TYPE_COLORS = {
  error_spike: "border-ll-danger bg-ll-danger",
  anomaly: "border-ll-warn bg-ll-warn",
  recovery: "border-ll-accent bg-ll-accent",
  state_change: "border-blue-400 bg-blue-400",
  default: "border-ll-muted bg-ll-muted",
};

const SEVERITY_TEXT = {
  critical: "text-ll-danger",
  high: "text-ll-danger",
  medium: "text-ll-warn",
  low: "text-ll-accent",
};

export default function TimelinePanel({ timeline }) {
  if (!timeline || timeline.length === 0) return null;

  return (
    <div className="px-6">
      <div className="mb-4 flex items-center gap-2">
        <h2 className="font-sans text-lg text-ll-muted">Event Timeline</h2>
        <InfoTooltip text="A chronological sequence of significant events found in your logs — spikes, anomalies, state changes, and recoveries." />
      </div>
      <div className="relative">
        <div className="absolute left-[11px] top-0 bottom-0 w-px bg-ll-border/10" />
        <div className="space-y-0">
          {timeline.map((event, i) => {
            const typeColor = EVENT_TYPE_COLORS[event.event_type] || EVENT_TYPE_COLORS.default;
            const sevClass = SEVERITY_TEXT[event.severity?.toLowerCase()] || "text-ll-muted";
            return (
              <div key={i} className="relative flex items-start gap-4 py-3 pl-1">
                <div className={`relative z-10 mt-1.5 h-[9px] w-[9px] shrink-0 rounded-full border-2 ${typeColor}`} />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    {event.timestamp && (
                      <span className="flex items-center gap-1 font-mono text-xs text-ll-muted">
                        <Clock className="h-3 w-3" />
                        {new Date(event.timestamp).toLocaleTimeString()}
                      </span>
                    )}
                    <span className="rounded bg-ll-border/10 px-1.5 py-0.5 font-mono text-[10px] text-ll-muted">
                      {event.event_type}
                    </span>
                    {event.severity && (
                      <span className={`font-mono text-[10px] font-semibold uppercase ${sevClass}`}>
                        {event.severity}
                      </span>
                    )}
                  </div>
                  <p className="mt-1 font-mono text-xs text-ll-text leading-relaxed">
                    {event.description}
                  </p>
                  {event.related_entries > 0 && (
                    <span className="mt-1 inline-block font-mono text-[10px] text-ll-muted">
                      {event.related_entries} related entries
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
