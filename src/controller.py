from __future__ import annotations

from model import Campus, Building, Floor
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
