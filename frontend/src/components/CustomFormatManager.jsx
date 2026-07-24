import { useEffect, useState } from "react";
import { AlertCircle, Check, Code2, Plus, Trash2, X } from "lucide-react";
import { addCustomFormat, deleteCustomFormat, getCustomFormats } from "../lib/api.js";
import InfoTooltip from "./InfoTooltip.jsx";

export default function CustomFormatManager() {
  const [formats, setFormats] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [name, setName] = useState("");
  const [pattern, setPattern] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  const loadFormats = async () => {
    try {
      const data = await getCustomFormats();
      setFormats(data.formats || []);
    } catch { /* offline */ }
  };

  useEffect(() => { loadFormats(); }, []);

  const handleAdd = async () => {
    setError(null);
    setSuccess(false);
    setLoading(true);
    try {
      await addCustomFormat({ name, pattern, description });
      setSuccess(true);
      setName("");
      setPattern("");
      setDescription("");
      loadFormats();
      setTimeout(() => { setSuccess(false); setShowAdd(false); }, 1500);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (formatName) => {
    try {
      await deleteCustomFormat(formatName);
      loadFormats();
    } catch { /* ignore */ }
  };

  return (
    <div className="mx-auto max-w-3xl p-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h2 className="flex items-center gap-2 font-sans text-xl font-semibold text-ll-text">
            <Code2 className="h-5 w-5 text-ll-accent" />
            Custom Log Formats
          </h2>
          <p className="mt-1 text-sm text-ll-muted">
            Define regex patterns to parse custom log formats
          </p>
        </div>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className="flex items-center gap-1.5 rounded-xl bg-ll-accent px-4 py-2 font-sans text-sm font-semibold text-black transition-all hover:brightness-110"
        >
          {showAdd ? <X className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
          {showAdd ? "Cancel" : "Add Format"}
        </button>
      </div>

      {showAdd && (
        <div className="mb-6 space-y-4 rounded-xl border border-ll-border/10 bg-ll-card/40 p-5">
          <div>
            <label className="mb-1 block font-sans text-xs font-medium text-ll-muted">Format Name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. my-app-logs"
              className="w-full rounded-lg border border-ll-border/10 bg-ll-input/60 px-3 py-2 font-mono text-sm text-ll-text placeholder:text-ll-muted focus:border-ll-accent focus:outline-none"
            />
          </div>
          <div>
            <div className="mb-1 flex items-center gap-1">
              <label className="font-sans text-xs font-medium text-ll-muted">Regex Pattern</label>
              <InfoTooltip text="Use Python-style named groups. Required: (?P<message>...). Optional: (?P<timestamp>...), (?P<level>...), (?P<service>...), (?P<host>...)." />
            </div>
            <textarea
              value={pattern}
              onChange={(e) => setPattern(e.target.value)}
              placeholder='e.g. (?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \[(?P<level>\w+)\] (?P<message>.*)'
              rows={3}
              className="w-full rounded-lg border border-ll-border/10 bg-ll-input/60 px-3 py-2 font-mono text-sm text-ll-text placeholder:text-ll-muted focus:border-ll-accent focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block font-sans text-xs font-medium text-ll-muted">Description (optional)</label>
            <input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Brief description of this format"
              className="w-full rounded-lg border border-ll-border/10 bg-ll-input/60 px-3 py-2 font-mono text-sm text-ll-text placeholder:text-ll-muted focus:border-ll-accent focus:outline-none"
            />
          </div>

          {error && (
            <div className="flex items-center gap-2 rounded-lg border border-ll-danger/30 bg-ll-danger/10 px-3 py-2 text-sm text-ll-danger">
              <AlertCircle className="h-4 w-4 shrink-0" />
              {error}
            </div>
          )}
          {success && (
            <div className="flex items-center gap-2 rounded-lg border border-ll-accent/30 bg-ll-accent/10 px-3 py-2 text-sm text-ll-accent">
              <Check className="h-4 w-4 shrink-0" />
              Format added successfully!
            </div>
          )}

          <button
            onClick={handleAdd}
            disabled={!name.trim() || !pattern.trim() || loading}
            className="rounded-lg bg-ll-accent px-4 py-2 font-sans text-sm font-semibold text-black transition-all hover:brightness-110 disabled:opacity-40"
          >
            {loading ? "Validating…" : "Add Format"}
          </button>
        </div>
      )}

      {formats.length === 0 ? (
        <div className="rounded-xl border border-ll-border/10 bg-ll-card/30 p-8 text-center">
          <Code2 className="mx-auto mb-3 h-10 w-10 text-ll-muted/30" />
          <p className="text-sm text-ll-muted">No custom formats defined yet.</p>
          <p className="mt-1 text-xs text-ll-muted/60">
            Built-in formats: nginx, python, docker, kubernetes, systemd
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {formats.map((fmt) => (
            <div key={fmt.name} className="rounded-xl border border-ll-border/10 bg-ll-card/40 p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-sm font-semibold text-ll-accent">{fmt.name}</span>
                    <span className="rounded bg-ll-border/10 px-1.5 py-0.5 font-mono text-[10px] text-ll-muted">
                      {fmt.groups.length} groups
                    </span>
                  </div>
                  {fmt.description && (
                    <p className="mt-1 text-xs text-ll-muted">{fmt.description}</p>
                  )}
                  <p className="mt-2 truncate font-mono text-[11px] text-ll-muted/60">{fmt.pattern}</p>
                  <div className="mt-2 flex flex-wrap gap-1">
                    {fmt.groups.map((g) => (
                      <span key={g} className="rounded bg-ll-accent/10 px-1.5 py-0.5 font-mono text-[10px] text-ll-accent">
                        {g}
                      </span>
                    ))}
                  </div>
                </div>
                <button
                  onClick={() => handleDelete(fmt.name)}
                  className="shrink-0 rounded p-1 text-ll-muted hover:text-ll-danger"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
