# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Deterministic PDF rendering for local simulated portfolio reports.

Formula version: ``portfolio-pdf-v1``. All content is supplied by the
application layer. The renderer adds no figures and never presents simulated
activity as brokerage performance.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from PySide6.QtGui import QFont, QPainter, QPdfWriter

if TYPE_CHECKING:
    from pathlib import Path

FORMULA_VERSION = "portfolio-pdf-v1"
_MARGIN = 50
_LINE_HEIGHT = 16
_SECTION_GAP = 10
_PAGE_BOTTOM = 760


@dataclass(frozen=True, slots=True)
class ReportLine:
    label: str
    value: str


@dataclass(frozen=True, slots=True)
class PortfolioReportData:
    """Explicit report content assembled from persisted local records."""

    title: str
    generated_at_utc: str
    reporting_period: str
    currency: str
    sections: tuple[tuple[str, tuple[ReportLine, ...]], ...]
    warnings: tuple[str, ...] = ()
    methodology_version: str = FORMULA_VERSION

    def as_text(self) -> str:
        """A plain-text rendering used for verification and accessibility."""

        parts = [
            self.title,
            f"Generated (UTC): {self.generated_at_utc}",
            f"Reporting period: {self.reporting_period}",
            f"Currency: {self.currency}",
        ]
        for heading, lines in self.sections:
            parts.append(heading)
            parts.extend(f"{line.label}: {line.value}" for line in lines)
        parts.extend(f"Warning: {warning}" for warning in self.warnings)
        parts.append(f"Methodology: {self.methodology_version}")
        return "\n".join(parts)


def render_portfolio_report(path: Path, data: PortfolioReportData) -> Path:
    """Write a multi-section PDF and return the destination path."""

    target = path.resolve()
    writer = QPdfWriter(str(target))
    writer.setTitle(data.title)
    painter = QPainter(writer)
    font = QFont()
    font.setPointSize(9)
    painter.setFont(font)

    y = _MARGIN + 12

    def write(text: str, *, indent: int = 0, bold: bool = False) -> None:
        nonlocal y
        if y > _PAGE_BOTTOM:
            writer.newPage()
            y = _MARGIN + 12
        font.setBold(bold)
        painter.setFont(font)
        painter.drawText(_MARGIN + indent, y, text)
        font.setBold(False)
        painter.setFont(font)
        y += _LINE_HEIGHT

    write(f"{data.title} — SIMULATED", bold=True)
    write(f"Generated (UTC): {data.generated_at_utc}")
    write(f"Reporting period: {data.reporting_period}")
    write(f"Currency: {data.currency}")
    write("This is a local simulation, not brokerage performance or a tax record.")
    y += _SECTION_GAP

    for heading, lines in data.sections:
        write(heading, bold=True)
        for line in lines:
            write(f"{line.label}: {line.value}", indent=12)
        y += _SECTION_GAP

    if data.warnings:
        write("Warnings", bold=True)
        for warning in data.warnings:
            write(warning, indent=12)
    write(f"Methodology: {data.methodology_version}")

    painter.end()
    return target
