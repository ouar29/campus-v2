from datetime import date
import asyncio

from model import Campus
from rendering import campus_map_parts
from campus_app import _read_uploaded_file
from export_cps import export_campus


class FakeUploadFile:
    def __init__(self, name: str, data: bytes):
        self.name = name
        self._data = data

    def read(self):
        return self._data


class FakeUploadEvent:
    def __init__(self, name: str, data: bytes):
        self.file = FakeUploadFile(name, data)


def test_campus_map_preview_renders_without_error():
    campus = Campus(id="campus-1", name="Campus Test")
    building = campus.add_building("Bâtiment A")
    building.add_floor("RDC", [[0.0, 0.0], [8.0, 0.0], [8.0, 5.0], [0.0, 5.0]], level=0)

    html, js = campus_map_parts(campus)

    assert "<svg" in html
    assert "campusmap-svg-" in html
    assert "ResizeObserver" in js


def test_read_uploaded_file_handles_nicegui_upload_event():
    event = FakeUploadEvent("campus.cps", b'{"name": "Test"}')

    result = asyncio.run(_read_uploaded_file(event))

    assert result is not None
    assert result[0] == "campus.cps"
    assert result[1] == b'{"name": "Test"}'
    

def test_export_campus_sets_version_to_today_date():
    campus = Campus(id="campus-1", name="Campus Test")
    campus.add_building("Bâtiment A")

    exported = export_campus(campus)

    assert exported["version"] == date.today().isoformat()


def test_create_building_and_floor():
    campus = Campus(id="campus-1", name="Campus Test")
    building = campus.add_building("Bâtiment A")
    floor = building.add_floor("RDC", [[0.0, 0.0], [10.0, 0.0], [10.0, 5.0], [0.0, 5.0]], level=0)

    assert len(campus.buildings) == 1
    assert campus.buildings[0].name == "Bâtiment A"
    assert floor.level == 0
    assert len(floor.polygon) == 4


def test_create_room_and_capacity():
    campus = Campus(id="campus-1", name="Campus Test")
    building = campus.add_building("Bâtiment B")
    floor = building.add_floor("1", [[0.0, 0.0], [6.0, 0.0], [6.0, 4.0], [0.0, 4.0]], level=1)
    room = floor.add_room("Salle 101", 24, [2.0, 2.0])

    assert room.name == "Salle 101"
    assert room.capacity == 24
    assert room.position == [2.0, 2.0]
    assert len(floor.rooms) == 1


def test_save_and_load_round_trip(tmp_path):
    campus = Campus(id="campus-1", name="Campus Test")
    building = campus.add_building("Bâtiment C")
    floor = building.add_floor("RDC", [[0.0, 0.0], [5.0, 0.0], [5.0, 3.0], [0.0, 3.0]], level=0)
    floor.add_room("Salle C1", 12, [1.5, 1.5])

    path = tmp_path / "campus.json"
    campus.save(path)
    loaded = Campus.load(path)

    assert loaded.name == "Campus Test"
    assert len(loaded.buildings) == 1
    assert loaded.buildings[0].floors[0].rooms[0].name == "Salle C1"
    assert loaded.buildings[0].floors[0].rooms[0].capacity == 12
