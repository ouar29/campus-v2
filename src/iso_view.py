"""Vue d'ensemble isométrique du campus : bâtiments empilés par étages.

Simplification assumée : chaque étage est affiché avec une empreinte
normalisée (même taille schématique) plutôt qu'à l'échelle réelle, et
l'ordre des étages dans la liste de chaque bâtiment est supposé aller
du rez-de-chaussée (index 0) vers le haut. L'objectif est une vue
d'organisation, pas un plan à l'échelle.
"""
from __future__ import annotations

import math

from model import Campus

ISO_COS30 = math.cos(math.radians(30))
ISO_SIN30 = math.sin(math.radians(30))

FOOTPRINT_SIZE = 10.0     # taille schématique (unités monde) de l'empreinte normalisée d'un étage
FLOOR_HEIGHT = 6.0        # espacement vertical entre étages
SLAB_THICKNESS = 4.0      # épaisseur visuelle de la "dalle" d'un étage (< FLOOR_HEIGHT = petit espace entre étages)
BUILDING_GAP = 15.0       # espacement horizontal (unités monde) entre bâtiments
OVERVIEW_SCALE = 16       # pixels par unité monde
MARGIN_PX = 60

PALETTE = ["#93c5fd", "#86efac", "#fca5a5", "#fcd34d", "#c4b5fd", "#67e8f9", "#fdba74"]


def _darken(hex_color: str, factor: float = 0.72) -> str:
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    r, g, b = (max(0, int(c * factor)) for c in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


def _normalize_polygon(polygon: list[list[float]]) -> list[tuple[float, float]]:
    """Recentre et met à l'échelle un polygone dans une empreinte canonique."""
    if not polygon:
        return [(-FOOTPRINT_SIZE / 2, -FOOTPRINT_SIZE / 2), (FOOTPRINT_SIZE / 2, -FOOTPRINT_SIZE / 2),
                (FOOTPRINT_SIZE / 2, FOOTPRINT_SIZE / 2), (-FOOTPRINT_SIZE / 2, FOOTPRINT_SIZE / 2)]
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
    w, h = max_x - min_x, max_y - min_y
    scale = FOOTPRINT_SIZE / max(w, h, 1e-6)
    cx, cy = (min_x + max_x) / 2, (min_y + max_y) / 2
    return [((x - cx) * scale, (y - cy) * scale) for x, y in polygon]


def _iso(x: float, y: float, z: float) -> tuple[float, float]:
    sx = (x - y) * ISO_COS30
    sy = (x + y) * ISO_SIN30 - z
    return sx * OVERVIEW_SCALE, sy * OVERVIEW_SCALE


def build_overview_svg(campus: Campus) -> str:
    elements: list[str] = []
    all_x: list[float] = []
    all_y: list[float] = []

    def record(px: float, py: float) -> None:
        all_x.append(px)
        all_y.append(py)

    for b_index, building in enumerate(campus.buildings):
        bx = b_index * BUILDING_GAP
        color = PALETTE[b_index % len(PALETTE)]
        wall_color = _darken(color)

        for f_index, floor in enumerate(building.floors):
            local_pts = _normalize_polygon(floor.polygon)
            world_pts = [(bx + x, y) for x, y in local_pts]
            z_bottom = f_index * FLOOR_HEIGHT
            z_top = z_bottom + SLAB_THICKNESS

            top_proj = [_iso(x, y, z_top) for x, y in world_pts]
            bottom_proj = [_iso(x, y, z_bottom) for x, y in world_pts]
            for px, py in top_proj + bottom_proj:
                record(px, py)

            # Parois latérales (extrusion) pour donner un effet de volume
            n = len(world_pts)
            for i in range(n):
                p1_top, p2_top = top_proj[i], top_proj[(i + 1) % n]
                p1_bot, p2_bot = bottom_proj[i], bottom_proj[(i + 1) % n]
                quad = f"{p1_bot[0]},{p1_bot[1]} {p2_bot[0]},{p2_bot[1]} {p2_top[0]},{p2_top[1]} {p1_top[0]},{p1_top[1]}"
                elements.append(f'<polygon points="{quad}" fill="{wall_color}" stroke="#1f2937" stroke-width="0.5"/>')

            # Face supérieure (dalle de l'étage)
            top_points = " ".join(f"{px},{py}" for px, py in top_proj)
            elements.append(
                f'<polygon points="{top_points}" fill="{color}" stroke="#1f2937" stroke-width="0.8">'
                f'<title>{building.name} — {floor.name} ({len(floor.rooms)} salle(s))</title></polygon>'
            )

            # Étiquette étage (centre approximatif de la face supérieure)
            cx = sum(p[0] for p in top_proj) / n
            cy = sum(p[1] for p in top_proj) / n
            elements.append(
                f'<text x="{cx}" y="{cy}" font-size="11" text-anchor="middle" '
                f'dominant-baseline="middle" fill="#1e293b" font-weight="600">{floor.name}</text>'
            )

        # Étiquette bâtiment, sous la base du rez-de-chaussée
        base_x, base_y = _iso(bx, 0, 0)
        record(base_x, base_y + 30)
        elements.append(
            f'<text x="{base_x}" y="{base_y + 26}" font-size="13" text-anchor="middle" '
            f'fill="#0f172a" font-weight="700">{building.name}</text>'
        )

    if not all_x:
        return '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="120">' \
               '<text x="20" y="60" font-size="14" fill="#64748b">Aucun bâtiment à afficher.</text></svg>'

    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)
    width = (max_x - min_x) + 2 * MARGIN_PX
    height = (max_y - min_y) + 2 * MARGIN_PX
    offset_x = -min_x + MARGIN_PX
    offset_y = -min_y + MARGIN_PX

    body = "".join(elements)
    return (
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
        f'style="width:100%; height:100%; background:#ffffff;">'
        f'<g transform="translate({offset_x},{offset_y})">{body}</g>'
        f"</svg>"
    )
