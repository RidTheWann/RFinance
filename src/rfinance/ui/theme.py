# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2026 RFinance Contributors
# See LICENSE for the full GNU General Public License version 3.
"""Central design tokens and Qt-compatible application stylesheets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from rfinance.ui.qt_compat import QtGui, QtWidgets

ThemeMode = Literal["dark", "light"]


@dataclass(frozen=True, slots=True)
class ThemeTokens:
    """Semantic colors for the application surface and financial states."""

    mode: ThemeMode
    bg_canvas: str
    bg_sidebar: str
    bg_surface: str
    bg_elevated: str
    bg_hover: str
    border_subtle: str
    border_strong: str
    text_primary: str
    text_secondary: str
    text_muted: str
    accent: str
    accent_hover: str
    accent_subtle: str
    positive: str
    positive_bg: str
    negative: str
    negative_bg: str
    warning: str
    warning_bg: str


DARK_THEME = ThemeTokens(
    mode="dark",
    bg_canvas="#0B0F17",
    bg_sidebar="#0F1522",
    bg_surface="#131B2B",
    bg_elevated="#1A2438",
    bg_hover="#222F47",
    border_subtle="#23304A",
    border_strong="#34466B",
    text_primary="#F1F5F9",
    text_secondary="#94A3B8",
    text_muted="#64748B",
    accent="#3B82F6",
    accent_hover="#2563EB",
    accent_subtle="#172554",
    positive="#10B981",
    positive_bg="#064E3B",
    negative="#EF4444",
    negative_bg="#7F1D1D",
    warning="#F59E0B",
    warning_bg="#78350F",
)

LIGHT_THEME = ThemeTokens(
    mode="light",
    bg_canvas="#F8FAFC",
    bg_sidebar="#F1F5F9",
    bg_surface="#FFFFFF",
    bg_elevated="#F1F5F9",
    bg_hover="#E2E8F0",
    border_subtle="#CBD5E1",
    border_strong="#94A3B8",
    text_primary="#0F172A",
    text_secondary="#475569",
    text_muted="#64748B",
    accent="#2563EB",
    accent_hover="#1D4ED8",
    accent_subtle="#DBEAFE",
    positive="#059669",
    positive_bg="#D1FAE5",
    negative="#DC2626",
    negative_bg="#FEE2E2",
    warning="#D97706",
    warning_bg="#FEF3C7",
)


def get_theme_tokens(mode: ThemeMode = "dark") -> ThemeTokens:
    """Return an immutable token set for a supported visual mode."""

    return DARK_THEME if mode == "dark" else LIGHT_THEME


def get_monospace_font(point_size: int = 10, bold: bool = False) -> QtGui.QFont:
    """Create a tabular-numeric font with safe platform fallbacks."""

    font = QtGui.QFont("JetBrains Mono")
    font.setStyleHint(QtGui.QFont.StyleHint.Monospace)
    if not QtGui.QFontInfo(font).exactMatch():
        font = QtGui.QFont("Consolas")
        font.setStyleHint(QtGui.QFont.StyleHint.Monospace)
    font.setPointSize(point_size)
    font.setBold(bold)
    return font


def build_stylesheet(tokens: ThemeTokens) -> str:
    """Build a Qt Style Sheet using properties supported by Qt's QSS parser."""

    t = tokens
    return f"""
    QMainWindow, QDialog {{
        background-color: {t.bg_canvas};
        color: {t.text_primary};
    }}

    QWidget {{
        color: {t.text_primary};
        font-family: "Segoe UI", "Inter", sans-serif;
        font-size: 13px;
    }}

    QLabel {{
        background-color: transparent;
    }}

    QLabel#pageTitle, QLabel#dividendPageTitle, QLabel#portfolioTitle {{
        color: {t.text_primary};
        font-size: 25px;
        font-weight: 700;
    }}

    QFrame#SidebarRail {{
        background-color: {t.bg_sidebar};
        border-right: 1px solid {t.border_subtle};
    }}

    QPushButton[navItem="true"] {{
        background-color: transparent;
        color: {t.text_secondary};
        border: none;
        border-left: 3px solid transparent;
        border-radius: 6px;
        padding: 10px 14px;
        text-align: left;
        font-weight: 500;
    }}

    QPushButton[navItem="true"]:hover {{
        background-color: {t.bg_hover};
        color: {t.text_primary};
    }}

    QPushButton[navItem="true"][active="true"] {{
        background-color: {t.accent_subtle};
        color: {t.text_primary};
        border-left: 3px solid {t.accent};
        font-weight: 600;
    }}

    QListWidget#mainNavigation {{
        background-color: {t.bg_sidebar};
        color: {t.text_secondary};
        border: none;
        padding: 10px 8px;
    }}

    QListWidget#mainNavigation::item {{
        min-height: 34px;
        padding: 5px 10px;
        border-radius: 6px;
        margin: 2px 0;
    }}

    QListWidget#mainNavigation::item:hover {{
        background-color: {t.bg_hover};
        color: {t.text_primary};
    }}

    QListWidget#mainNavigation::item:selected {{
        background-color: {t.accent_subtle};
        color: {t.text_primary};
        border-left: 3px solid {t.accent};
    }}

    QFrame[card="true"] {{
        background-color: {t.bg_surface};
        border: 1px solid {t.border_subtle};
        border-radius: 10px;
    }}

    QGroupBox {{
        background-color: {t.bg_surface};
        border: 1px solid {t.border_subtle};
        border-radius: 8px;
        margin-top: 14px;
        padding: 14px 12px 12px 12px;
        font-weight: 600;
        color: {t.text_secondary};
    }}

    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 12px;
        padding: 0 6px;
        background-color: {t.bg_canvas};
        color: {t.text_primary};
    }}

    QPushButton {{
        background-color: {t.bg_elevated};
        color: {t.text_primary};
        border: 1px solid {t.border_strong};
        border-radius: 6px;
        padding: 7px 14px;
        font-weight: 500;
    }}

    QPushButton:hover {{
        background-color: {t.bg_hover};
        border-color: {t.accent};
    }}

    QPushButton:pressed {{
        background-color: {t.accent_subtle};
    }}

    QPushButton:disabled {{
        color: {t.text_muted};
        background-color: {t.bg_surface};
        border-color: {t.border_subtle};
    }}

    QPushButton[variant="primary"] {{
        background-color: {t.accent};
        color: #FFFFFF;
        border: 1px solid {t.accent};
        font-weight: 600;
    }}

    QPushButton[variant="primary"]:hover {{
        background-color: {t.accent_hover};
        border-color: {t.accent_hover};
    }}

    QPushButton[variant="danger"] {{
        background-color: {t.negative_bg};
        color: {t.negative};
        border: 1px solid {t.negative};
    }}

    QLineEdit, QComboBox, QDateEdit, QSpinBox, QDoubleSpinBox,
    QPlainTextEdit, QTextEdit {{
        background-color: {t.bg_elevated};
        color: {t.text_primary};
        border: 1px solid {t.border_subtle};
        border-radius: 6px;
        padding: 6px 10px;
        selection-background-color: {t.accent};
    }}

    QLineEdit:focus, QComboBox:focus, QDateEdit:focus,
    QSpinBox:focus, QDoubleSpinBox:focus,
    QPlainTextEdit:focus, QTextEdit:focus {{
        border: 1px solid {t.accent};
    }}

    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}

    QComboBox QAbstractItemView {{
        background-color: {t.bg_elevated};
        color: {t.text_primary};
        selection-background-color: {t.accent_subtle};
        border: 1px solid {t.border_strong};
    }}

    QTabWidget::pane {{
        border: 1px solid {t.border_subtle};
        border-radius: 8px;
        background-color: {t.bg_surface};
        top: -1px;
    }}

    QTabBar::tab {{
        background-color: transparent;
        color: {t.text_secondary};
        padding: 8px 16px;
        border-bottom: 2px solid transparent;
        font-weight: 500;
    }}

    QTabBar::tab:hover {{
        color: {t.text_primary};
    }}

    QTabBar::tab:selected {{
        color: {t.accent};
        border-bottom: 2px solid {t.accent};
        font-weight: 600;
    }}

    QTableView, QTableWidget {{
        background-color: {t.bg_surface};
        alternate-background-color: {t.bg_elevated};
        color: {t.text_primary};
        gridline-color: {t.border_subtle};
        border: 1px solid {t.border_subtle};
        border-radius: 8px;
        selection-background-color: {t.accent_subtle};
        selection-color: {t.text_primary};
    }}

    QTableView::item, QTableWidget::item {{
        padding: 5px 7px;
    }}

    QHeaderView::section {{
        background-color: {t.bg_sidebar};
        color: {t.text_secondary};
        padding: 8px 10px;
        border: none;
        border-bottom: 1px solid {t.border_strong};
        border-right: 1px solid {t.border_subtle};
        font-weight: 600;
        font-size: 12px;
    }}

    QTableCornerButton::section {{
        background-color: {t.bg_sidebar};
        border: none;
        border-bottom: 1px solid {t.border_strong};
    }}

    QLabel[kpiTitle="true"] {{
        color: {t.text_secondary};
        font-size: 12px;
        font-weight: 600;
    }}

    QLabel[kpiValue="true"] {{
        color: {t.text_primary};
        font-size: 19px;
        font-weight: 700;
    }}

    QLabel[kpiProvenance="true"] {{
        color: {t.text_muted};
        font-size: 10px;
    }}

    QLabel[pill="positive"] {{
        background-color: {t.positive_bg};
        color: {t.positive};
        border-radius: 10px;
        padding: 2px 8px;
        font-weight: 600;
        font-size: 11px;
    }}

    QLabel[pill="negative"] {{
        background-color: {t.negative_bg};
        color: {t.negative};
        border-radius: 10px;
        padding: 2px 8px;
        font-weight: 600;
        font-size: 11px;
    }}

    QLabel[pill="warning"] {{
        background-color: {t.warning_bg};
        color: {t.warning};
        border-radius: 10px;
        padding: 2px 8px;
        font-weight: 600;
        font-size: 11px;
    }}

    QLabel[pill="neutral"] {{
        background-color: {t.bg_elevated};
        color: {t.text_secondary};
        border-radius: 10px;
        padding: 2px 8px;
        font-weight: 600;
        font-size: 11px;
    }}

    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 0px;
    }}

    QScrollBar::handle:vertical {{
        background: {t.border_strong};
        border-radius: 4px;
        min-height: 24px;
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}

    QScrollBar:horizontal {{
        background: transparent;
        height: 8px;
        margin: 0px;
    }}

    QScrollBar::handle:horizontal {{
        background: {t.border_strong};
        border-radius: 4px;
        min-width: 24px;
    }}

    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}
    """


def apply_app_theme(
    app: QtWidgets.QApplication,
    mode: ThemeMode = "dark",
) -> ThemeTokens:
    """Apply a complete palette and QSS theme to the current application."""

    tokens = get_theme_tokens(mode)
    app.setStyle("Fusion")
    app.setStyleSheet(build_stylesheet(tokens))
    return tokens
