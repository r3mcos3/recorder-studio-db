import pytest
from aiohttp import web

from studio import api, server
from studio.service import Studio


class FakeHA:
    def __init__(self):
        self.calls = []
        from studio import integration

        self.live_result = {"applied": True, "restart": [], "changed": ["filter"], "reason": None}  # what apply_config answers
        self.own_version = integration.source_version()  # version of our integration Home Assistant runs (None = not loaded)
        self.fallback = None  # answer of the Marketplace integration's recorder_studio.apply_config (None = not installed)
        self.flow_error, self.flow_result, self.flow_loads = False, {"type": "create_entry"}, True

    async def ws(self, command):
        if command == "config/entity_registry/list":
            return [{"entity_id": "sensor.a", "name": None, "original_name": "A", "device_id": "d1", "platform": "mqtt"}]
        return [{"id": "d1", "name": "Device one", "name_by_user": None}]

    async def states(self):
        return [{"entity_id": "sensor.a", "attributes": {}}, {"entity_id": "sensor.b_uptime", "attributes": {}}]

    async def call_service_response(self, domain, service, data=None):
        from studio import integration
        from studio.ha import HAError

        self.calls.append((domain, service, data))
        if isinstance(self.live_result, Exception):
            raise self.live_result
        if domain == integration.DOMAIN:
            if self.own_version is None:
                raise HAError(f"{domain}.{service}: service not found")
            return {**self.live_result, "version": self.own_version}
        if self.fallback is None:
            raise HAError(f"{domain}.{service}: service not found")
        return dict(self.fallback)

    async def start_config_flow(self, handler):
        from studio import integration
        from studio.ha import HAError

        self.calls.append(("flow", handler, None))
        if self.flow_error:
            raise HAError("config flow: HTTP 404 Invalid handler specified")
        if self.flow_result.get("type") == "create_entry" and self.flow_loads:
            self.own_version = integration.source_version()
        return self.flow_result

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
    assert body["result"]["live"]["applied"] is True
    assert ("recorder_studio_db", "apply_config", None) in studio.ha.calls
    assert not studio.pending_restart  # applied to the running recorder: no restart


async def test_changes_needing_a_restart_keep_the_banner(client, studio):
    studio.ha.live_result = {"applied": True, "restart": ["db_url"], "changed": [], "reason": None}
    await cmd(client, type="recorder_studio/set_recorded", entity_ids=["sensor.b_uptime"], recorded=False)
    assert studio.pending_restart
    status, body = await cmd(client, type="recorder_studio/get_state")
    assert body["result"]["pending_restart"] is True and body["result"]["live"]["restart"] == ["db_url"]


async def test_without_the_integration_a_restart_is_needed(client, studio):
    from studio.ha import HAError

    studio.ha.live_result = HAError("recorder_studio.apply_config: service not found")
    status, body = await cmd(client, type="recorder_studio/set_recorded", entity_ids=["sensor.b_uptime"], recorded=False)
    assert status == 200 and body["result"]["live"]["reason"] == "integration_missing"
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


async def test_integration_ready_when_home_assistant_runs_the_current_version(studio, tmp_path):
    info = await studio.ensure_integration()
    assert info["state"] == "ready" and info["loaded"] == info["version"]
    assert (studio.config_dir / "custom_components" / "recorder_studio_db" / "manifest.json").exists()
    assert not any(c[0] == "flow" for c in studio.ha.calls)


async def test_integration_restart_needed_when_home_assistant_has_never_seen_it(studio):
    studio.ha.own_version, studio.ha.flow_error = None, True
    info = await studio.ensure_integration()
    assert info["state"] == "restart_needed" and "Restart Home Assistant once" in info["message"]


async def test_integration_entry_is_created_without_a_restart_when_ha_knows_it(studio):
    studio.ha.own_version = None  # files were there from an earlier run, only the entry is missing
    info = await studio.ensure_integration()
    assert info["state"] == "ready" and ("flow", "recorder_studio_db", None) in studio.ha.calls


async def test_integration_old_version_loaded_needs_a_restart(studio):
    studio.ha.own_version = "0.0.1"
    info = await studio.ensure_integration()
    assert info["state"] == "restart_needed" and "0.0.1" in info["message"]


async def test_integration_install_error_is_reported(studio, monkeypatch):
    def boom(config_dir):
        raise OSError("read-only file system")

    monkeypatch.setattr("studio.integration.install", boom)
    info = await studio.ensure_integration()
    assert info["state"] == "error" and "read-only" in info["message"]


async def test_apply_falls_back_to_the_marketplace_integration(client, studio):
    studio.ha.own_version = None
    studio.ha.fallback = {"applied": True, "restart": [], "changed": ["filter"], "reason": None}
    status, body = await cmd(client, type="recorder_studio/set_recorded", entity_ids=["sensor.b_uptime"], recorded=False)
    assert body["result"]["live"]["via"] == "recorder_studio" and not studio.pending_restart


async def test_integration_commands(client, studio):
    status, body = await cmd(client, type="recorder_studio/integration_status")
    assert status == 200 and body["result"]["state"] == "unknown"
    status, body = await cmd(client, type="recorder_studio/integration_ensure")
    assert body["result"]["state"] == "ready"
    status, body = await cmd(client, type="recorder_studio/get_state")
    assert body["result"]["integration"]["state"] == "ready"


async def test_unknown_service_is_recognised_from_a_bare_400(aiohttp_client, monkeypatch):
    from studio import ha as ha_module

    async def unknown(request):
        return web.Response(status=400, text="400: Bad Request")

    async def good(request):
        return web.json_response({"changed_states": [], "service_response": {"applied": True}})

    app = web.Application()
    app.router.add_post("/api/services/recorder_studio_db/apply_config", unknown)
    app.router.add_post("/api/services/recorder_studio/apply_config", good)
    client = await aiohttp_client(app)
    monkeypatch.setattr(ha_module, "CORE", str(client.make_url("")).rstrip("/"))
    h = ha_module.HAClient()
    try:
        with pytest.raises(ha_module.HAError, match="service not found"):
            await h.call_service_response("recorder_studio_db", "apply_config")
        assert await h.call_service_response("recorder_studio", "apply_config") == {"applied": True}
    finally:
        await h.close()
