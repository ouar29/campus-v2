"""Modèle de données pour l'administration du campus.

Hiérarchie : Campus -> Buildings -> Floors (polygone) -> Rooms (polygone, nom, capacité)

Les polygones sont stockés comme des listes de points [x, y] (float),
dans le repère local de leur parent (un étage est dessiné dans son propre
repère, une salle est dessinée dans le repère de son étage).
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path

Point = list[float]  # [x, y]


@dataclass
class Room:
    id: str
    name: str
    capacity: int
    position: Point = field(default_factory=lambda: [0.0, 0.0])


@dataclass
class Floor:
    id: str
    name: str
    polygon: list[Point] = field(default_factory=list)
    rooms: list[Room] = field(default_factory=list)

    def add_room(self, name: str, capacity: int, position: Point) -> Room:
        room = Room(id=f"room-{uuid.uuid4().hex[:8]}", name=name, capacity=capacity, position=position)
        self.rooms.append(room)
        return room


@dataclass
class Building:
    id: str
    name: str
    floors: list[Floor] = field(default_factory=list)

    def add_floor(self, name: str, polygon: list[Point]) -> Floor:
        floor = Floor(id=f"floor-{uuid.uuid4().hex[:8]}", name=name, polygon=polygon)
        self.floors.append(floor)
        return floor


@dataclass
class Campus:
    id: str
    name: str
    buildings: list[Building] = field(default_factory=list)

    def add_building(self, name: str) -> Building:
        building = Building(id=f"bldg-{uuid.uuid4().hex[:8]}", name=name)
        self.buildings.append(building)
        return building

    # ---------- Persistance JSON ----------

    @staticmethod
    def load(path: str | Path) -> "Campus":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return Campus._from_dict(data)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8"
        )

    @staticmethod
    def _from_dict(data: dict) -> "Campus":
        buildings = []
        for b in data.get("buildings", []):
            floors = []
            for f in b.get("floors", []):
                rooms = [
                    Room(id=r["id"], name=r["name"], capacity=r["capacity"], position=r.get("position", [0.0, 0.0]))
                    for r in f.get("rooms", [])
                ]
                floors.append(
                    Floor(id=f["id"], name=f["name"], polygon=f.get("polygon", []), rooms=rooms)
                )
            buildings.append(Building(id=b["id"], name=b["name"], floors=floors))
        return Campus(id=data["id"], name=data["name"], buildings=buildings)
