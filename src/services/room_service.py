from __future__ import annotations

from geometry import polygon_centroid
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

    def move_room(self, source_floor: Floor, room: Room, target_floor: Floor) -> bool:
        if target_floor is source_floor:
            return False
        source_floor.rooms = [r for r in source_floor.rooms if r.id != room.id]
        room.position = polygon_centroid(target_floor.polygon)
        target_floor.rooms.append(room)
        return True
