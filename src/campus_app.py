"""Application graphique du campus.

Ce module contient l’interface utilisateur et la logique de composition de
l’application. Le point d’entrée reste volontairement minimal dans main.py.
"""
from __future__ import annotations

import base64
import json
import shutil
import uuid
import sys
from pathlib import Path

import platformdirs
from nicegui import events, native, ui

from controller import CampusController
from export_cps import export_campus
from import_cps import convert as convert_cps

async def _read_uploaded_file(event) -> tuple[str, bytes] | None:
    file = getattr(event, "file", None)
    if file is None:
        return None
    file_name = getattr(file, "name", "") or "campus.cps"
    try:
        data = file.read()
    except TypeError:
        return None
    if hasattr(data, "__await__"):
        data = await data
    return file_name, bytes(data)
from geometry import (
    DRAG_THRESHOLD_UNITS,
    EDGE_INSERT_THRESHOLD,
    VERTEX_DRAG_THRESHOLD,
    campus_transform,
    building_footprint,
    nearest_edge_insertion,
    nearest_vertex,
    px_to_world,
    transform_for_floor,
)
from iso_view import PALETTE, build_overview_parts
from model import Building, Campus, Floor, Room
from rendering import (
    blank_background,
    campus_map_parts,
    drawing_preview_content,
    floor_edit_content,
    floor_plan_content,
    text_scale_for_canvas,
)
from ui.dialogs import (
    open_new_building_dialog as open_new_building_dialog_ui,
    open_new_floor_dialog as open_new_floor_dialog_ui,
    open_new_room_dialog as open_new_room_dialog_ui,
)
from ui.layout import build_header, build_sidebar, build_main_area
from ui.theme import apply_theme
from ui.views import (
    open_campus_map_dialog,
    open_gestionnaires_dialog,
    open_validation_dialog,
)
from ui.campus_overview_view import open_overview_dialog

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

PADDING = 2.0
SCALE = 20
ROOM_RADIUS_UNITS = 1.0
DRAG_THRESHOLD_UNITS = 1.5
DEFAULT_CANVAS_W = 50.0
DEFAULT_CANVAS_H = 30.0

CAMPUS_ICON_SIZE = 8.0
CAMPUS_PADDING = 15.0

VERTEX_DRAG_THRESHOLD = 1.2
EDGE_INSERT_THRESHOLD = 0.9

def get_resource_path(relative_path: str) -> Path:
    """Obtient le chemin absolu vers une ressource, fonctionne en dev et avec PyInstaller."""
    if hasattr(sys, "_MEIPASS"):
        # Mode PyInstaller (dossier temporaire/interne)
        base_path = Path(sys._MEIPASS)
    else:
        # Mode développement classique (racine du projet)
        base_path = Path(__file__).resolve().parent.parent

    return base_path / relative_path


APP_NAME = "AdministrationCampus"
APP_AUTHOR = "CampusAdmin"  # à adapter au nom de ton organisation si besoin

DEFAULT_CAMPUS_TEMPLATE = {"id": "campus-default", "name": "Campus", "buildings": [], "extra": {}}


def get_data_path() -> Path:
    """Retourne le chemin du data.json à utiliser pour la lecture/écriture.

    En dev (lancé depuis les sources), on reste sur le fichier du dépôt —
    pratique pour éditer/versionner les données de test directement.

    En build PyInstaller, il ne faut JAMAIS écrire dans le bundle : en mode
    --onefile, `sys._MEIPASS` pointe vers un dossier temporaire supprimé à
    la fermeture de l'application, donc toute sauvegarde y serait perdue au
    prochain lancement (et en --onedir, écrire dans le dossier d'install
    pose des soucis de droits/mises à jour). On utilise donc un dossier de
    données utilisateur stable (AppData sous Windows, Application Support
    sous macOS, ~/.local/share sous Linux), et on y copie le data.json
    embarqué au tout premier lancement s'il n'existe pas encore.
    """
    if not getattr(sys, "frozen", False):
        return get_resource_path("src/data.json")

    user_dir = Path(platformdirs.user_data_dir(APP_NAME, APP_AUTHOR))
    user_dir.mkdir(parents=True, exist_ok=True)
    user_data_path = user_dir / "data.json"

    if not user_data_path.exists():
        bundled_default = get_resource_path("src/data.json")
        if bundled_default.exists():
            shutil.copy(bundled_default, user_data_path)
        else:
            # Pas de data.json embarqué (ne devrait pas arriver si le build
            # inclut bien --add-data pour src/data.json) : on démarre à vide
            # plutôt que de planter.
            user_data_path.write_text(
                json.dumps(DEFAULT_CAMPUS_TEMPLATE, indent=2, ensure_ascii=False), encoding="utf-8"
            )
    return user_data_path


class CampusApp:
    def __init__(self) -> None:
        self.dark = apply_theme()
        self.data_path = get_data_path()
        self.campus = Campus.load(self.data_path)
        self.sessions = [{
            "key": "session-default",
            "label": self.campus.name or "Campus",
            "campus": self.campus,
        }]
        self.current_session_key = self.sessions[0]["key"]
        self.controller = CampusController(self.campus, self.data_path)
        self.campus_service = self.controller.campus_service
        self.floor_service = self.controller.floor_service
        self.room_service = self.controller.room_service
        self.state = self.controller.state
        self.building_select = None
        self.floor_select = None
        self.session_select = None
        self.plan_container = None

    def _ensure_session_state(self) -> None:
        if not hasattr(self, "sessions") or not self.sessions:
            self.sessions = [{
                "key": "session-default",
                "label": getattr(self.campus, "name", "Campus") or "Campus",
                "campus": self.campus,
            }]
        if not hasattr(self, "current_session_key") or not self.current_session_key:
            self.current_session_key = self.sessions[0]["key"]

    def _replace_active_campus(self, campus: Campus, label: str | None = None) -> None:
        self._ensure_session_state()
        self.campus = campus
        self.controller = CampusController(self.campus, self.data_path)
        self.campus_service = self.controller.campus_service
        self.floor_service = self.controller.floor_service
        self.room_service = self.controller.room_service
        self.state = self.controller.state
        if label:
            self.current_session_key = next(
                (session["key"] for session in self.sessions if session["campus"] is campus),
                self.current_session_key,
            )

    def session_options(self) -> dict[str, str]:
        return {session["key"]: session["label"] for session in self.sessions}

    def current_session_label(self) -> str:
        for session in self.sessions:
            if session["key"] == self.current_session_key:
                return session["label"]
        return self.sessions[0]["label"] if self.sessions else "Campus"

    def add_session(self, campus: Campus, label: str | None = None) -> str:
        self._ensure_session_state()
        session_label = (label or campus.name or "Campus").strip() or "Campus"
        session_key = f"session-{uuid.uuid4().hex[:8]}"
        self.sessions.append({"key": session_key, "label": session_label, "campus": campus})
        self.current_session_key = session_key
        self._replace_active_campus(campus, session_label)
        self.save()
        if hasattr(self, "session_select") and self.session_select is not None:
            self.session_select.set_options(self.session_options())
            self.session_select.value = session_key
        return session_key

    def switch_session(self, session_key: str | None) -> None:
        if not session_key:
            return
        for session in self.sessions:
            if session["key"] == session_key:
                self.current_session_key = session_key
                self._replace_active_campus(session["campus"], session["label"])
                self.save()
                if hasattr(self, "session_select") and self.session_select is not None:
                    self.session_select.value = session_key
                self._refresh_campus_selection()
                self.render_plan_area()
                return

    def save(self) -> None:
        self.controller.save()

    def get_building(self, building_id: str) -> Building | None:
        return next((b for b in self.campus.buildings if b.id == building_id), None)

    def get_floor(self, building: Building, floor_id: str) -> Floor | None:
        return next((f for f in building.floors if f.id == floor_id), None)

    def buildings_options(self) -> dict[str, str]:
        return {b.id: b.name for b in self.campus.buildings}

    def floors_options(self, building: Building | None) -> dict[str, str]:
        return {f.id: f.name for f in building.floors} if building else {}

    @ui.refreshable
    def room_list(self) -> None:
        floor = self.state["floor"]
        if floor is None or not floor.rooms:
            ui.label("Aucune salle sur cet étage.").classes("text-sm text-gray-500 dark:text-gray-300")
            return
        for room in floor.rooms:
            with ui.row().classes("items-center gap-2 w-full py-1 border-b border-gray-100 dark:border-gray-700"):
                ui.icon("meeting_room").classes("text-blue-600 dark:text-indigo-300")
                ui.label(room.name).classes("font-medium grow")
                ui.label(f"{room.capacity} pers.").classes("text-sm text-gray-500 dark:text-gray-300")

    def build(self) -> None:
        self.plan_container = ui.column().classes("w-full h-full")
        self._bind_layout()

    def _bind_layout(self) -> None:
        build_header(self)
        build_sidebar(self)
        build_main_area(self)

    def start_geometry_edit(self) -> None:
        if self.state["floor"] is None:
            ui.notify("Sélectionne d'abord un étage", color="warning")
            return
        self.state["mode"] = "editing_geometry"
        self.state["dragging_vertex_index"] = None
        self.render_plan_area()

    def stop_geometry_edit(self) -> None:
        self.state["mode"] = None
        self.state["dragging_vertex_index"] = None
        self.render_plan_area()

    def render_plan_area(self) -> None:
        if self.plan_container is None:
            return
        self.plan_container.clear()
        with self.plan_container:
            mode = self.state["mode"]

            if mode == "drawing_floor":
                origin_x, origin_y = -PADDING, -PADDING
                with ui.row().classes("items-center gap-2 mb-2"):
                    ui.label(
                        f"Dessin du contour : « {self.state['pending_floor_name']} » — "
                        f"cliquez pour ajouter des sommets, double-cliquez pour fermer le contour"
                    ).classes("text-sm text-gray-600 dark:text-gray-300")
                    ui.button("Terminer", on_click=self.finish_floor_drawing).props("size=sm color=primary")
                    ui.button("Annuler", on_click=self.cancel_floor_drawing).props("size=sm flat")
                bg = blank_background(DEFAULT_CANVAS_W + 2 * PADDING, DEFAULT_CANVAS_H + 2 * PADDING)
                img = ui.interactive_image(
                    bg,
                    content=drawing_preview_content(self.state["pending_points"], origin_x, origin_y),
                    on_mouse=self.on_mouse,
                    events=["mousedown", "dblclick"],
                ).classes("w-full").style("max-width: 900px")
                self.state["plan_image"] = img
                return

            floor = self.state["floor"]
            if floor is None:
                ui.label("Aucun étage sélectionné. Crée un bâtiment puis un étage pour commencer.").classes("text-gray-500 dark:text-gray-300")
                self.state["plan_image"] = None
                return

            if mode == "editing_geometry":
                origin_x, origin_y, w_units, h_units = transform_for_floor(floor)
                text_scale = text_scale_for_canvas(w_units)
                with ui.row().classes("items-center gap-2 mb-2"):
                    ui.label(
                        "Édition du contour — glisse un sommet (orange), double-clique dessus pour le "
                        "supprimer, clique sur une arête pour y ajouter un sommet"
                    ).classes("text-sm text-gray-600 dark:text-gray-300")
                    ui.button("Terminer l'édition", on_click=self.stop_geometry_edit).props("size=sm color=primary")
                bg = blank_background(w_units, h_units)
                img = ui.interactive_image(
                    bg,
                    content=floor_edit_content(floor, origin_x, origin_y, text_scale),
                    on_mouse=self.on_mouse,
                    events=["mousedown", "mousemove", "mouseup", "dblclick"],
                ).classes("w-full").style("max-width: 900px")
                self.state["plan_image"] = img
                return

            if self.state["mode"] == "placing_room":
                ui.label(f"Clique sur le plan pour placer « {self.state['pending_room_name']} »").classes("text-sm text-blue-600 dark:text-indigo-300 mb-2")
            else:
                with ui.row().classes("items-center gap-2 mb-2"):
                    ui.button("Éditer le contour de cet étage", icon="edit", on_click=self.start_geometry_edit).props("size=sm outline")

            origin_x, origin_y, w_units, h_units = transform_for_floor(floor)
            text_scale = text_scale_for_canvas(w_units)
            bg = blank_background(w_units, h_units)
            img = ui.interactive_image(
                bg,
                content=floor_plan_content(floor, origin_x, origin_y, text_scale),
                on_mouse=self.on_mouse,
                events=["mousedown", "mousemove", "mouseup", "dblclick"],
            ).classes("w-full").style("max-width: 900px")
            self.state["plan_image"] = img

    def on_mouse(self, e: events.MouseEventArguments) -> None:
        mode = self.state["mode"]

        if mode == "editing_geometry":
            floor = self.state["floor"]
            if floor is None:
                return
            origin_x, origin_y, w_units, _ = transform_for_floor(floor)
            text_scale = text_scale_for_canvas(w_units)
            wx, wy = px_to_world(e.image_x, e.image_y, origin_x, origin_y)

            def redraw_edit() -> None:
                if self.state["plan_image"] is not None:
                    self.state["plan_image"].content = floor_edit_content(floor, origin_x, origin_y, text_scale)

            if e.type == "dblclick":
                idx, dist = nearest_vertex(floor.polygon, wx, wy)
                if idx is not None and dist <= VERTEX_DRAG_THRESHOLD and len(floor.polygon) > 3:
                    floor.polygon.pop(idx)
                    self.save()
                    redraw_edit()
                elif idx is not None and len(floor.polygon) <= 3:
                    ui.notify("Un contour doit garder au moins 3 sommets", color="warning")
                return

            if e.type == "mousedown":
                idx, dist = nearest_vertex(floor.polygon, wx, wy)
                if idx is not None and dist <= VERTEX_DRAG_THRESHOLD:
                    self.state["dragging_vertex_index"] = idx
                    return
                insertion = nearest_edge_insertion(floor.polygon, wx, wy, EDGE_INSERT_THRESHOLD)
                if insertion is not None:
                    insert_idx, point = insertion
                    floor.polygon.insert(insert_idx, [round(point[0], 2), round(point[1], 2)])
                    self.state["dragging_vertex_index"] = insert_idx
                    self.save()
                    redraw_edit()
                return

            if e.type == "mousemove":
                idx = self.state.get("dragging_vertex_index")
                if idx is None:
                    return
                floor.polygon[idx] = [round(wx, 2), round(wy, 2)]
                redraw_edit()
                return

            if e.type == "mouseup":
                if self.state.get("dragging_vertex_index") is not None:
                    self.save()
                    self.state["dragging_vertex_index"] = None
                return
            return

        if mode == "drawing_floor":
            if e.type == "dblclick":
                if self.state["pending_points"]:
                    self.state["pending_points"].pop()
                self.finish_floor_drawing()
                return
            if e.type != "mousedown":
                return
            origin_x, origin_y = -PADDING, -PADDING
            wx, wy = px_to_world(e.image_x, e.image_y, origin_x, origin_y)
            self.state["pending_points"].append([round(wx, 2), round(wy, 2)])
            if self.state["plan_image"] is not None:
                self.state["plan_image"].content = drawing_preview_content(self.state["pending_points"], origin_x, origin_y)
            return

        floor = self.state["floor"]
        if floor is None:
            return
        origin_x, origin_y, w_units, _ = transform_for_floor(floor)
        text_scale = text_scale_for_canvas(w_units)
        wx, wy = px_to_world(e.image_x, e.image_y, origin_x, origin_y)

        if mode == "placing_room":
            if e.type != "mousedown":
                return
            try:
                self.room_service.create_room(
                    floor,
                    self.state["pending_room_name"],
                    self.state["pending_room_capacity"],
                    [round(wx, 2), round(wy, 2)],
                )
            except ValueError as exc:
                ui.notify(str(exc), color="warning")
                return
            self.save()
            self.state["mode"] = None
            self.state["pending_room_name"] = None
            self.state["pending_room_capacity"] = None
            self.room_list.refresh()
            self.render_plan_area()
            return

        if e.type == "dblclick":
            nearest = min(
                floor.rooms,
                key=lambda r: (r.position[0] - wx) ** 2 + (r.position[1] - wy) ** 2,
                default=None,
            )
            if nearest is not None:
                dist = ((nearest.position[0] - wx) ** 2 + (nearest.position[1] - wy) ** 2) ** 0.5
                if dist <= DRAG_THRESHOLD_UNITS:
                    self.open_room_table_dialog(focus_room_id=nearest.id)
            return

        if e.type == "mousedown":
            nearest = min(
                floor.rooms,
                key=lambda r: (r.position[0] - wx) ** 2 + (r.position[1] - wy) ** 2,
                default=None,
            )
            if nearest is not None:
                dist = ((nearest.position[0] - wx) ** 2 + (nearest.position[1] - wy) ** 2) ** 0.5
                if dist <= DRAG_THRESHOLD_UNITS:
                    self.state["dragging_room_id"] = nearest.id

        elif e.type == "mousemove":
            if self.state["dragging_room_id"] is None:
                return
            room = next((r for r in floor.rooms if r.id == self.state["dragging_room_id"]), None)
            if room is None:
                return
            room.position = [round(wx, 2), round(wy, 2)]
            if self.state["plan_image"] is not None:
                self.state["plan_image"].content = floor_plan_content(floor, origin_x, origin_y, text_scale)

        elif e.type == "mouseup":
            if self.state["dragging_room_id"] is not None:
                self.save()
                self.state["dragging_room_id"] = None
                self.room_list.refresh()

    def open_new_building_dialog(self) -> None:
        open_new_building_dialog_ui(
            self.campus,
            self.state,
            self.save,
            self.building_select,
            self.floor_select,
            self.room_list,
            self.render_plan_area,
        )

    def open_new_floor_dialog(self) -> None:
        open_new_floor_dialog_ui(
            self.campus,
            self.state,
            self.save,
            self.floor_select,
            self.room_list,
            self.render_plan_area,
        )

    def open_new_room_dialog(self) -> None:
        open_new_room_dialog_ui(self.state, self.save, self.room_list, self.render_plan_area)

    def finish_floor_drawing(self) -> None:
        if len(self.state["pending_points"]) < 3:
            ui.notify("Il faut au moins 3 points pour former un contour", color="warning")
            return
        try:
            floor = self.floor_service.create_floor(
                self.state["building"],
                self.state["pending_floor_name"],
                self.state["pending_points"],
                level=self.state.get("pending_floor_level"),
            )
        except ValueError as exc:
            ui.notify(str(exc), color="warning")
            return
        self.save()
        self.state["mode"] = None
        self.state["pending_floor_name"] = None
        self.state["pending_floor_level"] = None
        self.state["pending_points"] = []
        self.state["floor"] = floor
        self.floor_select.set_options(self.floors_options(self.state["building"]))
        self.floor_select.value = floor.id
        self.room_list.refresh()
        self.render_plan_area()

    def cancel_floor_drawing(self) -> None:
        self.state["mode"] = None
        self.state["pending_floor_name"] = None
        self.state["pending_floor_level"] = None
        self.state["pending_points"] = []
        self.render_plan_area()

    def on_building_change(self, building_id: str) -> None:
        building = self.get_building(building_id)
        self.state["building"] = building
        self.state["floor"] = building.floors[0] if building and building.floors else None
        if self.floor_select is not None:
            self.floor_select.set_options(self.floors_options(building))
            self.floor_select.value = self.state["floor"].id if self.state["floor"] else None
        self.room_list.refresh()
        self.render_plan_area()

    def on_floor_change(self, floor_id: str) -> None:
        building = self.state["building"]
        if building:
            self.state["floor"] = self.get_floor(building, floor_id)
        self.room_list.refresh()
        self.render_plan_area()

    def open_campus_map_dialog(self) -> None:
        open_campus_map_dialog(self)

    def open_overview_dialog(self) -> None:
        open_overview_dialog(self)

    def open_room_table_dialog(self, focus_room_id: str | None = None) -> None:
        open_room_table_dialog(self, focus_room_id=focus_room_id)

    def open_gestionnaires_dialog(self) -> None:
        open_gestionnaires_dialog(self)

    def open_validation_dialog(self) -> None:
        open_validation_dialog(self)

    def _refresh_campus_selection(self) -> None:
        if hasattr(self, "session_select") and self.session_select is not None:
            self.session_select.set_options(self.session_options())
            self.session_select.value = self.current_session_key
        if self.building_select is not None:
            self.building_select.set_options(self.buildings_options())
            current_building_id = self.state["building"].id if self.state["building"] else None
            self.building_select.value = current_building_id
        if self.floor_select is not None:
            building = self.state["building"]
            self.floor_select.set_options(self.floors_options(building))
            current_floor_id = self.state["floor"].id if self.state["floor"] else None
            self.floor_select.value = current_floor_id
        self.room_list.refresh()
        self.render_plan_area()

    def import_cps_dialog(self) -> None:
        with ui.dialog() as dialog, ui.card().classes("w-[420px] max-w-[90vw]"):
            ui.label("Importer un campus depuis un fichier .cps").classes("text-lg font-semibold mb-2")
            upload = ui.upload(
                label="Choisir un fichier .cps",
                auto_upload=True,
                on_upload=lambda e: self._on_cps_import(e, dialog),
            ).props("accept=.cps")
            ui.button("Fermer", on_click=dialog.close).props("flat").classes("mt-3")
        dialog.open()

    async def _on_cps_import(self, event, dialog) -> None:
        payload = await _read_uploaded_file(event)
        if payload is None:
            ui.notify("Aucun fichier reçu pour l’import .cps", color="negative")
            return

        file_name, content = payload
        if not file_name.lower().endswith(".cps"):
            ui.notify("Le fichier doit avoir l’extension .cps", color="negative")
            return

        tmp_dir = Path.cwd() / ".campus-import-tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = tmp_dir / f"campus-import-{uuid.uuid4().hex}.cps"
        try:
            tmp_path.write_bytes(content)
            campus, skipped = convert_cps(str(tmp_path))
        except Exception as exc:
            ui.notify(f"Échec de l’import .cps : {exc}", color="negative")
            return
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass

        session_label = file_name.rsplit(".", 1)[0] if file_name.lower().endswith(".cps") else campus.name
        self.add_session(campus, session_label)

        if dialog is not None:
            try:
                dialog.close()
            except Exception:
                pass

        self._refresh_campus_selection()
        self.render_plan_area()

        if skipped:
            ui.notify(f"Import terminé avec {skipped} salle(s) ignorée(s) hors périmètre", color="warning")
        else:
            ui.notify("Campus importé avec succès", color="positive")
        dialog.close()

    def export_cps_dialog(self) -> None:
        default_name = f"{self.campus.name.lower().replace(' ', '_') or 'campus'}.cps"
        with ui.dialog() as dialog, ui.card().classes("w-[480px] max-w-[90vw]"):
            ui.label("Exporter le campus vers un fichier .cps").classes("text-lg font-semibold mb-2")
            file_name = ui.input("Nom du fichier", value=default_name).props("outlined")
            with ui.row().classes("w-full justify-end mt-3"):
                ui.button("Fermer", on_click=dialog.close).props("flat")
                ui.button("Exporter", on_click=lambda: self._on_cps_export(file_name.value, dialog)).props("color=primary")
        dialog.open()

    def _on_cps_export(self, file_name: str, dialog) -> None:
        target = (file_name or "campus_export.cps").strip()
        if not target.lower().endswith(".cps"):
            target = f"{target}.cps"

        path = Path(target).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        path.parent.mkdir(parents=True, exist_ok=True)

        try:
            payload = export_campus(self.campus)
            path.write_text(__import__("json").dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as exc:
            ui.notify(f"Échec de l’export .cps : {exc}", color="negative")
            return

        ui.notify(f"Exporté vers {path}", color="positive")
        try:
            ui.download(str(path))
        except Exception:
            pass
        dialog.close()

    def run(self) -> None:
        """Conservée pour compatibilité (ex. lancement direct d'une instance
        existante) — l'entrée normale de l'app passe par main(), qui construit
        l'UI dans une route @ui.page explicite (voir plus bas)."""
        ui.run(
            title="Administration Campus",
            favicon="🚀",
            port=native.find_open_port(),
            reload=False,
            show=True)


def main() -> None:
    # L'UI doit être construite dans une route explicite (@ui.page) plutôt
    # qu'au niveau du script : sans ça, NiceGUI 3.0 reconstruit la page en
    # ré-exécutant tout le script principal via runpy à chaque requête
    # (mode "script"/auto-index). Ça fonctionne en dev (sys.argv[0] est un
    # vrai fichier .py), mais plante dans l'exécutable PyInstaller — où
    # sys.argv[0] pointe vers le binaire compilé, pas du code source lisible
    # ("SyntaxError: source code string cannot contain null bytes").
    # Chaque nouvelle connexion crée sa propre instance de CampusApp, qui
    # recharge l'état depuis data.json — exactement le comportement qu'on
    # avait implicitement avant (le script entier était ré-exécuté à chaque
    # requête), mais sans dépendre de ce mécanisme fragile.
    @ui.page("/")
    def index() -> None:
        CampusApp().build()

    ui.run(
        title="Administration Campus",
        favicon="🚀",
        port=native.find_open_port(),
        reload=False,
        show=True)
