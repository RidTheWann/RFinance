# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from rfinance.data.contracts import DataQualityStatus, MarketObservationContract


def make_observation(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "instrument_id": "IDX:BBCA",
        "observed_at": datetime(2026, 11, 20, 9, 0, tzinfo=UTC),
        "acquired_at": datetime(2026, 11, 20, 9, 1, tzinfo=UTC),
        "open": Decimal("9000"),
        "high": Decimal("9200"),
        "low": Decimal("8900"),
        "close": Decimal("9100"),
        "volume": Decimal("1000"),
        "currency": "IDR",
        "source_id": "manual-import",
        "quality_status": DataQualityStatus.UNVERIFIED,
    }
    values.update(overrides)
    return values


def test_valid_observation_preserves_unverified_quality() -> None:
    observation = MarketObservationContract.model_validate(make_observation())
    assert observation.quality_status is DataQualityStatus.UNVERIFIED
    assert observation.close == Decimal("9100")


def test_observation_rejects_naive_timestamp() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        MarketObservationContract.model_validate(
            make_observation(observed_at=datetime(2026, 11, 20, 9, 0))
        )


def test_observation_rejects_inconsistent_ohlc() -> None:
    with pytest.raises(ValidationError, match="cannot exceed high"):
        MarketObservationContract.model_validate(make_observation(close=Decimal("9500")))


def test_observation_rejects_invalid_currency_code() -> None:
    with pytest.raises(ValidationError):
        MarketObservationContract.model_validate(make_observation(currency="RP"))
