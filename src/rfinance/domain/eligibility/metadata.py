# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Explicit sampling-frequency and corporate-action adjustment evidence.

Historical bar counts do not establish sampling frequency, and a price series
whose adjustment history is unknown must never be promoted to an adjusted one.
This module defines the narrow vocabulary shared by the evidence recorder and
the historical series service.
"""

from __future__ import annotations

from enum import StrEnum

FORMULA_VERSION = "instrument-metadata-evidence-v1"


class SamplingFrequency(StrEnum):
    """Stated sampling frequency of a supplied price series."""

    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    INTRADAY = "INTRADAY"
    UNKNOWN_AS_SUPPLIED = "UNKNOWN_AS_SUPPLIED"


class AdjustmentStatus(StrEnum):
    """Corporate-action adjustment state of a supplied price series."""

    NONE_CONFIRMED = "NONE_CONFIRMED"
    ADJUSTED = "ADJUSTED"
    UNKNOWN_AS_SUPPLIED = "UNKNOWN_AS_SUPPLIED"
