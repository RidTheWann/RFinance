# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Desktop form for audited simulated trade entry."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, cast

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from PySide6.QtGui import QCloseEvent

    from rfinance.application.portfolio_ledger import PortfolioLedgerService
    from rfinance.application.portfolio_trading import (
        PortfolioTradingService,
        VerifiedLotSizeService,
    )
    from rfinance.domain.portfolio.ledger import LedgerReplayResult


class TradeWorker(QObject):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, operation: Callable[[], object]) -> None:
        super().__init__()
        self._operation = operation

    @Slot()
    def run(self) -> None:
        try:
            result = self._operation()
        except Exception as error:
            self.failed.emit(str(error))
            return
        self.completed.emit(result)


class PortfolioTradingPage(QWidget):
    """Record a simulated BUY/SELL only with verified lot evidence."""

    def __init__(
        self,
        service: PortfolioTradingService,
        ledger: PortfolioLedgerService,
        lot_sizes: VerifiedLotSizeService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._ledger = ledger
        self._lot_sizes = lot_sizes
        self._thread: QThread | None = None
        self._worker: TradeWorker | None = None
        self._build_ui()
        self.refresh_lot_rule()

    @property
    def is_busy(self) -> bool:
        return self._thread is not None

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 8)
        layout.setSpacing(10)
        layout.addWidget(QLabel("Simulated trade entry (no real order is placed)"))

        form = QFormLayout()
        self.instrument_input = QLineEdit("IDX:BBCA")
        self.side_combo = QComboBox()
        self.side_combo.addItems(["BUY", "SELL"])
        self.quantity_input = QLineEdit()
        self.price_input = QLineEdit()
        self.fees_input = QLineEdit("0")
        self.taxes_input = QLineEdit("0")
        form.addRow("Instrument ID", self.instrument_input)
        form.addRow("Side", self.side_combo)
        form.addRow("Quantity (shares)", self.quantity_input)
        form.addRow("Unit price (IDR)", self.price_input)
        form.addRow("Fees (IDR)", self.fees_input)
        form.addRow("Taxes (IDR)", self.taxes_input)
        layout.addLayout(form)

        self.lot_rule_label = QLabel()
        self.lot_rule_label.setObjectName("lotRuleStatus")
        self.lot_rule_label.setWordWrap(True)
        layout.addWidget(self.lot_rule_label)

        self.submit_button = QPushButton("Record simulated trade")
        self.submit_button.setObjectName("recordSimulatedTradeButton")
        self.submit_button.clicked.connect(self._submit)
        layout.addWidget(self.submit_button)

        self.status_label = QLabel("No simulated trade has been recorded in this session.")
        self.status_label.setObjectName("tradingStatus")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        layout.addStretch(1)

    def refresh_lot_rule(self) -> None:
        instrument_id = self.instrument_input.text().strip()
        rule = self._lot_sizes.lot_size_for(instrument_id)
        if rule is None:
            self.lot_rule_label.setText(
                f"No verified lot-size evidence for {instrument_id}. "
                "Trading is blocked until the instrument is reviewed with evidence."
            )
        else:
            self.lot_rule_label.setText(
                f"Verified lot size: {rule.size} shares. Evidence: {rule.source_reference}."
            )

    def _submit(self) -> None:
        if self.is_busy:
            return
        self.refresh_lot_rule()
        instrument_id = self.instrument_input.text().strip()
        try:
            quantity = Decimal(self.quantity_input.text().strip())
            price = Decimal(self.price_input.text().strip())
            fees = Decimal(self.fees_input.text().strip() or "0")
            taxes = Decimal(self.taxes_input.text().strip() or "0")
        except (ValueError, InvalidOperation):
            self.status_label.setText("Enter valid Decimal values for quantity, price and costs.")
            return
        side = self.side_combo.currentText()

        def operation() -> object:
            if side == "BUY":
                return self._service.buy(
                    instrument_id,
                    quantity=quantity,
                    unit_price=price,
                    fees=fees,
                    taxes=taxes,
                )
            return self._service.sell(
                instrument_id,
                quantity=quantity,
                unit_price=price,
                fees=fees,
                taxes=taxes,
            )

        def on_success(result: object) -> None:
            snapshot = cast("LedgerReplayResult", result)
            self.status_label.setText(
                f"{side} recorded: cash {snapshot.cash_balance:,.2f} IDR; "
                f"{len(snapshot.positions)} open position(s). Simulated only."
            )

        self._start_worker(operation, on_success)

    def _start_worker(
        self,
        operation: Callable[[], object],
        on_success: Callable[[object], None],
    ) -> None:
        thread = QThread(self)
        worker = TradeWorker(operation)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.completed.connect(on_success)
        worker.failed.connect(self._on_failed)
        worker.completed.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.completed.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(lambda: self._on_thread_finished(thread))
        thread.finished.connect(thread.deleteLater)
        self._thread = thread
        self._worker = worker
        self.submit_button.setEnabled(False)
        self.status_label.setText("Recording simulated trade…")
        thread.start()

    def _on_failed(self, message: str) -> None:
        self.submit_button.setEnabled(True)
        self.status_label.setText(f"Trade rejected: {message}")

    def _on_thread_finished(self, thread: QThread) -> None:
        if self._thread is thread:
            self._thread = None
            self._worker = None
        self.submit_button.setEnabled(True)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.is_busy:
            event.ignore()
            return
        super().closeEvent(event)
