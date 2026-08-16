from __future__ import annotations

from model import Building, Floor


class FloorService:
    def __init__(self, campus):
        self.campus = campus

    def create_floor(self, building: Building, name: str, polygon, level=None) -> Floor:
        if not name or not name.strip():
            raise ValueError("Le nom de l'étage est requis")
        if len(polygon) < 3:
            raise ValueError("Un contour doit contenir au moins 3 points")
        return building.add_floor(name.strip(), polygon, level=level)

    def add_vertex(self, floor: Floor, point):
        floor.polygon.append([round(point[0], 2), round(point[1], 2)])

    def remove_vertex(self, floor: Floor, index):
        if len(floor.polygon) > 3:
            floor.polygon.pop(index)

    def insert_vertex(self, floor: Floor, index: int, point):
        floor.polygon.insert(index, [round(point[0], 2), round(point[1], 2)])
