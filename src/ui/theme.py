from __future__ import annotations

from nicegui import ui

from theme import (
    THEME_ACCENT,
    THEME_DARK,
    THEME_DARK_PAGE,
    THEME_PRIMARY,
    THEME_SECONDARY,
)


def apply_theme() -> ui.dark_mode:
    ui.colors(
        primary=THEME_PRIMARY,
        secondary=THEME_SECONDARY,
        accent=THEME_ACCENT,
        dark=THEME_DARK,
        dark_page=THEME_DARK_PAGE,
    )
    return ui.dark_mode(True)
