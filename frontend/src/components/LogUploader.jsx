import { useCallback, useRef, useState } from "react";
import { FileText, Plus, Upload, X } from "lucide-react";
import InfoTooltip from "./InfoTooltip.jsx";

export default function LogUploader({ onSubmit, disabled }) {
  const [text, setText] = useState("");
  const [files, setFiles] = useState([]);
  const [drag, setDrag] = useState(false);
  const fileInputRef = useRef(null);

  const lineCount = text ? text.split("\n").length : 0;

  const onDrop = useCallback((e) => {
    e.preventDefault();
    setDrag(false);
    const dropped = Array.from(e.dataTransfer.files || []);
    if (dropped.length) setFiles((prev) => [...prev, ...dropped]);
  }, []);

  const addFiles = (e) => {
    const selected = Array.from(e.target.files || []);
    if (selected.length) setFiles((prev) => [...prev, ...selected]);
    e.target.value = "";
  };

  const removeFile = (index) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const hasInput = Boolean(files.length > 0 || text.trim());

  const handleSubmit = () => {
    if (files.length > 0) {
      onSubmit({ logText: null, logFile: files[0], allFiles: files });
    } else {
      onSubmit({ logText: text, logFile: null, allFiles: [] });
    }
  };

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-6">
      <div
        role="button"
        tabIndex={0}
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={onDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`cursor-pointer rounded-xl border-2 border-dashed p-12 text-center transition-all ${
          drag
            ? "border-ll-accent bg-ll-accent/5 scale-[1.01]"
            : "border-ll-border/20 bg-ll-card/40 hover:border-ll-border/40"
        }`}
      >
        <Upload className="mx-auto mb-4 h-10 w-10 text-ll-muted" />
        <p className="font-sans text-lg text-ll-muted">
          Drop log files here or click to browse
        </p>
        <p className="mt-2 font-mono text-xs text-ll-muted/60">
          Supports multiple files — .log, .txt up to 10MB each
        </p>
        <input
          ref={fileInputRef}
          type="file"
          accept=".log,.txt,.json"
          multiple
          className="hidden"
          onChange={addFiles}
        />
      </div>

      {files.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm text-ll-muted">
            <FileText className="h-4 w-4" />
            <span className="font-sans">{files.length} file{files.length > 1 ? "s" : ""} selected</span>
            <InfoTooltip text="Multiple files will be concatenated and analyzed together, enabling cross-source correlation." />
          </div>
          <div className="space-y-1">
            {files.map((f, i) => (
              <div key={i} className="flex items-center gap-2 rounded-lg border border-ll-border/10 bg-ll-card/40 px-3 py-2">
                <FileText className="h-4 w-4 shrink-0 text-ll-accent" />
                <span className="min-w-0 flex-1 truncate font-mono text-sm text-ll-text">{f.name}</span>
                <span className="shrink-0 font-mono text-xs text-ll-muted">{(f.size / 1024).toFixed(1)}KB</span>
                <button onClick={() => removeFile(i)} className="shrink-0 rounded p-0.5 text-ll-muted hover:text-ll-danger">
                  <X className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
          <button
            onClick={() => fileInputRef.current?.click()}
            className="flex items-center gap-1 rounded px-2 py-1 font-sans text-xs text-ll-accent hover:bg-ll-accent/10"
          >
            <Plus className="h-3 w-3" /> Add more files
          </button>
        </div>
      )}

      <div className="relative">
        <textarea
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            if (e.target.value) setFiles([]);
          }}
          placeholder="Or paste raw logs here…"
          rows={10}
          className="w-full resize-y rounded-xl border border-ll-border/10 bg-ll-input/60 p-4 font-mono text-sm text-ll-text placeholder:text-ll-muted focus:border-ll-accent focus:outline-none"
        />
        {text.trim() && (
          <span className="absolute bottom-3 right-3 rounded bg-ll-accent/20 px-2 py-0.5 font-mono text-xs text-ll-accent">
            {lineCount} lines
          </span>
        )}
      </div>

      <button
        type="button"
        disabled={!hasInput || disabled}
        onClick={handleSubmit}
        className="w-full rounded-xl bg-ll-accent py-3.5 font-sans font-semibold text-black transition-all hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
      >
        Analyse Logs
      </button>
    </div>
  );
}
