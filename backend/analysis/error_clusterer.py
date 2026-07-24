"""
Groups similar error messages together using embeddings + DBSCAN clustering.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
import numpy as np
import structlog
from sklearn.cluster import DBSCAN

import config
from parsers.base_parser import LogEntry, LogLevel

logger = structlog.get_logger(__name__)

_UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.I,
)
_HEX_HASH_RE = re.compile(r"\b[0-9a-f]{32,64}\b", re.I)
_IP_RE = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
)
# Unix-ish paths and Windows paths
_PATH_RE = re.compile(
    r"(?:/[A-Za-z0-9_.\-~]+)+|(?:[a-z]:\\(?:[^\\\s]+\\)*[^\\\s]+)",
    re.I,
)
_NUM_RE = re.compile(r"\d+")

_HIGH_SIGNAL = (
    "exception",
    "traceback",
    "failed",
    "refused",
    "timeout",
    "killed",
    "crash",
    "fatal",
    "panic",
    "segfault",
    "oom",
    "memory",
    "disk",
    "permission",
)


@dataclass
class ErrorCluster:
    cluster_id: int
    representative_message: str
    count: int
    first_seen: datetime
    last_seen: datetime
    severity: str
    sample_messages: list[str]
    affected_services: list[str]


class ErrorClusterer:
    """
    Groups error and critical log entries by semantic similarity.
    Embedding model loads lazily on first cluster() call.
    """

    _model: object | None = None

    def _get_model(self):
        if ErrorClusterer._model is None:
            from sentence_transformers import SentenceTransformer

            ErrorClusterer._model = SentenceTransformer(config.EMBEDDING_MODEL)
        return ErrorClusterer._model

    def _normalize_message_for_dedup(self, msg: str) -> str:
        s = msg.lower()
        s = _UUID_RE.sub("<ID>", s)
        s = _IP_RE.sub("<IP>", s)
        s = _PATH_RE.sub("<PATH>", s)
        s = _HEX_HASH_RE.sub("<ID>", s)
        s = _NUM_RE.sub("<NUM>", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    def _deduplicate_messages(
        self, messages: list[str]
    ) -> tuple[list[str], np.ndarray, list[int]]:
        """
        Exact dedup after normalization. Returns canonical reps, counts per unique,
        and mapping from each original row -> unique index.
        """
        key_to_uid: dict[str, int] = {}
        unique_reps: list[str] = []
        counts: list[int] = []
        err_to_unique: list[int] = []

        for msg in messages:
            key = self._normalize_message_for_dedup(msg)
            if key not in key_to_uid:
                key_to_uid[key] = len(unique_reps)
                unique_reps.append(msg[:2000])
                counts.append(0)
            uid = key_to_uid[key]
            counts[uid] += 1
            err_to_unique.append(uid)

        return unique_reps, np.asarray(counts, dtype=np.int64), err_to_unique

    def _priority_tier(self, msg: str) -> int:
        u = msg.upper()
        if "ERROR" in u or "CRITICAL" in u or "CRIT]" in u or "[CRIT" in u:
            return 0
        low = msg.lower()
        if any(w in low for w in _HIGH_SIGNAL):
            return 1
        return 2

    def _prioritized_sample_indices(
        self, unique_reps: list[str], unique_count: np.ndarray, max_n: int
    ) -> list[int]:
        """Return up to max_n unique indices, highest priority first."""
        if len(unique_reps) <= max_n:
            return list(range(len(unique_reps)))
        indices = list(range(len(unique_reps)))
        indices.sort(
            key=lambda i: (
                self._priority_tier(unique_reps[i]),
                -int(unique_count[i]),
                i,
            )
        )
        return sorted(indices[:max_n])

    def _encode_batch(self, messages: list[str]) -> np.ndarray:
        model = self._get_model()
        try:
            emb = model.encode(
                messages,
                batch_size=32,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
        except TypeError:
            emb = model.encode(messages, show_progress_bar=False)
        return np.asarray(emb, dtype=np.float32)

    def _build_clusters(
        self,
        err_entries: list[LogEntry],
        unique_reps: list[str],
        unique_count: np.ndarray,
        err_to_unique: list[int],
        kept_unique_indices: list[int],
        embeddings: np.ndarray,
        labels: np.ndarray,
        dropped_unique_indices: list[int],
    ) -> list[ErrorCluster]:
        row_to_unique = kept_unique_indices
        out: list[ErrorCluster] = []

        def entry_indices_for_uniques(uniques: set[int]) -> list[int]:
            return [i for i, u in enumerate(err_to_unique) if u in uniques]

        def make_cluster(
            cluster_id: int,
            uniques: set[int],
            sub_emb: np.ndarray | None,
            rows: list[int] | None,
        ) -> None:
            if not uniques:
                return
            members_idx = entry_indices_for_uniques(uniques)
            if not members_idx:
                return
            if sub_emb is not None and rows is not None and len(rows) > 0:
                centroid = np.mean(sub_emb, axis=0, keepdims=True)
                norm = np.linalg.norm(centroid) or 1.0
                centroid = centroid / norm
                sims = (sub_emb @ centroid.T).ravel()
                best_local = int(np.argmax(sims))
                best_u = row_to_unique[rows[best_local]]
                rep = unique_reps[best_u]
            else:
                u0 = next(iter(uniques))
                rep = unique_reps[u0]

            times = [
                err_entries[i].timestamp
                for i in members_idx
                if err_entries[i].timestamp
            ]
            if not times:
                times = [datetime.min]
            services = sorted(
                {
                    err_entries[i].service
                    for i in members_idx
                    if err_entries[i].service
                }
            )
            samples = [err_entries[i].message[:300] for i in members_idx[:3]]
            sev = (
                "critical"
                if any(
                    err_entries[i].level == LogLevel.CRITICAL for i in members_idx
                )
                else "high"
            )
            total = int(sum(unique_count[u] for u in uniques))
            out.append(
                ErrorCluster(
                    cluster_id=cluster_id,
                    representative_message=rep[:500],
                    count=total,
                    first_seen=min(times),
                    last_seen=max(times),
                    severity=sev,
                    sample_messages=samples,
                    affected_services=list(services)[:10],
                )
            )

        # Dropped uniques (never encoded): one cluster per unique
        for j in dropped_unique_indices:
            u_set = {j}
            members_idx = entry_indices_for_uniques(u_set)
            if not members_idx:
                continue
            times = [
                err_entries[i].timestamp
                for i in members_idx
                if err_entries[i].timestamp
            ]
            if not times:
                times = [datetime.min]
            services = sorted(
                {
                    err_entries[i].service
                    for i in members_idx
                    if err_entries[i].service
                }
            )
            samples = [err_entries[i].message[:300] for i in members_idx[:3]]
            sev = (
                "critical"
                if any(
                    err_entries[i].level == LogLevel.CRITICAL for i in members_idx
                )
                else "high"
            )
            out.append(
                ErrorCluster(
                    cluster_id=-3000 - j,
                    representative_message=unique_reps[j][:500],
                    count=int(unique_count[j]),
                    first_seen=min(times),
                    last_seen=max(times),
                    severity=sev,
                    sample_messages=samples,
                    affected_services=list(services)[:10],
                )
            )

        if embeddings.size == 0:
            out.sort(key=lambda c: c.count, reverse=True)
            return out[: config.MAX_CLUSTERS]

        by_label: dict[int, list[int]] = {}
        for row, lab in enumerate(labels.tolist()):
            by_label.setdefault(int(lab), []).append(row)

        for lab, rows in by_label.items():
            uniques = {row_to_unique[r] for r in rows}
            if lab == -1:
                for r in rows:
                    u = row_to_unique[r]
                    sub = embeddings[[r]]
                    make_cluster(-1000 - r, {u}, sub, [r])
                continue
            sub = embeddings[rows]
            make_cluster(lab, uniques, sub, rows)

        out.sort(key=lambda c: c.count, reverse=True)
        return out[: config.MAX_CLUSTERS]

    def cluster(self, entries: list[LogEntry]) -> list[ErrorCluster]:
        err_entries = [
            e
            for e in entries
            if e.level in (LogLevel.ERROR, LogLevel.CRITICAL)
        ]
        if not err_entries:
            return []

        if len(err_entries) < config.MIN_CLUSTER_SIZE:
            singles: list[ErrorCluster] = []
            for i, e in enumerate(err_entries):
                ts = e.timestamp or datetime.min
                singles.append(
                    ErrorCluster(
                        cluster_id=-1 - i,
                        representative_message=e.message[:500],
                        count=1,
                        first_seen=ts,
                        last_seen=ts,
                        severity="high"
                        if e.level == LogLevel.CRITICAL
                        else "medium",
                        sample_messages=[e.message[:300]],
                        affected_services=[s for s in [e.service] if s],
                    )
                )
            return sorted(singles, key=lambda c: c.count, reverse=True)

        messages = [e.message[:2000] for e in err_entries]
        unique_reps, unique_count, err_to_unique = self._deduplicate_messages(
            messages
        )
        u_n = len(unique_reps)
        logger.info(
            "clusterer_dedup_complete",
            original_count=len(messages),
            unique_count=u_n,
            reduction_ratio=f"{(1 - u_n / max(len(messages), 1)):.1%}",
        )

        kept = self._prioritized_sample_indices(
            unique_reps, unique_count, config.MAX_CLUSTER_ENCODE_SAMPLES
        )
        kept_set = set(kept)
        dropped = [j for j in range(u_n) if j not in kept_set]

        sampled_reps = [unique_reps[i] for i in kept]
        embeddings = (
            self._encode_batch(sampled_reps) if sampled_reps else np.zeros((0, 1))
        )

        if len(embeddings) == 0:
            labels = np.array([], dtype=np.int64)
        elif len(embeddings) == 1:
            labels = np.array([0], dtype=np.int64)
        else:
            clustering = DBSCAN(
                eps=0.3,
                min_samples=config.MIN_CLUSTER_SIZE,
                metric="cosine",
            )
            labels = clustering.fit_predict(embeddings)

        return self._build_clusters(
            err_entries,
            unique_reps,
            unique_count,
            err_to_unique,
            kept,
            embeddings,
            labels,
            dropped,
        )
