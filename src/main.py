"""Administration graphique du campus - étape 2 : édition interactive.

Fonctionnalités :
- Créer un bâtiment (formulaire : nom)
- Créer un étage (dessin interactif du contour : clic pour ajouter des sommets)
- Créer une salle (formulaire nom/capacité, puis clic sur le plan pour la positionner)
- Déplacer une salle existante par glisser-déposer sur le plan

Lancer avec :  python main.py
"""
from __future__ import annotations

import base64
import uuid

from nicegui import events, ui

from model import Campus, Building, Floor, Room
from iso_view import build_overview_parts, PALETTE

DATA_PATH = "src/data.json"

# Palette du thème sombre "indigo", utilisée à la fois pour la configuration
# NiceGUI/Quasar (ui.colors) et pour nos SVG faits main (qui ne bénéficient
# pas automatiquement du mode sombre, contrairement aux composants Quasar).
THEME_PRIMARY = "#6366f1"      # indigo-500
THEME_SECONDARY = "#4f46e5"    # indigo-600
THEME_ACCENT = "#818cf8"       # indigo-400
THEME_DARK = "#312e81"         # indigo-900 (surfaces : cartes, dialogues)
THEME_DARK_PAGE = "#1e1b4b"    # indigo-950 (fond de page, plus sombre)

CANVAS_BG = "#211d55"          # fond des plans/canevas SVG (dérivé de indigo-950/900)
CANVAS_STROKE = "#4338ca"      # indigo-700, bordure du canevas
FLOOR_FILL = "#3730a3"         # indigo-800, remplissage du contour d'étage
FLOOR_STROKE = "#a5b4fc"       # indigo-300, contour d'étage
GRID_LINE_COLOR = "#4338ca"    # indigo-700, grille de fond du canevas de dessin
TEXT_PRIMARY = "#eef2ff"       # indigo-50, texte principal sur fond sombre
TEXT_SECONDARY = "#c7d2fe"     # indigo-200, texte secondaire sur fond sombre

PADDING = 2.0          # marge (en unités monde) autour du contour affiché
SCALE = 20              # pixels par unité monde
ROOM_RADIUS_UNITS = 1.0
DRAG_THRESHOLD_UNITS = 1.5   # distance max pour "attraper" une salle au clic

DEFAULT_CANVAS_W = 50.0  # unités monde, utilisé pour dessiner un nouvel étage
DEFAULT_CANVAS_H = 30.0

CAMPUS_ICON_SIZE = 8.0        # taille (unités monde) du carré représentant un bâtiment sur le plan du campus
CAMPUS_PADDING = 15.0         # marge généreuse pour la vue du plan du campus

VERTEX_DRAG_THRESHOLD = 1.2   # distance max pour "attraper" un sommet de contour au clic
EDGE_INSERT_THRESHOLD = 0.9   # distance max à une arête pour y insérer un nouveau sommet au clic


# ---------------------------------------------------------------------------
# Utilitaires géométrie / rendu SVG
# ---------------------------------------------------------------------------

def bounding_box(polygon: list[list[float]]) -> tuple[float, float, float, float]:
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    return min(xs), min(ys), max(xs), max(ys)


def transform_for_floor(floor: Floor | None) -> tuple[float, float, float, float]:
    """Retourne (min_x, min_y, w_units, h_units) pour le repère d'affichage."""
    if floor and floor.polygon:
        min_x, min_y, max_x, max_y = bounding_box(floor.polygon)
        return min_x - PADDING, min_y - PADDING, (max_x - min_x) + 2 * PADDING, (max_y - min_y) + 2 * PADDING
    return -PADDING, -PADDING, DEFAULT_CANVAS_W + 2 * PADDING, DEFAULT_CANVAS_H + 2 * PADDING


def world_to_px(x: float, y: float, origin_x: float, origin_y: float) -> tuple[float, float]:
    return (x - origin_x) * SCALE, (y - origin_y) * SCALE


def px_to_world(px: float, py: float, origin_x: float, origin_y: float) -> tuple[float, float]:
    return px / SCALE + origin_x, py / SCALE + origin_y


def blank_background(w_units: float, h_units: float) -> str:
    """Image de fond (data URI SVG) de taille pixel fixe = w_units*SCALE x h_units*SCALE.

    Sert de référence de taille pour interactive_image : les coordonnées
    image_x/image_y des événements souris seront exprimées dans cet espace pixel.
    """
    w_px, h_px = w_units * SCALE, h_units * SCALE
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w_px}" height="{h_px}">'
        f'<rect width="100%" height="100%" fill="{CANVAS_BG}" stroke="{CANVAS_STROKE}" stroke-width="1"/>'
        f"</svg>"
    )
    b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{b64}"


def grid_lines_svg(origin_x: float, origin_y: float, w_units: float, h_units: float, step: float = 5.0) -> str:
    parts = []
    x = -(origin_x % step)
    while x < w_units:
        px, _ = world_to_px(origin_x + x, 0, origin_x, origin_y)
        parts.append(f'<line x1="{px}" y1="0" x2="{px}" y2="{h_units * SCALE}" stroke="{GRID_LINE_COLOR}" stroke-width="1"/>')
        x += step
    y = -(origin_y % step)
    while y < h_units:
        _, py = world_to_px(0, origin_y + y, origin_x, origin_y)
        parts.append(f'<line x1="0" y1="{py}" x2="{w_units * SCALE}" y2="{py}" stroke="{GRID_LINE_COLOR}" stroke-width="1"/>')
        y += step
    return "".join(parts)


def room_svg(room: Room, origin_x: float, origin_y: float) -> str:
    cx, cy = world_to_px(room.position[0], room.position[1], origin_x, origin_y)
    r = ROOM_RADIUS_UNITS * SCALE
    return (
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#93c5fd" fill-opacity="0.9" '
        f'stroke="#1d4ed8" stroke-width="2"><title>{room.name} — {room.capacity} pers.</title></circle>'
        f'<text x="{cx}" y="{cy - r - 10}" font-size="20" font-weight="600" text-anchor="middle" fill="{TEXT_PRIMARY}">{room.name}</text>'
        f'<text x="{cx}" y="{cy + r + 22}" font-size="16" text-anchor="middle" fill="{TEXT_SECONDARY}">{room.capacity} pers.</text>'
    )


def floor_plan_content(floor: Floor, origin_x: float, origin_y: float) -> str:
    parts = []
    poly_px = " ".join(f"{px},{py}" for px, py in (world_to_px(x, y, origin_x, origin_y) for x, y in floor.polygon))
    parts.append(f'<polygon points="{poly_px}" fill="{FLOOR_FILL}" stroke="{FLOOR_STROKE}" stroke-width="2"/>')
    for room in floor.rooms:
        parts.append(room_svg(room, origin_x, origin_y))
    return "".join(parts)


def drawing_preview_content(points: list[list[float]], origin_x: float, origin_y: float) -> str:
    w_units, h_units = DEFAULT_CANVAS_W, DEFAULT_CANVAS_H
    parts = [grid_lines_svg(origin_x, origin_y, w_units, h_units)]
    if points:
        px_points = [world_to_px(x, y, origin_x, origin_y) for x, y in points]
        line_points = " ".join(f"{px},{py}" for px, py in px_points)
        parts.append(f'<polyline points="{line_points}" fill="none" stroke="#1d4ed8" stroke-width="2" stroke-dasharray="6,4"/>')
        for i, (px, py) in enumerate(px_points):
            radius = 6 if i == 0 else 5
            fill = "#dc2626" if i == 0 else "#1d4ed8"  # 1er point en rouge : double-clic ferme ici
            parts.append(f'<circle cx="{px}" cy="{py}" r="{radius}" fill="{fill}"/>')
    return "".join(parts)


def _reference_floor(building: Building) -> Floor | None:
    """Étage de référence pour l'empreinte au sol : le niveau 0 (RDC) si présent,
    sinon l'étage de niveau le plus bas (utile si un bâtiment n'a par ex. qu'un sous-sol)."""
    if not building.floors:
        return None
    zero = next((f for f in building.floors if f.level == 0), None)
    return zero if zero is not None else min(building.floors, key=lambda f: f.level)


def building_footprint(building: Building) -> list[list[float]]:
    """Polygone réel (coordonnées monde) de l'empreinte du bâtiment, basé sur
    son étage de référence. Repli sur un carré générique si le bâtiment n'a
    pas encore d'étage dessiné."""
    floor = _reference_floor(building)
    bx, by = building.position
    if floor is not None and floor.polygon:
        return [[bx + x, by + y] for x, y in floor.polygon]
    half = CAMPUS_ICON_SIZE / 2
    return [[bx - half, by - half], [bx + half, by - half], [bx + half, by + half], [bx - half, by + half]]



def campus_transform(campus: Campus) -> tuple[float, float, float, float]:
    """Retourne (origin_x, origin_y, w_units, h_units) pour le plan du campus,
    englobant l'empreinte réelle (RDC) de chaque bâtiment."""
    if campus.buildings:
        all_pts = [p for b in campus.buildings for p in building_footprint(b)]
        xs = [p[0] for p in all_pts]
        ys = [p[1] for p in all_pts]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
    else:
        min_x, max_x, min_y, max_y = 0.0, 60.0, 0.0, 40.0
    return (
        min_x - CAMPUS_PADDING,
        min_y - CAMPUS_PADDING,
        (max_x - min_x) + 2 * CAMPUS_PADDING,
        (max_y - min_y) + 2 * CAMPUS_PADDING,
    )


CAMPUS_MAP_LABEL_FONT_PX = 24  # taille FIXE en pixels écran des noms de bâtiment, quelle que soit l'échelle du plan


def campus_map_shapes_svg(campus: Campus, origin_x: float, origin_y: float) -> str:
    """Formes des bâtiments uniquement (pas de texte : les noms sont affichés
    par une surcouche HTML à taille fixe, voir campus_map_parts)."""
    parts = []
    for building in campus.buildings:
        footprint = building_footprint(building)
        color = PALETTE[hash(building.id) % len(PALETTE)]
        pts_px = [world_to_px(x, y, origin_x, origin_y) for x, y in footprint]
        points_str = " ".join(f"{px},{py}" for px, py in pts_px)
        parts.append(
            f'<polygon points="{points_str}" fill="{color}" fill-opacity="0.85" stroke="#1f2937" stroke-width="2">'
            f'<title>{building.name} ({len(building.floors)} étage(s))</title></polygon>'
        )
    return "".join(parts)


def campus_grid_step(w_units: float, h_units: float) -> float:
    """Choisit un pas de grille 'rond' adapté à l'échelle réelle du campus,
    pour environ 8 à 12 lignes visibles sur la plus grande dimension."""
    extent = max(w_units, h_units, 1.0)
    raw_step = extent / 10.0
    nice_steps = [1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 5000, 10000]
    for step in nice_steps:
        if step >= raw_step:
            return step
    return nice_steps[-1]


def _escape_js_string(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def campus_map_parts(campus: Campus) -> tuple[str, str]:
    """Retourne (html, js) pour le plan du campus : vue du dessus à l'échelle
    réelle (aucune déformation, voir campus_transform/building_footprint),
    avec les noms de bâtiment affichés en HTML par-dessus le SVG, à une taille
    FIXE en pixels écran (CAMPUS_MAP_LABEL_FONT_PX) — indépendante de
    l'échelle/étendue réelle du campus, contrairement à du texte SVG classique
    qui se redimensionne avec le reste du dessin.

    Le JS mesure la taille RÉELLEMENT affichée du SVG (getBoundingClientRect)
    pour positionner les étiquettes au bon endroit, et recalcule au
    redimensionnement (ResizeObserver) — même principe déjà utilisé et
    éprouvé pour la vue isométrique.
    """
    origin_x, origin_y, w_units, h_units = campus_transform(campus)
    w_px, h_px = w_units * SCALE, h_units * SCALE
    step = campus_grid_step(w_units, h_units)
    uid = uuid.uuid4().hex

    svg = (
        f'<svg id="campusmap-svg-{uid}" width="{w_px}" height="{h_px}" viewBox="0 0 {w_px} {h_px}" '
        f'xmlns="http://www.w3.org/2000/svg" style="display:block; max-width:100%; max-height:100%; '
        f'width:auto; height:auto; background:{CANVAS_BG}; border:1px solid {CANVAS_STROKE}; border-radius:8px;">'
        + grid_lines_svg(origin_x, origin_y, w_units, h_units, step=step)
        + campus_map_shapes_svg(campus, origin_x, origin_y)
        + "</svg>"
    )

    labels_json = "[" + ",".join(
        (
            lambda pts_px: f'{{"name":"{_escape_js_string(building.name)}",'
            f'"cx":{sum(p[0] for p in pts_px) / len(pts_px)},'
            f'"cy":{sum(p[1] for p in pts_px) / len(pts_px)}}}'
        )([world_to_px(x, y, origin_x, origin_y) for x, y in building_footprint(building)])
        for building in campus.buildings
    ) + "]"

    html = f"""
    <div id="campusmap-wrap-{uid}" style="position:relative; width:100%; height:100%; display:flex;
         align-items:center; justify-content:center; overflow:hidden;">
      {svg}
      <div id="campusmap-labels-{uid}" style="position:absolute; top:0; left:0; width:100%; height:100%; pointer-events:none;"></div>
      <div style="position:absolute; left:8px; bottom:8px; font-size:13px; color:{TEXT_SECONDARY};">
        grille : {step:g} unités — échelle réelle, aucune déformation
      </div>
    </div>
    """

    js = f"""
    (function() {{
        const wrap = document.getElementById("campusmap-wrap-{uid}");
        const svgEl = document.getElementById("campusmap-svg-{uid}");
        const layer = document.getElementById("campusmap-labels-{uid}");
        if (!wrap || !svgEl || !layer) {{ return; }}
        const labels = {labels_json};
        const viewW = {w_px};
        const viewH = {h_px};

        function reposition() {{
            if (!wrap.isConnected) return;
            const svgRect = svgEl.getBoundingClientRect();
            const wrapRect = wrap.getBoundingClientRect();
            if (svgRect.width === 0 || svgRect.height === 0) return;
            const scaleX = svgRect.width / viewW;
            const scaleY = svgRect.height / viewH;
            const offsetLeft = svgRect.left - wrapRect.left;
            const offsetTop = svgRect.top - wrapRect.top;
            layer.innerHTML = "";
            labels.forEach(function(lbl) {{
                const div = document.createElement("div");
                div.textContent = lbl.name;
                div.style.position = "absolute";
                div.style.left = (offsetLeft + lbl.cx * scaleX) + "px";
                div.style.top = (offsetTop + lbl.cy * scaleY) + "px";
                div.style.transform = "translate(-50%, -50%)";
                div.style.fontSize = "{CAMPUS_MAP_LABEL_FONT_PX}px";
                div.style.fontWeight = "700";
                div.style.color = "{TEXT_PRIMARY}";
                div.style.textShadow = "0 0 4px #0f0e2a, 0 0 6px #0f0e2a, 0 0 8px #0f0e2a";
                div.style.whiteSpace = "nowrap";
                layer.appendChild(div);
            }});
        }}

        const resizeObserver = new ResizeObserver(reposition);
        resizeObserver.observe(wrap);

        // La mesure du SVG (getBoundingClientRect) peut être faussée si elle a
        // lieu PENDANT l'animation d'ouverture du dialogue (transform CSS de
        // la transition Quasar) : le ResizeObserver ne se redéclenche pas
        // ensuite car la taille de boîte ne change pas réellement (seule la
        // transformation visuelle change). On recalcule donc en boucle sur
        // quelques dizaines de frames pour couvrir la durée de la transition,
        // ce qui corrige automatiquement toute mesure prise trop tôt.
        let framesLeft = 40;  // ~40 frames ≈ 650ms à 60fps, couvre les transitions Quasar habituelles
        function pollReposition() {{
            reposition();
            framesLeft -= 1;
            if (framesLeft > 0) {{
                requestAnimationFrame(pollReposition);
            }}
        }}
        requestAnimationFrame(pollReposition);
    }})();
    """
    return html, js


def floor_edit_content(floor: Floor, origin_x: float, origin_y: float) -> str:
    """Plan de l'étage avec poignées de sommets pour l'édition du contour."""
    parts = [floor_plan_content(floor, origin_x, origin_y)]
    for i, (x, y) in enumerate(floor.polygon):
        px, py = world_to_px(x, y, origin_x, origin_y)
        parts.append(f'<circle cx="{px}" cy="{py}" r="7" fill="#f59e0b" stroke="#78350f" stroke-width="2"/>')
    return "".join(parts)


def nearest_vertex(polygon: list[list[float]], wx: float, wy: float) -> tuple[int | None, float]:
    if not polygon:
        return None, float("inf")
    best_i, best_dist = None, float("inf")
    for i, (x, y) in enumerate(polygon):
        dist = ((x - wx) ** 2 + (y - wy) ** 2) ** 0.5
        if dist < best_dist:
            best_i, best_dist = i, dist
    return best_i, best_dist


def nearest_edge_insertion(polygon: list[list[float]], wx: float, wy: float, threshold: float) -> tuple[int, list[float]] | None:
    """Trouve le point le plus proche sur une arête du polygone, si sous le seuil.
    Retourne (index d'insertion, point) ou None."""
    n = len(polygon)
    best = None
    best_dist = threshold
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        dx, dy = x2 - x1, y2 - y1
        seg_len2 = dx * dx + dy * dy
        if seg_len2 == 0:
            continue
        t = max(0.0, min(1.0, ((wx - x1) * dx + (wy - y1) * dy) / seg_len2))
        cx, cy = x1 + t * dx, y1 + t * dy
        dist = ((wx - cx) ** 2 + (wy - cy) ** 2) ** 0.5
        if dist < best_dist:
            best_dist = dist
            best = (i + 1, [cx, cy])
    return best


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

def main() -> None:
    ui.colors(
        primary=THEME_PRIMARY,
        secondary=THEME_SECONDARY,
        accent=THEME_ACCENT,
        dark=THEME_DARK,
        dark_page=THEME_DARK_PAGE,
    )
    dark = ui.dark_mode(True)  # thème sombre indigo activé par défaut

    campus = Campus.load(DATA_PATH)

    state: dict = {
        "building": campus.buildings[0] if campus.buildings else None,
        "floor": None,
        "mode": None,            # None | "drawing_floor" | "placing_room"
        "pending_floor_name": None,
        "pending_floor_level": None,
        "pending_points": [],
        "pending_room_name": None,
        "pending_room_capacity": None,
        "dragging_room_id": None,
        "dragging_vertex_index": None,
        "plan_image": None,      # référence à l'élément ui.interactive_image courant
    }
    if state["building"] and state["building"].floors:
        state["floor"] = state["building"].floors[0]

    def save() -> None:
        campus.save(DATA_PATH)

    def get_building(building_id: str) -> Building | None:
        return next((b for b in campus.buildings if b.id == building_id), None)

    def get_floor(building: Building, floor_id: str) -> Floor | None:
        return next((f for f in building.floors if f.id == floor_id), None)

    # ------------------------------------------------------------------
    # Rendu de la liste des salles (barre latérale)
    # ------------------------------------------------------------------

    @ui.refreshable
    def room_list() -> None:
        floor = state["floor"]
        if floor is None or not floor.rooms:
            ui.label("Aucune salle sur cet étage.").classes("text-sm text-gray-500 dark:text-gray-300")
            return
        for room in floor.rooms:
            with ui.row().classes("items-center gap-2 w-full py-1 border-b border-gray-100 dark:border-gray-700"):
                ui.icon("meeting_room").classes("text-blue-600 dark:text-indigo-300")
                ui.label(room.name).classes("font-medium grow")
                ui.label(f"{room.capacity} pers.").classes("text-sm text-gray-500 dark:text-gray-300")

    # ------------------------------------------------------------------
    # Zone du plan (reconstruite à chaque changement de mode/sélection)
    # ------------------------------------------------------------------

    plan_container = ui.column().classes("w-full h-full")

    def start_geometry_edit() -> None:
        if state["floor"] is None:
            ui.notify("Sélectionne d'abord un étage", color="warning")
            return
        state["mode"] = "editing_geometry"
        state["dragging_vertex_index"] = None
        render_plan_area()

    def stop_geometry_edit() -> None:
        state["mode"] = None
        state["dragging_vertex_index"] = None
        render_plan_area()

    def render_plan_area() -> None:
        plan_container.clear()
        with plan_container:
            mode = state["mode"]

            if mode == "drawing_floor":
                origin_x, origin_y = -PADDING, -PADDING
                with ui.row().classes("items-center gap-2 mb-2"):
                    ui.label(
                        f"Dessin du contour : « {state['pending_floor_name']} » — "
                        f"cliquez pour ajouter des sommets, double-cliquez pour fermer le contour"
                    ).classes("text-sm text-gray-600 dark:text-gray-300")
                    ui.button("Terminer", on_click=finish_floor_drawing).props("size=sm color=primary")
                    ui.button("Annuler", on_click=cancel_floor_drawing).props("size=sm flat")
                bg = blank_background(DEFAULT_CANVAS_W + 2 * PADDING, DEFAULT_CANVAS_H + 2 * PADDING)
                img = ui.interactive_image(
                    bg,
                    content=drawing_preview_content(state["pending_points"], origin_x, origin_y),
                    on_mouse=on_mouse,
                    events=["mousedown", "dblclick"],
                ).classes("w-full").style("max-width: 900px")
                state["plan_image"] = img
                return

            floor = state["floor"]
            if floor is None:
                ui.label("Aucun étage sélectionné. Crée un bâtiment puis un étage pour commencer.").classes("text-gray-500 dark:text-gray-300")
                state["plan_image"] = None
                return

            if mode == "editing_geometry":
                origin_x, origin_y, w_units, h_units = transform_for_floor(floor)
                with ui.row().classes("items-center gap-2 mb-2"):
                    ui.label(
                        "Édition du contour — glisse un sommet (orange), double-clique dessus pour le "
                        "supprimer, clique sur une arête pour y ajouter un sommet"
                    ).classes("text-sm text-gray-600 dark:text-gray-300")
                    ui.button("Terminer l'édition", on_click=stop_geometry_edit).props("size=sm color=primary")
                bg = blank_background(w_units, h_units)
                img = ui.interactive_image(
                    bg,
                    content=floor_edit_content(floor, origin_x, origin_y),
                    on_mouse=on_mouse,
                    events=["mousedown", "mousemove", "mouseup", "dblclick"],
                ).classes("w-full").style("max-width: 900px")
                state["plan_image"] = img
                return

            if state["mode"] == "placing_room":
                ui.label(f"Clique sur le plan pour placer « {state['pending_room_name']} »").classes("text-sm text-blue-600 dark:text-indigo-300 mb-2")
            else:
                with ui.row().classes("items-center gap-2 mb-2"):
                    ui.button("Éditer le contour de cet étage", icon="edit", on_click=start_geometry_edit).props("size=sm outline")

            origin_x, origin_y, w_units, h_units = transform_for_floor(floor)
            bg = blank_background(w_units, h_units)
            img = ui.interactive_image(
                bg,
                content=floor_plan_content(floor, origin_x, origin_y),
                on_mouse=on_mouse,
                events=["mousedown", "mousemove", "mouseup"],
            ).classes("w-full").style("max-width: 900px")
            state["plan_image"] = img

    # ------------------------------------------------------------------
    # Gestion de la souris sur le plan
    # ------------------------------------------------------------------

    def on_mouse(e: events.MouseEventArguments) -> None:
        mode = state["mode"]

        # --- Édition du contour d'un étage existant ---
        if mode == "editing_geometry":
            floor = state["floor"]
            if floor is None:
                return
            origin_x, origin_y, _, _ = transform_for_floor(floor)
            wx, wy = px_to_world(e.image_x, e.image_y, origin_x, origin_y)

            def redraw_edit() -> None:
                if state["plan_image"] is not None:
                    state["plan_image"].content = floor_edit_content(floor, origin_x, origin_y)

            if e.type == "dblclick":
                idx, dist = nearest_vertex(floor.polygon, wx, wy)
                if idx is not None and dist <= VERTEX_DRAG_THRESHOLD and len(floor.polygon) > 3:
                    floor.polygon.pop(idx)
                    save()
                    redraw_edit()
                elif idx is not None and len(floor.polygon) <= 3:
                    ui.notify("Un contour doit garder au moins 3 sommets", color="warning")
                return

            if e.type == "mousedown":
                idx, dist = nearest_vertex(floor.polygon, wx, wy)
                if idx is not None and dist <= VERTEX_DRAG_THRESHOLD:
                    state["dragging_vertex_index"] = idx
                    return
                insertion = nearest_edge_insertion(floor.polygon, wx, wy, EDGE_INSERT_THRESHOLD)
                if insertion is not None:
                    insert_idx, point = insertion
                    floor.polygon.insert(insert_idx, [round(point[0], 2), round(point[1], 2)])
                    state["dragging_vertex_index"] = insert_idx
                    save()
                    redraw_edit()
                return

            if e.type == "mousemove":
                idx = state.get("dragging_vertex_index")
                if idx is None:
                    return
                floor.polygon[idx] = [round(wx, 2), round(wy, 2)]
                redraw_edit()
                return

            if e.type == "mouseup":
                if state.get("dragging_vertex_index") is not None:
                    save()
                    state["dragging_vertex_index"] = None
                return
            return

        # --- Dessin du contour d'un nouvel étage ---
        if mode == "drawing_floor":
            if e.type == "dblclick":
                # Un double-clic déclenche deux mousedown avant l'événement dblclick :
                # le dernier point ajouté correspond au 2e clic du double-clic, superflu.
                if state["pending_points"]:
                    state["pending_points"].pop()
                finish_floor_drawing()
                return
            if e.type != "mousedown":
                return
            origin_x, origin_y = -PADDING, -PADDING
            wx, wy = px_to_world(e.image_x, e.image_y, origin_x, origin_y)
            state["pending_points"].append([round(wx, 2), round(wy, 2)])
            if state["plan_image"] is not None:
                state["plan_image"].content = drawing_preview_content(state["pending_points"], origin_x, origin_y)
            return

        floor = state["floor"]
        if floor is None:
            return
        origin_x, origin_y, _, _ = transform_for_floor(floor)
        wx, wy = px_to_world(e.image_x, e.image_y, origin_x, origin_y)

        # --- Placement d'une nouvelle salle ---
        if mode == "placing_room":
            if e.type != "mousedown":
                return
            floor.add_room(state["pending_room_name"], state["pending_room_capacity"], [round(wx, 2), round(wy, 2)])
            save()
            state["mode"] = None
            state["pending_room_name"] = None
            state["pending_room_capacity"] = None
            room_list.refresh()
            render_plan_area()
            return

        # --- Déplacement (glisser-déposer) d'une salle existante ---
        if e.type == "mousedown":
            nearest = min(
                floor.rooms,
                key=lambda r: (r.position[0] - wx) ** 2 + (r.position[1] - wy) ** 2,
                default=None,
            )
            if nearest is not None:
                dist = ((nearest.position[0] - wx) ** 2 + (nearest.position[1] - wy) ** 2) ** 0.5
                if dist <= DRAG_THRESHOLD_UNITS:
                    state["dragging_room_id"] = nearest.id

        elif e.type == "mousemove":
            if state["dragging_room_id"] is None:
                return
            room = next((r for r in floor.rooms if r.id == state["dragging_room_id"]), None)
            if room is None:
                return
            room.position = [round(wx, 2), round(wy, 2)]
            if state["plan_image"] is not None:
                state["plan_image"].content = floor_plan_content(floor, origin_x, origin_y)

        elif e.type == "mouseup":
            if state["dragging_room_id"] is not None:
                save()
                state["dragging_room_id"] = None
                room_list.refresh()

    # ------------------------------------------------------------------
    # Actions de création (dialogues)
    # ------------------------------------------------------------------

    def open_new_building_dialog() -> None:
        with ui.dialog() as dialog, ui.card():
            ui.label("Nouveau bâtiment").classes("text-lg font-semibold")
            name_input = ui.input("Nom du bâtiment").classes("w-full")

            def confirm() -> None:
                if not name_input.value:
                    ui.notify("Le nom est requis", color="warning")
                    return
                building = campus.add_building(name_input.value)
                save()
                state["building"] = building
                state["floor"] = None
                building_select.set_options(buildings_options())
                building_select.value = building.id
                floor_select.set_options({})
                floor_select.value = None
                room_list.refresh()
                render_plan_area()
                dialog.close()

            with ui.row().classes("justify-end w-full mt-2"):
                ui.button("Annuler", on_click=dialog.close).props("flat")
                ui.button("Créer", on_click=confirm)
        dialog.open()

    def open_new_floor_dialog() -> None:
        if state["building"] is None:
            ui.notify("Sélectionne ou crée d'abord un bâtiment", color="warning")
            return
        building = state["building"]
        default_level = (max((f.level for f in building.floors), default=-1)) + 1
        clone_options = {"__none__": "Aucun — dessiner un nouveau contour"}
        clone_options.update({f.id: f.name for f in building.floors})
        with ui.dialog() as dialog, ui.card():
            ui.label("Nouvel étage").classes("text-lg font-semibold")
            name_input = ui.input("Nom de l'étage (ex : RDC, 1er étage, Sous-sol)").classes("w-full")
            level_input = ui.number(
                "Niveau (0 = RDC, négatif = sous-sol, positif = étage)",
                value=default_level,
                precision=0,
            ).classes("w-full")
            clone_select = ui.select(
                clone_options, value="__none__", label="Copier la géométrie de"
            ).classes("w-full")

            def confirm() -> None:
                if not name_input.value:
                    ui.notify("Le nom est requis", color="warning")
                    return
                level = int(level_input.value if level_input.value is not None else default_level)

                if clone_select.value and clone_select.value != "__none__":
                    source_floor = get_floor(building, clone_select.value)
                    if source_floor is None or not source_floor.polygon:
                        ui.notify("Impossible de copier ce contour", color="warning")
                        return
                    new_floor = building.add_floor(
                        name_input.value, [list(p) for p in source_floor.polygon], level=level
                    )
                    save()
                    state["floor"] = new_floor
                    floor_select.set_options(floors_options(building))
                    floor_select.value = new_floor.id
                    room_list.refresh()
                    render_plan_area()
                    dialog.close()
                    return

                state["mode"] = "drawing_floor"
                state["pending_floor_name"] = name_input.value
                state["pending_floor_level"] = level
                state["pending_points"] = []
                dialog.close()
                render_plan_area()

            with ui.row().classes("justify-end w-full mt-2"):
                ui.button("Annuler", on_click=dialog.close).props("flat")
                ui.button("Créer", on_click=confirm)
        dialog.open()

    def finish_floor_drawing() -> None:
        if len(state["pending_points"]) < 3:
            ui.notify("Il faut au moins 3 points pour former un contour", color="warning")
            return
        floor = state["building"].add_floor(
            state["pending_floor_name"], state["pending_points"], level=state.get("pending_floor_level")
        )
        save()
        state["mode"] = None
        state["pending_floor_name"] = None
        state["pending_floor_level"] = None
        state["pending_points"] = []
        state["floor"] = floor
        floor_select.set_options(floors_options(state["building"]))
        floor_select.value = floor.id
        room_list.refresh()
        render_plan_area()

    def cancel_floor_drawing() -> None:
        state["mode"] = None
        state["pending_floor_name"] = None
        state["pending_floor_level"] = None
        state["pending_points"] = []
        render_plan_area()

    def open_new_room_dialog() -> None:
        if state["floor"] is None:
            ui.notify("Sélectionne ou crée d'abord un étage", color="warning")
            return
        with ui.dialog() as dialog, ui.card():
            ui.label("Nouvelle salle").classes("text-lg font-semibold")
            name_input = ui.input("Nom de la salle").classes("w-full")
            capacity_input = ui.number("Capacité (personnes)", value=10, min=1, precision=0).classes("w-full")

            def confirm() -> None:
                if not name_input.value:
                    ui.notify("Le nom est requis", color="warning")
                    return
                state["mode"] = "placing_room"
                state["pending_room_name"] = name_input.value
                state["pending_room_capacity"] = int(capacity_input.value or 1)
                dialog.close()
                render_plan_area()

            with ui.row().classes("justify-end w-full mt-2"):
                ui.button("Annuler", on_click=dialog.close).props("flat")
                ui.button("Placer sur le plan", on_click=confirm)
        dialog.open()

    # ------------------------------------------------------------------
    # Sélection bâtiment / étage
    # ------------------------------------------------------------------

    def buildings_options() -> dict[str, str]:
        return {b.id: b.name for b in campus.buildings}

    def floors_options(building: Building | None) -> dict[str, str]:
        return {f.id: f.name for f in building.floors} if building else {}

    def on_building_change(building_id: str) -> None:
        building = get_building(building_id)
        state["building"] = building
        state["floor"] = building.floors[0] if building and building.floors else None
        floor_select.set_options(floors_options(building))
        floor_select.value = state["floor"].id if state["floor"] else None
        room_list.refresh()
        render_plan_area()

    def on_floor_change(floor_id: str) -> None:
        building = state["building"]
        if building:
            state["floor"] = get_floor(building, floor_id)
        room_list.refresh()
        render_plan_area()

    # ------------------------------------------------------------------
    # Mise en page
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Plan du campus (glisser-déposer des bâtiments)
    # ------------------------------------------------------------------

    def open_campus_map_dialog() -> None:
        container_ref: dict = {"el": None}  # rempli une fois le ui.column créé dans le bon contexte (dialogue)
        search = {"query": ""}

        def redraw_map() -> None:
            if container_ref["el"] is None:
                return
            container_ref["el"].clear()
            html, js = campus_map_parts(campus)
            with container_ref["el"]:
                ui.html(html).classes("w-full h-full")
            ui.timer(0.05, lambda: ui.run_javascript(js), once=True)

        def make_position_handlers(building: Building):
            def on_x_change(e) -> None:
                try:
                    building.position[0] = float(e.value)
                except (TypeError, ValueError):
                    return
                save()
                redraw_map()

            def on_y_change(e) -> None:
                try:
                    building.position[1] = float(e.value)
                except (TypeError, ValueError):
                    return
                save()
                redraw_map()

            return on_x_change, on_y_change

        def render_building_position_row(building: Building) -> None:
            on_x_change, on_y_change = make_position_handlers(building)
            with ui.row().classes("w-full items-center gap-3 py-1 border-b border-gray-100 dark:border-gray-700"):
                ui.label(building.name).classes("flex-1 font-medium")
                ui.number(label="X", value=building.position[0], step=1, on_change=on_x_change).props("dense outlined").classes("w-32")
                ui.number(label="Y", value=building.position[1], step=1, on_change=on_y_change).props("dense outlined").classes("w-32")

        @ui.refreshable
        def rows_view() -> None:
            query = search["query"].strip().lower()
            shown = False
            for building in campus.buildings:
                if query and query not in building.name.lower():
                    continue
                shown = True
                render_building_position_row(building)
            if not shown:
                ui.label("Aucun bâtiment ne correspond à la recherche.").classes("text-gray-500 dark:text-gray-300 py-4")

        def on_search_change(e) -> None:
            search["query"] = e.value or ""
            rows_view.refresh()

        with ui.dialog().props("maximized") as dialog, ui.card().classes("w-full h-full"):
            with ui.row().classes("items-center justify-between w-full mb-2"):
                ui.label("Plan du campus").classes("text-lg font-semibold")
                ui.button(icon="close", on_click=dialog.close).props("flat round")

            if not campus.buildings:
                ui.label("Aucun bâtiment à positionner. Crée d'abord un bâtiment.").classes("text-gray-500 dark:text-gray-300")
            else:
                ui.label("Vérification visuelle (lecture seule)").classes("text-xs text-gray-500 dark:text-gray-300 mb-1")
                with ui.element("div").style("width: 100%; height: 40vh;"):
                    container_ref["el"] = ui.column().classes("w-full h-full")

                ui.separator().classes("my-3")

                ui.label(
                    "Table des positions (coordonnées réelles, mêmes unités que les contours d'étage) "
                    "— modifie X/Y ici."
                ).classes("text-xs text-gray-500 dark:text-gray-300 mb-1")
                ui.input(
                    label="Rechercher un bâtiment...", on_change=on_search_change,
                ).classes("w-full mb-2").props("clearable dense outlined")

                with ui.row().classes("w-full items-center gap-3 pb-2 border-b-2 border-gray-300 dark:border-gray-600 text-sm font-semibold text-gray-500 dark:text-gray-300"):
                    ui.label("Bâtiment").classes("flex-1")
                    ui.label("X").classes("w-32")
                    ui.label("Y").classes("w-32")

                rows_view()

                redraw_map()

        dialog.open()

    # ------------------------------------------------------------------
    # Vue d'ensemble isométrique
    # ------------------------------------------------------------------

    def open_overview_dialog() -> None:
        try:
            html, js = build_overview_parts(campus)
        except Exception as exc:  # évite un échec silencieux du bouton
            ui.notify(f"Erreur lors de la génération de la vue d'ensemble : {exc}", color="negative")
            raise
        with ui.dialog().props("maximized") as dialog, ui.card().classes("w-full h-full"):
            with ui.row().classes("items-center justify-between w-full"):
                ui.label("Vue d'ensemble du campus").classes("text-lg font-semibold")
                ui.button(icon="close", on_click=dialog.close).props("flat round")
            ui.html(html).classes("w-full h-full")
        dialog.open()
        ui.timer(0.05, lambda: ui.run_javascript(js), once=True)

    # ------------------------------------------------------------------
    # Liste éditable de toutes les salles (vue synthétique)
    # ------------------------------------------------------------------

    def open_room_table_dialog() -> None:
        search = {"query": ""}

        @ui.refreshable
        def rows_view() -> None:
            query = search["query"].strip().lower()
            shown = False
            for building in campus.buildings:
                for floor in building.floors:
                    for room in floor.rooms:
                        if query and query not in room.name.lower() and query not in building.name.lower() and query not in floor.name.lower():
                            continue
                        shown = True
                        render_room_row(building, floor, room)
            if not shown:
                ui.label("Aucune salle ne correspond à la recherche.").classes("text-gray-500 dark:text-gray-300 py-4")

        def on_search_change(e) -> None:
            search["query"] = e.value or ""
            rows_view.refresh()

        with ui.dialog().props("maximized") as dialog, ui.card().classes("w-full h-full"):
            with ui.row().classes("items-center justify-between w-full mb-2"):
                ui.label("Toutes les salles").classes("text-lg font-semibold")
                ui.button(icon="close", on_click=dialog.close).props("flat round")

            has_any_room = any(floor.rooms for building in campus.buildings for floor in building.floors)
            if not has_any_room:
                ui.label("Aucune salle créée pour l'instant.").classes("text-gray-500 dark:text-gray-300")
            else:
                ui.input(
                    label="Rechercher une salle (nom, bâtiment, étage)...",
                    on_change=on_search_change,
                ).classes("w-full mb-2").props("clearable dense outlined")

                with ui.scroll_area().classes("w-full h-full"):
                    with ui.row().classes("w-full items-center gap-3 pb-2 border-b-2 border-gray-300 dark:border-gray-600 text-sm font-semibold text-gray-500 dark:text-gray-300"):
                        ui.label("Bâtiment").classes("w-40")
                        ui.label("Étage").classes("w-40")
                        ui.label("Nom de la salle").classes("flex-1")
                        ui.label("Capacité").classes("w-32")

                    rows_view()

        dialog.open()

    def render_room_row(building: Building, floor: Floor, room: Room) -> None:
        def on_name_change(e) -> None:
            new_name = (e.value or "").strip()
            if not new_name:
                ui.notify("Le nom ne peut pas être vide", color="warning")
                return
            room.name = new_name
            save()
            room_list.refresh()
            render_plan_area()

        def on_capacity_change(e) -> None:
            try:
                new_capacity = int(e.value)
            except (TypeError, ValueError):
                return
            if new_capacity < 1:
                ui.notify("La capacité doit être d'au moins 1 personne", color="warning")
                return
            room.capacity = new_capacity
            save()
            room_list.refresh()
            render_plan_area()

        with ui.row().classes("w-full items-center gap-3 py-1 border-b border-gray-100 dark:border-gray-700"):
            ui.label(building.name).classes("w-40 text-sm text-gray-600 dark:text-gray-300")
            ui.label(floor.name).classes("w-40 text-sm text-gray-600 dark:text-gray-300")
            ui.input(value=room.name, on_change=on_name_change).classes("flex-1").props("dense")
            ui.number(value=room.capacity, min=1, precision=0, on_change=on_capacity_change).classes("w-32").props("dense")
            ui.button(icon="tune", on_click=lambda: open_room_details_dialog(room)).props("flat round size=sm").tooltip("Détails avancés")

    def open_room_details_dialog(room: Room) -> None:
        extra = room.extra

        with ui.dialog() as dialog, ui.card().classes("w-[640px] max-w-full"):
            ui.label(f"Détails avancés — {room.name}").classes("text-lg font-semibold mb-2")

            with ui.grid(columns=2).classes("w-full gap-3"):
                old_name_input = ui.input("Ancien nom (oldName)", value=extra.get("oldName", "")).props("dense")
                alt_name_input = ui.input("Nom alternatif (altName)", value=extra.get("altName", "")).props("dense")
                access_input = ui.input("Accès (access)", value=extra.get("access", "")).props("dense")
                zone_input = ui.input("Zone", value=extra.get("zone", "")).props("dense")
                booking_type_input = ui.input("Type de réservation (roomBookingType)", value=extra.get("roomBookingType", "")).props("dense")
                phone_input = ui.input("Téléphone (telephoneNumber)", value=extra.get("telephoneNumber", "")).props("dense")
                type_input = ui.input("Type", value=extra.get("type", "")).props("dense")
                room_type_input = ui.input("Type de salle (roomType)", value=extra.get("roomType", "meetingRoom")).props("dense")

            available_switch = ui.checkbox("Disponible (available)", value=bool(extra.get("available", True))).classes("mt-1")
            comment_input = ui.textarea("Commentaire", value=extra.get("comment", "")).classes("w-full")

            raw_equipments = extra.get("equipments", [])
            equipments_text = ", ".join(raw_equipments) if isinstance(raw_equipments, list) else ""
            equipments_input = ui.input(
                "Équipements (séparés par des virgules)", value=equipments_text
            ).classes("w-full")

            ui.label("Responsables de la salle (roomManagers)").classes("text-sm font-semibold text-gray-500 dark:text-gray-300 mt-3")
            managers_container = ui.column().classes("w-full gap-1")
            managers_state: list[dict] = [dict(m) for m in extra.get("roomManagers", {}).get("value", [])]

            def render_managers() -> None:
                managers_container.clear()
                with managers_container:
                    if not managers_state:
                        ui.label("Aucun responsable renseigné.").classes("text-xs text-gray-400 dark:text-gray-500")
                    for i in range(len(managers_state)):
                        with ui.row().classes("items-center gap-2 w-full"):
                            ui.input(
                                "Nom", value=managers_state[i].get("name", ""),
                                on_change=lambda e, i=i: managers_state[i].update(name=e.value),
                            ).classes("flex-1").props("dense")
                            ui.input(
                                "Téléphone", value=managers_state[i].get("telephoneNumber", ""),
                                on_change=lambda e, i=i: managers_state[i].update(telephoneNumber=e.value),
                            ).classes("flex-1").props("dense")
                            ui.input(
                                "Email", value=managers_state[i].get("email", ""),
                                on_change=lambda e, i=i: managers_state[i].update(email=e.value),
                            ).classes("flex-1").props("dense")
                            ui.button(icon="delete", on_click=lambda i=i: remove_manager(i)).props("flat round size=sm")

            def remove_manager(i: int) -> None:
                managers_state.pop(i)
                render_managers()

            def add_manager() -> None:
                managers_state.append({"name": "", "telephoneNumber": "", "email": ""})
                render_managers()

            render_managers()
            ui.button("+ Responsable", on_click=add_manager).props("size=sm outline").classes("mt-1")

            def confirm() -> None:
                extra["oldName"] = old_name_input.value or ""
                extra["altName"] = alt_name_input.value or ""
                extra["access"] = access_input.value or ""
                extra["zone"] = zone_input.value or ""
                extra["roomBookingType"] = booking_type_input.value or ""
                extra["telephoneNumber"] = phone_input.value or ""
                extra["type"] = type_input.value or ""
                extra["roomType"] = room_type_input.value or "meetingRoom"
                extra["available"] = bool(available_switch.value)
                extra["comment"] = comment_input.value or ""
                extra["equipments"] = [s.strip() for s in (equipments_input.value or "").split(",") if s.strip()]
                extra["roomManagers"] = {
                    "value": [
                        m for m in managers_state
                        if (m.get("name") or m.get("telephoneNumber") or m.get("email"))
                    ]
                }
                save()
                ui.notify("Détails enregistrés")
                dialog.close()

            with ui.row().classes("justify-end w-full mt-3"):
                ui.button("Annuler", on_click=dialog.close).props("flat")
                ui.button("Enregistrer", on_click=confirm)
        dialog.open()

    with ui.header().classes("items-center justify-between"):
        ui.label("Administration du Campus").classes("text-lg font-semibold")
        with ui.row().classes("items-center gap-2"):
            ui.button("Toutes les salles", icon="table_rows", on_click=open_room_table_dialog).props("outline color=white")
            ui.button("Plan du campus", icon="map", on_click=open_campus_map_dialog).props("outline color=white")
            ui.button("Vue d'ensemble (isométrique)", icon="view_in_ar", on_click=open_overview_dialog).props("outline color=white")
            ui.button(icon="light_mode", on_click=dark.disable).props("flat round color=white").tooltip("Thème clair").bind_visibility_from(dark, "value", value=True)
            ui.button(icon="dark_mode", on_click=dark.enable).props("flat round color=white").tooltip("Thème sombre").bind_visibility_from(dark, "value", value=False)

    with ui.left_drawer().classes("gap-2 p-4"):
        ui.label("Sélection").classes("text-sm font-semibold text-gray-500 dark:text-gray-300")
        building_select = ui.select(
            buildings_options(),
            value=state["building"].id if state["building"] else None,
            label="Bâtiment",
            on_change=lambda e: on_building_change(e.value),
        ).classes("w-full")
        ui.button("+ Bâtiment", on_click=open_new_building_dialog).props("size=sm outline").classes("w-full")

        floor_select = ui.select(
            floors_options(state["building"]),
            value=state["floor"].id if state["floor"] else None,
            label="Étage",
            on_change=lambda e: on_floor_change(e.value),
        ).classes("w-full")
        ui.button("+ Étage", on_click=open_new_floor_dialog).props("size=sm outline").classes("w-full")

        ui.separator()
        with ui.row().classes("items-center justify-between w-full"):
            ui.label("Salles de l'étage").classes("text-sm font-semibold text-gray-500 dark:text-gray-300")
            ui.button("+ Salle", on_click=open_new_room_dialog).props("size=sm outline")
        room_list()

    with ui.column().classes("w-full h-full items-stretch p-4"):
        render_plan_area()

    ui.run(title="Administration Campus", reload=False)


if __name__ in {"__main__", "__mp_main__"}:
    main()
