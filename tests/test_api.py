import pytest
from aiohttp import web

from studio import api, server
from studio.service import Studio


class FakeHA:
    def __init__(self):
        self.calls = []

    async def ws(self, command):
        if command == "config/entity_registry/list":
            return [{"entity_id": "sensor.a", "name": None, "original_name": "A", "device_id": "d1", "platform": "mqtt"}]
        return [{"id": "d1", "name": "Device one", "name_by_user": None}]

    async def states(self):
        return [{"entity_id": "sensor.a", "attributes": {}}, {"entity_id": "sensor.b_uptime", "attributes": {}}]

    async def call_service(self, domain, service, data=None):
        self.calls.append((domain, service, data or {}))

    async def backups(self):
        return ["2026-11-16T10:00:00+00:00"]

    async def close(self):
        pass


@pytest.fixture
def studio(tmp_path, synthetic_db):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "home-assistant_v2.db").write_bytes(synthetic_db.read_bytes())
    (tmp_path / "config" / "configuration.yaml").write_text("homeassistant:\n  name: x\n")
    return Studio(FakeHA(), tmp_path / "config", tmp_path / "studio.json")


@pytest.fixture
async def client(aiohttp_client, studio, monkeypatch):
    monkeypatch.setenv("STUDIO_DEV", "1")
    app = server.make_app(studio=studio, ha=studio.ha)
    app.on_startup.clear()
    return await aiohttp_client(app)


async def cmd(client, **msg):
    r = await client.post("/api/command", json=msg)
    return r.status, await r.json()


async def test_get_state_after_analyze(client):
    await cmd(client, type="recorder_studio/analyze", light=False)
    status, body = await cmd(client, type="recorder_studio/get_state")
    assert status == 200
    res = body["result"]
    assert res["sqlite"] and res["engine"] == "sqlite"
    assert res["summary"]["total_records"] == 100
    assert any(e["entity_id"] == "sensor.a" for d in res["tree"] for e in d["entities"])


async def test_set_recorded_writes_yaml(client, studio):
    status, body = await cmd(client, type="recorder_studio/set_recorded", entity_ids=["sensor.b_uptime"], recorded=False)
    assert status == 200 and body["result"]["excluded"] == 1
    yaml_text = (studio.config_dir / "recorder_studio.yaml").read_text()
    assert "sensor.b_uptime" in yaml_text
    assert studio.pending_restart


async def test_purge_requires_confirm_and_calls_services(client, studio):
    status, body = await cmd(client, type="recorder_studio/purge", kind="entities", entity_ids=["sensor.a"])
    assert status == 400 and body["code"] == "confirm_required"
    status, body = await cmd(client, type="recorder_studio/purge", kind="entities", entity_ids=["sensor.a"], confirm=True)
    assert status == 200
    assert studio.ha.calls == [("recorder", "purge_entities", {"entity_id": ["sensor.a"], "keep_days": 0})]


async def test_invalid_rules_and_unknown_command(client):
    status, body = await cmd(client, type="recorder_studio/save_settings", purge_keep_days=7, commit_interval=5, auto_purge=True, auto_repack=True, rules_text="exclude: [")
    assert status == 400 and body["code"] == "invalid_rules"
    status, _ = await cmd(client, type="recorder_studio/nope")
    assert status == 400


async def test_backup_status(client):
    status, body = await cmd(client, type="recorder_studio/backup_status")
    assert status == 200 and body["result"]["known"] and body["result"]["count"] == 1


async def test_ingress_only(aiohttp_client, studio, monkeypatch):
    monkeypatch.delenv("STUDIO_DEV", raising=False)
    app = server.make_app(studio=studio, ha=studio.ha)
    app.on_startup.clear()
    c = await aiohttp_client(app)
    assert (await c.get("/")).status == 403


async def test_db_status_sqlite_default(client):
    status, body = await cmd(client, type="recorder_studio/db_status")
    r = body["result"]
    assert status == 200 and r["engine"] == "sqlite" and r["default_sqlite"] and r["configured"] and r["target_url"] is None


async def test_db_activate_separate_sqlite_file(client, studio, monkeypatch):
    monkeypatch.setattr("studio.service.sqlite_file", lambda: "recorder_studio.db")
    monkeypatch.setattr("studio.api.sqlite_file", lambda: "recorder_studio.db")
    status, body = await cmd(client, type="recorder_studio/db_activate", confirm=True)
    assert status == 200
    assert "db_url: sqlite:////config/recorder_studio.db" in (studio.config_dir / "recorder_studio.yaml").read_text()
    status, body = await cmd(client, type="recorder_studio/db_status")
    assert body["result"]["configured"] and body["result"]["current_url"] == "sqlite:////config/recorder_studio.db"
    status, body = await cmd(client, type="recorder_studio/db_deactivate", confirm=True)
    assert status == 200 and "db_url" not in (studio.config_dir / "recorder_studio.yaml").read_text()


async def test_db_activate_needs_confirm(client):
    status, body = await cmd(client, type="recorder_studio/db_activate")
    assert status == 400 and body["code"] == "confirm_required"
