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
    level: int = 0   # 0 = rez-de-chaussée, négatif = sous-sol, positif = étage
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
    position: Point = field(default_factory=lambda: [0.0, 0.0])
    floors: list[Floor] = field(default_factory=list)

    def add_floor(self, name: str, polygon: list[Point], level: int | None = None) -> Floor:
        if level is None:
            level = (max((f.level for f in self.floors), default=-1)) + 1
        floor = Floor(id=f"floor-{uuid.uuid4().hex[:8]}", name=name, level=level, polygon=polygon)
        self.floors.append(floor)
        return floor


BUILDING_DEFAULT_SPACING = 20.0


@dataclass
class Campus:
    id: str
    name: str
    buildings: list[Building] = field(default_factory=list)

    def add_building(self, name: str, position: Point | None = None) -> Building:
        if position is None:
            max_x = max((b.position[0] for b in self.buildings), default=-BUILDING_DEFAULT_SPACING)
            position = [max_x + BUILDING_DEFAULT_SPACING, 0.0]
        building = Building(id=f"bldg-{uuid.uuid4().hex[:8]}", name=name, position=position)
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
            for f_index, f in enumerate(b.get("floors", [])):
                rooms = [
                    Room(id=r["id"], name=r["name"], capacity=r["capacity"], position=r.get("position", [0.0, 0.0]))
                    for r in f.get("rooms", [])
                ]
                floors.append(
                    Floor(
                        id=f["id"],
                        name=f["name"],
                        level=f.get("level", f_index),
                        polygon=f.get("polygon", []),
                        rooms=rooms,
                    )
                )
            buildings.append(
                Building(id=b["id"], name=b["name"], position=b.get("position", [0.0, 0.0]), floors=floors)
            )
        return Campus(id=data["id"], name=data["name"], buildings=buildings)
