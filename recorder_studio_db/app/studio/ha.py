"""Client for Home Assistant Core through the Supervisor proxy (REST + websocket) and the Supervisor API."""
from __future__ import annotations

import os
import time
from typing import Any

import aiohttp

CORE = os.environ.get("HA_CORE_URL", "http://supervisor/core")
SUPERVISOR = os.environ.get("HA_SUPERVISOR_URL", "http://supervisor")
TOKEN = os.environ.get("SUPERVISOR_TOKEN") or os.environ.get("HA_TOKEN", "")
REGISTRY_TTL = 60


class HAError(Exception):
    pass


class HAClient:
    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None
        self._reg: dict[str, tuple[float, Any]] = {}

    @property
    def session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers={"Authorization": f"Bearer {TOKEN}"}, timeout=aiohttp.ClientTimeout(total=60))
        return self._session

    async def close(self) -> None:
        if self._session:
            await self._session.close()

    async def states(self) -> list[dict[str, Any]]:
        async with self.session.get(f"{CORE}/api/states") as r:
            if r.status != 200:
                raise HAError(f"states: HTTP {r.status}")
            return await r.json()

    async def call_service(self, domain: str, service: str, data: dict | None = None) -> None:
        async with self.session.post(f"{CORE}/api/services/{domain}/{service}", json=data or {}) as r:
            if r.status >= 300:
                raise HAError(f"{domain}.{service}: HTTP {r.status} {(await r.text())[:200]}")

    async def ws(self, command: str) -> Any:
        """One websocket command (used for the registries; cached briefly)."""
        hit = self._reg.get(command)
        if hit and time.monotonic() - hit[0] < REGISTRY_TTL:
            return hit[1]
        url = CORE.replace("http", "ws", 1) + "/websocket"
        async with self.session.ws_connect(url) as ws:
            hello = await ws.receive_json()
            if hello.get("type") == "auth_required":
                await ws.send_json({"type": "auth", "access_token": TOKEN})
                reply = await ws.receive_json()
                if reply.get("type") != "auth_ok":
                    raise HAError(f"websocket authentication failed ({reply.get('type')}: {reply.get('message')}; token {'set' if TOKEN else 'MISSING'})")
            await ws.send_json({"id": 1, "type": command})
            msg = await ws.receive_json()
            if not msg.get("success"):
                raise HAError(f"{command}: {msg.get('error')}")
        self._reg[command] = (time.monotonic(), msg["result"])
        return msg["result"]

    async def backups(self) -> list[str]:
        async with self.session.get(f"{SUPERVISOR}/backups") as r:
            if r.status != 200:
                raise HAError(f"backups: HTTP {r.status}")
            body = await r.json()
        return [b.get("date") for b in body["data"]["backups"] if b.get("date")]
