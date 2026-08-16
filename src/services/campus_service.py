from __future__ import annotations

from model import Campus, Building


class CampusService:
    def __init__(self, campus: Campus):
        self.campus = campus

    def create_building(self, name: str) -> Building:
        if not name or not name.strip():
            raise ValueError("Le nom du bâtiment est requis")
        return self.campus.add_building(name.strip())

    def save(self, path: str):
        self.campus.save(path)
