# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Evidence-backed sampling-frequency and adjustment decisions."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import select

from rfinance.domain.eligibility.metadata import (
    FORMULA_VERSION,
    AdjustmentStatus,
    SamplingFrequency,
)
from rfinance.storage.models.instrument_metadata import InstrumentMetadataEventRecord
from rfinance.storage.models.instrument_registry import InstrumentRegistryRecord

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.orm import Session, sessionmaker

_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
_COPY_CHUNK_BYTES = 1024 * 1024
MAX_EVIDENCE_BYTES = 25 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class MetadataDecision:
    """A persisted metadata decision with its evidence and reviewer."""

    event_id: str
    instrument_id: str
    source_id: str
    sampling_frequency: SamplingFrequency
    adjustment_status: AdjustmentStatus
    decision: str
    reviewer_label: str
    notes: str
    evidence_reference: str
    evidence_sha256: str
    decided_at_utc: str
    methodology_version: str


class InstrumentMetadataEvidenceService:
    """Record evidence before a price-series metadata claim may be used."""

    def __init__(
        self,
        sessions: sessionmaker[Session],
        *,
        data_directory: Path | None = None,
    ) -> None:
        self._sessions = sessions
        self._data_directory = data_directory

    def record_from_file(
        self,
        instrument_id: str,
        *,
        source_id: str,
        sampling_frequency: SamplingFrequency,
        adjustment_status: AdjustmentStatus,
        decision: str,
        reviewer_label: str,
        notes: str,
        evidence_file: Path,
        decided_at: datetime | None = None,
    ) -> MetadataDecision:
        """Archive a user-selected evidence file and append one metadata decision."""

        if not isinstance(sampling_frequency, SamplingFrequency):
            raise ValueError("sampling_frequency must be a SamplingFrequency")
        if not isinstance(adjustment_status, AdjustmentStatus):
            raise ValueError("adjustment_status must be an AdjustmentStatus")
        if decision not in {"VERIFIED", "REJECTED"}:
            raise ValueError("decision must be VERIFIED or REJECTED")
        for name, value in (
            ("reviewer_label", reviewer_label),
            ("notes", notes),
            ("source_id", source_id),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must not be empty")
        moment = datetime.now(UTC) if decided_at is None else decided_at
        if moment.tzinfo is None or moment.utcoffset() is None:
            raise ValueError("decided_at must be timezone-aware")
        moment_utc = moment.astimezone(UTC)

        if self._data_directory is None:
            raise RuntimeError("a persistent data directory is required for evidence review")
        try:
            source = evidence_file.expanduser().resolve(strict=True)
        except OSError as error:
            raise ValueError(f"selected evidence file is unavailable: {error}") from error
        if not source.is_file():
            raise ValueError("selected evidence path is not a regular file")
        if source.stat().st_size > MAX_EVIDENCE_BYTES:
            raise ValueError("evidence file exceeds the 25 MiB limit")

        root = self._data_directory.resolve()
        root.mkdir(parents=True, exist_ok=True)
        archive = root / "Documents" / "MetadataEvidence"
        archive.mkdir(parents=True, exist_ok=True)
        if not archive.resolve().is_relative_to(root):
            raise ValueError("the metadata evidence archive resolves outside RFinance data storage")

        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", source.name)[:120] or "evidence"
        destination = archive / f"{uuid4()}_{safe_name}"
        temporary = archive / f".{destination.name}.part"
        digest = hashlib.sha256()
        copied = 0
        try:
            with source.open("rb") as source_handle, temporary.open("xb") as target:
                while chunk := source_handle.read(_COPY_CHUNK_BYTES):
                    copied += len(chunk)
                    if copied > MAX_EVIDENCE_BYTES:
                        raise ValueError("evidence file grew beyond the configured size limit")
                    digest.update(chunk)
                    target.write(chunk)
                target.flush()
                os.fsync(target.fileno())
            temporary.replace(destination)
        except Exception:
            temporary.unlink(missing_ok=True)
            destination.unlink(missing_ok=True)
            raise

        raw = (
            f"{instrument_id}|{source_id.strip()}|{sampling_frequency.value}|"
            f"{adjustment_status.value}|{decision}|{digest.hexdigest()}|"
            f"{moment_utc.date().isoformat()}"
        )
        event_id = hashlib.sha256(raw.encode()).hexdigest()[:32]
        with self._sessions.begin() as session:
            instrument = session.get(InstrumentRegistryRecord, instrument_id)
            if instrument is None:
                raise ValueError("instrument does not exist in the local registry")
            if instrument.verification_status != "VERIFIED" or instrument.active is False:
                raise ValueError("only an active VERIFIED instrument can receive metadata evidence")
            if session.get(InstrumentMetadataEventRecord, event_id) is not None:
                raise ValueError("an identical metadata decision is already recorded")
            session.add(
                InstrumentMetadataEventRecord(
                    event_id=event_id,
                    instrument_id=instrument_id,
                    source_id=source_id.strip(),
                    sampling_frequency=sampling_frequency.value,
                    adjustment_status=adjustment_status.value,
                    decision=decision,
                    reviewer_label=reviewer_label.strip(),
                    notes=notes.strip(),
                    evidence_reference=destination.relative_to(root).as_posix(),
                    evidence_sha256=digest.hexdigest(),
                    decided_at_utc=moment_utc.isoformat(),
                    methodology_version=FORMULA_VERSION,
                )
            )
        return MetadataDecision(
            event_id=event_id,
            instrument_id=instrument_id,
            source_id=source_id.strip(),
            sampling_frequency=sampling_frequency,
            adjustment_status=adjustment_status,
            decision=decision,
            reviewer_label=reviewer_label.strip(),
            notes=notes.strip(),
            evidence_reference=destination.relative_to(root).as_posix(),
            evidence_sha256=digest.hexdigest(),
            decided_at_utc=moment_utc.isoformat(),
            methodology_version=FORMULA_VERSION,
        )

    def latest_verified(self, instrument_id: str, source_id: str) -> MetadataDecision | None:
        """Return the latest VERIFIED decision, or ``None`` when evidence is absent."""

        with self._sessions() as session:
            events = session.scalars(
                select(InstrumentMetadataEventRecord)
                .where(
                    InstrumentMetadataEventRecord.instrument_id == instrument_id,
                    InstrumentMetadataEventRecord.source_id == source_id,
                )
                .order_by(
                    InstrumentMetadataEventRecord.decided_at_utc.desc(),
                    InstrumentMetadataEventRecord.event_id.desc(),
                )
            ).all()
        for event in events:
            if event.decision != "VERIFIED":
                return None
            return MetadataDecision(
                event_id=event.event_id,
                instrument_id=event.instrument_id,
                source_id=event.source_id,
                sampling_frequency=SamplingFrequency(event.sampling_frequency),
                adjustment_status=AdjustmentStatus(event.adjustment_status),
                decision=event.decision,
                reviewer_label=event.reviewer_label,
                notes=event.notes,
                evidence_reference=event.evidence_reference,
                evidence_sha256=event.evidence_sha256,
                decided_at_utc=event.decided_at_utc,
                methodology_version=event.methodology_version,
            )
        return None
