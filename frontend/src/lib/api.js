const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export async function analyseLogs({ logText, logFile }) {
  const formData = new FormData();
  if (logFile) formData.append("log_file", logFile);
  else formData.append("log_text", logText);

  const response = await fetch(`${BASE_URL}/api/analyse`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    let errBody = {};
    try {
      errBody = await response.json();
    } catch {
      /* ignore */
    }
    const msg =
      errBody.message ||
      errBody.detail?.message ||
      (typeof errBody.detail === "string" ? errBody.detail : null) ||
      "Analysis failed";
    throw new Error(msg);
  }

  return response.json();
}

export async function analyseLogsStream({ logText, logFile, onProgress, onComplete, onError }) {
  const formData = new FormData();
  if (logFile) formData.append("log_file", logFile);
  else formData.append("log_text", logText);

  const response = await fetch(`${BASE_URL}/api/analyse-stream`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    let errBody = {};
    try { errBody = await response.json(); } catch { /* ignore */ }
    throw new Error(errBody.message || "Analysis failed");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        try {
          const data = JSON.parse(line.slice(6));
          if (data.type === "progress") onProgress?.(data);
          else if (data.type === "complete") onComplete?.(data.result);
          else if (data.type === "error") onError?.(data.message);
        } catch { /* malformed SSE line */ }
      }
    }
  }
}

export async function getHealth() {
  const response = await fetch(`${BASE_URL}/api/health`);
  return response.json();
}

export async function saveReport(reportJson) {
  const response = await fetch(`${BASE_URL}/api/reports`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(reportJson),
  });
  return response.json();
}

export async function getSharedReport(reportId) {
  const response = await fetch(`${BASE_URL}/api/reports/${reportId}`);
  if (!response.ok) throw new Error("Report not found");
  return response.json();
}

export async function getFormats() {
  const response = await fetch(`${BASE_URL}/api/formats`);
  return response.json();
}

export async function addCustomFormat({ name, pattern, description }) {
  const response = await fetch(`${BASE_URL}/api/formats/custom`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, pattern, description }),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail?.message || err.message || "Failed to add format");
  }
  return response.json();
}

export async function getCustomFormats() {
  const response = await fetch(`${BASE_URL}/api/formats/custom`);
  return response.json();
}

export async function deleteCustomFormat(name) {
  const response = await fetch(`${BASE_URL}/api/formats/custom/${encodeURIComponent(name)}`, {
    method: "DELETE",
  });
  return response.json();
}
