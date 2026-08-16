from __future__ import annotations

from nicegui import ui

THEME_PRIMARY = "#6366f1"
THEME_SECONDARY = "#4f46e5"
THEME_ACCENT = "#818cf8"
THEME_DARK = "#312e81"
THEME_DARK_PAGE = "#1e1b4b"

CANVAS_BG = "#211d55"
CANVAS_STROKE = "#4338ca"
FLOOR_FILL = "#3730a3"
FLOOR_STROKE = "#a5b4fc"
GRID_LINE_COLOR = "#4338ca"
TEXT_PRIMARY = "#eef2ff"
TEXT_SECONDARY = "#c7d2fe"


def apply_theme() -> ui.dark_mode:
    ui.colors(
        primary=THEME_PRIMARY,
        secondary=THEME_SECONDARY,
        accent=THEME_ACCENT,
        dark=THEME_DARK,
        dark_page=THEME_DARK_PAGE,
    )
    return ui.dark_mode(True)
