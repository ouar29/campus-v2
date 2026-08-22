from __future__ import annotations

import uuid

from model import Campus, Building, Floor, Gestionnaire, Room
from services.campus_service import CampusService
from services.floor_service import FloorService
from services.room_service import RoomService


class CampusController:
    def __init__(self, campus: Campus, data_path: str):
        self.campus = campus
        self.data_path = data_path
        self.campus_service = CampusService(campus)
        self.floor_service = FloorService(campus)
        self.room_service = RoomService(campus)

        self.state: dict = {
            "building": campus.buildings[0] if campus.buildings else None,
            "floor": None,
            "mode": None,
            "pending_floor_name": None,
            "pending_floor_level": None,
            "pending_points": [],
            "pending_room_name": None,
            "pending_room_capacity": None,
            "dragging_room_id": None,
            "dragging_vertex_index": None,
            "plan_image": None,
        }
        if self.state["building"] and self.state["building"].floors:
            self.state["floor"] = self.state["building"].floors[0]

    def save(self) -> None:
        self.campus.save(self.data_path)

    def get_building(self, building_id: str) -> Building | None:
        return next((b for b in self.campus.buildings if b.id == building_id), None)

    def get_floor(self, building: Building, floor_id: str) -> Floor | None:
        return next((f for f in building.floors if f.id == floor_id), None)

    def _iter_rooms(self):
        for building in self.campus.buildings:
            for floor in building.floors:
                yield from floor.rooms

    def get_room(self, room_id: str) -> Room | None:
        return next((r for r in self._iter_rooms() if r.id == room_id), None)

    # ---------- Gestionnaires de salles ----------

    def get_gestionnaires(self) -> list[Gestionnaire]:
        return self.campus.gestionnaires

    def get_gestionnaire(self, gestionnaire_id: str) -> Gestionnaire | None:
        return next((g for g in self.campus.gestionnaires if g.id == gestionnaire_id), None)

    def add_gestionnaire(self, nom: str, email: str = "", telephone: str = "") -> Gestionnaire:
        gestionnaire = Gestionnaire(id=f"gest-{uuid.uuid4().hex[:8]}", nom=nom, email=email, telephone=telephone)
        self.campus.gestionnaires.append(gestionnaire)
        self.save()
        return gestionnaire

    def update_gestionnaire(self, gestionnaire_id: str, **changes) -> None:
        gestionnaire = self.get_gestionnaire(gestionnaire_id)
        if gestionnaire is None:
            raise ValueError(f"Gestionnaire introuvable : {gestionnaire_id}")
        for key, value in changes.items():
            setattr(gestionnaire, key, value)
        self.save()

    def delete_gestionnaire(self, gestionnaire_id: str, *, cascade: bool = True) -> None:
        rooms_using = [r for r in self._iter_rooms() if gestionnaire_id in r.gestionnaire_ids]
        if rooms_using and not cascade:
            raise ValueError(f"Gestionnaire assigné à {len(rooms_using)} salle(s), suppression bloquée.")
        for room in rooms_using:
            room.gestionnaire_ids = [gid for gid in room.gestionnaire_ids if gid != gestionnaire_id]
        self.campus.gestionnaires = [g for g in self.campus.gestionnaires if g.id != gestionnaire_id]
        self.save()

    def get_rooms_for_gestionnaire(self, gestionnaire_id: str) -> list[Room]:
        return [r for r in self._iter_rooms() if gestionnaire_id in r.gestionnaire_ids]

    def assign_gestionnaires_to_room(self, room_id: str, gestionnaire_ids: list[str]) -> None:
        room = self.get_room(room_id)
        if room is None:
            raise ValueError(f"Salle introuvable : {room_id}")
        unknown = [gid for gid in gestionnaire_ids if self.get_gestionnaire(gid) is None]
        if unknown:
            raise ValueError(f"Gestionnaire(s) introuvable(s) : {unknown}")
        room.gestionnaire_ids = list(dict.fromkeys(gestionnaire_ids))
        self.save()

    def buildings_options(self) -> dict[str, str]:
        return {b.id: b.name for b in self.campus.buildings}

    def floors_options(self, building: Building | None) -> dict[str, str]:
        return {f.id: f.name for f in building.floors} if building else {}

    def create_building(self, name: str) -> Building:
        building = self.campus_service.create_building(name)
        self.state["building"] = building
        self.state["floor"] = None
        self.save()
        return building

    def create_floor(self, building: Building, name: str, polygon, level=None) -> Floor:
        floor = self.floor_service.create_floor(building, name, polygon, level=level)
        self.state["building"] = building
        self.state["floor"] = floor
        self.save()
        return floor

    def create_room(self, floor: Floor, name: str, capacity: int, position) -> None:
        self.room_service.create_room(floor, name, capacity, position)
        self.save()

    def on_building_change(self, building_id: str) -> None:
        building = self.get_building(building_id)
        self.state["building"] = building
        self.state["floor"] = building.floors[0] if building and building.floors else None

    def on_floor_change(self, floor_id: str) -> None:
        building = self.state["building"]
        if building:
            self.state["floor"] = self.get_floor(building, floor_id)
