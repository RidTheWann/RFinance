# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Desktop workflow for evidence-qualified historical technical analysis."""

from __future__ import annotations

from datetime import UTC
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rfinance.application.historical_price_series import HistoricalSeriesChoice
from rfinance.application.technical_analysis import (
    TechnicalAnalysisReport,
    TechnicalAnalysisService,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from decimal import Decimal


class TechnicalAnalysisWorker(QObject):
    """Execute catalogue queries or indicator calculation outside the Qt thread."""

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


class TechnicalAnalysisPage(QWidget):
    """Read-only technical view; source observations remain immutable."""

    def __init__(
        self,
        service: TechnicalAnalysisService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._thread: QThread | None = None
        self._worker: TechnicalAnalysisWorker | None = None
        self._task: str | None = None
        self._choices: tuple[HistoricalSeriesChoice, ...] = ()
        self._build_ui()

    @property
    def is_busy(self) -> bool:
        """Whether a catalogue or analysis task is still executing."""

        return self._thread is not None and self._thread.isRunning()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(12)

        title = QLabel("Technical Analysis")
        title.setObjectName("technicalAnalysisTitle")
        title.setStyleSheet("font-size: 26px; font-weight: 600;")
        layout.addWidget(title)
        description = QLabel(
            "Indicators use verified historical bars from one selected source. "
            "Historical dates are not rejected by the current-quote freshness window; "
            "no frequency inference, resampling, interpolation, or corporate-action "
            "adjustment is performed."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        controls = QFormLayout()
        self.instrument_combo = QComboBox()
        self.instrument_combo.setObjectName("technicalInstrumentCombo")
        self.source_combo = QComboBox()
        self.source_combo.setObjectName("technicalSourceCombo")
        self.max_gap_spin = QSpinBox()
        self.max_gap_spin.setObjectName("technicalMaxGapDays")
        self.max_gap_spin.setRange(1, 365)
        self.max_gap_spin.setValue(7)
        self.max_gap_spin.setSuffix(" calendar days")
        controls.addRow("Instrument", self.instrument_combo)
        controls.addRow("Single data source", self.source_combo)
        controls.addRow("Break indicator windows after gaps greater than", self.max_gap_spin)
        layout.addLayout(controls)

        actions = QHBoxLayout()
        self.refresh_catalog_button = QPushButton("Refresh available histories")
        self.refresh_catalog_button.setObjectName("refreshTechnicalCatalogButton")
        self.refresh_catalog_button.clicked.connect(self.refresh_catalog)
        self.analyze_button = QPushButton("Calculate indicators")
        self.analyze_button.setObjectName("calculateTechnicalIndicatorsButton")
        self.analyze_button.clicked.connect(self.analyze)
        self.analyze_button.setEnabled(False)
        actions.addWidget(self.refresh_catalog_button)
        actions.addWidget(self.analyze_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.summary_label = QLabel(
            "No historical series selected. Import lawful data, verify instrument identity "
            "and review individual price observations before analysis."
        )
        self.summary_label.setObjectName("technicalSummary")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        self.status_label = QLabel("Catalogue has not been loaded. No live provider is configured.")
        self.status_label.setObjectName("technicalStatus")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.indicator_table = QTableWidget(0, 4)
        self.indicator_table.setObjectName("technicalIndicatorTable")
        self.indicator_table.setHorizontalHeaderLabels(
            ["Indicator", "Latest aligned value", "Unit", "Parameters / warm-up"]
        )
        self.indicator_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.indicator_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.indicator_table.setAlternatingRowColors(True)
        self.indicator_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.indicator_table, 1)

        self.instrument_combo.currentIndexChanged.connect(self._populate_sources)
        self.source_combo.currentIndexChanged.connect(self._update_analyze_enabled)

    def refresh_catalog(self) -> None:
        """Load locally stored instrument/source choices on a worker thread."""

        self._start_task("catalog", self._service.available_series)

    def analyze(self) -> None:
        """Calculate indicators for the explicitly selected instrument and source."""

        instrument_id = self.instrument_combo.currentData()
        source_id = self.source_combo.currentData()
        if not isinstance(instrument_id, str) or not isinstance(source_id, str):
            self.status_label.setText("Select an available instrument and one source.")
            return
        max_gap_days = self.max_gap_spin.value()
        self._start_task(
            "analysis",
            lambda: self._service.analyze(
                instrument_id,
                source_id,
                max_gap_days=max_gap_days,
            ),
        )

    def _start_task(self, task: str, operation: Callable[[], object]) -> None:
        if self._thread is not None:
            return
        thread = QThread(self)
        worker = TechnicalAnalysisWorker(operation)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.completed.connect(self._task_completed)
        worker.failed.connect(self._task_failed)
        worker.completed.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.completed.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)
        thread.finished.connect(lambda: self._thread_finished(thread))
        thread.finished.connect(thread.deleteLater)
        self._thread = thread
        self._worker = worker
        self._task = task
        self._set_busy(True)
        status_message = (
            "Loading eligible local series…"
            if task == "catalog"
            else "Calculating Decimal indicators…"
        )
        self.status_label.setText(status_message)
        thread.start()

    @Slot(object)
    def _task_completed(self, result: object) -> None:
        if self._task == "catalog":
            self._render_catalog(result)
        elif self._task == "analysis":
            self._render_report(result)

    @Slot(str)
    def _task_failed(self, message: str) -> None:
        self.status_label.setText(f"Technical analysis failed: {message}")

    def _thread_finished(self, thread: QThread) -> None:
        if self._thread is thread:
            self._thread = None
            self._worker = None
            self._task = None
        self._set_busy(False)

    def _set_busy(self, busy: bool) -> None:
        self.refresh_catalog_button.setEnabled(not busy)
        self.analyze_button.setEnabled(
            not busy
            and isinstance(self.instrument_combo.currentData(), str)
            and isinstance(self.source_combo.currentData(), str)
        )
        self.instrument_combo.setEnabled(not busy)
        self.source_combo.setEnabled(not busy)
        self.max_gap_spin.setEnabled(not busy)

    def _render_catalog(self, result: object) -> None:
        if not isinstance(result, tuple):
            raise TypeError("technical series catalogue returned an invalid result")
        choices = tuple(item for item in result if isinstance(item, HistoricalSeriesChoice))
        self._choices = choices
        self.instrument_combo.blockSignals(True)
        self.source_combo.blockSignals(True)
        self.instrument_combo.clear()
        self.source_combo.clear()

        seen_instruments: set[str] = set()
        for choice in choices:
            if choice.instrument_id in seen_instruments:
                continue
            seen_instruments.add(choice.instrument_id)
            self.instrument_combo.addItem(
                f"{choice.ticker} — {choice.company_name} [{choice.instrument_id}]",
                choice.instrument_id,
            )
        self.instrument_combo.blockSignals(False)
        self.source_combo.blockSignals(False)
        self._populate_sources()
        if not choices:
            self.summary_label.setText(
                "No verified, active instrument/source pairs are available. "
                "Import local historical data, verify the instrument master, and review prices."
            )
            self.status_label.setText("No eligible instrument catalogue entries were found.")
        else:
            self.status_label.setText(
                f"Loaded {len(seen_instruments)} verified instrument(s) across "
                f"{len(choices)} source pair(s). Select one source; sources are never blended."
            )

    def _populate_sources(self, *_args: object) -> None:
        instrument_id = self.instrument_combo.currentData()
        self.source_combo.blockSignals(True)
        self.source_combo.clear()
        if isinstance(instrument_id, str):
            for choice in self._choices:
                if choice.instrument_id == instrument_id:
                    self.source_combo.addItem(
                        f"{choice.source_name} [{choice.source_id}]",
                        choice.source_id,
                    )
        self.source_combo.blockSignals(False)
        self._update_analyze_enabled()

    def _update_analyze_enabled(self, *_args: object) -> None:
        self.analyze_button.setEnabled(
            self._thread is None
            and isinstance(self.instrument_combo.currentData(), str)
            and isinstance(self.source_combo.currentData(), str)
        )

    @staticmethod
    def _display_value(value: Decimal | None) -> str:
        return "— (warm-up / unavailable)" if value is None else format(value, ".8f")

    def _render_report(self, result: object) -> None:
        if not isinstance(result, TechnicalAnalysisReport):
            raise TypeError("technical analysis service returned an invalid report")
        series = result.series
        self.indicator_table.setRowCount(len(result.indicators))
        for row, reading in enumerate(result.indicators):
            values = (
                reading.label,
                self._display_value(reading.value),
                reading.unit,
                reading.parameters,
            )
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                cell.setToolTip(
                    f"Formula: {result.formula_version}\n"
                    f"Report: {result.methodology_version}\n"
                    f"Observation eligibility: {series.eligibility_methodology}\n"
                    f"Source: {series.source_name} ({series.source_id})\n"
                    f"Adjustment status: {series.adjustment_status}"
                )
                self.indicator_table.setItem(row, column, cell)
        self.indicator_table.resizeColumnsToContents()

        if not series.points:
            reason_text = ", ".join(
                f"{reason} ({count})" for reason, count in series.rejected_reasons
            )
            self.summary_label.setText(
                "No eligible historical prices are available for this instrument/source. "
                "Indicator values remain unavailable; no figures were fabricated."
            )
            self.status_label.setText(
                f"{series.rejected_count} observation(s) rejected. "
                f"Diagnostics: {reason_text or 'no observations in the selected source'}."
            )
            return

        first = series.points[0]
        latest = series.points[-1]
        close_text = self._display_value(result.latest_close)
        self.summary_label.setText(
            f"{series.ticker} — {series.company_name} | Latest verified close: "
            f"{series.currency} {close_text} per unit | "
            f"{latest.observed_at.astimezone(UTC).strftime('%Y-%m-%d %H:%M UTC')}"
        )
        self.status_label.setText(
            f"{len(series.points):,} verified historical bar(s), from "
            f"{first.observed_at.astimezone().date()} to "
            f"{latest.observed_at.astimezone().date()}. "
            f"{series.rejected_count:,} row(s) rejected; {len(series.gaps)} gap break(s) "
            f"greater than {series.max_gap_days} calendar days. "
            f"Source: {series.source_name}. Adjustment: {series.adjustment_status}. "
            "Bars are not resampled; all indicator periods count observations, not calendar days."
        )
