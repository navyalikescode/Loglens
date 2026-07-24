import { useEffect, useState } from "react";
import { getHealth } from "../lib/api.js";

const STATUS = {
  connected: { color: "bg-green-500", label: "Connected" },
  llm: { color: "bg-ll-accent", label: "Connected (LLM active)" },
  degraded: { color: "bg-ll-warn", label: "Connected (no LLM)" },
  disconnected: { color: "bg-ll-danger", label: "Backend offline" },
  checking: { color: "bg-ll-muted", label: "Checking…" },
};

export default function HealthIndicator() {
  const [status, setStatus] = useState("checking");
  const [details, setDetails] = useState(null);
  const [showTooltip, setShowTooltip] = useState(false);

  useEffect(() => {
    let mounted = true;
    const check = async () => {
      try {
        const data = await getHealth();
        if (!mounted) return;
        setDetails(data);
        setStatus(data.groq_configured ? "llm" : "degraded");
      } catch {
        if (!mounted) return;
        setStatus("disconnected");
        setDetails(null);
      }
    };
    check();
    const id = setInterval(check, 30000);
    return () => { mounted = false; clearInterval(id); };
  }, []);

  const s = STATUS[status];

  return (
    <div className="relative">
      <button
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
        className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-xs font-mono text-ll-muted transition-colors hover:bg-ll-border/10"
      >
        <span className={`h-2 w-2 rounded-full ${s.color} ${status === "checking" ? "animate-pulse" : ""}`} />
        <span className="hidden sm:inline">{s.label}</span>
      </button>
      {showTooltip && details && (
        <div className="absolute right-0 top-full z-50 mt-2 w-56 rounded-lg border border-ll-border/10 bg-ll-surface p-3 text-xs shadow-xl">
          <p className="text-ll-text font-medium">Backend Status</p>
          <div className="mt-2 space-y-1 text-ll-muted">
            <p>Mode: <span className="text-ll-accent">{details.report_mode}</span></p>
            <p>Prompt: <span className="text-ll-accent">v{details.prompt_version}</span></p>
            <p>LLM: <span className={details.groq_configured ? "text-green-400" : "text-ll-warn"}>{details.groq_configured ? "Active" : "Template fallback"}</span></p>
          </div>
        </div>
      )}
    </div>
  );
}
