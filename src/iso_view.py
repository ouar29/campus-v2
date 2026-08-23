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

FOOTPRINT_SIZE = 18.0     # taille schématique (unités monde) de l'empreinte normalisée d'un étage (agrandie)
FLOOR_HEIGHT = 11.0       # espacement vertical entre étages (agrandi, effet plus imposant)
SLAB_THICKNESS = 2.2      # épaisseur visuelle de la "dalle" d'un étage
TOP_FACE_OPACITY = 0.72   # transparence de la face supérieure (couleur de l'étage)
WALL_OPACITY = 0.85       # transparence des parois latérales
OVERVIEW_SCALE = 16       # pixels par unité monde
MARGIN_PX = 50            # marge serrée autour des bâtiments pour le cadrage initial (focus)
GRID_SPACING = 10.0       # espacement (unités monde) de la grille au sol
GRID_CANVAS_PADDING = 500 # marge supplémentaire (px) pour que la grille déborde largement des bâtiments (pan)
GRID_COLOR = "#4338ca"     # indigo-700, grille discrète sur fond sombre
GRID_AXIS_COLOR = "#a5b4fc"  # indigo-300, axes principaux (plus visibles)

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


def _rotate_xy(x: float, y: float, angle_deg: float) -> tuple[float, float]:
    """Rotation 2D (x, y) autour de l'origine, d'un angle en degrés.

    Appliquer cette rotation à toutes les coordonnées monde avant projection
    isométrique équivaut à faire tourner la caméra autour de l'axe vertical
    (z) : c'est ce qui permet les boutons « tourner à gauche/droite » de la
    vue d'ensemble.
    """
    if not angle_deg:
        return x, y
    a = math.radians(angle_deg)
    ca, sa = math.cos(a), math.sin(a)
    return x * ca - y * sa, x * sa + y * ca


def _iso(x: float, y: float, z: float, angle_deg: float = 0.0) -> tuple[float, float]:
    x, y = _rotate_xy(x, y, angle_deg)
    sx = (x - y) * ISO_COS30
    sy = (x + y) * ISO_SIN30 - z
    return sx * OVERVIEW_SCALE, sy * OVERVIEW_SCALE


def _unproject_ground(sx: float, sy: float, angle_deg: float = 0.0) -> tuple[float, float]:
    """Inverse de _iso(x, y, 0, angle_deg) : retrouve les coordonnées monde (x, y)
    au sol à partir d'un point écran. Sert à déterminer quelle portion de la
    grille au sol doit être dessinée pour couvrir toute la zone visible du
    canevas, quelle que soit la rotation courante.
    """
    a = sx / (ISO_COS30 * OVERVIEW_SCALE)
    b = sy / (ISO_SIN30 * OVERVIEW_SCALE)
    x, y = (a + b) / 2, (b - a) / 2
    return _rotate_xy(x, y, -angle_deg)


def _ground_grid_svg(screen_x_range: tuple[float, float], screen_y_range: tuple[float, float], angle_deg: float = 0.0) -> str:
    """Grille isométrique au niveau du sol (z=0), couvrant toute la zone
    écran donnée (dans le même repère pré-décalage que les bâtiments)."""
    corners = [
        (screen_x_range[0], screen_y_range[0]),
        (screen_x_range[1], screen_y_range[0]),
        (screen_x_range[0], screen_y_range[1]),
        (screen_x_range[1], screen_y_range[1]),
    ]
    world_corners = [_unproject_ground(sx, sy, angle_deg) for sx, sy in corners]
    xs = [c[0] for c in world_corners]
    ys = [c[1] for c in world_corners]

    x0 = math.floor(min(xs) / GRID_SPACING) * GRID_SPACING - GRID_SPACING
    x1 = math.ceil(max(xs) / GRID_SPACING) * GRID_SPACING + GRID_SPACING
    y0 = math.floor(min(ys) / GRID_SPACING) * GRID_SPACING - GRID_SPACING
    y1 = math.ceil(max(ys) / GRID_SPACING) * GRID_SPACING + GRID_SPACING

    lines = []
    x = x0
    while x <= x1:
        p1, p2 = _iso(x, y0, 0, angle_deg), _iso(x, y1, 0, angle_deg)
        is_axis = abs(x) < 1e-6
        color, width, opacity = (GRID_AXIS_COLOR, 1.4, 0.7) if is_axis else (GRID_COLOR, 0.6, 0.35)
        lines.append(f'<line x1="{p1[0]}" y1="{p1[1]}" x2="{p2[0]}" y2="{p2[1]}" stroke="{color}" stroke-width="{width}" opacity="{opacity}"/>')
        x += GRID_SPACING
    y = y0
    while y <= y1:
        p1, p2 = _iso(x0, y, 0, angle_deg), _iso(x1, y, 0, angle_deg)
        is_axis = abs(y) < 1e-6
        color, width, opacity = (GRID_AXIS_COLOR, 1.4, 0.7) if is_axis else (GRID_COLOR, 0.6, 0.35)
        lines.append(f'<line x1="{p1[0]}" y1="{p1[1]}" x2="{p2[0]}" y2="{p2[1]}" stroke="{color}" stroke-width="{width}" opacity="{opacity}"/>')
        y += GRID_SPACING

    return "".join(lines)


POSITION_COMPRESSION_MIN_SLOPE = 0.2  # pente locale minimale garantie, même très loin du centroïde
POSITION_COMPRESSION_SPAN = 40.0      # distance (unités monde) à partir de laquelle la compression devient sensible


def _compress_position(centroid_x: float, centroid_y: float, position: list[float]) -> tuple[float, float]:
    """Compresse la position d'un bâtiment par rapport au centre du campus,
    pour que les grands écarts (campus étalé) n'écrasent pas visuellement les
    autres bâtiments dans cette vue d'ensemble schématique. Utilisé
    UNIQUEMENT pour la mise en page de la vue isométrique — n'affecte ni la
    position réelle stockée, ni le plan du campus (vue du dessus), qui reste
    à l'échelle réelle.

    `MIN_SLOPE*d + (1-MIN_SLOPE)*SPAN*tanh(d/SPAN)` plutôt qu'une loi de
    puissance : la tangente hyperbolique donne une pente locale de 1 à
    l'origine (petits écarts quasi préservés, comme voulu), qui décroît
    ensuite mais ne descend JAMAIS sous `MIN_SLOPE` (la composante linéaire
    du terme). Avec l'ancienne loi de puissance `K*d^p`, la pente locale
    `K*p*d^(p-1)` tendait vers 0 quand `d` augmentait : deux bâtiments
    proches l'un de l'autre mais tous deux loin du centroïde (par ex. à
    cause d'un troisième bâtiment isolé ailleurs sur le campus, qui déplace
    le centroïde) voyaient alors leur écart mutuel quasiment écrasé à zéro
    après compression — d'où des collisions visuelles dans la vue iso alors
    que les bâtiments sont clairement séparés dans la vue plan (à l'échelle
    réelle, non déformée).

    Cette pente plancher réduit fortement le risque de collision mais ne
    l'élimine pas complètement à elle seule (un écart réel modeste entre deux
    bâtiments très éloignés du centroïde peut encore donner un écart affiché
    inférieur à l'empreinte schématique) : voir `_declutter_positions`, qui
    apporte la garantie géométrique finale.
    """
    dx, dy = position[0] - centroid_x, position[1] - centroid_y
    span = POSITION_COMPRESSION_SPAN
    slope = POSITION_COMPRESSION_MIN_SLOPE
    cx = slope * dx + (1 - slope) * span * math.tanh(dx / span)
    cy = slope * dy + (1 - slope) * span * math.tanh(dy / span)
    return cx, cy


MIN_BUILDING_SEPARATION = FOOTPRINT_SIZE * 1.15  # marge de sécurité au-delà de l'empreinte schématique
DECLUTTER_ITERATIONS = 60


def _declutter_positions(positions: dict[str, tuple[float, float]]) -> dict[str, tuple[float, float]]:
    """Écarte itérativement les bâtiments dont la position calculée (après
    compression) serait trop proche d'un autre pour afficher deux empreintes
    schématiques sans chevauchement, en les repoussant le long de l'axe qui
    les relie.

    Filet de sécurité géométrique : garantit l'absence de collision visuelle
    quelle que soit l'imperfection résiduelle de `_compress_position` (dont
    la compression, même avec pente plancher, ne suffit pas toujours à elle
    seule — voir sa docstring), plutôt que de compter uniquement sur un
    compromis mathématique parfait entre « compresser les grands écarts » et
    « ne jamais rapprocher deux bâtiments voisins ».
    """
    ids = list(positions.keys())
    if len(ids) < 2:
        return dict(positions)

    pos = {k: list(v) for k, v in positions.items()}
    for _ in range(DECLUTTER_ITERATIONS):
        moved = False
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a, b = ids[i], ids[j]
                dx = pos[b][0] - pos[a][0]
                dy = pos[b][1] - pos[a][1]
                dist = math.hypot(dx, dy)
                if dist >= MIN_BUILDING_SEPARATION:
                    continue
                moved = True
                if dist < 1e-6:
                    # Positions quasi identiques : direction arbitraire mais
                    # stable (angle d'or, évite les alignements dégénérés
                    # entre plus de deux bâtiments superposés).
                    angle = (i - j) * 2.399963
                    ux, uy = math.cos(angle), math.sin(angle)
                else:
                    ux, uy = dx / dist, dy / dist
                overlap = (MIN_BUILDING_SEPARATION - dist) / 2
                pos[a][0] -= ux * overlap
                pos[a][1] -= uy * overlap
                pos[b][0] += ux * overlap
                pos[b][1] += uy * overlap
        if not moved:
            break
    return {k: (v[0], v[1]) for k, v in pos.items()}


def _build_overview(campus: Campus, angle_deg: float = 0.0) -> tuple[str, float, float]:
    """Construit le SVG complet. Retourne (svg, focus_width, focus_height) où
    focus_width/height est la taille du contenu utile (bâtiments + marge),
    à distinguer de la taille totale du canevas (qui inclut la grille étendue) —
    c'est cette taille "utile" qui doit servir à cadrer la vue initiale.

    `angle_deg` fait tourner la scène autour de l'axe vertical (pas de 45°
    fournis par les boutons de rotation) ; le cadrage (bounding box) est
    recalculé à partir des points déjà tournés, donc la vue reste centrée
    quelle que soit la rotation.
    """
    elements: list[str] = []
    all_x: list[float] = []
    all_y: list[float] = []

    def record(px: float, py: float) -> None:
        all_x.append(px)
        all_y.append(py)

    if campus.buildings:
        centroid_x = sum(b.position[0] for b in campus.buildings) / len(campus.buildings)
        centroid_y = sum(b.position[1] for b in campus.buildings) / len(campus.buildings)
    else:
        centroid_x = centroid_y = 0.0

    raw_positions = {
        building.id: _compress_position(centroid_x, centroid_y, building.position)
        for building in campus.buildings
    }
    building_positions = _declutter_positions(raw_positions)

    for building in campus.buildings:
        bx, by = building_positions[building.id]
        color = PALETTE[hash(building.id) % len(PALETTE)]
        wall_color = _darken(color)

        for floor in building.floors:
            local_pts = _normalize_polygon(floor.polygon)
            world_pts = [(bx + x, by + y) for x, y in local_pts]
            z_bottom = floor.level * FLOOR_HEIGHT
            z_top = z_bottom + SLAB_THICKNESS

            top_proj = [_iso(x, y, z_top, angle_deg) for x, y in world_pts]
            bottom_proj = [_iso(x, y, z_bottom, angle_deg) for x, y in world_pts]
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
                f'<text x="{cx}" y="{cy}" font-size="24" text-anchor="middle" '
                f'dominant-baseline="middle" fill="#eef2ff" font-weight="700" paint-order="stroke" '
                f'stroke="#1e1b4b" stroke-width="4" stroke-linejoin="round">{floor.name}</text>'
            )

        # Étiquette bâtiment, bien visible sous la base du rez-de-chaussée
        # (halo sombre autour du texte pour rester lisible quelle que soit la couleur derrière)
        base_x, base_y = _iso(bx, by, 0, angle_deg)
        record(base_x, base_y + 42)
        elements.append(
            f'<text x="{base_x}" y="{base_y + 34}" font-size="24" text-anchor="middle" '
            f'fill="#eef2ff" font-weight="700" paint-order="stroke" stroke="#1e1b4b" stroke-width="5" '
            f'stroke-linejoin="round">{building.name}</text>'
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
    grid = _ground_grid_svg((-offset_x, width - offset_x), (-offset_y, height - offset_y), angle_deg)

    body = grid + "".join(elements)
    # Le viewBox initial cible directement la zone utile (bâtiments + petite marge),
    # PAS le canevas complet (qui inclut la grande marge de grille pour le pan).
    # C'est ce qui garantit un cadrage correct dès le premier rendu HTML/SVG,
    # sans dépendre d'un calcul JavaScript exécuté après coup (source de bugs
    # de timing avec l'animation d'ouverture du dialogue).
    initial_view_box = f"{GRID_CANVAS_PADDING} {GRID_CANVAS_PADDING} {focus_width} {focus_height}"
    svg = (
        f'<svg width="{width}" height="{height}" viewBox="{initial_view_box}" '
        f'xmlns="http://www.w3.org/2000/svg" style="display:block; width:100%; height:100%; background:#1e1b4b;">'
        f'<g transform="translate({offset_x},{offset_y})">{body}</g>'
        f"</svg>"
    )
    return svg, focus_width, focus_height


def build_overview_svg(campus: Campus, angle_deg: float = 0.0) -> str:
    svg, _, _ = _build_overview(campus, angle_deg)
    return svg


def build_overview_parts(campus: Campus, angle_deg: float = 0.0) -> tuple[str, str]:
    """Retourne (html, js) pour la vue d'ensemble isométrique avec navigation.

    Le cadrage initial (zoom sur les bâtiments) est déjà correct dans le HTML
    seul, via le viewBox calculé en Python (voir _build_overview) — le JS
    n'est nécessaire que pour le pan/zoom INTERACTIF ensuite, ce qui rend le
    premier affichage indépendant de tout timing d'exécution JS (contrairement
    à une approche précédente qui recalculait le cadrage en JS après coup, et
    qui pouvait tomber avant que le dialogue ait sa taille finale).

    Le JS est retourné séparément et doit être exécuté via ui.run_javascript()
    APRÈS que le html ait été inséré (ui.html) : un <script> inséré via
    innerHTML n'est PAS exécuté par le navigateur, donc on ne peut pas se
    contenter de l'embarquer dans le HTML.

    `angle_deg` (pas de 45° côté appelant) fait tourner toute la scène autour
    de l'axe vertical avant projection — la rotation change la géométrie
    projetée elle-même, donc elle est recalculée côté serveur à chaque appel
    plutôt qu'en CSS/JS côté client (contrairement au zoom/pan ci-dessous,
    qui ne fait que déplacer le viewBox sur un SVG déjà projeté).
    """
    svg_content, focus_w, focus_h = _build_overview(campus, angle_deg)
    uid = uuid.uuid4().hex

    html = f"""
    <div id="iso-wrap-{uid}" style="width:100%; height:100%; min-height:70vh; overflow:hidden;
         position:relative; background:#1e1b4b; cursor:grab; border-radius:8px;">
      <div style="position:absolute; top:8px; right:8px; z-index:10; display:flex; flex-direction:column; gap:4px;">
        <button onclick="window.isoZoom_{uid} && window.isoZoom_{uid}(1.25)"
                style="width:34px;height:34px;border-radius:6px;border:1px solid #6366f1;background:#312e81;color:#eef2ff;cursor:pointer;font-size:18px;">+</button>
        <button onclick="window.isoZoom_{uid} && window.isoZoom_{uid}(0.8)"
                style="width:34px;height:34px;border-radius:6px;border:1px solid #6366f1;background:#312e81;color:#eef2ff;cursor:pointer;font-size:18px;">&minus;</button>
        <button onclick="window.isoReset_{uid} && window.isoReset_{uid}()"
                style="width:34px;height:34px;border-radius:6px;border:1px solid #6366f1;background:#312e81;color:#eef2ff;cursor:pointer;font-size:14px;">&#8635;</button>
      </div>
      {svg_content}
    </div>
    """

    js = f"""
    (function() {{
        const wrap = document.getElementById("iso-wrap-{uid}");
        if (!wrap) {{ return; }}
        const svgEl = wrap.querySelector("svg");
        if (!svgEl) {{ return; }}

        // Le viewBox initial (déjà cadré sur les bâtiments, calculé en Python)
        // sert de référence pour le bouton "reset".
        const initial = svgEl.getAttribute("viewBox").split(" ").map(Number);
        let [vx, vy, vw, vh] = initial;

        function applyViewBox() {{
            svgEl.setAttribute("viewBox", vx + " " + vy + " " + vw + " " + vh);
        }}

        let dragging = false, startX = 0, startY = 0, startVx = 0, startVy = 0;

        window["isoZoom_{uid}"] = function(factor) {{
            if (!wrap.isConnected) return;
            const rect = wrap.getBoundingClientRect();
            const mx = rect.width / 2, my = rect.height / 2;
            const worldX = vx + (mx / rect.width) * vw;
            const worldY = vy + (my / rect.height) * vh;
            const newVw = vw / factor;
            const newVh = vh / factor;
            vx = worldX - (mx / rect.width) * newVw;
            vy = worldY - (my / rect.height) * newVh;
            vw = newVw;
            vh = newVh;
            applyViewBox();
        }};

        window["isoReset_{uid}"] = function() {{
            [vx, vy, vw, vh] = initial;
            applyViewBox();
        }};

        wrap.addEventListener("mousedown", function(e) {{
            dragging = true;
            startX = e.clientX; startY = e.clientY; startVx = vx; startVy = vy;
            wrap.style.cursor = "grabbing";
        }});
        window.addEventListener("mousemove", function(e) {{
            if (!dragging || !wrap.isConnected) return;
            const rect = wrap.getBoundingClientRect();
            const dxWorld = (e.clientX - startX) * (vw / rect.width);
            const dyWorld = (e.clientY - startY) * (vh / rect.height);
            vx = startVx - dxWorld;
            vy = startVy - dyWorld;
            applyViewBox();
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
            const factor = e.deltaY < 0 ? 1.15 : 0.87;
            const worldX = vx + (mx / rect.width) * vw;
            const worldY = vy + (my / rect.height) * vh;
            const newVw = vw / factor;
            const newVh = vh / factor;
            vx = worldX - (mx / rect.width) * newVw;
            vy = worldY - (my / rect.height) * newVh;
            vw = newVw;
            vh = newVh;
            applyViewBox();
        }}, {{ passive: false }});
    }})();
    """

    return html, js
