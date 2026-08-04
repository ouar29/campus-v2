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
from iso_view import build_overview_svg

DATA_PATH = "src/data.json"

PADDING = 2.0          # marge (en unités monde) autour du contour affiché
SCALE = 20              # pixels par unité monde
ROOM_RADIUS_UNITS = 1.0
DRAG_THRESHOLD_UNITS = 1.5   # distance max pour "attraper" une salle au clic

DEFAULT_CANVAS_W = 50.0  # unités monde, utilisé pour dessiner un nouvel étage
DEFAULT_CANVAS_H = 30.0


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
        if len(points) >= 3:
            parts.append(f'<polygon points="{line_points}" fill="#bfdbfe" fill-opacity="0.4" stroke="#1d4ed8" stroke-width="2" stroke-dasharray="6,4"/>')
        else:
            parts.append(f'<polyline points="{line_points}" fill="none" stroke="#1d4ed8" stroke-width="2" stroke-dasharray="6,4"/>')
        for px, py in px_points:
            parts.append(f'<circle cx="{px}" cy="{py}" r="5" fill="#1d4ed8"/>')
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
                    ui.label(f"Dessin du contour : « {state['pending_floor_name']} » — cliquez pour ajouter des sommets").classes("text-sm text-gray-600")
                    ui.button("Terminer", on_click=finish_floor_drawing).props("size=sm color=primary")
                    ui.button("Annuler", on_click=cancel_floor_drawing).props("size=sm flat")
                bg = blank_background(DEFAULT_CANVAS_W + 2 * PADDING, DEFAULT_CANVAS_H + 2 * PADDING)
                img = ui.interactive_image(
                    bg,
                    content=drawing_preview_content(state["pending_points"], origin_x, origin_y),
                    on_mouse=on_mouse,
                    events=["mousedown"],
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
        with ui.dialog() as dialog, ui.card():
            ui.label("Nouvel étage").classes("text-lg font-semibold")
            name_input = ui.input("Nom de l'étage (ex : RDC, 1er étage)").classes("w-full")

            def confirm() -> None:
                if not name_input.value:
                    ui.notify("Le nom est requis", color="warning")
                    return
                state["mode"] = "drawing_floor"
                state["pending_floor_name"] = name_input.value
                state["pending_points"] = []
                dialog.close()
                render_plan_area()

            with ui.row().classes("justify-end w-full mt-2"):
                ui.button("Annuler", on_click=dialog.close).props("flat")
                ui.button("Dessiner le contour", on_click=confirm)
        dialog.open()

    def finish_floor_drawing() -> None:
        if len(state["pending_points"]) < 3:
            ui.notify("Il faut au moins 3 points pour former un contour", color="warning")
            return
        floor = state["building"].add_floor(state["pending_floor_name"], state["pending_points"])
        save()
        state["mode"] = None
        state["pending_floor_name"] = None
        state["pending_points"] = []
        state["floor"] = floor
        floor_select.set_options(floors_options(state["building"]))
        floor_select.value = floor.id
        room_list.refresh()
        render_plan_area()

    def cancel_floor_drawing() -> None:
        state["mode"] = None
        state["pending_floor_name"] = None
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
    # Vue d'ensemble isométrique
    # ------------------------------------------------------------------

    def open_overview_dialog() -> None:
        with ui.dialog().props("maximized") as dialog, ui.card().classes("w-full h-full"):
            with ui.row().classes("items-center justify-between w-full"):
                ui.label("Vue d'ensemble du campus").classes("text-lg font-semibold")
                ui.button(icon="close", on_click=dialog.close).props("flat round")
            ui.html(build_overview_svg(campus)).classes("w-full h-full")
        dialog.open()

    with ui.header().classes("items-center justify-between"):
        ui.label("Administration du Campus").classes("text-lg font-semibold")
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
