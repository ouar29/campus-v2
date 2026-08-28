"""Palette de l'application — source unique de vérité pour les couleurs.

Ce module est volontairement **sans dépendance à NiceGUI** : il est importé
aussi bien par la couche de rendu SVG (`rendering.py`, `iso_view.py`, qui ne
connaissent pas l'UI) que par `ui/theme.py`, qui applique ces couleurs au
thème Quasar/NiceGUI.

Toute nouvelle couleur doit être ajoutée ici plutôt qu'écrite en dur dans un
f-string SVG, pour qu'un changement de thème reste un changement local.
"""
from __future__ import annotations

# --- Thème NiceGUI/Quasar -------------------------------------------------
THEME_PRIMARY = "#6366f1"      # indigo-500
THEME_SECONDARY = "#4f46e5"    # indigo-600
THEME_ACCENT = "#818cf8"       # indigo-400
THEME_DARK = "#312e81"         # indigo-900, surfaces sombres (boutons, cartes)
THEME_DARK_PAGE = "#1e1b4b"    # indigo-950, fond de page et des vues SVG

# --- Plan 2D (rendering.py) ----------------------------------------------
CANVAS_BG = "#211d55"          # fond du canevas du plan
CANVAS_STROKE = "#4338ca"      # indigo-700, bordure du canevas
FLOOR_FILL = "#3730a3"         # indigo-800, remplissage du contour d'étage
FLOOR_STROKE = "#a5b4fc"       # indigo-300, contour d'étage
GRID_LINE_COLOR = CANVAS_STROKE

TEXT_PRIMARY = "#eef2ff"       # indigo-50, libellés principaux
TEXT_SECONDARY = "#c7d2fe"     # indigo-200, libellés secondaires (capacités)
TEXT_MUTED = "#64748b"         # slate-500, messages d'état vides

OUTLINE_DARK = "#1f2937"       # gray-800, liseré autour des formes colorées

# Salles : disponible / indisponible
ROOM_FILL = "#93c5fd"
ROOM_STROKE = "#1d4ed8"
ROOM_UNAVAILABLE_FILL = "#6b7280"
ROOM_UNAVAILABLE_STROKE = "#ef4444"

# Tracé d'un contour d'étage en cours de dessin / d'édition
DRAW_LINE_COLOR = ROOM_STROKE
DRAW_FIRST_VERTEX_COLOR = "#dc2626"   # premier sommet, pour fermer le polygone
VERTEX_FILL = "#f59e0b"               # sommets déplaçables
VERTEX_STROKE = "#78350f"
TEXT_SHADOW_COLOR = "#0f0e2a"         # halo derrière les libellés HTML du plan

# Couleurs de bâtiment sur le plan 2D (indexées par hash de l'id)
PLAN_PALETTE = [
    "#60a5fa",
    "#f59e0b",
    "#34d399",
    "#f472b6",
    "#a78bfa",
    "#f87171",
    "#2dd4bf",
]

# --- Vue isométrique (iso_view.py) ---------------------------------------
ISO_BG = THEME_DARK_PAGE
ISO_GRID_COLOR = CANVAS_STROKE
ISO_GRID_AXIS_COLOR = FLOOR_STROKE
ISO_LABEL_HALO = THEME_DARK_PAGE   # contour des libellés, pour le contraste

# Teintes pastel, plus lisibles sur les volumes 3D que la palette du plan 2D
ISO_PALETTE = [
    "#93c5fd",
    "#86efac",
    "#fca5a5",
    "#fcd34d",
    "#c4b5fd",
    "#67e8f9",
    "#fdba74",
]
