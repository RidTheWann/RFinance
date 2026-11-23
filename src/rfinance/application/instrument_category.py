# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Evidence-backed instrument category and lot-size decisions."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import select

from rfinance.analysis.portfolio.valuation import ValuationCategory
from rfinance.domain.portfolio.allocation import InvestableInstrument
from rfinance.storage.models.instrument_category import InstrumentCategoryEventRecord
from rfinance.storage.models.instrument_registry import InstrumentRegistryRecord

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy.orm import Session, sessionmaker

FORMULA_VERSION = "instrument-category-v1"
_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
_ALLOWED_CATEGORIES = frozenset(
    {
        ValuationCategory.EQUITY_INDEX,
        ValuationCategory.DIVIDEND_EQUITY,
        ValuationCategory.MONEY_MARKET,
    }
)
_COPY_CHUNK_BYTES = 1024 * 1024
MAX_EVIDENCE_BYTES = 25 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class CategoryDecision:
    """A persisted category decision with its evidence and reviewer."""

    event_id: str
    instrument_id: str
    category: ValuationCategory
    lot_size: Decimal
    decision: str
    reviewer_label: str
    notes: str
    evidence_reference: str
    evidence_sha256: str
    decided_at_utc: str

    def __post_init__(self) -> None:
        if not _SHA256_PATTERN.fullmatch(self.evidence_sha256):
            raise ValueError("evidence_sha256 must be a 64-character hex digest")


class InstrumentCategoryService:
    """Promote or reject category evidence only with explicit reviewer input."""

    def __init__(
        self,
        sessions: sessionmaker[Session],
        *,
        data_directory: Path | None = None,
    ) -> None:
        self._sessions = sessions
        self._data_directory = data_directory

    def record(
        self,
        instrument_id: str,
        *,
        category: ValuationCategory,
        lot_size: Decimal,
        decision: str,
        reviewer_label: str,
        notes: str,
        evidence_reference: str,
        evidence_sha256: str,
        decided_at: datetime | None = None,
    ) -> CategoryDecision:
        """Append one explicit category decision for a verified instrument."""

        if category not in _ALLOWED_CATEGORIES:
            raise ValueError("category must be an investable target category")
        if not isinstance(lot_size, Decimal) or not lot_size.is_finite() or lot_size <= 0:
            raise ValueError("lot_size must be a positive finite Decimal")
        if decision not in {"VERIFIED", "REJECTED"}:
            raise ValueError("decision must be VERIFIED or REJECTED")
        for name, value in (
            ("reviewer_label", reviewer_label),
            ("notes", notes),
            ("evidence_reference", evidence_reference),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must not be empty")
        if not _SHA256_PATTERN.fullmatch(evidence_sha256):
            raise ValueError("evidence_sha256 must be a 64-character hex digest")
        moment = datetime.now(UTC) if decided_at is None else decided_at
        if moment.tzinfo is None or moment.utcoffset() is None:
            raise ValueError("decided_at must be timezone-aware")
        moment_utc = moment.astimezone(UTC)

        with self._sessions.begin() as session:
            instrument = session.get(InstrumentRegistryRecord, instrument_id)
            if instrument is None:
                raise ValueError("instrument does not exist in the local registry")
            if instrument.verification_status != "VERIFIED" or instrument.active is False:
                raise ValueError("only an active VERIFIED instrument can receive category evidence")
            raw = (
                f"{instrument_id}|{category.value}|{format(lot_size, 'f')}|{decision}|"
                f"{evidence_sha256}|{moment_utc.date().isoformat()}"
            )
            event_id = hashlib.sha256(raw.encode()).hexdigest()[:32]
            if session.get(InstrumentCategoryEventRecord, event_id) is not None:
                raise ValueError("an identical category decision is already recorded")
            session.add(
                InstrumentCategoryEventRecord(
                    event_id=event_id,
                    instrument_id=instrument_id,
                    category=category.value,
                    lot_size=format(lot_size, "f"),
                    decision=decision,
                    reviewer_label=reviewer_label.strip(),
                    notes=notes.strip(),
                    evidence_reference=evidence_reference.strip(),
                    evidence_sha256=evidence_sha256.lower(),
                    decided_at_utc=moment_utc.isoformat(),
                    methodology_version=FORMULA_VERSION,
                )
            )
        return CategoryDecision(
            event_id=event_id,
            instrument_id=instrument_id,
            category=category,
            lot_size=lot_size,
            decision=decision,
            reviewer_label=reviewer_label.strip(),
            notes=notes.strip(),
            evidence_reference=evidence_reference.strip(),
            evidence_sha256=evidence_sha256.lower(),
            decided_at_utc=moment_utc.isoformat(),
        )

    def record_from_file(
        self,
        instrument_id: str,
        *,
        category: ValuationCategory,
        lot_size: Decimal,
        decision: str,
        reviewer_label: str,
        notes: str,
        evidence_file: Path,
        decided_at: datetime | None = None,
    ) -> CategoryDecision:
        """Archive a user-selected evidence file, hash it, and record the decision."""

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
        archive = root / "Documents" / "CategoryEvidence"
        archive.mkdir(parents=True, exist_ok=True)
        if not archive.resolve().is_relative_to(root):
            raise ValueError("the category evidence archive resolves outside RFinance data storage")

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
            return self.record(
                instrument_id,
                category=category,
                lot_size=lot_size,
                decision=decision,
                reviewer_label=reviewer_label,
                notes=notes,
                evidence_reference=destination.relative_to(root).as_posix(),
                evidence_sha256=digest.hexdigest(),
                decided_at=decided_at,
            )
        except Exception:
            temporary.unlink(missing_ok=True)
            destination.unlink(missing_ok=True)
            raise

    def latest_decisions(self) -> tuple[CategoryDecision, ...]:
        """Return the newest decision per instrument with evidence intact."""

        with self._sessions() as session:
            events = session.scalars(
                select(InstrumentCategoryEventRecord).order_by(
                    InstrumentCategoryEventRecord.decided_at_utc.desc(),
                    InstrumentCategoryEventRecord.event_id.desc(),
                )
            ).all()
        latest: dict[str, InstrumentCategoryEventRecord] = {}
        for event in events:
            latest.setdefault(event.instrument_id, event)
        return tuple(
            CategoryDecision(
                event_id=event.event_id,
                instrument_id=event.instrument_id,
                category=ValuationCategory(event.category),
                lot_size=Decimal(event.lot_size),
                decision=event.decision,
                reviewer_label=event.reviewer_label,
                notes=event.notes,
                evidence_reference=event.evidence_reference,
                evidence_sha256=event.evidence_sha256,
                decided_at_utc=event.decided_at_utc,
            )
            for event in sorted(latest.values(), key=lambda item: item.instrument_id)
        )

    def verified_investables(self) -> tuple[InvestableInstrument, ...]:
        """Project verified, still-active decisions into allocation-plan inputs."""

        with self._sessions() as session:
            instruments = {
                row.instrument_id: row
                for row in session.scalars(select(InstrumentRegistryRecord)).all()
            }
        result: list[InvestableInstrument] = []
        for decision in self.latest_decisions():
            instrument = instruments.get(decision.instrument_id)
            if (
                decision.decision != "VERIFIED"
                or instrument is None
                or instrument.verification_status != "VERIFIED"
                or instrument.active is False
            ):
                continue
            result.append(
                InvestableInstrument(
                    instrument_id=decision.instrument_id,
                    category=decision.category,
                    lot_size=decision.lot_size,
                    evidence_reference=decision.evidence_reference,
                )
            )
        return tuple(sorted(result, key=lambda item: item.instrument_id))
