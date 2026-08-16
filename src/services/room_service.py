from __future__ import annotations

from model import Floor, Room


class RoomService:
    def __init__(self, campus):
        self.campus = campus

    def create_room(self, floor: Floor, name: str, capacity: int, position) -> Room:
        if not name or not name.strip():
            raise ValueError("Le nom de la salle est requis")
        capacity = int(capacity)
        if capacity < 1:
            raise ValueError("La capacité doit être au moins 1")
        return floor.add_room(name.strip(), capacity, [round(position[0], 2), round(position[1], 2)])
