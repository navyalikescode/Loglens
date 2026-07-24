import { useEffect, useState } from "react";
import { Check, Loader2 } from "lucide-react";

const STEPS = [
  { label: "Parsing logs…", hint: "Detecting format and extracting structured entries" },
  { label: "Detecting anomalies…", hint: "Statistical analysis for unusual patterns" },
  { label: "Clustering errors…", hint: "Grouping similar errors using embeddings" },
  { label: "Building timeline…", hint: "Reconstructing the sequence of events" },
  { label: "Identifying root cause…", hint: "Correlating signals to find likely causes" },
  { label: "Generating report…", hint: "Compiling findings into an incident report" },
];

export default function AnalysisPipeline({ active, finished, serverStep }) {
  const [step, setStep] = useState(0);
  const [started] = useState(() => Date.now());
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!active) { setStep(0); return; }
    if (finished) { setStep(STEPS.length); return; }
    if (typeof serverStep === "number" && serverStep >= 0) {
      setStep(serverStep);
      return;
    }
    const id = setInterval(() => {
      setStep((s) => Math.min(s + 1, STEPS.length - 1));
    }, 500);
    return () => clearInterval(id);
  }, [active, finished, serverStep]);

  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 200);
    return () => clearInterval(id);
  }, [active, started]);

  return (
    <div className="mx-auto max-w-xl space-y-4 p-6 font-sans">
      <div className="flex justify-between text-sm text-ll-muted">
        <span>Pipeline</span>
        <span className="font-mono">{elapsed}s elapsed</span>
      </div>
      <ul className="space-y-3">
        {STEPS.map(({ label, hint }, i) => {
          const done = finished || i < step;
          const running = active && !finished && i === step;
          return (
            <li
              key={label}
              className={`flex items-center gap-3 rounded-xl border px-4 py-3 transition-all ${
                done
                  ? "border-ll-accent/20 bg-ll-accent/5"
                  : running
                    ? "border-ll-warn/30 bg-ll-warn/5"
                    : "border-ll-border/10 bg-ll-card/30"
              }`}
            >
              {done ? (
                <Check className="h-5 w-5 shrink-0 text-ll-accent" />
              ) : running ? (
                <Loader2 className="h-5 w-5 shrink-0 animate-spin text-ll-warn" />
              ) : (
                <span className="h-5 w-5 shrink-0 rounded-full border-2 border-ll-border/20" />
              )}
              <div className="min-w-0">
                <span className={`text-sm ${done ? "text-ll-text" : running ? "text-ll-text" : "text-ll-muted"}`}>
                  {label}
                </span>
                {running && (
                  <p className="mt-0.5 text-xs text-ll-muted">{hint}</p>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
