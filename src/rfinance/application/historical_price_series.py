"""Load provenance-qualified historical bars for deterministic technical analysis."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from sqlalchemy import select

from rfinance.domain.eligibility.historical import (
    FORMULA_VERSION as HISTORICAL_ELIGIBILITY_VERSION,
)
from rfinance.domain.eligibility.historical import historical_observation_reasons
from rfinance.domain.eligibility.observation import (
    InstrumentState,
    InstrumentStatus,
    ObservationCandidate,
    ObservationQuality,
    SourcePolicyStatus,
    SourceState,
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


MAX_HISTORY_OBSERVATIONS = 100_000
SERIES_METHOD_VERSION = "historical-price-series-v1"
ADJUSTMENT_STATUS = "UNKNOWN_AS_SUPPLIED"


@dataclass(frozen=True, slots=True)
class HistoricalSeriesChoice:
    """One selectable instrument/source pair present in local storage."""

    instrument_id: str
    ticker: str
    company_name: str
    currency: str
    source_id: str
    source_name: str


@dataclass(frozen=True, slots=True)
class HistoricalPricePoint:
    """One eligible bar with immutable observation and acquisition provenance."""

    observation_id: str
    observed_at: datetime
    acquired_at: datetime
    close: Decimal
    high: Decimal | None
    low: Decimal | None
    volume: Decimal | None
    currency: str


@dataclass(frozen=True, slots=True)
class HistoricalGap:
    """An interval large enough to break rolling indicator windows."""

    previous_observed_at: datetime
    next_observed_at: datetime
    elapsed_days: int


@dataclass(frozen=True, slots=True)
class HistoricalPriceSeriesSnapshot:
    """Single-instrument, single-source, eligible time series and its diagnostics."""

    instrument_id: str
    ticker: str
    company_name: str
    source_id: str
    source_name: str
    currency: str
    points: tuple[HistoricalPricePoint, ...]
    closes: tuple[Decimal | None, ...]
    highs: tuple[Decimal | None, ...]
    lows: tuple[Decimal | None, ...]
    gaps: tuple[HistoricalGap, ...]
    rejected_count: int
    rejected_reasons: tuple[tuple[str, int], ...]
    max_gap_days: int
    adjustment_status: str
    methodology_version: str = SERIES_METHOD_VERSION
    eligibility_methodology: str = HISTORICAL_ELIGIBILITY_VERSION


@dataclass(frozen=True, slots=True)
class _JoinedObservation:
    observation: MarketObservationRecord
    instrument: InstrumentRegistryRecord | None
    source: SourceRegistryRecord | None


@dataclass(frozen=True, slots=True)
class _ParsedObservation:
    candidate: ObservationCandidate
    point: HistoricalPricePoint


class HistoricalPriceSeriesService:
    """Select verified historical bars without applying current-market staleness.

    Historical data is never merged across sources, resampled, interpolated,
    or automatically corporate-action adjusted. Every selected point retains
    its source and observation ID for evidence inspection.
    """

    def __init__(
        self,
        sessions: sessionmaker[Session],
        *,
        allow_unreviewed_sources: bool = True,
        max_observations: int = MAX_HISTORY_OBSERVATIONS,
    ) -> None:
        if max_observations <= 0 or max_observations > MAX_HISTORY_OBSERVATIONS:
            raise ValueError(f"max_observations must be between 1 and {MAX_HISTORY_OBSERVATIONS}")
        self._sessions = sessions
        self._allow_unreviewed_sources = allow_unreviewed_sources
        self._max_observations = max_observations

    def available_series(self) -> tuple[HistoricalSeriesChoice, ...]:
        """Return active verified instrument/source pairs with local observations."""

        with self._sessions() as session:
            rows = session.execute(
                select(
                    InstrumentRegistryRecord.instrument_id,
                    InstrumentRegistryRecord.ticker,
                    InstrumentRegistryRecord.company_name,
                    InstrumentRegistryRecord.currency,
                    MarketObservationRecord.source_id,
                    SourceRegistryRecord.display_name,
                )
                .join(
                    MarketObservationRecord,
                    MarketObservationRecord.instrument_id == InstrumentRegistryRecord.instrument_id,
                )
                .join(
                    SourceRegistryRecord,
                    SourceRegistryRecord.source_id == MarketObservationRecord.source_id,
                )
                .where(
                    InstrumentRegistryRecord.verification_status == "VERIFIED",
                    InstrumentRegistryRecord.active.is_(True),
                    InstrumentRegistryRecord.currency.is_not(None),
                    SourceRegistryRecord.policy_status.notin_(("BLOCKED", "RESTRICTED")),
                )
                .distinct()
                .order_by(
                    InstrumentRegistryRecord.ticker,
                    MarketObservationRecord.source_id,
                )
            ).all()

        return tuple(
            HistoricalSeriesChoice(
                instrument_id=instrument_id,
                ticker=ticker or instrument_id,
                company_name=company_name or instrument_id,
                currency=currency,
                source_id=source_id,
                source_name=source_name,
            )
            for instrument_id, ticker, company_name, currency, source_id, source_name in rows
            if currency is not None
        )

    def load(
        self,
        instrument_id: str,
        source_id: str,
        *,
        as_of: datetime | None = None,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        max_gap_days: int = 7,
    ) -> HistoricalPriceSeriesSnapshot:
        """Load a single-source price series through a historical-specific gate."""

        if not instrument_id.strip() or not source_id.strip():
            raise ValueError("instrument_id and source_id are required")
        if isinstance(max_gap_days, bool) or not isinstance(max_gap_days, int):
            raise ValueError("max_gap_days must be an integer")
        if max_gap_days < 1 or max_gap_days > 365:
            raise ValueError("max_gap_days must be between 1 and 365")

        reference = datetime.now(UTC) if as_of is None else as_of
        self._validate_aware(reference, "as_of")
        if start_at is not None:
            self._validate_aware(start_at, "start_at")
        if end_at is not None:
            self._validate_aware(end_at, "end_at")
        if (
            start_at is not None
            and end_at is not None
            and start_at.astimezone(UTC) > end_at.astimezone(UTC)
        ):
            raise ValueError("start_at must not be later than end_at")
        if end_at is not None and end_at.astimezone(UTC) > reference.astimezone(UTC):
            raise ValueError("end_at must not be later than as_of")
        if start_at is not None and start_at.astimezone(UTC) > reference.astimezone(UTC):
            raise ValueError("start_at must not be later than as_of")

        rows, latest_decisions = self._load_rows(instrument_id, source_id)
        instrument_record = next(
            (row.instrument for row in rows if row.instrument is not None),
            None,
        )
        source_record = next((row.source for row in rows if row.source is not None), None)
        if instrument_record is None:
            raise ValueError(f"Instrument identity is unavailable: {instrument_id}")
        if instrument_record.currency is None:
            raise ValueError(f"Instrument currency is unavailable: {instrument_id}")
        if source_record is None:
            raise ValueError(f"Source registry record is unavailable: {source_id}")

        instrument_state = self._instrument_state(instrument_record)
        source_state = self._source_state(source_record)
        instruments: Mapping[str, InstrumentState] = (
            {} if instrument_state is None else {instrument_id: instrument_state}
        )
        sources: Mapping[str, SourceState] = (
            {} if source_state is None else {source_id: source_state}
        )
        expected_currency = instrument_record.currency
        parsed: list[_ParsedObservation] = []
        rejected: Counter[str] = Counter()

        for row in rows:
            record = row.observation
            try:
                observed_at = datetime.fromisoformat(record.observed_at_utc)
            except ValueError:
                rejected["INVALID_TIMESTAMP"] += 1
                continue
            if observed_at.tzinfo is None or observed_at.utcoffset() is None:
                rejected["INVALID_TIMESTAMP"] += 1
                continue

            observed_utc = observed_at.astimezone(UTC)
            if start_at is not None and observed_utc < start_at.astimezone(UTC):
                continue
            if end_at is not None and observed_utc > end_at.astimezone(UTC):
                continue

            try:
                item = self._parse_observation(
                    record,
                    latest_decisions.get(record.observation_id, record.quality_status),
                )
            except (InvalidOperation, TypeError, ValueError) as error:
                rejected[f"MALFORMED_OBSERVATION:{error}"] += 1
                continue

            reasons = historical_observation_reasons(
                item.candidate,
                instruments=instruments,
                sources=sources,
                as_of=reference,
                expected_currency=expected_currency,
                allow_unreviewed_sources=self._allow_unreviewed_sources,
            )
            if reasons:
                rejected.update(reason.value for reason in reasons)
                continue
            parsed.append(item)

        parsed.sort(key=lambda item: item.point.observed_at.astimezone(UTC))
        if len(parsed) > self._max_observations:
            raise ValueError(
                f"Eligible historical series has {len(parsed):,} points; the current limit is "
                f"{self._max_observations:,}. Narrow the requested date range."
            )
        deduplicated: list[_ParsedObservation] = []
        for item in parsed:
            current_time = item.point.observed_at.astimezone(UTC)
            if deduplicated and deduplicated[-1].point.observed_at.astimezone(UTC) == current_time:
                deduplicated.pop()
                rejected["DUPLICATE_UTC_TIMESTAMP"] += 2
                # The stored unique key normally prevents this. If alternate
                # ISO representations bypass it, refuse both records.
                continue
            deduplicated.append(item)

        points = tuple(item.point for item in deduplicated)
        closes: list[Decimal | None] = []
        highs: list[Decimal | None] = []
        lows: list[Decimal | None] = []
        gaps: list[HistoricalGap] = []

        for index, point in enumerate(points):
            if index:
                previous = points[index - 1]
                elapsed = point.observed_at.astimezone(UTC) - previous.observed_at.astimezone(UTC)
                if elapsed > timedelta(days=max_gap_days):
                    gaps.append(
                        HistoricalGap(
                            previous_observed_at=previous.observed_at,
                            next_observed_at=point.observed_at,
                            elapsed_days=int(elapsed.total_seconds() // 86_400),
                        )
                    )
                    closes.append(None)
                    highs.append(None)
                    lows.append(None)
            closes.append(point.close)
            highs.append(point.high)
            lows.append(point.low)

        return HistoricalPriceSeriesSnapshot(
            instrument_id=instrument_id,
            ticker=instrument_record.ticker or instrument_id,
            company_name=instrument_record.company_name or instrument_id,
            source_id=source_id,
            source_name=source_record.display_name,
            currency=expected_currency,
            points=points,
            closes=tuple(closes),
            highs=tuple(highs),
            lows=tuple(lows),
            gaps=tuple(gaps),
            rejected_count=sum(rejected.values()),
            rejected_reasons=tuple(sorted(rejected.items())),
            max_gap_days=max_gap_days,
            adjustment_status=ADJUSTMENT_STATUS,
        )

    def _load_rows(
        self,
        instrument_id: str,
        source_id: str,
    ) -> tuple[tuple[_JoinedObservation, ...], dict[str, str]]:
        with self._sessions() as session:
            records = session.execute(
                select(
                    MarketObservationRecord,
                    InstrumentRegistryRecord,
                    SourceRegistryRecord,
                )
                .outerjoin(
                    InstrumentRegistryRecord,
                    InstrumentRegistryRecord.instrument_id == MarketObservationRecord.instrument_id,
                )
                .outerjoin(
                    SourceRegistryRecord,
                    SourceRegistryRecord.source_id == MarketObservationRecord.source_id,
                )
                .where(
                    MarketObservationRecord.instrument_id == instrument_id,
                    MarketObservationRecord.source_id == source_id,
                )
            ).all()
            rows = tuple(
                _JoinedObservation(observation=observation, instrument=instrument, source=source)
                for observation, instrument, source in records
            )
            observation_ids = [row.observation.observation_id for row in rows]
            latest: dict[str, tuple[datetime, str, str]] = {}
            if observation_ids:
                events = session.scalars(
                    select(ObservationReviewEventRecord).where(
                        ObservationReviewEventRecord.observation_id.in_(observation_ids)
                    )
                ).all()
                for event in events:
                    try:
                        reviewed_at = datetime.fromisoformat(event.reviewed_at_utc)
                    except ValueError:
                        continue
                    if reviewed_at.tzinfo is None or reviewed_at.utcoffset() is None:
                        continue
                    candidate = (
                        reviewed_at.astimezone(UTC),
                        event.review_id,
                        event.decision,
                    )
                    current = latest.get(event.observation_id)
                    if current is None or candidate[:2] > current[:2]:
                        latest[event.observation_id] = candidate

        return rows, {observation_id: item[2] for observation_id, item in latest.items()}

    @staticmethod
    def _parse_observation(
        record: MarketObservationRecord,
        effective_quality: str,
    ) -> _ParsedObservation:
        observed_at = datetime.fromisoformat(record.observed_at_utc)
        acquired_at = datetime.fromisoformat(record.acquired_at_utc)
        close = Decimal(record.close)
        high = None if record.high is None else Decimal(record.high)
        low = None if record.low is None else Decimal(record.low)
        volume = None if record.volume is None else Decimal(record.volume)

        for field_name, value in (
            ("close", close),
            ("high", high),
            ("low", low),
            ("volume", volume),
        ):
            if value is not None and (not value.is_finite() or value < 0):
                raise ValueError(f"{field_name} is not finite and non-negative")
        if close <= 0:
            raise ValueError("close must be positive")
        if high is not None and close > high:
            raise ValueError("close exceeds high")
        if low is not None and close < low:
            raise ValueError("close is below low")
        if high is not None and low is not None and high < low:
            raise ValueError("high is below low")
        if high is not None and high <= 0:
            raise ValueError("high must be positive")
        if low is not None and low <= 0:
            raise ValueError("low must be positive")

        candidate = ObservationCandidate(
            instrument_id=record.instrument_id,
            observed_at=observed_at,
            acquired_at=acquired_at,
            close=close,
            currency=record.currency,
            source_id=record.source_id,
            quality=ObservationQuality(effective_quality),
        )
        point = HistoricalPricePoint(
            observation_id=record.observation_id,
            observed_at=observed_at,
            acquired_at=acquired_at,
            close=close,
            high=high,
            low=low,
            volume=volume,
            currency=record.currency,
        )
        return _ParsedObservation(candidate=candidate, point=point)

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
    def _validate_aware(value: datetime, field_name: str) -> None:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{field_name} must be timezone-aware")
