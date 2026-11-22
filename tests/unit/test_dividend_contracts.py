# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from rfinance.data.contracts import (
    CASH_DIVIDEND_TYPES,
    OBSERVED_DIVIDEND_STATUSES,
    DividendEventContract,
    DividendEventStatus,
    DividendType,
)

BASE = {
    "event_key": "event-1",
    "instrument_id": "IDX:BBCA",
    "source_label": "Issuer report",
    "dividend_type": DividendType.CASH,
    "event_status": DividendEventStatus.CONFIRMED,
    "amount_per_share": Decimal("100"),
    "currency": "IDR",
    "ex_date": date(2026, 5, 20),
    "acquired_at": datetime(2026, 11, 21, 10, tzinfo=UTC),
}


def test_contract_defaults_to_unverified_quality() -> None:
    contract = DividendEventContract(**BASE)
    assert contract.quality_status.value == "UNVERIFIED"
    assert contract.unit == "PER_SHARE"
    assert contract.transformation_version == "dividend-event-v1"


@pytest.mark.parametrize("dividend_type", sorted(CASH_DIVIDEND_TYPES))
def test_cash_types_require_an_amount(dividend_type: DividendType) -> None:
    with pytest.raises(ValidationError, match="require amount_per_share"):
        DividendEventContract(**{**BASE, "dividend_type": dividend_type, "amount_per_share": None})


@pytest.mark.parametrize("dividend_type", [DividendType.STOCK, DividendType.RIGHTS])
def test_non_cash_types_reject_cash_amounts(dividend_type: DividendType) -> None:
    with pytest.raises(ValidationError, match="non-cash distributions"):
        DividendEventContract(**{**BASE, "dividend_type": dividend_type})


def test_non_cash_types_can_be_recorded_without_an_amount() -> None:
    contract = DividendEventContract(
        **{
            **BASE,
            "dividend_type": DividendType.STOCK,
            "amount_per_share": None,
        }
    )
    assert contract.amount_per_share is None


def test_naive_acquired_at_is_rejected() -> None:
    naive = datetime(2026, 11, 21, 10)
    with pytest.raises(ValidationError, match="timezone-aware"):
        DividendEventContract(**{**BASE, "acquired_at": naive})


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        DividendEventContract(**{**BASE, "unexpected": "value"})


def test_invalid_currency_and_period_are_rejected() -> None:
    with pytest.raises(ValidationError):
        DividendEventContract(**{**BASE, "currency": "IDR1"})
    with pytest.raises(ValidationError, match="reporting_period_start"):
        DividendEventContract(
            **{
                **BASE,
                "reporting_period_start": date(2026, 2, 1),
                "reporting_period_end": date(2026, 1, 1),
            }
        )


def test_observation_statuses_are_only_confirmed_and_historical() -> None:
    assert {item.value for item in OBSERVED_DIVIDEND_STATUSES} == {"CONFIRMED", "HISTORICAL"}
