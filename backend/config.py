"""
Single source of truth for all LogLens configuration.
All values read from environment. Never call os.getenv outside this file.
"""

import os

from dotenv import load_dotenv

load_dotenv()

# LLM
GROQ_API_KEY: str | None = os.getenv("GROQ_API_KEY")
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama3-8b-8192")

# Embeddings
EMBEDDING_MODEL: str = os.getenv(
    "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
)

# Analysis tuning
ANOMALY_ZSCORE_THRESHOLD: float = float(os.getenv("ANOMALY_ZSCORE_THRESHOLD", "2.5"))
MAX_CLUSTERS: int = int(os.getenv("MAX_CLUSTERS", "8"))
MIN_CLUSTER_SIZE: int = int(os.getenv("MIN_CLUSTER_SIZE", "2"))
MAX_CLUSTER_ENCODE_SAMPLES: int = int(os.getenv("MAX_CLUSTER_ENCODE_SAMPLES", "200"))
TIMELINE_MAX_EVENTS: int = int(os.getenv("TIMELINE_MAX_EVENTS", "100"))

# API
MAX_LOG_SIZE_MB: int = int(os.getenv("MAX_LOG_SIZE_MB", "10"))
MAX_LOG_LINES: int = int(os.getenv("MAX_LOG_LINES", "50000"))
RATE_LIMIT: str = os.getenv("RATE_LIMIT", "10/minute")
ASK_TIMEOUT_SECONDS: int = int(os.getenv("ASK_TIMEOUT_SECONDS", "60"))
CORS_ORIGINS: list[str] = os.getenv(
    "CORS_ORIGINS", "http://localhost:5173"
).split(",")

# Observability
PHOENIX_PORT: int = int(os.getenv("PHOENIX_PORT", "6006"))
SKIP_PHOENIX: bool = os.getenv("SKIP_PHOENIX", "false").lower() == "true"

# Admin
ADMIN_API_KEY: str | None = os.getenv("ADMIN_API_KEY")

# Evals
MAX_EVAL_ROWS: int = int(os.getenv("MAX_EVAL_ROWS", "15"))
