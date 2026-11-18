"""aiohttp server behind Home Assistant ingress: serves the panel and one command endpoint."""
from __future__ import annotations

import asyncio
import contextlib
import logging
import os

from aiohttp import web

from . import api
from .const import ALERT_INTERVAL_HOURS, PORT, WWW_DIR, addon_options
from . import engines
from .ha import HAClient, HAError
from .service import Studio

_LOGGER = logging.getLogger("studio")
INGRESS_IP = "172.30.32.2"  # the Supervisor ingress gateway; nothing else may talk to us


LOCAL_ONLY_PATHS = {"/api/prestop"}  # called by the container's own stop script, never through ingress
LOOPBACK = {"127.0.0.1", "::1"}


@web.middleware
async def only_ingress(request: web.Request, handler):
    if not os.environ.get("STUDIO_DEV"):
        allowed = request.remote in LOOPBACK if request.path in LOCAL_ONLY_PATHS else request.remote == INGRESS_IP
        if not allowed:
            raise web.HTTPForbidden()
    return await handler(request)


async def prestop(request: web.Request) -> web.Response:
    """The container is about to stop: let Home Assistant's recorder wait, then stop the database gracefully.

    Called by /usr/local/bin/prestop from an s6 service, which runs before s6 sends SIGTERM to every process. Idempotent.
    """
    studio: Studio = request.app["studio"]
    paused = False
    if studio.server:
        with contextlib.suppress(Exception):
            paused = await asyncio.wait_for(studio.pause_recorder(), PAUSE_TIMEOUT)
        _LOGGER.info("prestop: recorder paused=%s, stopping the database gracefully", paused)
        await studio.server.stop()
        _LOGGER.info("prestop: database stopped")
    return web.json_response({"paused": paused, "database_stopped": True})


async def command(request: web.Request) -> web.Response:
    studio: Studio = request.app["studio"]
    try:
        body = await request.json()
        kind = str(body["type"]).removeprefix("recorder_studio/")
        handler = api.COMMANDS[kind]
    except (ValueError, KeyError, TypeError):
        return web.json_response({"code": "unknown_command", "message": "Unknown command"}, status=400)
    try:
        return web.json_response({"result": await handler(studio, body)})
    except api.ApiError as err:
        return web.json_response({"code": err.code, "message": err.message}, status=400)
    except Exception as err:  # noqa: BLE001
        _LOGGER.exception("command %s failed", kind)
        return web.json_response({"code": "internal_error", "message": str(err)}, status=500)


async def index(_request: web.Request) -> web.FileResponse:
    return web.FileResponse(WWW_DIR / "index.html", headers={"Cache-Control": "no-cache"})


async def _background(app: web.Application) -> None:
    studio: Studio = app["studio"]
    await asyncio.sleep(120)
    while True:
        try:
            await studio.background_check()
        except Exception:  # noqa: BLE001
            _LOGGER.exception("background check failed")
        await asyncio.sleep(ALERT_INTERVAL_HOURS * 3600)


METRICS_INTERVAL = 30 * 60  # seconds between background measurements for the sensors
PAUSE_TIMEOUT = 6  # seconds the shutdown may spend on asking the recorder to wait (the container is only given ~10 s)
METRICS_RETRY = 60  # seconds between attempts while the sensors cannot be reached


async def _metrics(app: web.Application) -> None:
    """Keeps the Home Assistant sensors current while the panel is closed (a full analysis also feeds the history).

    While the sensors cannot be reached (Home Assistant restarting, integration not loaded yet) the last figures are
    offered again every minute, so they appear shortly after Home Assistant is back instead of 30 minutes later.
    """
    studio: Studio = app["studio"]
    await asyncio.sleep(90)
    while True:
        try:
            await studio.analyze(full=True)
        except Exception:  # noqa: BLE001
            _LOGGER.exception("metrics refresh failed")
        waited = 0
        while waited < METRICS_INTERVAL:
            step = METRICS_INTERVAL if studio.metrics_pushed else METRICS_RETRY
            await asyncio.sleep(step)
            waited += step
            if not studio.metrics_pushed:
                await studio.push_metrics()


async def _integration(app: web.Application) -> None:
    """Install the bundled integration and check Home Assistant runs it; Home Assistant may still be starting."""
    studio: Studio = app["studio"]
    for attempt in range(40):
        try:
            info = await studio.ensure_integration()
            _LOGGER.info("integration: %s (%s)", info["state"], info.get("message") or "ok")
            if info["state"] == "ready":
                await studio.push_metrics()
            return
        except HAError as err:
            _LOGGER.info("integration check waits for Home Assistant (%s)", err)
        except Exception:  # noqa: BLE001
            _LOGGER.exception("integration check failed")
            return
        await asyncio.sleep(30)


async def _start(app: web.Application) -> None:
    if app["studio"].server:
        await app["studio"].server.start()
    try:
        await app["studio"].migrate_db_url_secret()
    except Exception:  # noqa: BLE001 - never block the start-up on this
        _LOGGER.exception("could not move the database password to secrets.yaml")
    app["task"] = asyncio.create_task(_background(app))
    app["integration_task"] = asyncio.create_task(_integration(app))
    app["metrics_task"] = asyncio.create_task(_metrics(app))


async def _stop(app: web.Application) -> None:
    for key in ("task", "integration_task", "metrics_task"):
        task = app.get(key)
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
    studio: Studio = app["studio"]
    if studio.server:
        with contextlib.suppress(Exception):
            # planned stop: first let Home Assistant's recorder wait, so no history is lost while the database is down
            await asyncio.wait_for(studio.pause_recorder(), PAUSE_TIMEOUT)
        await studio.server.stop()
    await app["ha"].close()


def make_app(studio: Studio | None = None, ha: HAClient | None = None) -> web.Application:
    ha = ha or HAClient()
    app = web.Application(middlewares=[only_ingress])
    if studio is None:
        studio = Studio(ha)
        studio.server = studio.make_server()
    app["ha"], app["studio"] = ha, studio
    app.router.add_post("/api/command", command)
    app.router.add_post("/api/prestop", prestop)
    app.router.add_get("/", index)
    app.router.add_static("/", WWW_DIR, follow_symlinks=False)
    app.on_startup.append(_start)
    app.on_cleanup.append(_stop)
    return app


def main() -> None:
    logging.basicConfig(level=getattr(logging, str(addon_options().get("log_level", "info")).upper(), logging.INFO))
    web.run_app(make_app(), host="0.0.0.0", port=PORT, print=None)


if __name__ == "__main__":
    main()
