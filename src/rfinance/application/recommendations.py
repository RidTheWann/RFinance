# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Evaluate deterministic recommendations and persist their evidence record."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import select

from rfinance.domain.recommendations.screening import (
    Recommendation,
    RecommendationAction,
    RiskFlag,
    ScreeningInput,
    ScreeningPolicy,
    evaluate_candidate,
)
from rfinance.storage.models.recommendation import RecommendationRecord

if TYPE_CHECKING:
    from sqlalchemy.orm import Session, sessionmaker


@dataclass(frozen=True, slots=True)
class RecommendationSummary:
    recommendation_id: str
    instrument_id: str
    action: str
    generated_at_utc: str
    confidence_level: Decimal
    risk_flags: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    explanation: str
    methodology_version: str


class RecommendationService:
    """Evaluate a candidate and retain an immutable, inspectable result."""

    def __init__(
        self,
        sessions: sessionmaker[Session],
        *,
        policy: ScreeningPolicy | None = None,
    ) -> None:
        self._sessions = sessions
        self._policy = policy or ScreeningPolicy()

    def evaluate(
        self,
        candidate: ScreeningInput,
        *,
        generated_at: datetime | None = None,
    ) -> Recommendation:
        """Run the deterministic engine, then append the result to local storage."""

        moment = generated_at or candidate.as_of
        if moment.tzinfo is None or moment.utcoffset() is None:
            raise ValueError("generated_at must be timezone-aware")
        result = evaluate_candidate(candidate, policy=self._policy)
        stored = replace(result, generated_at=moment.astimezone(UTC))
        with self._sessions.begin() as session:
            session.add(self._to_record(stored))
        return stored

    @staticmethod
    def _to_record(result: Recommendation) -> RecommendationRecord:
        return RecommendationRecord(
            recommendation_id=str(uuid4()),
            instrument_id=result.instrument_id,
            action=result.action.value,
            generated_at_utc=result.generated_at.isoformat(),
            evidence_ids_json=json.dumps(list(result.evidence_ids), sort_keys=True),
            risk_flags_json=json.dumps([item.value for item in result.risk_flags], sort_keys=True),
            confidence_level=format(result.confidence_level, "f"),
            explanation=result.explanation,
            invalidation_conditions_json=json.dumps(
                list(result.invalidation_conditions), sort_keys=True
            ),
            data_freshness_utc=(
                None if result.data_freshness is None else result.data_freshness.isoformat()
            ),
            methodology_version=result.methodology_version,
            fundamental_assessment=result.fundamental_assessment,
            price_assessment=result.price_assessment,
            dividend_assessment=result.dividend_assessment,
        )

    def recent(self, *, limit: int = 50) -> tuple[RecommendationSummary, ...]:
        """Return persisted recommendations newest first for inspection."""

        if limit <= 0 or limit > 500:
            raise ValueError("limit must be between 1 and 500")
        with self._sessions() as session:
            records = session.scalars(
                select(RecommendationRecord)
                .order_by(
                    RecommendationRecord.generated_at_utc.desc(),
                    RecommendationRecord.recommendation_id.desc(),
                )
                .limit(limit)
            ).all()
        return tuple(
            RecommendationSummary(
                recommendation_id=record.recommendation_id,
                instrument_id=record.instrument_id,
                action=record.action,
                generated_at_utc=record.generated_at_utc,
                confidence_level=Decimal(record.confidence_level),
                risk_flags=tuple(json.loads(record.risk_flags_json)),
                evidence_ids=tuple(json.loads(record.evidence_ids_json)),
                explanation=record.explanation,
                methodology_version=record.methodology_version,
            )
            for record in records
        )

    def get(self, recommendation_id: str) -> Recommendation | None:
        """Reconstruct a stored recommendation for evidence inspection."""

        with self._sessions() as session:
            record = session.get(RecommendationRecord, recommendation_id)
            if record is None:
                return None
            return Recommendation(
                instrument_id=record.instrument_id,
                action=RecommendationAction(record.action),
                generated_at=datetime.fromisoformat(record.generated_at_utc),
                evidence_ids=tuple(json.loads(record.evidence_ids_json)),
                risk_flags=tuple(RiskFlag(item) for item in json.loads(record.risk_flags_json)),
                confidence_level=Decimal(record.confidence_level),
                explanation=record.explanation,
                invalidation_conditions=tuple(json.loads(record.invalidation_conditions_json)),
                data_freshness=(
                    None
                    if record.data_freshness_utc is None
                    else datetime.fromisoformat(record.data_freshness_utc)
                ),
                methodology_version=record.methodology_version,
                fundamental_assessment=record.fundamental_assessment,
                price_assessment=record.price_assessment,
                dividend_assessment=record.dividend_assessment,
            )
