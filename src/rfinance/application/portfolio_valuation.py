"""Application service connecting persisted, audited prices to portfolio valuation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from sqlalchemy import select

from rfinance.analysis.portfolio.valuation import (
    PriceQuote,
    ValuationCategory,
    ValuationResult,
    value_portfolio,
)
from rfinance.domain.eligibility.observation import (
    FORMULA_VERSION as ELIGIBILITY_FORMULA_VERSION,
)
from rfinance.domain.eligibility.observation import (
    EligibilityPolicy,
    InstrumentState,
    InstrumentStatus,
    ObservationCandidate,
    ObservationQuality,
    SourcePolicyStatus,
    SourceState,
    select_eligible_observations,
)
from rfinance.storage.models.data_ingestion import (
    MarketObservationRecord,
    SourceRegistryRecord,
)
from rfinance.storage.models.instrument_registry import InstrumentRegistryRecord
from rfinance.storage.models.observation_review import ObservationReviewEventRecord

if TYPE_CHECKING:
    from collections.abc import Mapping

    from sqlalchemy.orm import Session, sessionmaker

    from rfinance.application.portfolio_ledger import PortfolioLedgerService


@dataclass(frozen=True, slots=True)
class PriceEvidence:
    """Provenance for the latest eligible observation used for one position."""

    observation_id: str
    instrument_id: str
    source_id: str
    source_name: str
    observed_at_utc: str
    acquired_at_utc: str
    close: Decimal
    currency: str
    age_days: int
    effective_quality: str = ObservationQuality.VERIFIED.value


@dataclass(frozen=True, slots=True)
class UnvaluedPosition:
    """Reason a ledger position does not have an eligible current price."""

    instrument_id: str
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PortfolioValuationSnapshot:
    """Valuation result plus source evidence and per-position eligibility diagnostics."""

    valuation: ValuationResult
    price_evidence: tuple[PriceEvidence, ...]
    unvalued_positions: tuple[UnvaluedPosition, ...]
    observations_considered: int
    observations_rejected: int
    eligibility_methodology: str = ELIGIBILITY_FORMULA_VERSION


@dataclass(frozen=True, slots=True)
class _JoinedObservation:
    observation: MarketObservationRecord
    instrument: InstrumentRegistryRecord | None
    source: SourceRegistryRecord | None


@dataclass(frozen=True, slots=True)
class _StoredObservation:
    observation_id: str
    source_name: str
    instrument_type: str | None


@dataclass(frozen=True, slots=True)
class _MalformedObservation:
    instrument_id: str
    reason: str


class PortfolioValuationService:
    """Build valuation inputs from persisted records after all eligibility gates pass.

    Only observations with effective VERIFIED status, a VERIFIED active
    instrument identity, matching currency, acceptable source policy, valid
    timestamps and a fresh positive close can enter valuation. Raw observation
    rows are never mutated by this service.
    """

    def __init__(
        self,
        sessions: sessionmaker[Session],
        ledger: PortfolioLedgerService,
        *,
        base_currency: str = "IDR",
        eligibility_policy: EligibilityPolicy | None = None,
    ) -> None:
        if len(base_currency) != 3 or not base_currency.isascii() or not base_currency.isupper():
            raise ValueError("base_currency must be a three-letter uppercase currency code")
        self._sessions = sessions
        self._ledger = ledger
        self._base_currency = base_currency
        self._policy = EligibilityPolicy() if eligibility_policy is None else eligibility_policy

    def value(self, *, as_of: datetime | None = None) -> PortfolioValuationSnapshot:
        """Value the current ledger snapshot with its newest eligible persisted prices."""

        reference = datetime.now(UTC) if as_of is None else as_of
        if reference.tzinfo is None or reference.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        reference_utc = reference.astimezone(UTC)
        ledger_snapshot = self._ledger.snapshot()
        if ledger_snapshot.currency != self._base_currency:
            raise ValueError("portfolio ledger currency does not match valuation base currency")

        instrument_ids = tuple(ledger_snapshot.positions)
        rows, latest_decisions = self._load_observations(instrument_ids)
        candidates: list[ObservationCandidate] = []
        stored_by_candidate: dict[ObservationCandidate, _StoredObservation] = {}
        instruments: dict[str, InstrumentState] = {}
        sources: dict[str, SourceState] = {}
        malformed: list[_MalformedObservation] = []

        for row in rows:
            observation = row.observation
            if row.instrument is not None:
                state = self._instrument_state(row.instrument)
                if state is not None:
                    instruments[observation.instrument_id] = state
            if row.source is not None:
                state = self._source_state(row.source)
                if state is not None:
                    sources[observation.source_id] = state

            effective_quality = latest_decisions.get(
                observation.observation_id,
                observation.quality_status,
            )
            try:
                candidate = self._candidate(observation, effective_quality)
            except (InvalidOperation, TypeError, ValueError) as error:
                malformed.append(
                    _MalformedObservation(
                        instrument_id=observation.instrument_id,
                        reason=f"INVALID_PERSISTED_OBSERVATION: {error}",
                    )
                )
                continue

            stored_by_candidate[candidate] = _StoredObservation(
                observation_id=observation.observation_id,
                source_name="Unknown source" if row.source is None else row.source.display_name,
                instrument_type=(
                    None if row.instrument is None else row.instrument.instrument_type
                ),
            )
            candidates.append(candidate)

        report = select_eligible_observations(
            candidates,
            instruments=instruments,
            sources=sources,
            as_of=reference_utc,
            expected_currency=self._base_currency,
            policy=self._policy,
        )

        eligible_by_instrument: dict[str, list[ObservationCandidate]] = {}
        for candidate in report.eligible:
            eligible_by_instrument.setdefault(candidate.instrument_id, []).append(candidate)

        quotes: list[PriceQuote] = []
        evidence: list[PriceEvidence] = []
        categories: dict[str, ValuationCategory] = {}
        conflicts: dict[str, tuple[str, ...]] = {}
        conflicting_observation_count = 0

        for instrument_id, observations in eligible_by_instrument.items():
            latest_observed_at = max(item.observed_at.astimezone(UTC) for item in observations)
            latest_observations = [
                item
                for item in observations
                if item.observed_at.astimezone(UTC) == latest_observed_at
            ]
            latest_closes = {item.close for item in latest_observations}
            if len(latest_closes) > 1:
                # Multiple sources disagree about the latest price. Do not pick
                # one arbitrarily or fall back to an older observation.
                conflicts[instrument_id] = ("CONFLICTING_LATEST_OBSERVATIONS",)
                conflicting_observation_count += len(latest_observations)
                continue

            selected = max(
                latest_observations,
                key=lambda item: (item.acquired_at.astimezone(UTC), item.source_id),
            )
            stored = stored_by_candidate[selected]
            quote = PriceQuote(
                instrument_id=instrument_id,
                close=selected.close,
                currency=selected.currency,
                observed_at=selected.observed_at,
                quality=selected.quality,
            )
            quotes.append(quote)
            categories[instrument_id] = self._category(stored.instrument_type)
            evidence.append(
                PriceEvidence(
                    observation_id=stored.observation_id,
                    instrument_id=instrument_id,
                    source_id=selected.source_id,
                    source_name=stored.source_name,
                    observed_at_utc=selected.observed_at.astimezone(UTC).isoformat(),
                    acquired_at_utc=selected.acquired_at.astimezone(UTC).isoformat(),
                    close=selected.close,
                    currency=selected.currency,
                    age_days=max(
                        0,
                        int(
                            (reference_utc - selected.observed_at.astimezone(UTC))
                            .total_seconds()
                            // 86_400
                        ),
                    ),
                )
            )

        valuation = value_portfolio(
            ledger_snapshot,
            quotes=quotes,
            categories=categories,
            as_of=reference_utc,
            currency=self._base_currency,
            max_age_days=self._policy.max_observation_age_days,
        )

        latest_rejections: dict[str, tuple[datetime, set[str]]] = {}
        for candidate, decision in report.rejected:
            instrument_id = candidate.instrument_id
            observed_at = candidate.observed_at.astimezone(UTC)
            reasons = {reason.value for reason in decision.reasons}
            current = latest_rejections.get(instrument_id)
            if current is None or observed_at > current[0]:
                latest_rejections[instrument_id] = (observed_at, reasons)
            elif observed_at == current[0]:
                current[1].update(reasons)

        malformed_by_instrument: dict[str, str] = {}
        for item in malformed:
            malformed_by_instrument.setdefault(item.instrument_id, item.reason)

        unvalued: list[UnvaluedPosition] = []
        for instrument_id in valuation.unvalued_instruments:
            if instrument_id in conflicts:
                reasons = conflicts[instrument_id]
            elif instrument_id in latest_rejections:
                reasons = tuple(sorted(latest_rejections[instrument_id][1]))
            elif instrument_id in malformed_by_instrument:
                reasons = (malformed_by_instrument[instrument_id],)
            else:
                reasons = ("NO_OBSERVATIONS",)
            unvalued.append(UnvaluedPosition(instrument_id, reasons))

        return PortfolioValuationSnapshot(
            valuation=valuation,
            price_evidence=tuple(evidence),
            unvalued_positions=tuple(unvalued),
            observations_considered=len(rows),
            observations_rejected=(
                len(report.rejected) + len(malformed) + conflicting_observation_count
            ),
        )

    def _load_observations(
        self,
        instrument_ids: tuple[str, ...],
    ) -> tuple[tuple[_JoinedObservation, ...], Mapping[str, str]]:
        if not instrument_ids:
            return (), {}

        with self._sessions() as session:
            records = session.execute(
                select(
                    MarketObservationRecord,
                    InstrumentRegistryRecord,
                    SourceRegistryRecord,
                )
                .outerjoin(
                    InstrumentRegistryRecord,
                    InstrumentRegistryRecord.instrument_id
                    == MarketObservationRecord.instrument_id,
                )
                .outerjoin(
                    SourceRegistryRecord,
                    SourceRegistryRecord.source_id == MarketObservationRecord.source_id,
                )
                .where(MarketObservationRecord.instrument_id.in_(instrument_ids))
            ).all()
            joined = tuple(
                _JoinedObservation(
                    observation=observation,
                    instrument=instrument,
                    source=source,
                )
                for observation, instrument, source in records
            )

            observation_ids = [item.observation.observation_id for item in joined]
            decisions: dict[str, tuple[datetime, str, str]] = {}
            if observation_ids:
                review_events = session.scalars(
                    select(ObservationReviewEventRecord).where(
                        ObservationReviewEventRecord.observation_id.in_(observation_ids)
                    )
                ).all()
                for event in review_events:
                    reviewed_at = datetime.fromisoformat(event.reviewed_at_utc)
                    if reviewed_at.tzinfo is None or reviewed_at.utcoffset() is None:
                        continue
                    candidate = (
                        reviewed_at.astimezone(UTC),
                        event.review_id,
                        event.decision,
                    )
                    current = decisions.get(event.observation_id)
                    if current is None or candidate[:2] > current[:2]:
                        decisions[event.observation_id] = candidate

        return joined, {observation_id: value[2] for observation_id, value in decisions.items()}

    @staticmethod
    def _instrument_state(record: InstrumentRegistryRecord) -> InstrumentState | None:
        if record.currency is None:
            return None
        try:
            return InstrumentState(
                instrument_id=record.instrument_id,
                verification_status=InstrumentStatus(record.verification_status),
                active=record.active is True,
                currency=record.currency,
            )
        except ValueError:
            return None

    @staticmethod
    def _source_state(record: SourceRegistryRecord) -> SourceState | None:
        try:
            return SourceState(
                source_id=record.source_id,
                policy_status=SourcePolicyStatus(record.policy_status),
            )
        except ValueError:
            return None

    @staticmethod
    def _candidate(
        record: MarketObservationRecord,
        effective_quality: str,
    ) -> ObservationCandidate:
        return ObservationCandidate(
            instrument_id=record.instrument_id,
            observed_at=datetime.fromisoformat(record.observed_at_utc),
            acquired_at=datetime.fromisoformat(record.acquired_at_utc),
            close=Decimal(record.close),
            currency=record.currency,
            source_id=record.source_id,
            quality=ObservationQuality(effective_quality),
        )

    @staticmethod
    def _category(instrument_type: str | None) -> ValuationCategory:
        # A generic EQUITY or ETF label does not prove index replication or
        # dividend policy. Only the explicit MONEY_MARKET type is mapped here.
        if instrument_type == "MONEY_MARKET":
            return ValuationCategory.MONEY_MARKET
        return ValuationCategory.OTHER
