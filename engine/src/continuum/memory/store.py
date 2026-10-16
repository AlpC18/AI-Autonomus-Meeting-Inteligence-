# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Yüksel Alp Çiğtekin / AI Meeting Intelligence. All rights reserved.

"""Persistent, tenant-isolated vector memory of meeting transcripts.

Isolation is enforced twice. Each tenant/project pair has its own Qdrant
collection, so a query physically cannot reach another scope's vectors; and
every query also filters on the tenant and project stored with each point.
There is deliberately no way to read or write without a :class:`TenantScope`.
"""

import hashlib
import threading
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from types import TracebackType
from typing import Self

import numpy as np
from qdrant_client import QdrantClient, models

from continuum.memory.scope import TenantScope
from continuum.transcript import Segment

Embedder = Callable[[list[str]], Sequence[np.ndarray]]
"""Turns texts into vectors, one per text, all of the store's dimension."""

_POINT_NAMESPACE = uuid.UUID("6f0e2a8e-4b1f-4d55-9c53-1c2f6f8a7d10")


@dataclass(frozen=True, slots=True)
class Meeting:
    """The recording session a segment belongs to.

    ``started_at`` must be timezone-aware; segment times are offsets from it.
    """

    meeting_id: str
    started_at: datetime


@dataclass(frozen=True, slots=True)
class MemoryHit:
    """One stored transcript segment returned by a search, best match first.

    ``disputed`` is true when the statement contradicted the record at the time
    it was said, so it must not be treated as a record itself.
    """

    text: str
    speaker: str
    source: str
    meeting_id: str
    spoken_at: datetime
    score: float
    tenant_id: str
    project_id: str
    disputed: bool = False


class MemoryStore:
    """Owns the on-disk vector database. Use as a context manager.

    Only one process may open a given ``directory`` at a time (embedded Qdrant
    locks it). Obtain a :class:`ScopedMemory` with :meth:`scoped` to do
    anything; the store itself exposes no read or write operations.

    ``model_id`` names the embedding model behind ``embed``. Data stored with
    one model is invisible when the store is opened with another.
    """

    # ponytail: embedded Qdrant scans vectors linearly and stores them
    # unencrypted; fine for tens of thousands of segments per project. Move to
    # a Qdrant server (same client API) and disk encryption beyond that.
    def __init__(
        self, directory: Path, embed: Embedder, dimensions: int, model_id: str = "default"
    ) -> None:
        self._client = QdrantClient(path=str(directory))
        self._embed = embed
        self._dimensions = dimensions
        # Vectors from different models are not comparable, so each model gets
        # its own collections: switching model starts fresh instead of mixing.
        self._model_tag = hashlib.sha256(f"{model_id}/{dimensions}".encode()).hexdigest()[:8]
        # Embedded Qdrant is not safe for concurrent calls from several threads.
        self._lock = threading.Lock()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._client.close()

    def scoped(self, scope: TenantScope) -> "ScopedMemory":
        """Return the memory of exactly one tenant and project."""
        return ScopedMemory(
            self._client, self._lock, self._embed, self._dimensions, scope, self._model_tag
        )


class ScopedMemory:
    """Reads and writes the memory of a single :class:`TenantScope`.

    Created by :meth:`MemoryStore.scoped`. Calls block while embedding and
    writing to disk, so run them in a worker thread from async code.
    """

    def __init__(
        self,
        client: QdrantClient,
        lock: threading.Lock,
        embed: Embedder,
        dimensions: int,
        scope: TenantScope,
        model_tag: str,
    ) -> None:
        self._client = client
        self._lock = lock
        self._embed = embed
        self._dimensions = dimensions
        self._scope = scope
        self._collection = f"{scope.collection_name}_{model_tag}"

    def add_segment(self, segment: Segment, meeting: Meeting, *, disputed: bool = False) -> None:
        """Store one transcript segment, tagged with scope, speaker and time.

        Pass ``disputed=True`` for a statement that was flagged as
        contradicting the record, so later fact checks do not rely on it.

        Storing the same segment of the same meeting again replaces the
        earlier copy instead of duplicating it.
        """
        vector = self._embed([segment.text])[0]
        point_id = uuid.uuid5(
            _POINT_NAMESPACE, f"{meeting.meeting_id}/{segment.source}/{segment.start!r}"
        )
        point = models.PointStruct(
            id=str(point_id),
            vector=np.asarray(vector, dtype=np.float32).tolist(),
            payload={
                "tenant_id": self._scope.tenant_id,
                "project_id": self._scope.project_id,
                "meeting_id": meeting.meeting_id,
                "text": segment.text,
                "speaker": segment.speaker,
                "source": segment.source,
                "start": segment.start,
                "end": segment.end,
                "spoken_at": (meeting.started_at + timedelta(seconds=segment.start)).isoformat(),
                "disputed": disputed,
            },
        )
        with self._lock:
            if not self._client.collection_exists(self._collection):
                self._client.create_collection(
                    self._collection,
                    vectors_config=models.VectorParams(
                        size=self._dimensions, distance=models.Distance.COSINE
                    ),
                )
            self._client.upsert(self._collection, [point])

    def search(self, query: str, limit: int = 5) -> list[MemoryHit]:
        """Return up to ``limit`` stored segments most similar to ``query``.

        Only this scope's data is searched. Returns an empty list when the
        scope has stored nothing yet.

        Raises:
            ValueError: if ``limit`` is less than 1.
        """
        if limit < 1:
            raise ValueError(f"limit must be at least 1, got {limit}")
        vector = np.asarray(self._embed([query])[0], dtype=np.float32).tolist()
        with self._lock:
            if not self._client.collection_exists(self._collection):
                return []
            response = self._client.query_points(
                self._collection,
                query=vector,
                query_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="tenant_id", match=models.MatchValue(value=self._scope.tenant_id)
                        ),
                        models.FieldCondition(
                            key="project_id",
                            match=models.MatchValue(value=self._scope.project_id),
                        ),
                    ]
                ),
                limit=limit,
            )
        return [
            MemoryHit(
                text=point.payload["text"],
                speaker=point.payload["speaker"],
                source=point.payload["source"],
                meeting_id=point.payload["meeting_id"],
                spoken_at=datetime.fromisoformat(point.payload["spoken_at"]),
                score=point.score,
                tenant_id=point.payload["tenant_id"],
                project_id=point.payload["project_id"],
                disputed=bool(point.payload.get("disputed", False)),
            )
            for point in response.points
            if point.payload is not None
        ]
