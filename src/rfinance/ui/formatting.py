# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Shared, locale-stable display formatters for the desktop UI.

Financial values keep their exact Decimal representation in services and
storage; these helpers only render values for human reading. Missing values are
shown explicitly instead of being coerced to zero.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from decimal import Decimal

MISSING = "—"


def format_idr(value: Decimal | None) -> str:
    """Render an IDR amount with grouping, or ``—`` when unavailable."""

    return MISSING if value is None else f"Rp{value:,.2f}"


def format_percent(value: Decimal | None) -> str:
    """Render a ratio as a percentage, or ``—`` when unavailable."""

    return MISSING if value is None else f"{value * 100:,.2f}%"


def format_decimal(value: Decimal | None) -> str:
    """Render an exact Decimal for inspection, or ``—`` when unavailable."""

    return MISSING if value is None else format(value, "f")
