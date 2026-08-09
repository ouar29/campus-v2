"""Vue d'ensemble isométrique du campus : bâtiments empilés par étages.

Simplification assumée : chaque étage est affiché avec une empreinte
normalisée (même taille schématique) plutôt qu'à l'échelle réelle, et
l'ordre des étages dans la liste de chaque bâtiment est supposé aller
du rez-de-chaussée (index 0) vers le haut. L'objectif est une vue
d'organisation, pas un plan à l'échelle.
"""
from __future__ import annotations

import math
import uuid

from model import Campus

ISO_COS30 = math.cos(math.radians(30))
ISO_SIN30 = math.sin(math.radians(30))

FOOTPRINT_SIZE = 10.0     # taille schématique (unités monde) de l'empreinte normalisée d'un étage
FLOOR_HEIGHT = 6.0        # espacement vertical entre étages
SLAB_THICKNESS = 1.2      # épaisseur visuelle de la "dalle" d'un étage (fine, pour bien voir les étages séparés)
TOP_FACE_OPACITY = 0.72   # transparence de la face supérieure (couleur de l'étage)
WALL_OPACITY = 0.85       # transparence des parois latérales
OVERVIEW_SCALE = 16       # pixels par unité monde
MARGIN_PX = 60
GRID_SPACING = 10.0       # espacement (unités monde) de la grille au sol
GRID_CANVAS_PADDING = 500 # marge supplémentaire (px) pour que la grille déborde largement des bâtiments
GRID_COLOR = "#94a3b8"
GRID_AXIS_COLOR = "#475569"

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


def _unproject_ground(sx: float, sy: float) -> tuple[float, float]:
    """Inverse de _iso(x, y, 0) : retrouve les coordonnées monde (x, y) au sol
    à partir d'un point écran. Sert à déterminer quelle portion de la grille
    au sol doit être dessinée pour couvrir toute la zone visible du canevas.
    """
    a = sx / (ISO_COS30 * OVERVIEW_SCALE)
    b = sy / (ISO_SIN30 * OVERVIEW_SCALE)
    return (a + b) / 2, (b - a) / 2


def _ground_grid_svg(screen_x_range: tuple[float, float], screen_y_range: tuple[float, float]) -> str:
    """Grille isométrique au niveau du sol (z=0), couvrant toute la zone
    écran donnée (dans le même repère pré-décalage que les bâtiments)."""
    corners = [
        (screen_x_range[0], screen_y_range[0]),
        (screen_x_range[1], screen_y_range[0]),
        (screen_x_range[0], screen_y_range[1]),
        (screen_x_range[1], screen_y_range[1]),
    ]
    world_corners = [_unproject_ground(sx, sy) for sx, sy in corners]
    xs = [c[0] for c in world_corners]
    ys = [c[1] for c in world_corners]

    x0 = math.floor(min(xs) / GRID_SPACING) * GRID_SPACING - GRID_SPACING
    x1 = math.ceil(max(xs) / GRID_SPACING) * GRID_SPACING + GRID_SPACING
    y0 = math.floor(min(ys) / GRID_SPACING) * GRID_SPACING - GRID_SPACING
    y1 = math.ceil(max(ys) / GRID_SPACING) * GRID_SPACING + GRID_SPACING

    lines = []
    x = x0
    while x <= x1:
        p1, p2 = _iso(x, y0, 0), _iso(x, y1, 0)
        is_axis = abs(x) < 1e-6
        color, width, opacity = (GRID_AXIS_COLOR, 1.4, 0.7) if is_axis else (GRID_COLOR, 0.6, 0.35)
        lines.append(f'<line x1="{p1[0]}" y1="{p1[1]}" x2="{p2[0]}" y2="{p2[1]}" stroke="{color}" stroke-width="{width}" opacity="{opacity}"/>')
        x += GRID_SPACING
    y = y0
    while y <= y1:
        p1, p2 = _iso(x0, y, 0), _iso(x1, y, 0)
        is_axis = abs(y) < 1e-6
        color, width, opacity = (GRID_AXIS_COLOR, 1.4, 0.7) if is_axis else (GRID_COLOR, 0.6, 0.35)
        lines.append(f'<line x1="{p1[0]}" y1="{p1[1]}" x2="{p2[0]}" y2="{p2[1]}" stroke="{color}" stroke-width="{width}" opacity="{opacity}"/>')
        y += GRID_SPACING

    return "".join(lines)


def _build_overview(campus: Campus) -> tuple[str, float, float]:
    """Construit le SVG complet. Retourne (svg, focus_width, focus_height) où
    focus_width/height est la taille du contenu utile (bâtiments + marge),
    à distinguer de la taille totale du canevas (qui inclut la grille étendue) —
    c'est cette taille "utile" qui doit servir à cadrer la vue initiale.
    """
    elements: list[str] = []
    all_x: list[float] = []
    all_y: list[float] = []

    def record(px: float, py: float) -> None:
        all_x.append(px)
        all_y.append(py)

    for building in campus.buildings:
        bx, by = building.position
        color = PALETTE[hash(building.id) % len(PALETTE)]
        wall_color = _darken(color)

        for floor in building.floors:
            local_pts = _normalize_polygon(floor.polygon)
            world_pts = [(bx + x, by + y) for x, y in local_pts]
            z_bottom = floor.level * FLOOR_HEIGHT
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
                elements.append(
                    f'<polygon points="{quad}" fill="{wall_color}" fill-opacity="{WALL_OPACITY}" '
                    f'stroke="#1f2937" stroke-width="0.5"/>'
                )

            # Face supérieure (dalle de l'étage)
            level_tag = " — sous-sol" if floor.level < 0 else ""
            top_points = " ".join(f"{px},{py}" for px, py in top_proj)
            elements.append(
                f'<polygon points="{top_points}" fill="{color}" fill-opacity="{TOP_FACE_OPACITY}" '
                f'stroke="#1f2937" stroke-width="0.8">'
                f'<title>{building.name} — {floor.name} ({len(floor.rooms)} salle(s)){level_tag}</title></polygon>'
            )

            # Étiquette étage (centre approximatif de la face supérieure)
            cx = sum(p[0] for p in top_proj) / n
            cy = sum(p[1] for p in top_proj) / n
            elements.append(
                f'<text x="{cx}" y="{cy}" font-size="11" text-anchor="middle" '
                f'dominant-baseline="middle" fill="#1e293b" font-weight="600">{floor.name}</text>'
            )

        # Étiquette bâtiment, sous la base du rez-de-chaussée
        base_x, base_y = _iso(bx, by, 0)
        record(base_x, base_y + 30)
        elements.append(
            f'<text x="{base_x}" y="{base_y + 26}" font-size="13" text-anchor="middle" '
            f'fill="#0f172a" font-weight="700">{building.name}</text>'
        )

    if not all_x:
        empty_svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="120">'
            '<text x="20" y="60" font-size="14" fill="#64748b">Aucun bâtiment à afficher.</text></svg>'
        )
        return empty_svg, 400.0, 120.0

    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)
    focus_width = (max_x - min_x) + 2 * MARGIN_PX
    focus_height = (max_y - min_y) + 2 * MARGIN_PX
    width = focus_width + 2 * GRID_CANVAS_PADDING
    height = focus_height + 2 * GRID_CANVAS_PADDING
    offset_x = -min_x + MARGIN_PX + GRID_CANVAS_PADDING
    offset_y = -min_y + MARGIN_PX + GRID_CANVAS_PADDING

    # Grille au sol (niveau 0), en repère pré-décalage (même repère que les
    # bâtiments avant application du translate) pour couvrir tout le canevas.
    grid = _ground_grid_svg((-offset_x, width - offset_x), (-offset_y, height - offset_y))

    body = grid + "".join(elements)
    svg = (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
        f'xmlns="http://www.w3.org/2000/svg" style="display:block; background:#f8fafc;">'
        f'<g transform="translate({offset_x},{offset_y})">{body}</g>'
        f"</svg>"
    )
    return svg, focus_width, focus_height


def build_overview_svg(campus: Campus) -> str:
    svg, _, _ = _build_overview(campus)
    return svg


def build_overview_parts(campus: Campus) -> tuple[str, str]:
    """Retourne (html, js) pour la vue d'ensemble isométrique avec navigation.

    Le JS est retourné séparément et doit être exécuté via ui.run_javascript()
    APRÈS que le html ait été inséré (ui.html) : un <script> inséré via
    innerHTML n'est PAS exécuté par le navigateur, donc on ne peut pas se
    contenter de l'embarquer dans le HTML.
    """
    svg_content, focus_w, focus_h = _build_overview(campus)
    uid = uuid.uuid4().hex

    import re

    match = re.search(r'width="([\d.]+)" height="([\d.]+)"', svg_content)
    full_w, full_h = (match.group(1), match.group(2)) if match else (str(focus_w), str(focus_h))

    html = f"""
    <div id="iso-wrap-{uid}" style="width:100%; height:100%; min-height:70vh; overflow:hidden;
         position:relative; background:#ffffff; cursor:grab; border-radius:8px;">
      <div style="position:absolute; top:8px; right:8px; z-index:10; display:flex; flex-direction:column; gap:4px;">
        <button onclick="window.isoZoom_{uid} && window.isoZoom_{uid}(1.25)"
                style="width:34px;height:34px;border-radius:6px;border:1px solid #cbd5e1;background:white;cursor:pointer;font-size:18px;">+</button>
        <button onclick="window.isoZoom_{uid} && window.isoZoom_{uid}(0.8)"
                style="width:34px;height:34px;border-radius:6px;border:1px solid #cbd5e1;background:white;cursor:pointer;font-size:18px;">&minus;</button>
        <button onclick="window.isoReset_{uid} && window.isoReset_{uid}()"
                style="width:34px;height:34px;border-radius:6px;border:1px solid #cbd5e1;background:white;cursor:pointer;font-size:14px;">&#8635;</button>
      </div>
      <div id="iso-inner-{uid}" style="position:absolute; top:0; left:0; transform-origin: 0 0;">
        {svg_content}
      </div>
    </div>
    """

    js = f"""
    (function() {{
        const wrap = document.getElementById("iso-wrap-{uid}");
        const inner = document.getElementById("iso-inner-{uid}");
        if (!wrap || !inner) {{ return; }}
        const svgW = {full_w};
        const svgH = {full_h};
        const focusW = {focus_w};
        const focusH = {focus_h};

        let scale = 1, tx = 0, ty = 0;
        let dragging = false, startX = 0, startY = 0, startTx = 0, startTy = 0;

        function applyTransform() {{
            inner.style.transform = "translate(" + tx + "px, " + ty + "px) scale(" + scale + ")";
        }}

        function fitToView() {{
            const rect = wrap.getBoundingClientRect();
            const fit = Math.min(rect.width / focusW, rect.height / focusH) * 0.9;
            scale = Math.max(0.05, fit || 1);
            // Le contenu utile (bâtiments) est centré dans le grand canevas (grille) :
            // on centre donc le canevas complet, à l'échelle calculée sur le contenu utile.
            tx = rect.width / 2 - (svgW / 2) * scale;
            ty = rect.height / 2 - (svgH / 2) * scale;
            applyTransform();
        }}

        window["isoZoom_{uid}"] = function(factor) {{
            if (!wrap.isConnected) return;
            const rect = wrap.getBoundingClientRect();
            const cx = rect.width / 2, cy = rect.height / 2;
            const newScale = Math.min(5, Math.max(0.1, scale * factor));
            tx = cx - (cx - tx) * (newScale / scale);
            ty = cy - (cy - ty) * (newScale / scale);
            scale = newScale;
            applyTransform();
        }};
        window["isoReset_{uid}"] = fitToView;

        wrap.addEventListener("mousedown", function(e) {{
            dragging = true;
            startX = e.clientX; startY = e.clientY; startTx = tx; startTy = ty;
            wrap.style.cursor = "grabbing";
        }});
        window.addEventListener("mousemove", function(e) {{
            if (!dragging || !wrap.isConnected) return;
            tx = startTx + (e.clientX - startX);
            ty = startTy + (e.clientY - startY);
            applyTransform();
        }});
        window.addEventListener("mouseup", function() {{
            if (!dragging) return;
            dragging = false;
            if (wrap.isConnected) wrap.style.cursor = "grab";
        }});
        wrap.addEventListener("wheel", function(e) {{
            e.preventDefault();
            const rect = wrap.getBoundingClientRect();
            const mx = e.clientX - rect.left, my = e.clientY - rect.top;
            const factor = e.deltaY < 0 ? 1.12 : 0.89;
            const newScale = Math.min(5, Math.max(0.1, scale * factor));
            tx = mx - (mx - tx) * (newScale / scale);
            ty = my - (my - ty) * (newScale / scale);
            scale = newScale;
            applyTransform();
        }}, {{ passive: false }});

        fitToView();
    }})();
    """

    return html, js
