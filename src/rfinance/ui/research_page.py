# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Desktop view for inspecting persisted, evidence-linked recommendations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from rfinance.application.recommendations import RecommendationService


class ResearchPage(QWidget):
    """Read-only inspection of deterministic screening results and their evidence."""

    def __init__(self, service: RecommendationService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = service
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
