# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Validated, provider-independent data contracts."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DataQualityStatus(StrEnum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    ESTIMATED = "ESTIMATED"
    STALE = "STALE"
    INCOMPLETE = "INCOMPLETE"
    REJECTED = "REJECTED"
    SIMULATED = "SIMULATED"


class InstrumentType(StrEnum):
    EQUITY = "EQUITY"
    ETF = "ETF"
    MUTUAL_FUND = "MUTUAL_FUND"
    BOND = "BOND"
    MONEY_MARKET = "MONEY_MARKET"
    INDEX = "INDEX"
    OTHER = "OTHER"


class InstrumentContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    instrument_id: str = Field(min_length=1, max_length=128)
    ticker: str = Field(min_length=1, max_length=32)
    exchange: str = Field(min_length=1, max_length=32)
    instrument_type: InstrumentType
    company_name: str = Field(min_length=1, max_length=256)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    sector: str | None = Field(default=None, max_length=128)
    active: bool = True
    lot_size: int | None = Field(default=None, gt=0)
    minimum_investment: Decimal | None = Field(default=None, gt=Decimal("0"))


class MarketObservationContract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    instrument_id: str = Field(min_length=1, max_length=128)
    observed_at: datetime
    acquired_at: datetime
    open: Decimal | None = Field(default=None, ge=Decimal("0"))
    high: Decimal | None = Field(default=None, ge=Decimal("0"))
    low: Decimal | None = Field(default=None, ge=Decimal("0"))
    close: Decimal = Field(gt=Decimal("0"))
    volume: Decimal | None = Field(default=None, ge=Decimal("0"))
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    source_id: str = Field(min_length=1, max_length=128)
    quality_status: DataQualityStatus

    @model_validator(mode="after")
    def validate_observation(self) -> MarketObservationContract:
        if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        if self.acquired_at.tzinfo is None or self.acquired_at.utcoffset() is None:
            raise ValueError("acquired_at must be timezone-aware")
        if self.high is not None and self.low is not None and self.high < self.low:
            raise ValueError("high cannot be lower than low")
        prices = [
            value
            for value in (self.open, self.high, self.low, self.close)
            if value is not None
        ]
        if self.high is not None and any(value > self.high for value in prices):
            raise ValueError("OHLC values cannot exceed high")
        if self.low is not None and any(value < self.low for value in prices):
            raise ValueError("OHLC values cannot be below low")
        return self


class DividendType(StrEnum):
    """Cash and non-cash corporate distributions."""

    CASH = "CASH"
    INTERIM = "INTERIM"
    FINAL = "FINAL"
    SPECIAL = "SPECIAL"
    STOCK = "STOCK"
    RIGHTS = "RIGHTS"


class DividendEventStatus(StrEnum):
    """Lifecycle state of a dividend event, distinct from its data quality."""

    ANNOUNCED = "ANNOUNCED"
    CONFIRMED = "CONFIRMED"
    HISTORICAL = "HISTORICAL"
    ESTIMATED = "ESTIMATED"
    SIMULATED = "SIMULATED"
    CANCELLED = "CANCELLED"


CASH_DIVIDEND_TYPES = frozenset(
    {
        DividendType.CASH,
        DividendType.INTERIM,
        DividendType.FINAL,
        DividendType.SPECIAL,
    }
)
# Statuses that describe an actually observed distribution, never a forecast.
OBSERVED_DIVIDEND_STATUSES = frozenset(
    {DividendEventStatus.CONFIRMED, DividendEventStatus.HISTORICAL}
)


class DividendEventContract(BaseModel):
    """A user-supplied dividend observation with explicit provenance.

    The contract is deliberately source-agnostic and rejects unknown fields.
    It records what the document said, when it was obtained, and the quality
    state at ingestion. It never certifies the observation as verified cash.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_key: str = Field(min_length=1, max_length=128)
    instrument_id: str = Field(min_length=1, max_length=128)
    source_label: str = Field(min_length=1, max_length=256)
    dividend_type: DividendType
    event_status: DividendEventStatus
    amount_per_share: Decimal | None = Field(default=None, gt=Decimal("0"))
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    ex_date: date
    cum_date: date | None = None
    record_date: date | None = None
    payment_date: date | None = None
    quality_status: DataQualityStatus = DataQualityStatus.UNVERIFIED
    acquired_at: datetime
    announced_at: datetime | None = None
    reporting_period_start: date | None = None
    reporting_period_end: date | None = None
    source_document_ref: str | None = Field(default=None, max_length=1024)
    original_value: str | None = Field(default=None, max_length=256)
    unit: str = Field(default="PER_SHARE", min_length=1, max_length=64)
    notes: str | None = Field(default=None, max_length=2048)
    transformation_version: str = Field(
        default="dividend-event-v1", min_length=1, max_length=64
    )

    @model_validator(mode="after")
    def validate_dividend_event(self) -> DividendEventContract:
        if self.acquired_at.tzinfo is None or self.acquired_at.utcoffset() is None:
            raise ValueError("acquired_at must be timezone-aware")
        if self.announced_at is not None and (
            self.announced_at.tzinfo is None or self.announced_at.utcoffset() is None
        ):
            raise ValueError("announced_at must be timezone-aware")
        if self.dividend_type in CASH_DIVIDEND_TYPES and self.amount_per_share is None:
            raise ValueError("cash dividend types require amount_per_share")
        if self.dividend_type not in CASH_DIVIDEND_TYPES and self.amount_per_share is not None:
            raise ValueError("non-cash distributions cannot carry a cash amount_per_share")
        if (
            self.reporting_period_start is not None
            and self.reporting_period_end is not None
            and self.reporting_period_start > self.reporting_period_end
        ):
            raise ValueError("reporting_period_start cannot follow reporting_period_end")
        return self
