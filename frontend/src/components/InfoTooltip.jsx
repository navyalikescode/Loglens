import { useState } from "react";
import { HelpCircle } from "lucide-react";

export default function InfoTooltip({ text }) {
  const [show, setShow] = useState(false);
  return (
    <span className="relative inline-flex">
      <button
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => setShow(false)}
        onClick={() => setShow((s) => !s)}
        className="text-ll-muted/60 transition-colors hover:text-ll-accent"
      >
        <HelpCircle className="h-4 w-4" />
      </button>
      {show && (
        <span className="absolute bottom-full left-1/2 z-50 mb-2 w-64 -translate-x-1/2 rounded-lg border border-ll-border/10 bg-ll-surface p-3 font-sans text-xs leading-relaxed text-ll-text shadow-xl">
          {text}
          <span className="absolute left-1/2 top-full -translate-x-1/2 border-4 border-transparent border-t-ll-surface" />
        </span>
      )}
    </span>
  );
}
