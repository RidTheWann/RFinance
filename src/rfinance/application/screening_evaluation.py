# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Assemble deterministic screening evidence from persisted local records."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from rfinance.analysis.fundamental.metrics import (
    ComputedMetric,
    compute_fundamental_metrics,
)
from rfinance.domain.recommendations.screening import (
    EvidenceItem,
    EvidenceKind,
    Recommendation,
    ScreeningInput,
)
from rfinance.storage.models.data_ingestion import SourceRegistryRecord
from rfinance.storage.models.instrument_registry import InstrumentRegistryRecord

if TYPE_CHECKING:
    from collections.abc import Mapping
    from decimal import Decimal

    from sqlalchemy.orm import Session, sessionmaker

    from rfinance.application.dividend_events import DividendEventService
    from rfinance.application.financial_statements import FinancialStatementService
    from rfinance.application.observation_review import ObservationReviewService
    from rfinance.application.recommendations import RecommendationService
    from rfinance.application.risk_monitoring import RiskMonitoringService


class ScreeningEvaluationService:
    """Build screening inputs from real local evidence and delegate the decision."""

    def __init__(
        self,
        sessions: sessionmaker[Session],
        *,
        dividend_events: DividendEventService,
        observation_review: ObservationReviewService,
        recommendations: RecommendationService,
        financial_statements: FinancialStatementService | None = None,
        risk_monitoring: RiskMonitoringService | None = None,
        base_currency: str = "IDR",
    ) -> None:
        self._sessions = sessions
        self._dividend_events = dividend_events
        self._observation_review = observation_review
        self._recommendations = recommendations
        self._financial_statements = financial_statements
        self._risk_monitoring = risk_monitoring
        self._base_currency = base_currency

    def evaluate(
        self,
        instrument_id: str,
        *,
        fundamentals: Mapping[str, Decimal | None],
        as_of: datetime | None = None,
        portfolio_drawdown: Decimal | None = None,
        use_persisted_fundamentals: bool = False,
    ) -> Recommendation:
        """Evaluate one instrument; all numeric inputs remain explicit."""

        moment = as_of or datetime.now(UTC)
        if moment.tzinfo is None or moment.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        moment = moment.astimezone(UTC)

        with self._sessions() as session:
            instrument = session.get(InstrumentRegistryRecord, instrument_id)
            if instrument is None:
                raise ValueError("instrument does not exist in the local registry")
            source: SourceRegistryRecord | None = None
            observation = next(
                (
                    item
                    for item in self._observation_review.list_candidates(limit=2_000)
                    if item.instrument_id == instrument_id
                ),
                None,
            )
            if observation is not None:
                source = session.get(SourceRegistryRecord, observation.source_id)

        identity_ok = (
            instrument.verification_status == "VERIFIED" and instrument.active is not False
        )
        price_quality: str | None = None
        price_age: int | None = None
        price_evidence_id: str | None = None
        observed_at: datetime | None = None
        if observation is not None:
            observed_at = datetime.fromisoformat(observation.observed_at_utc)
            price_age = max(0, (moment.date() - observed_at.date()).days)
            price_evidence_id = observation.observation_id
            blocked_source = source is not None and source.policy_status in {
                "BLOCKED",
                "RESTRICTED",
            }
            if identity_ok and not blocked_source:
                price_quality = observation.effective_quality
            else:
                price_quality = "UNVERIFIED"

        if use_persisted_fundamentals:
            if self._financial_statements is None:
                raise ValueError("no financial statement service is configured")
            persisted = self._financial_statements.verified_inputs(instrument_id, as_of=moment)
            fundamentals = {**fundamentals, **persisted}

        metrics: tuple[ComputedMetric, ...] = compute_fundamental_metrics(fundamentals)
        dividend_ids = tuple(
            event.event_id
            for event in self._dividend_events.list_events(limit=2_000)
            if event.instrument_id == instrument_id
            and event.effective_quality == "VERIFIED"
            and event.event_status in {"CONFIRMED", "HISTORICAL"}
            and event.dividend_type in {"CASH", "INTERIM", "FINAL", "SPECIAL"}
        )

        evidence: list[EvidenceItem] = []
        for metric in metrics:
            evidence.append(
                EvidenceItem(
                    evidence_id=f"metric:{metric.name}",
                    kind=EvidenceKind.FUNDAMENTAL_METRIC,
                    reference=(
                        "verified-filing"
                        if use_persisted_fundamentals and metric.name in fundamentals
                        else "operator-supplied-input"
                    ),
                    quality="VERIFIED" if use_persisted_fundamentals else "UNVERIFIED",
                    summary=(
                        f"{metric.formula} from "
                        + (
                            "verified local filing values"
                            if use_persisted_fundamentals
                            else "explicitly supplied operator inputs"
                        )
                    ),
                )
            )
        if observation is not None:
            evidence.append(
                EvidenceItem(
                    evidence_id=f"price:{observation.observation_id}",
                    kind=EvidenceKind.PRICE_OBSERVATION,
                    reference=observation.source_id,
                    quality=price_quality or "UNVERIFIED",
                    observed_at=observed_at,
                    summary=f"Review-adjusted close {observation.close} {observation.currency}",
                )
            )
        for event_id in dividend_ids:
            evidence.append(
                EvidenceItem(
                    evidence_id=f"dividend:{event_id}",
                    kind=EvidenceKind.DIVIDEND_EVENT,
                    reference=event_id,
                    quality="VERIFIED",
                    summary="Verified observed cash dividend event",
                )
            )

        risk_controls = (
            self._risk_monitoring.screening_controls()
            if self._risk_monitoring is not None
            else None
        )
        candidate = ScreeningInput(
            instrument_id=instrument_id,
            as_of=moment,
            currency=self._base_currency,
            metrics=metrics,
            price_observation_age_days=price_age,
            price_quality=price_quality,
            price_evidence_id=price_evidence_id,
            dividend_evidence_ids=dividend_ids,
            portfolio_drawdown=portfolio_drawdown,
            risk_controls=risk_controls,
            evidence=tuple(evidence),
        )
        return self._recommendations.evaluate(candidate, generated_at=moment)
