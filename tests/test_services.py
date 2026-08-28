import pytest

from model import Campus
from services.campus_service import CampusService
from services.floor_service import FloorService
from services.room_service import RoomService


def test_campus_service_create_building():
    campus = Campus(id="campus-1", name="Campus")
    service = CampusService(campus)

    building = service.create_building("Bâtiment X")

    assert building.name == "Bâtiment X"
    assert len(campus.buildings) == 1


def test_floor_service_create_floor_validates_polygon():
    campus = Campus(id="campus-1", name="Campus")
    building = campus.add_building("Bâtiment Y")
    service = FloorService(campus)

    floor = service.create_floor(building, "RDC", [[0.0, 0.0], [4.0, 0.0], [4.0, 2.0], [0.0, 2.0]], level=0)

    assert floor.name == "RDC"
    assert floor.level == 0
    assert len(building.floors) == 1

    with pytest.raises(ValueError):
        service.create_floor(building, "Erreur", [[0.0, 0.0], [1.0, 1.0]], level=1)


def test_room_service_create_room_and_validates_capacity():
    campus = Campus(id="campus-1", name="Campus")
    building = campus.add_building("Bâtiment Z")
    floor = building.add_floor("1", [[0.0, 0.0], [5.0, 0.0], [5.0, 3.0], [0.0, 3.0]], level=1)
    service = RoomService(campus)

    room = service.create_room(floor, "Salle A", 18, [1.5, 1.5])

    assert room.name == "Salle A"
    assert room.capacity == 18
    assert room.position == [1.5, 1.5]
    assert len(floor.rooms) == 1

    with pytest.raises(ValueError):
        service.create_room(floor, "Salle invalide", 0, [0.0, 0.0])
