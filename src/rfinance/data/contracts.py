"""Validated, provider-independent data contracts."""

from __future__ import annotations

from datetime import datetime
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
