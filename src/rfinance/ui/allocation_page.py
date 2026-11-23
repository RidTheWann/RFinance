# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Desktop view for the deterministic allocation gap plan."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QThread, Signal, Slot
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

from rfinance.ui.category_evidence_page import CategoryEvidencePanel

if TYPE_CHECKING:
    from collections.abc import Sequence
    from decimal import Decimal

    from rfinance.application.allocation_planning import AllocationPlanningService
    from rfinance.application.instrument_category import InstrumentCategoryService
    from rfinance.domain.portfolio.allocation import (
        AllocationPlan,
        InvestableInstrument,
    )


class AllocationPlanWorker(QObject):
    """Run allocation planning away from the Qt main thread."""

    completed = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        service: AllocationPlanningService,
        instruments: Sequence[InvestableInstrument],
    ) -> None:
        super().__init__()
        self._service = service
        self._instruments = instruments

    @Slot()
    def run(self) -> None:
        try:
            result = self._service.plan(instruments=self._instruments)
        except Exception as error:
            self.failed.emit(str(error))
            return
        self.completed.emit(result)


class AllocationPage(QWidget):
    """Read-only target-versus-current view; no order entry lives here."""

    def __init__(
        self,
        service: AllocationPlanningService,
        *,
        instruments: Sequence[InvestableInstrument] = (),
        category_service: InstrumentCategoryService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._instruments = tuple(instruments)
        self._category_service = category_service
        self._thread: QThread | None = None
        self._worker: AllocationPlanWorker | None = None
        self._build_ui()

    @property
    def is_busy(self) -> bool:
        return self._thread is not None

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("Allocation plan — simulated targets")
        title.setStyleSheet("font-size: 17px; font-weight: 600;")
        header.addWidget(title)
        header.addStretch(1)
        self.refresh_button = QPushButton("Refresh allocation plan")
        self.refresh_button.setObjectName("refreshAllocationPlanButton")
        self.refresh_button.clicked.connect(self.refresh)
        header.addWidget(self.refresh_button)
        layout.addLayout(header)

        self.summary_label = QLabel("Refresh to compare holdings with configured targets.")
        self.summary_label.setObjectName("allocationPlanSummary")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        self.table = QTableWidget(0, 8)
        self.table.setObjectName("allocationPlanTable")
        self.table.setHorizontalHeaderLabels(
            [
                "Category",
                "Target",
                "Target amount",
                "Current value",
                "Difference",
                "Status",
                "Instrument",
                "Lots",
            ]
        )
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)
        if self._category_service is not None:
            self.category_panel = CategoryEvidencePanel(self._category_service, self)
            layout.addWidget(self.category_panel)
        self.refresh()

    @staticmethod
    def _idr(value: Decimal) -> str:
        return f"Rp{value:,.2f}"

    def refresh(self) -> None:
        if self._thread is not None:
            return
        thread = QThread(self)
        worker = AllocationPlanWorker(self._service, self._instruments)
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
        self.summary_label.setText("Deriving allocation gaps from the local valuation…")
        thread.start()

    @Slot(object)
    def _render(self, plan: AllocationPlan) -> None:
        self.table.setRowCount(len(plan.lines))
        for row, line in enumerate(plan.lines):
            values = (
                line.category.value,
                f"{line.target:.0%}",
                self._idr(line.target_amount),
                self._idr(line.current_value),
                self._idr(line.difference),
                line.action.value,
                line.instrument_id or "—",
                str(line.quantity_lots) if line.quantity_lots is not None else "—",
            )
            tooltip = "\n".join(line.reasons) or "No diagnostics."
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(tooltip)
                self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()
        self.summary_label.setText(
            f"Portfolio value: {self._idr(plan.total_value)} · "
            f"Cash: {self._idr(plan.cash)} · Methodology: {plan.methodology_version}. "
            + " ".join(plan.warnings)
        )
        self.refresh_button.setEnabled(True)

    @Slot(str)
    def _failed(self, message: str) -> None:
        self.summary_label.setText(f"Allocation planning failed: {message}")
        self.refresh_button.setEnabled(True)

    def _thread_finished(self, thread: QThread) -> None:
        if self._thread is thread:
            self._thread = None
            self._worker = None
        self.refresh_button.setEnabled(True)
