"""Desktop view for evidence-qualified simulated portfolio valuation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from decimal import Decimal

    from rfinance.application.portfolio_valuation import (
        PortfolioValuationService,
        PortfolioValuationSnapshot,
    )


class PortfolioValuationWorker(QObject):
    """Run valuation queries away from the Qt main thread."""

    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, service: PortfolioValuationService) -> None:
        super().__init__()
        self._service = service

    @Slot()
    def run(self) -> None:
        try:
            result = self._service.value()
        except Exception as error:
            self.failed.emit(str(error))
            return
        self.completed.emit(result)


class PortfolioValuationPage(QWidget):
    """Read-only valuation surface; accounting remains in application/domain services."""

    def __init__(
        self,
        service: PortfolioValuationService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._thread: QThread | None = None
        self._worker: PortfolioValuationWorker | None = None
        self._build_ui()

    @property
    def is_busy(self) -> bool:
        """Whether a valuation worker is running."""

        return self._thread is not None and self._thread.isRunning()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("Market valuation — simulated")
        title.setStyleSheet("font-size: 17px; font-weight: 600;")
        header.addWidget(title)
        header.addStretch(1)
        self.refresh_button = QPushButton("Refresh valuation")
        self.refresh_button.setObjectName("refreshPortfolioValuationButton")
        self.refresh_button.clicked.connect(self.refresh)
        header.addWidget(self.refresh_button)
        layout.addLayout(header)

        metrics = QHBoxLayout()
        self.market_value_label = QLabel("Eligible market value: —")
        self.portfolio_value_label = QLabel("Portfolio value: —")
        self.unrealized_label = QLabel("Unrealized P/L: —")
        for label in (self.market_value_label, self.portfolio_value_label, self.unrealized_label):
            label.setWordWrap(True)
            metrics.addWidget(label)
        layout.addLayout(metrics)

        self.status_label = QLabel(
            "Refresh to value open positions using fresh, VERIFIED observations only."
        )
        self.status_label.setObjectName("portfolioValuationStatus")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.positions_table = QTableWidget(0, 8)
        self.positions_table.setObjectName("portfolioValuationPositions")
        self.positions_table.setHorizontalHeaderLabels(
            [
                "Instrument",
                "Quantity",
                "Average cost",
                "Price",
                "Market value",
                "Unrealized P/L",
                "Observed (UTC)",
                "Source",
            ]
        )
        self.positions_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.positions_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.positions_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.positions_table.setAlternatingRowColors(True)
        self.positions_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.positions_table)

    @staticmethod
    def _idr(value: Decimal | None) -> str:
        return "—" if value is None else f"Rp{value:,.2f}"

    @staticmethod
    def _cell(value: str, tooltip: str = "") -> QTableWidgetItem:
        item = QTableWidgetItem(value)
        if tooltip:
            item.setToolTip(tooltip)
        return item

    def refresh(self) -> None:
        """Start a single background valuation refresh."""

        if self._thread is not None:
            return
        thread = QThread(self)
        worker = PortfolioValuationWorker(self._service)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.completed.connect(self._render)
        worker.failed.connect(self._failed)
        worker.completed.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.completed.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(lambda: self._thread_finished(thread))
        thread.finished.connect(thread.deleteLater)
        self._thread = thread
        self._worker = worker
        self.refresh_button.setEnabled(False)
        self.status_label.setText(
            "Reconstructing the ledger and checking persisted price evidence…"
        )
        thread.start()

    @Slot(object)
    def _render(self, snapshot: PortfolioValuationSnapshot) -> None:
        valuation = snapshot.valuation
        complete = valuation.is_complete
        self.market_value_label.setText(
            f"Eligible market value: {self._idr(valuation.market_value)}"
        )
        self.portfolio_value_label.setText(
            f"{'Portfolio value' if complete else 'Partial portfolio value'}: "
            f"{self._idr(valuation.total_value)}"
        )
        self.unrealized_label.setText(
            f"Unrealized P/L (priced positions): {self._idr(valuation.unrealized_profit_loss)}"
        )

        evidence_by_instrument = {item.instrument_id: item for item in snapshot.price_evidence}
        reasons_by_instrument = {
            item.instrument_id: item.reasons for item in snapshot.unvalued_positions
        }
        positions = valuation.positions
        self.positions_table.setRowCount(len(positions))

        for row, position in enumerate(positions):
            evidence = evidence_by_instrument.get(position.instrument_id)
            if evidence is None:
                reason = ", ".join(reasons_by_instrument.get(position.instrument_id, ()))
                values = (
                    position.instrument_id,
                    format(position.quantity, "f"),
                    self._idr(position.average_cost),
                    "Not valued",
                    "Not included",
                    "Not available",
                    "—",
                    "—",
                )
                tooltip = f"Position is not valued. Eligibility diagnostics: {reason or 'unknown'}"
            else:
                values = (
                    position.instrument_id,
                    format(position.quantity, "f"),
                    self._idr(position.average_cost),
                    self._idr(evidence.close),
                    self._idr(position.market_value),
                    self._idr(position.unrealized_profit_loss),
                    evidence.observed_at_utc.replace("T", " "),
                    evidence.source_name,
                )
                tooltip = (
                    f"Observation ID: {evidence.observation_id}\n"
                    f"Source ID: {evidence.source_id}\n"
                    f"Acquired (UTC): {evidence.acquired_at_utc}\n"
                    f"Age: {evidence.age_days} day(s)\n"
                    f"Effective quality: {evidence.effective_quality}\n"
                    f"Eligibility methodology: {snapshot.eligibility_methodology}\n"
                    f"Valuation methodology: {valuation.methodology_version}"
                )
            for column, value in enumerate(values):
                item = self._cell(value, tooltip)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, position.instrument_id)
                self.positions_table.setItem(row, column, item)

        self.positions_table.resizeColumnsToContents()
        if not positions:
            self.status_label.setText(
                "Cash-only simulation: no open asset positions are recorded. "
                "No market value or brokerage performance is implied."
            )
        elif complete:
            self.status_label.setText(
                f"Complete simulated valuation: all {len(positions)} open position(s) "
                f"have fresh VERIFIED {valuation.currency} prices. "
                f"{snapshot.observations_considered} stored observation(s) checked; "
                f"{snapshot.observations_rejected} rejected by eligibility/conflict gates. "
                f"Methodology: {valuation.methodology_version}."
            )
        else:
            missing = ", ".join(
                f"{item.instrument_id} ({', '.join(item.reasons)})"
                for item in snapshot.unvalued_positions
            )
            self.status_label.setText(
                f"PARTIAL valuation: {len(snapshot.price_evidence)}/{len(positions)} "
                "position(s) have eligible prices. Unvalued positions are excluded "
                f"from market value and the partial total: {missing}. "
                "No price-at-cost or zero-price substitution was made."
            )

    @Slot(str)
    def _failed(self, message: str) -> None:
        self.status_label.setText(f"Portfolio valuation failed: {message}")

    def _thread_finished(self, thread: QThread) -> None:
        if self._thread is thread:
            self._thread = None
            self._worker = None
        self.refresh_button.setEnabled(True)
