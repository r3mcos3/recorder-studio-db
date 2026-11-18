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

    async def addon_hostname(self):
        return "abc-recorder-studio-db"

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


async def test_db_activate_separate_sqlite_file(client, studio):
    status, body = await cmd(client, type="recorder_studio/db_set_engine", engine="sqlite", sqlite_file="recorder_studio.db", confirm=True)
    assert status == 200 and studio.sqlite_file == "recorder_studio.db"
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


class FakeServer:
    def __init__(self, engine):
        self.engine, self.running, self.state, self.error, self.stopped = engine, False, "stopped", None, False
        self.creds = {"user": "homeassistant", "database": "homeassistant", "password": "pw"}

    async def start(self):
        self.running, self.state = True, "running"

    async def stop(self):
        self.running, self.state, self.stopped = False, "stopped", True

    def info(self):
        return {"engine": self.engine, "state": self.state, "error": None, "port": 5432}


async def test_choose_engine_from_the_panel(client, studio, monkeypatch):
    monkeypatch.setattr("studio.engines.DatabaseServer", FakeServer)
    status, body = await cmd(client, type="recorder_studio/db_set_engine", engine="postgresql")
    assert status == 400 and body["code"] == "confirm_required"
    status, body = await cmd(client, type="recorder_studio/db_set_engine", engine="postgresql", confirm=True)
    assert status == 200 and studio.engine == "postgresql" and studio.server.running
    first = studio.server
    status, body = await cmd(client, type="recorder_studio/db_status")
    assert body["result"]["engine"] == "postgresql" and body["result"]["state"] == "running"
    assert body["result"]["target_url"].startswith("postgresql://homeassistant:***@")
    status, body = await cmd(client, type="recorder_studio/db_set_engine", engine="mariadb", confirm=True)
    assert status == 200 and first.stopped and studio.server.engine == "mariadb"
    status, body = await cmd(client, type="recorder_studio/db_set_engine", engine="sqlite", confirm=True)
    assert status == 200 and studio.server is None and studio.engine == "sqlite"


async def test_cannot_stop_the_server_home_assistant_records_into(client, studio, monkeypatch):
    monkeypatch.setattr("studio.engines.DatabaseServer", FakeServer)
    await cmd(client, type="recorder_studio/db_set_engine", engine="postgresql", confirm=True)
    await cmd(client, type="recorder_studio/db_activate", confirm=True)
    status, body = await cmd(client, type="recorder_studio/db_set_engine", engine="sqlite", confirm=True)
    assert status == 400 and body["code"] == "invalid_engine" and studio.engine == "postgresql"
    await cmd(client, type="recorder_studio/db_deactivate", confirm=True)
    status, _ = await cmd(client, type="recorder_studio/db_set_engine", engine="sqlite", confirm=True)
    assert status == 200


async def test_invalid_engine_and_filename(client):
    assert (await cmd(client, type="recorder_studio/db_set_engine", engine="oracle", confirm=True))[0] == 400
    assert (await cmd(client, type="recorder_studio/db_set_engine", engine="sqlite", sqlite_file="../x.db", confirm=True))[0] == 400


async def test_old_pymysql_url_is_migrated(tmp_path):
    from studio.service import Studio
    from studio import store
    sp = tmp_path / "s.json"
    data = store.merge({})
    data["options"]["db_url"] = "mysql+pymysql://u:p@h:3306/db?charset=utf8mb4"
    store.save(sp, data)
    studio = Studio(None, config_dir=tmp_path, store_path=sp)
    assert studio.data["options"]["db_url"] == "mysql://u:p@h:3306/db?charset=utf8mb4"


async def test_history_copy_through_the_api(client, studio, tmp_path):
    import sqlite3
    from test_history_copy import build_source, build_target

    cfg = tmp_path / "config"
    build_source(cfg / "old.db")
    dst = tmp_path / "dst.db"
    build_target(dst)

    class SqlServer(FakeServer):
        dialect = "sqlite"

        def connect(self, write=False):
            return sqlite3.connect(dst)

    studio.server = SqlServer("postgresql")
    status, body = await cmd(client, type="recorder_studio/history_status")
    assert status == 200 and body["result"]["available"] is False and "old.db" in body["result"]["sources"]
    status, body = await cmd(client, type="recorder_studio/history_copy_start", source="old.db", confirm=True)
    assert status == 400 and "Start PostgreSQL" in body["message"]
    await studio.server.start()
    status, body = await cmd(client, type="recorder_studio/history_copy_start", source="old.db")
    assert body["code"] == "confirm_required"
    status, body = await cmd(client, type="recorder_studio/history_copy_start", source="../x.db", confirm=True)
    assert status == 400
    status, body = await cmd(client, type="recorder_studio/history_copy_start", source="old.db", confirm=True)
    assert status == 200
    await studio._copy_task
    status, body = await cmd(client, type="recorder_studio/history_status")
    r = body["result"]
    assert r["state"] == "done" and r["copied"]["states"] == 3 and r["done"] == r["total"]
    assert r["done_before"][0]["source"] == "old.db"
    # a second copy would duplicate everything
    status, body = await cmd(client, type="recorder_studio/history_copy_start", source="old.db", confirm=True)
    assert status == 400 and "already copied" in body["message"]
    status, body = await cmd(client, type="recorder_studio/history_copy_start", source="old.db", confirm=True, force=True)
    assert status == 200
    await studio._copy_task
