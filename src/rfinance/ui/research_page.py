# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Desktop view for inspecting persisted, evidence-linked recommendations."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rfinance.domain.recommendations.screening import Recommendation

if TYPE_CHECKING:
    from collections.abc import Callable

    from rfinance.application.recommendations import RecommendationService
    from rfinance.application.risk_monitoring import RiskMonitoringService
    from rfinance.application.screening_evaluation import ScreeningEvaluationService


class EvaluationWorker(QObject):
    """Run one screening evaluation outside the Qt main thread."""

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


class ResearchPage(QWidget):
    """Inspect stored recommendations and run a guided evidence evaluation."""

    def __init__(
        self,
        service: RecommendationService,
        *,
        evaluation: ScreeningEvaluationService | None = None,
        risk_monitoring: RiskMonitoringService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._evaluation = evaluation
        self._risk_monitoring = risk_monitoring
        self._thread: QThread | None = None
        self._worker: EvaluationWorker | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        title = QLabel("Research Center")
        title.setObjectName("researchPageTitle")
        title.setStyleSheet("font-size: 26px; font-weight: 600;")
        layout.addWidget(title)
        layout.addWidget(
            QLabel(
                "Deterministic screening results are stored with their evidence, risk flags "
                "and invalidation conditions. Confidence measures evidence quality, not the "
                "probability of profit. A result is research, not a trade instruction."
            )
        )
        self.risk_control_label = QLabel("")
        self.risk_control_label.setObjectName("researchRiskControlStatus")
        self.risk_control_label.setWordWrap(True)
        layout.addWidget(self.risk_control_label)

        form = QFormLayout()
        self.evaluate_instrument_input = QLineEdit("IDX:BBCA")
        self.evaluate_revenue_input = QLineEdit()
        self.evaluate_previous_revenue_input = QLineEdit()
        self.evaluate_net_income_input = QLineEdit()
        self.evaluate_average_equity_input = QLineEdit()
        self.evaluate_total_debt_input = QLineEdit()
        self.evaluate_total_equity_input = QLineEdit()
        self.evaluate_eps_input = QLineEdit()
        self.evaluate_price_input = QLineEdit()
        self.use_filings_checkbox = QCheckBox(
            "Use verified local filings instead of the inputs below"
        )
        form.addRow("Instrument ID", self.evaluate_instrument_input)
        form.addRow("Revenue", self.evaluate_revenue_input)
        form.addRow("Prior revenue", self.evaluate_previous_revenue_input)
        form.addRow("Net income", self.evaluate_net_income_input)
        form.addRow("Average equity", self.evaluate_average_equity_input)
        form.addRow("Total debt", self.evaluate_total_debt_input)
        form.addRow("Total equity", self.evaluate_total_equity_input)
        form.addRow("EPS", self.evaluate_eps_input)
        form.addRow("Price", self.evaluate_price_input)
        form.addRow("", self.use_filings_checkbox)
        layout.addLayout(form)

        self.evaluate_button = QPushButton("Evaluate from local evidence")
        self.evaluate_button.setObjectName("evaluateScreeningButton")
        self.evaluate_button.clicked.connect(self._run_evaluation)
        layout.addWidget(self.evaluate_button)
        self.evaluation_detail_label = QLabel(
            "Fundamental inputs are operator-supplied, not verified filing values."
        )
        self.evaluation_detail_label.setObjectName("evaluationDetail")
        self.evaluation_detail_label.setWordWrap(True)
        layout.addWidget(self.evaluation_detail_label)

        self.refresh_button = QPushButton("Refresh recommendations")
        self.refresh_button.setObjectName("refreshRecommendationsButton")
        self.refresh_button.clicked.connect(self.refresh)
        layout.addWidget(self.refresh_button)

        self.empty_label = QLabel("No recommendations have been evaluated and stored yet.")
        self.empty_label.setObjectName("researchEmpty")
        layout.addWidget(self.empty_label)

        self.table = QTableWidget(0, 6)
        self.table.setObjectName("researchRecommendationsTable")
        self.table.setHorizontalHeaderLabels(
            [
                "Generated (UTC)",
                "Instrument",
                "Action",
                "Confidence",
                "Risk flags",
                "Methodology",
            ]
        )
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.hide()
        layout.addWidget(self.table, 1)

        self.detail_label = QLabel("Select a recommendation to inspect its evidence and reasoning.")
        self.detail_label.setObjectName("researchDetail")
        self.detail_label.setWordWrap(True)
        layout.addWidget(self.detail_label)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.refresh()
        self.refresh_risk_controls()

    def refresh_risk_controls(self) -> None:
        """Show persisted risk-control state that gates new BUY_CANDIDATE results."""

        if self._risk_monitoring is None:
            self.risk_control_label.setText("")
            return
        controls = self._risk_monitoring.screening_controls()
        if not controls.review_required:
            self.risk_control_label.setText(
                "Risk controls: no active review events. Evaluation uses current stored evidence."
            )
            return
        if controls.buy_candidates_suspended or controls.critical:
            state = "new BUY_CANDIDATE promotion is suspended"
        else:
            state = "a non-blocking review is recorded"
        self.risk_control_label.setText(
            f"Risk controls: {len(controls.active_event_ids)} active review event(s); {state}. "
            "Resolve the event in Risk Management before a BUY_CANDIDATE can be promoted."
        )

    def _run_evaluation(self) -> None:
        if self._evaluation is None:
            self.evaluation_detail_label.setText("Guided evaluation is unavailable.")
            return
        if self._thread is not None and self._thread.isRunning():
            return
        try:
            fields = {
                "revenue": self.evaluate_revenue_input.text().strip(),
                "revenue_previous": self.evaluate_previous_revenue_input.text().strip(),
                "net_income": self.evaluate_net_income_input.text().strip(),
                "average_equity": self.evaluate_average_equity_input.text().strip(),
                "total_debt": self.evaluate_total_debt_input.text().strip(),
                "total_equity": self.evaluate_total_equity_input.text().strip(),
                "earnings_per_share": self.evaluate_eps_input.text().strip(),
                "price": self.evaluate_price_input.text().strip(),
            }
            fundamentals = {
                name: None if not value else Decimal(value) for name, value in fields.items()
            }
        except (ValueError, TypeError, InvalidOperation):
            self.evaluation_detail_label.setText("Enter valid Decimal fundamental inputs.")
            return

        evaluation = self._evaluation
        instrument_id = self.evaluate_instrument_input.text().strip()

        def operation() -> object:
            return evaluation.evaluate(
                instrument_id,
                fundamentals=fundamentals,
                use_persisted_fundamentals=self.use_filings_checkbox.isChecked(),
            )

        def on_success(result: object) -> None:
            self._on_evaluation_done(result)

        self._start_worker(operation, on_success)

    def _start_worker(
        self,
        operation: Callable[[], object],
        on_success: Callable[[object], None],
    ) -> None:
        thread = QThread(self)
        worker = EvaluationWorker(operation)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.completed.connect(on_success)
        worker.failed.connect(self._on_evaluation_failed)
        worker.completed.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.completed.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(lambda: self._on_thread_finished(thread))
        thread.finished.connect(thread.deleteLater)
        self._thread = thread
        self._worker = worker
        self.evaluate_button.setEnabled(False)
        self.evaluation_detail_label.setText("Evaluating from local evidence…")
        thread.start()

    def _on_evaluation_done(self, result: object) -> None:
        assert isinstance(result, Recommendation)
        self.evaluate_button.setEnabled(True)
        self.evaluation_detail_label.setText(
            f"Action: {result.action.value}\n"
            f"Explanation: {result.explanation}\n"
            f"Evidence: {', '.join(result.evidence_ids) or 'none'}\n"
            f"Risk flags: {', '.join(flag.value for flag in result.risk_flags) or 'none'}\n"
            f"Invalidation: {'; '.join(result.invalidation_conditions)}"
        )
        self.refresh()
        self.refresh_risk_controls()

    def _on_evaluation_failed(self, message: str) -> None:
        self.evaluate_button.setEnabled(True)
        self.evaluation_detail_label.setText(f"Evaluation failed: {message}")

    def _on_thread_finished(self, thread: QThread) -> None:
        if self._thread is thread:
            self._thread = None
            self._worker = None

    def refresh(self) -> None:
        items = self._service.recent(limit=100)
        self.table.setRowCount(len(items))
        self.empty_label.setVisible(not items)
        self.table.setVisible(bool(items))
        for row, item in enumerate(items):
            values = (
                item.generated_at_utc.replace("T", " "),
                item.instrument_id,
                item.action,
                f"{item.confidence_level:.2f}",
                ", ".join(item.risk_flags) or "none",
                item.methodology_version,
            )
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setData(Qt.ItemDataRole.UserRole, item.recommendation_id)
                if column == 2:
                    cell.setToolTip(
                        "BUY_CANDIDATE is blocked when evidence is stale, unverified or "
                        "materially incomplete."
                    )
                cell.setToolTip(
                    f"{cell.toolTip()}\nExplanation: {item.explanation}\n"
                    f"Evidence: {', '.join(item.evidence_ids) or 'none'}"
                )
                self.table.setItem(row, column, cell)
        self.table.resizeColumnsToContents()
        if items:
            self.table.selectRow(0)
        else:
            self.detail_label.setText("No recommendations have been evaluated and stored yet.")

    def _on_selection_changed(self) -> None:
        selected = self.table.selectedItems()
        if not selected:
            return
        recommendation_id = selected[0].data(Qt.ItemDataRole.UserRole)
        if not isinstance(recommendation_id, str):
            return
        result = self._service.get(recommendation_id)
        if result is None:
            return
        self.detail_label.setText(
            f"Action: {result.action.value}\n"
            f"Explanation: {result.explanation}\n"
            f"Evidence IDs: {', '.join(result.evidence_ids) or 'none'}\n"
            f"Risk flags: {', '.join(flag.value for flag in result.risk_flags) or 'none'}\n"
            f"Invalidation conditions: {'; '.join(result.invalidation_conditions)}\n"
            f"Fundamental: {result.fundamental_assessment}\n"
            f"Price: {result.price_assessment}\n"
            f"Dividend: {result.dividend_assessment}"
        )
