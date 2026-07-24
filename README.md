# LogLens

Server logs are the most important source of truth when something breaks in production. But a 50,000-line log dump is impossible to read in an incident. LogLens analyses any log format in seconds and produces a structured incident report you can act on immediately—ready to paste into Jira or PagerDuty.

## How it works

```
Log Input → Auto Parser → Anomaly Detection → Error Clustering → Timeline → Root Cause → Report (Markdown + JSON)
```

## What makes it different from a chatbot

Anomaly detection (z-scores, silence gaps, cascade windows), error clustering (embeddings + DBSCAN), and root-cause ranking are **deterministic, local methods**—no LLM involved. That keeps analysis fast, free, and reproducible on modest hardware. A **single** LLM call (Groq `llama3-8b-8192` via LangChain LCEL) is used only to turn the structured findings into a polished narrative; if no API key is set, a full **template** report is generated instead.

## Supported log formats

| Format | Example |
|--------|---------|
| **Nginx** | `127.0.0.1 - - [10/Oct/2000:13:55:36 -0700] "GET /x HTTP/1.0" 200 2326` |
| **Python / uvicorn** | `INFO: 127.0.0.1:1 - "GET / HTTP/1.1" 200 OK` |
| **Python logging** | `2024-01-15 12:00:00,000 ERROR module:42 message` |
| **Docker** | `2024-01-15T12:00:00.000000000Z stderr F error` |
| **Kubernetes** | `5m Warning BackOff pod/my-pod Back-off restarting` |
| **systemd** | `Jan 15 12:00:00 hostname nginx[1]: started` |

Unknown lines fall back to a generic timestamp/keyword parser.

## Backend setup (`uv`)

```bash
cd backend
cp .env.example .env   # add GROQ_API_KEY if you want LLM prose
uv sync --all-groups
SKIP_PHOENIX=true uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Free Groq API key

Create a key at [https://console.groq.com](https://console.groq.com) (about two minutes, no credit card). Set `GROQ_API_KEY` in `backend/.env`.

## Running without Groq

Leave `GROQ_API_KEY` unset (or empty). The API still runs the full pipeline; `ReportGenerator` uses a **complete Jinja-style template** fallback so you always get usable Markdown sections.

## Phoenix observability

With `SKIP_PHOENIX=false`, the app registers OpenTelemetry export to Phoenix. For a local UI, start Phoenix (included in `backend/docker-compose.yml` as the `phoenix` service) and open port **6006**. Override the OTLP URL with `PHOENIX_OTLP_ENDPOINT` if needed.

## Evaluations

```bash
cd backend
SKIP_PHOENIX=true uv run python -m evals.eval_pipeline
```

Results are written under `backend/data/eval_results/eval_<timestamp>.json`.

## Tests

```bash
cd backend
SKIP_PHOENIX=1 uv run pytest tests/ -v
```

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Set `VITE_API_URL` if the API is not on `http://localhost:8000`.

## Docker

From `backend/`:

```bash
docker compose up --build
```

The API listens on **8000**; Phoenix on **6006**. Uses CPU PyTorch wheels via `uv` lock.

## Dashboard (UI)

*(Screenshot placeholder: capture the dark dashboard after an analysis run—upload zone, pipeline steps, anomaly chart, cluster cards, and Markdown report with severity badge.)*

- **Log upload**: drag/drop or paste, line count, analyse button.  
- **Pipeline**: staged progress (UX) while the single `/api/analyse` request runs.  
- **Anomaly chart**: per-minute stacked areas plus anomaly markers (falls back to level distribution without timestamps).  
- **Clusters**: representative message, counts, samples.  
- **Incident report**: Markdown render, copy/download JSON & Markdown.

## Project layout

See the repository tree: `backend/` (FastAPI, parsers, analysis, pipeline, report, evals, tests) and `frontend/` (Vite + React + Tailwind + Recharts).
