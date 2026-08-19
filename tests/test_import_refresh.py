import asyncio
from pathlib import Path

from campus_app import CampusApp
from import_cps import _load_json_lenient, convert


class FakeSelect:
    def __init__(self):
        self.options = None
        self.value = None

    def set_options(self, options):
        self.options = options


class FakeList:
    def refresh(self):
        return None


class FakeDialog:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class FakeFile:
    def __init__(self, name, content):
        self.name = name
        self._content = content

    async def read(self):
        return self._content


class FakeEvent:
    def __init__(self, name, content):
        self.file = FakeFile(name, content)


def test_lenient_loader_handles_malformed_sample_cps():
    data = _load_json_lenient("samples/campus.cps")
    assert data["name"] == "Site"
    assert len(data["buildings"]) >= 2

    campus, skipped = convert("samples/campus.cps")
    assert campus.name == "Site"
    assert skipped >= 0


def test_import_replaces_model_and_refreshes_selection(monkeypatch, tmp_path):
    import nicegui.ui as ui

    monkeypatch.setattr(ui, "notify", lambda *args, **kwargs: None)

    app = CampusApp.__new__(CampusApp)
    app.campus = type("CampusState", (), {"name": "Ancien", "buildings": []})()
    app.data_path = tmp_path / "data.json"
    app.controller = None
    app.campus_service = None
    app.floor_service = None
    app.room_service = None
    app.state = {"building": None, "floor": None}
    app.building_select = FakeSelect()
    app.floor_select = FakeSelect()
    app.room_list = FakeList()
    app.plan_container = None
    app.save = lambda: None

    sample_path = Path("samples/louvre_grand_site.cps")
    dialog = FakeDialog()

    asyncio.run(app._on_cps_import(FakeEvent(sample_path.name, sample_path.read_bytes()), dialog))

    assert app.campus.name == "Grand Site Louvre"
    assert len(app.campus.buildings) == 2
    assert app.building_select.value == app.state["building"].id
    assert app.floor_select.value == app.state["floor"].id
    assert dialog.closed is True
