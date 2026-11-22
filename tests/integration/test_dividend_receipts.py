# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Persistence tests for confirmed dividend receipts."""

from pathlib import Path

import pytest
import sqlalchemy as sa

from rfinance.storage.database import Database


def test_migration_extends_ledger_event_types_and_creates_receipt_table(
    tmp_path: Path,
) -> None:
    database = Database.open(tmp_path / "receipts.sqlite3")
    database.upgrade()

    with database.sessions.begin() as session:
        session.execute(
            sa.text(
                "INSERT INTO portfolio_ledger_events "
                "(event_id, sequence, occurred_at_utc, event_type, currency, amount, "
                "fees, taxes) VALUES "
                "('legacy', 1, '2026-11-21T00:00:00+00:00', 'CAPITAL_INJECTION', "
                "'IDR', '5000000', '0', '0')"
            )
        )

    with database.sessions.begin() as session:
        session.execute(
            sa.text(
                "INSERT INTO portfolio_ledger_events "
                "(event_id, sequence, occurred_at_utc, event_type, currency, amount, "
                "instrument_id, source_reference, fees, taxes) VALUES "
                "('receipt', 2, '2026-11-22T00:00:00+00:00', 'CONFIRMED_DIVIDEND', "
                "'IDR', '100000', 'IDX:BBCA', 'DIVIDEND_RECEIPT:event-1', '0', '0')"
            )
        )

    assert sa.inspect(database.engine).has_table("dividend_receipts") is True

    with database.sessions.begin() as session:
        session.execute(
            sa.text(
                "INSERT INTO dividend_receipts "
                "(receipt_id, dividend_event_id, instrument_id, net_amount, "
                "reinvestment, money_market, withdrawal, reinvest_weight, "
                "money_market_weight, withdrawal_weight, recorded_at_utc, "
                "methodology_version) VALUES "
                "('r1', 'event-1', 'IDX:BBCA', '100000', '50000', '30000', '20000', "
                "'0.5', '0.3', '0.2', '2026-11-22T00:00:00+00:00', 'dividend-receipt-v1')"
            )
        )
    with pytest.raises(sa.exc.IntegrityError), database.sessions.begin() as session:
        session.execute(
            sa.text(
                "INSERT INTO dividend_receipts "
                "(receipt_id, dividend_event_id, instrument_id, net_amount, "
                "reinvestment, money_market, withdrawal, reinvest_weight, "
                "money_market_weight, withdrawal_weight, recorded_at_utc, "
                "methodology_version) VALUES "
                "('r2', 'event-1', 'IDX:BBCA', '100000', '50000', '30000', '20000', "
                "'0.5', '0.3', '0.2', '2026-11-22T00:00:00+00:00', 'dividend-receipt-v1')"
            )
        )
    with pytest.raises(sa.exc.IntegrityError), database.sessions.begin() as session:
        session.execute(sa.text("UPDATE dividend_receipts SET net_amount = '1'"))
    database.close()
