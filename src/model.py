"""Modèle de données pour l'administration du campus.

Hiérarchie : Campus -> Buildings -> Floors (polygone) -> Rooms (polygone, nom, capacité)

Les polygones sont stockés comme des listes de points [x, y] (float),
dans le repère local de leur parent (un étage est dessiné dans son propre
repère, une salle est dessinée dans le repère de son étage).

Chaque entité porte aussi un champ `extra` : un dictionnaire libre qui
conserve tous les champs d'origine non gérés explicitement par notre
modèle (ex : import depuis un fichier .cps d'un autre projet — access,
equipments, roomManagers, dimensions, zoneMarkers, id numérique d'origine,
etc.). Cela permet un ré-export fidèle vers ce format d'origine (voir
export_cps.py) sans perdre d'information, même si notre UI ne manipule
que name/capacity/position/polygon.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

Point = list[float]  # [x, y]

@dataclass
class Gestionnaire:
    id: str
    nom: str
    email: str = ""
    telephone: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "nom": self.nom,
            "email": self.email,
            "telephone": self.telephone,
        }

    @staticmethod
    def from_dict(data: dict) -> "Gestionnaire":
        return Gestionnaire(
            id=data["id"],
            nom=data.get("nom", ""),
            email=data.get("email", ""),
            telephone=data.get("telephone", ""),
        )

def _room_manager_key(name: str, email: str) -> tuple[str, str]:
    return name.strip().lower(), (email or "").strip().lower()


def migrate_room_managers(campus: "Campus") -> int:
    """Fusionne les anciens `extra["roomManagers"]` (liste libre par salle,
    héritée du format .cps d'origine) dans l'annuaire partagé
    `campus.gestionnaires`, et relie chaque salle via `gestionnaire_ids`.

    Les gestionnaires sont dédupliqués par (nom, email), insensible à la
    casse. Le champ `extra["roomManagers"]` est retiré une fois migré : il
    ne doit plus subsister qu'une seule source de vérité pour les
    gestionnaires de salle. `export_cps.py` doit reconstruire `roomManagers`
    à partir de `gestionnaire_ids` au moment de l'export, pour rester
    conforme au format .cps d'origine.

    Retourne le nombre de gestionnaires nouvellement créés.
    """
    lookup: dict[tuple[str, str], Gestionnaire] = {
        _room_manager_key(g.nom, g.email): g for g in campus.gestionnaires
    }
    created = 0

    for building in campus.buildings:
        for floor in building.floors:
            for room in floor.rooms:
                legacy = room.extra.pop("roomManagers", None)
                if not legacy:
                    continue
                for m in legacy.get("value", []):
                    name = (m.get("name") or "").strip()
                    if not name:
                        continue
                    email = (m.get("email") or "").strip()
                    telephone = (m.get("telephoneNumber") or "").strip()
                    key = _room_manager_key(name, email)
                    gestionnaire = lookup.get(key)
                    if gestionnaire is None:
                        gestionnaire = Gestionnaire(
                            id=f"gest-{uuid.uuid4().hex[:8]}", nom=name, email=email, telephone=telephone
                        )
                        campus.gestionnaires.append(gestionnaire)
                        lookup[key] = gestionnaire
                        created += 1
                    elif telephone and not gestionnaire.telephone:
                        gestionnaire.telephone = telephone
                    if gestionnaire.id not in room.gestionnaire_ids:
                        room.gestionnaire_ids.append(gestionnaire.id)

    return created


@dataclass
class Room:
    id: str
    name: str
    capacity: int
    position: Point = field(default_factory=lambda: [0.0, 0.0])
    gestionnaire_ids: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Floor:
    id: str
    name: str
    level: int = 0   # 0 = rez-de-chaussée, négatif = sous-sol, positif = étage
    polygon: list[Point] = field(default_factory=list)
    rooms: list[Room] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

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
    extra: dict[str, Any] = field(default_factory=dict)

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
    gestionnaires: list[Gestionnaire] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

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
        p = Path(path)
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        campus = Campus._from_dict(data)
        migrate_room_managers(campus)
        return campus

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
                    Room(
                        id=r["id"],
                        name=r["name"],
                        capacity=r["capacity"],
                        position=r.get("position", [0.0, 0.0]),
                        gestionnaire_ids=r.get("gestionnaire_ids", []),
                        extra=r.get("extra", {}),
                    )
                    for r in f.get("rooms", [])
                ]
                floors.append(
                    Floor(
                        id=f["id"],
                        name=f["name"],
                        level=f.get("level", f_index),
                        polygon=f.get("polygon", []),
                        rooms=rooms,
                        extra=f.get("extra", {}),
                    )
                )
            buildings.append(
                Building(
                    id=b["id"],
                    name=b["name"],
                    position=b.get("position", [0.0, 0.0]),
                    floors=floors,
                    extra=b.get("extra", {}),
                )
            )
        gestionnaires = [Gestionnaire.from_dict(g) for g in data.get("gestionnaires", [])]
        return Campus(
            id=data["id"],
            name=data["name"],
            buildings=buildings,
            gestionnaires=gestionnaires,
            extra=data.get("extra", {}),
        )
