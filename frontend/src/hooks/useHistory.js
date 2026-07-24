import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "ll-history";
const MAX_ENTRIES = 50;

function loadHistory() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
  } catch {
    return [];
  }
}

function persistHistory(entries) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
  } catch {
    /* quota exceeded — silently drop oldest */
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(entries.slice(0, 20)));
    } catch { /* give up */ }
  }
}

function generateTitle(result) {
  const source = result?.metadata?.log_source || "unknown";
  const severity = result?.severity || "P4";
  const lines = result?.metadata?.total_lines || 0;
  return `${source} analysis — ${severity} (${lines} lines)`;
}

export default function useHistory() {
  const [history, setHistory] = useState(loadHistory);

  useEffect(() => {
    persistHistory(history);
  }, [history]);

  const addEntry = useCallback((result) => {
    const entry = {
      id: crypto.randomUUID(),
      timestamp: new Date().toISOString(),
      title: generateTitle(result),
      severity: result?.severity || "P4",
      logSource: result?.metadata?.log_source || "unknown",
      totalLines: result?.metadata?.total_lines || 0,
      clusterCount: result?.error_clusters?.length || 0,
      anomalyCount: result?.anomalies?.length || 0,
      bookmarked: false,
      result,
    };
    setHistory((prev) => [entry, ...prev].slice(0, MAX_ENTRIES));
    return entry.id;
  }, []);

  const removeEntry = useCallback((id) => {
    setHistory((prev) => prev.filter((e) => e.id !== id));
  }, []);

  const toggleBookmark = useCallback((id) => {
    setHistory((prev) =>
      prev.map((e) => (e.id === id ? { ...e, bookmarked: !e.bookmarked } : e))
    );
  }, []);

  const clearHistory = useCallback(() => {
    setHistory([]);
  }, []);

  const getEntry = useCallback(
    (id) => history.find((e) => e.id === id) || null,
    [history]
  );

  return { history, addEntry, removeEntry, toggleBookmark, clearHistory, getEntry };
}
