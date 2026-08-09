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

from nicegui import events, ui

from model import Campus, Building, Floor, Room
from iso_view import build_overview_parts, PALETTE

DATA_PATH = "src/data.json"

PADDING = 2.0          # marge (en unités monde) autour du contour affiché
SCALE = 20              # pixels par unité monde
ROOM_RADIUS_UNITS = 1.0
DRAG_THRESHOLD_UNITS = 1.5   # distance max pour "attraper" une salle au clic

DEFAULT_CANVAS_W = 50.0  # unités monde, utilisé pour dessiner un nouvel étage
DEFAULT_CANVAS_H = 30.0

CAMPUS_ICON_SIZE = 8.0        # taille (unités monde) du carré représentant un bâtiment sur le plan du campus
CAMPUS_DRAG_THRESHOLD = 6.0   # distance max pour "attraper" un bâtiment au clic
CAMPUS_PADDING = 15.0         # marge généreuse pour pouvoir glisser les bâtiments sans sortir du canevas


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
        f'<rect width="100%" height="100%" fill="#fafafa" stroke="#ddd" stroke-width="1"/>'
        f"</svg>"
    )
    b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{b64}"


def grid_lines_svg(origin_x: float, origin_y: float, w_units: float, h_units: float, step: float = 5.0) -> str:
    parts = []
    x = -(origin_x % step)
    while x < w_units:
        px, _ = world_to_px(origin_x + x, 0, origin_x, origin_y)
        parts.append(f'<line x1="{px}" y1="0" x2="{px}" y2="{h_units * SCALE}" stroke="#e5e7eb" stroke-width="1"/>')
        x += step
    y = -(origin_y % step)
    while y < h_units:
        _, py = world_to_px(0, origin_y + y, origin_x, origin_y)
        parts.append(f'<line x1="0" y1="{py}" x2="{w_units * SCALE}" y2="{py}" stroke="#e5e7eb" stroke-width="1"/>')
        y += step
    return "".join(parts)


def room_svg(room: Room, origin_x: float, origin_y: float) -> str:
    cx, cy = world_to_px(room.position[0], room.position[1], origin_x, origin_y)
    r = ROOM_RADIUS_UNITS * SCALE
    return (
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#93c5fd" fill-opacity="0.9" '
        f'stroke="#1d4ed8" stroke-width="2"><title>{room.name} — {room.capacity} pers.</title></circle>'
        f'<text x="{cx}" y="{cy - r - 6}" font-size="14" text-anchor="middle" fill="#1e293b">{room.name}</text>'
        f'<text x="{cx}" y="{cy + r + 16}" font-size="12" text-anchor="middle" fill="#475569">{room.capacity} pers.</text>'
    )


def floor_plan_content(floor: Floor, origin_x: float, origin_y: float) -> str:
    parts = []
    poly_px = " ".join(f"{px},{py}" for px, py in (world_to_px(x, y, origin_x, origin_y) for x, y in floor.polygon))
    parts.append(f'<polygon points="{poly_px}" fill="#eef2f7" stroke="#334155" stroke-width="2"/>')
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


def campus_transform(campus: Campus) -> tuple[float, float, float, float]:
    """Retourne (origin_x, origin_y, w_units, h_units) pour le plan du campus."""
    if campus.buildings:
        xs = [b.position[0] for b in campus.buildings]
        ys = [b.position[1] for b in campus.buildings]
        half = CAMPUS_ICON_SIZE / 2
        min_x, max_x = min(xs) - half, max(xs) + half
        min_y, max_y = min(ys) - half, max(ys) + half
    else:
        min_x, max_x, min_y, max_y = 0.0, 60.0, 0.0, 40.0
    return (
        min_x - CAMPUS_PADDING,
        min_y - CAMPUS_PADDING,
        (max_x - min_x) + 2 * CAMPUS_PADDING,
        (max_y - min_y) + 2 * CAMPUS_PADDING,
    )


def campus_map_content(campus: Campus, origin_x: float, origin_y: float) -> str:
    parts = []
    half = CAMPUS_ICON_SIZE / 2
    for building in campus.buildings:
        bx, by = building.position
        color = PALETTE[hash(building.id) % len(PALETTE)]
        x1, y1 = world_to_px(bx - half, by - half, origin_x, origin_y)
        x2, y2 = world_to_px(bx + half, by + half, origin_x, origin_y)
        cx, cy = world_to_px(bx, by, origin_x, origin_y)
        parts.append(
            f'<rect x="{x1}" y="{y1}" width="{x2 - x1}" height="{y2 - y1}" rx="6" '
            f'fill="{color}" fill-opacity="0.85" stroke="#1f2937" stroke-width="2">'
            f'<title>{building.name} ({len(building.floors)} étage(s))</title></rect>'
        )
        parts.append(
            f'<text x="{cx}" y="{cy}" font-size="13" text-anchor="middle" dominant-baseline="middle" '
            f'fill="#0f172a" font-weight="600">{building.name}</text>'
        )
    return "".join(parts)


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

def main() -> None:
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
            ui.label("Aucune salle sur cet étage.").classes("text-sm text-gray-500")
            return
        for room in floor.rooms:
            with ui.row().classes("items-center gap-2 w-full py-1 border-b border-gray-100"):
                ui.icon("meeting_room").classes("text-blue-600")
                ui.label(room.name).classes("font-medium grow")
                ui.label(f"{room.capacity} pers.").classes("text-sm text-gray-500")

    # ------------------------------------------------------------------
    # Zone du plan (reconstruite à chaque changement de mode/sélection)
    # ------------------------------------------------------------------

    plan_container = ui.column().classes("w-full h-full")

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
                    ).classes("text-sm text-gray-600")
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
                ui.label("Aucun étage sélectionné. Crée un bâtiment puis un étage pour commencer.").classes("text-gray-500")
                state["plan_image"] = None
                return

            if state["mode"] == "placing_room":
                ui.label(f"Clique sur le plan pour placer « {state['pending_room_name']} »").classes("text-sm text-blue-600 mb-2")

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
        # Origine/dimensions figées à l'ouverture : elles ne doivent PAS bouger
        # pendant une session de glisser-déposer, sinon le mapping pixel -> unité
        # devient incohérent avec l'image de fond (déjà générée à taille fixe).
        origin_x, origin_y, w_units, h_units = campus_transform(campus)
        drag_state = {"id": None}
        img_ref: dict = {"el": None}

        def redraw() -> None:
            if img_ref["el"] is not None:
                img_ref["el"].content = campus_map_content(campus, origin_x, origin_y)

        def on_campus_mouse(e: events.MouseEventArguments) -> None:
            wx, wy = px_to_world(e.image_x, e.image_y, origin_x, origin_y)

            if e.type == "mousedown":
                nearest = min(
                    campus.buildings,
                    key=lambda b: (b.position[0] - wx) ** 2 + (b.position[1] - wy) ** 2,
                    default=None,
                )
                if nearest is not None:
                    dist = ((nearest.position[0] - wx) ** 2 + (nearest.position[1] - wy) ** 2) ** 0.5
                    if dist <= CAMPUS_DRAG_THRESHOLD:
                        drag_state["id"] = nearest.id

            elif e.type == "mousemove":
                if drag_state["id"] is None:
                    return
                building = next((b for b in campus.buildings if b.id == drag_state["id"]), None)
                if building is None:
                    return
                building.position = [round(wx, 2), round(wy, 2)]
                redraw()

            elif e.type == "mouseup":
                if drag_state["id"] is not None:
                    save()
                    drag_state["id"] = None

        with ui.dialog().props("maximized") as dialog, ui.card().classes("w-full h-full"):
            with ui.row().classes("items-center justify-between w-full"):
                ui.label("Plan du campus — glisse les bâtiments pour les repositionner").classes("text-lg font-semibold")
                ui.button(icon="close", on_click=dialog.close).props("flat round")
            if not campus.buildings:
                ui.label("Aucun bâtiment à positionner. Crée d'abord un bâtiment.").classes("text-gray-500")
            else:
                bg = blank_background(w_units, h_units)
                img = ui.interactive_image(
                    bg,
                    content=campus_map_content(campus, origin_x, origin_y),
                    on_mouse=on_campus_mouse,
                    events=["mousedown", "mousemove", "mouseup"],
                ).classes("w-full h-full")
                img_ref["el"] = img
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
                ui.label("Aucune salle ne correspond à la recherche.").classes("text-gray-500 py-4")

        def on_search_change(e) -> None:
            search["query"] = e.value or ""
            rows_view.refresh()

        with ui.dialog().props("maximized") as dialog, ui.card().classes("w-full h-full"):
            with ui.row().classes("items-center justify-between w-full mb-2"):
                ui.label("Toutes les salles").classes("text-lg font-semibold")
                ui.button(icon="close", on_click=dialog.close).props("flat round")

            has_any_room = any(floor.rooms for building in campus.buildings for floor in building.floors)
            if not has_any_room:
                ui.label("Aucune salle créée pour l'instant.").classes("text-gray-500")
            else:
                ui.input(
                    label="Rechercher une salle (nom, bâtiment, étage)...",
                    on_change=on_search_change,
                ).classes("w-full mb-2").props("clearable dense outlined")

                with ui.scroll_area().classes("w-full h-full"):
                    with ui.row().classes("w-full items-center gap-3 pb-2 border-b-2 border-gray-300 text-sm font-semibold text-gray-500"):
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

        with ui.row().classes("w-full items-center gap-3 py-1 border-b border-gray-100"):
            ui.label(building.name).classes("w-40 text-sm text-gray-600")
            ui.label(floor.name).classes("w-40 text-sm text-gray-600")
            ui.input(value=room.name, on_change=on_name_change).classes("flex-1").props("dense")
            ui.number(value=room.capacity, min=1, precision=0, on_change=on_capacity_change).classes("w-32").props("dense")

    with ui.header().classes("items-center justify-between"):
        ui.label("Administration du Campus").classes("text-lg font-semibold")
        with ui.row().classes("items-center gap-2"):
            ui.button("Toutes les salles", icon="table_rows", on_click=open_room_table_dialog).props("outline color=white")
            ui.button("Plan du campus", icon="map", on_click=open_campus_map_dialog).props("outline color=white")
            ui.button("Vue d'ensemble (isométrique)", icon="view_in_ar", on_click=open_overview_dialog).props("outline color=white")

    with ui.left_drawer().classes("gap-2 p-4"):
        ui.label("Sélection").classes("text-sm font-semibold text-gray-500")
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
            ui.label("Salles de l'étage").classes("text-sm font-semibold text-gray-500")
            ui.button("+ Salle", on_click=open_new_room_dialog).props("size=sm outline")
        room_list()

    with ui.column().classes("w-full h-full items-stretch p-4"):
        render_plan_area()

    ui.run(title="Administration Campus", reload=False)


if __name__ in {"__main__", "__mp_main__"}:
    main()
