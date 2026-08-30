"""Palettes de l'application — source unique de vérité pour les couleurs.

Ce module est volontairement **sans dépendance à NiceGUI** : il est importé
aussi bien par la couche de rendu SVG (`rendering.py`, `iso_view.py`, qui ne
connaissent pas l'UI) que par `ui/theme.py`, qui applique les couleurs de
marque au thème Quasar/NiceGUI.

Deux palettes complètes cohabitent, `DARK` et `LIGHT`, sélectionnées par
`palette_for(dark)`. Les SVG sont générés côté serveur (le plan est même une
image encodée en data URI) : ils ne peuvent donc pas réagir au thème par du
CSS comme le reste de la page. La palette doit être choisie **au moment du
rendu** et redescendue explicitement aux fonctions de dessin, ce qui impose
aussi de redessiner le plan quand l'utilisateur bascule de thème (voir
`CampusApp.set_dark_mode()`).

Toute nouvelle couleur s'ajoute comme un champ de `Palette`, avec sa valeur
dans les deux palettes, plutôt qu'écrite en dur dans un f-string SVG.
"""
from __future__ import annotations

from dataclasses import dataclass

# --- Couleurs de marque (thème NiceGUI/Quasar) ----------------------------
# Communes aux deux thèmes : Quasar dérive lui-même ses variantes claires et
# sombres à partir de ces teintes.
THEME_PRIMARY = "#6366f1"      # indigo-500
THEME_SECONDARY = "#4f46e5"    # indigo-600
THEME_ACCENT = "#818cf8"       # indigo-400
THEME_DARK = "#312e81"         # indigo-900, surfaces sombres (boutons, cartes)
THEME_DARK_PAGE = "#1e1b4b"    # indigo-950, fond de page en thème sombre


@dataclass(frozen=True)
class Palette:
    """Toutes les couleurs que les rendus SVG interpolent dans leurs chaînes."""

    # Plan 2D (rendering.py)
    CANVAS_BG: str             # fond du canevas du plan
    CANVAS_STROKE: str         # bordure du canevas
    FLOOR_FILL: str            # remplissage du contour d'étage
    FLOOR_STROKE: str          # trait du contour d'étage
    GRID_LINE_COLOR: str

    TEXT_PRIMARY: str          # libellés principaux
    TEXT_SECONDARY: str        # libellés secondaires (capacités)
    TEXT_MUTED: str            # messages d'état vides
    TEXT_SHADOW_COLOR: str     # halo derrière les libellés HTML du plan

    OUTLINE_DARK: str          # liseré autour des formes colorées

    ROOM_FILL: str
    ROOM_STROKE: str
    ROOM_UNAVAILABLE_FILL: str
    ROOM_UNAVAILABLE_STROKE: str

    DRAW_LINE_COLOR: str            # tracé d'un contour en cours de dessin
    DRAW_FIRST_VERTEX_COLOR: str    # premier sommet, pour fermer le polygone
    VERTEX_FILL: str                # sommets déplaçables
    VERTEX_STROKE: str

    PLAN_PALETTE: tuple[str, ...]   # bâtiments du plan 2D (indexés par hash d'id)

    # Vue isométrique (iso_view.py)
    ISO_BG: str
    ISO_GRID_COLOR: str
    ISO_GRID_AXIS_COLOR: str
    ISO_LABEL_HALO: str             # contour des libellés, pour le contraste
    ISO_PANEL_BG: str               # fond des boutons zoom/rotation
    ISO_PANEL_BORDER: str
    ISO_PANEL_TEXT: str
    ISO_PALETTE: tuple[str, ...]    # teintes des volumes 3D


DARK = Palette(
    CANVAS_BG="#211d55",
    CANVAS_STROKE="#4338ca",       # indigo-700
    FLOOR_FILL="#3730a3",          # indigo-800
    FLOOR_STROKE="#a5b4fc",        # indigo-300
    GRID_LINE_COLOR="#4338ca",
    TEXT_PRIMARY="#eef2ff",        # indigo-50
    TEXT_SECONDARY="#c7d2fe",      # indigo-200
    TEXT_MUTED="#64748b",          # slate-500
    TEXT_SHADOW_COLOR="#0f0e2a",
    OUTLINE_DARK="#1f2937",        # gray-800
    ROOM_FILL="#93c5fd",
    ROOM_STROKE="#1d4ed8",
    ROOM_UNAVAILABLE_FILL="#6b7280",
    ROOM_UNAVAILABLE_STROKE="#ef4444",
    DRAW_LINE_COLOR="#1d4ed8",
    DRAW_FIRST_VERTEX_COLOR="#dc2626",
    VERTEX_FILL="#f59e0b",
    VERTEX_STROKE="#78350f",
    PLAN_PALETTE=(
        "#60a5fa",
        "#f59e0b",
        "#34d399",
        "#f472b6",
        "#a78bfa",
        "#f87171",
        "#2dd4bf",
    ),
    ISO_BG=THEME_DARK_PAGE,
    ISO_GRID_COLOR="#4338ca",
    ISO_GRID_AXIS_COLOR="#a5b4fc",
    ISO_LABEL_HALO=THEME_DARK_PAGE,
    ISO_PANEL_BG=THEME_DARK,
    ISO_PANEL_BORDER=THEME_PRIMARY,
    ISO_PANEL_TEXT="#eef2ff",
    # Teintes pastel, plus lisibles sur les volumes 3D que la palette du plan 2D
    ISO_PALETTE=(
        "#93c5fd",
        "#86efac",
        "#fca5a5",
        "#fcd34d",
        "#c4b5fd",
        "#67e8f9",
        "#fdba74",
    ),
)

# Thème clair : mêmes rôles, valeurs pensées pour un fond papier. Les teintes
# de remplissage sont plus saturées qu'en sombre (un pastel disparaîtrait sur
# du blanc) et les textes passent en gris ardoise foncé — du texte clair sur
# fond clair était exactement le défaut que ce thème corrige.
LIGHT = Palette(
    CANVAS_BG="#f8fafc",           # slate-50
    CANVAS_STROKE="#cbd5e1",       # slate-300
    FLOOR_FILL="#e0e7ff",          # indigo-100
    FLOOR_STROKE="#4f46e5",        # indigo-600
    GRID_LINE_COLOR="#e2e8f0",     # slate-200
    TEXT_PRIMARY="#1e293b",        # slate-800
    TEXT_SECONDARY="#475569",      # slate-600
    TEXT_MUTED="#64748b",          # slate-500
    TEXT_SHADOW_COLOR="#ffffff",
    OUTLINE_DARK="#334155",        # slate-700
    ROOM_FILL="#60a5fa",           # blue-400 : un bleu pâle disparaîtrait
    ROOM_STROKE="#1d4ed8",         # sur le remplissage clair du contour d'étage
    ROOM_UNAVAILABLE_FILL="#e2e8f0",
    ROOM_UNAVAILABLE_STROKE="#dc2626",
    DRAW_LINE_COLOR="#1d4ed8",
    DRAW_FIRST_VERTEX_COLOR="#dc2626",
    VERTEX_FILL="#f59e0b",
    VERTEX_STROKE="#78350f",
    PLAN_PALETTE=(
        "#3b82f6",
        "#d97706",
        "#059669",
        "#db2777",
        "#7c3aed",
        "#dc2626",
        "#0d9488",
    ),
    ISO_BG="#f1f5f9",              # slate-100
    ISO_GRID_COLOR="#cbd5e1",
    ISO_GRID_AXIS_COLOR="#94a3b8", # slate-400
    ISO_LABEL_HALO="#ffffff",
    ISO_PANEL_BG="#ffffff",
    ISO_PANEL_BORDER="#c7d2fe",
    ISO_PANEL_TEXT="#1e293b",
    ISO_PALETTE=(
        "#60a5fa",
        "#4ade80",
        "#f87171",
        "#fbbf24",
        "#a78bfa",
        "#22d3ee",
        "#fb923c",
    ),
)


def palette_for(dark: bool | None) -> Palette:
    """Palette active. `None` (thème « système » de NiceGUI) est traité comme
    sombre, qui reste le thème par défaut de l'application."""
    return DARK if dark is None or dark else LIGHT
