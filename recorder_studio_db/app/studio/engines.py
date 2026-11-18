"""Runs the database server the add-on is configured for (PostgreSQL or MariaDB) and manages its credentials.

SQLite needs no server: Home Assistant owns that file and the add-on only reads it.
"""
from __future__ import annotations

import asyncio
import contextlib
import glob
import json
import logging
import os
from pathlib import Path
import secrets
import shutil
from typing import Any
from urllib.parse import quote

from .const import DATA_DIR
from .core import db_stats_sql

_LOGGER = logging.getLogger(__name__)

DB_NAME = DB_USER = "homeassistant"
PG_DATA = DATA_DIR / "postgres"
PG_SOCK = "/run/postgresql"
MY_DATA = DATA_DIR / "mariadb"
MY_SOCK = "/run/mysqld/mysqld.sock"
HASSIO_NET = "172.30.32.0/23"
START_TIMEOUT = 300  # crash recovery on a big database can take a while


def find_binary(name: str) -> str | None:
    """Alpine keeps some PostgreSQL binaries in /usr/libexec/postgresql<N>/ instead of /usr/bin."""
    found = shutil.which(name)
    if found:
        return found
    hits = sorted(glob.glob(f"/usr/libexec/postgresql*/{name}") + glob.glob(f"/usr/lib/postgresql*/bin/{name}"))
    return hits[-1] if hits else None


def load_credentials(path: Path | None = None) -> dict[str, str]:
    path = path or DATA_DIR / "credentials.json"
    try:
        creds = json.loads(path.read_text(encoding="utf-8"))
        if creds.get("password"):
            return creds
    except (OSError, ValueError):
        pass
    creds = {"user": DB_USER, "database": DB_NAME, "password": secrets.token_urlsafe(24)}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(creds), encoding="utf-8")
    os.chmod(path, 0o600)
    return creds


def build_db_url(engine: str, host: str, creds: dict[str, str]) -> str:
    user, pw, db = quote(creds["user"], safe=""), quote(creds["password"], safe=""), quote(creds["database"], safe="")
    if engine == "postgresql":
        return f"postgresql://{user}:{pw}@{host}:5432/{db}"
    return f"mysql://{user}:{pw}@{host}:3306/{db}?charset=utf8mb4"


def mask_url(url: str) -> str:
    """postgresql://user:secret@host/db -> postgresql://user:***@host/db"""
    if "@" not in url or "://" not in url:
        return url
    head, _, rest = url.partition("://")
    cred, _, tail = rest.rpartition("@")
    return f"{head}://{cred.split(':', 1)[0]}:***@{tail}"


class DatabaseServer:
    """Starts, monitors and stops one database server process inside the add-on container."""

    def __init__(self, engine: str, creds: dict[str, str] | None = None) -> None:
        if engine not in ("postgresql", "mariadb"):
            raise ValueError(f"no server for engine {engine}")
        self.engine = engine
        self.dialect = engine
        self.creds = creds or load_credentials()
        self.state = "stopped"  # stopped | starting | running | failed
        self.error: str | None = None
        self._proc: asyncio.subprocess.Process | None = None
        self._task: asyncio.Task | None = None
        self._stopping = False

    @property
    def running(self) -> bool:
        return self.state == "running"

    @property
    def port(self) -> int:
        return 5432 if self.engine == "postgresql" else 3306

    @property
    def label(self) -> str:
        return f"{self.engine}:{DB_NAME}"

    # ---- helpers ------------------------------------------------------
    async def _run(self, *cmd: str, check: bool = True) -> str:
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        out, _ = await proc.communicate()
        text = out.decode(errors="replace").strip()
        if check and proc.returncode:
            raise RuntimeError(f"{' '.join(cmd[:3])} failed ({proc.returncode}): {text[-400:]}")
        return text

    def connect(self, write: bool = False):
        """DB-API connection to the local server: read-only for statistics and status, writable for the history copy."""
        if self.engine == "postgresql":
            import psycopg2

            conn = psycopg2.connect(host="127.0.0.1", port=5432, dbname=DB_NAME, user=self.creds["user"], password=self.creds["password"], connect_timeout=10)
            conn.set_session(readonly=not write, autocommit=not write)
            return conn
        import pymysql

        return pymysql.connect(host="127.0.0.1", port=3306, database=DB_NAME, user=self.creds["user"], password=self.creds["password"], connect_timeout=10, autocommit=not write)

    # ---- lifecycle ----------------------------------------------------
    async def start(self) -> None:
        self._stopping = False
        self._task = asyncio.create_task(self._supervise())

    async def stop(self) -> None:
        self._stopping = True
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        await self._terminate()
        self.state = "stopped"

    async def _terminate(self) -> None:
        proc = self._proc
        if proc and proc.returncode is None:
            import signal

            proc.send_signal(signal.SIGINT if self.engine == "postgresql" else signal.SIGTERM)  # PostgreSQL: fast shutdown
            try:
                await asyncio.wait_for(proc.wait(), 60)
            except asyncio.TimeoutError:
                proc.kill()
        self._proc = None

    async def _supervise(self) -> None:
        delay = 5
        while not self._stopping:
            try:
                self.state, self.error = "starting", None
                await (self._start_postgres() if self.engine == "postgresql" else self._start_mariadb())
                await self._check_tcp()
                self.state = "running"
                _LOGGER.info("%s is running", self.engine)
                delay = 5
                await self._proc.wait()  # type: ignore[union-attr]
                if self._stopping:
                    return
                self.error = f"{self.engine} exited with code {self._proc.returncode}"  # type: ignore[union-attr]
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001
                self.error = str(err)
                await self._terminate()
            self.state = "failed"
            _LOGGER.error("%s: %s (restarting in %ss)", self.engine, self.error, delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 120)

    async def _wait_ready(self, probe: list[str]) -> None:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + START_TIMEOUT
        while loop.time() < deadline:
            if self._proc and self._proc.returncode is not None:
                raise RuntimeError(f"{self.engine} stopped during start-up (code {self._proc.returncode}); see the add-on log")
            proc = await asyncio.create_subprocess_exec(*probe, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
            if await proc.wait() == 0:
                return
            await asyncio.sleep(1)
        raise RuntimeError(f"{self.engine} did not become ready within {START_TIMEOUT}s")

    async def _check_tcp(self) -> None:
        """Only report "running" once a real TCP login works (the way Home Assistant will connect), not just the local socket."""
        last: Exception | None = None
        for _ in range(30):
            try:
                await asyncio.to_thread(lambda: self.connect().close())
                return
            except Exception as err:  # noqa: BLE001
                last = err
                await asyncio.sleep(1)
        raise RuntimeError(f"{self.engine} is up but refuses TCP logins: {last}")

    # ---- PostgreSQL ---------------------------------------------------
    async def _start_postgres(self) -> None:
        postgres, initdb = find_binary("postgres"), find_binary("initdb")
        if not postgres or not initdb:
            raise RuntimeError("PostgreSQL is not installed in this image")
        os.makedirs(PG_SOCK, exist_ok=True)
        PG_DATA.mkdir(parents=True, exist_ok=True)
        await self._run("chown", "-R", "postgres:postgres", str(PG_DATA), PG_SOCK)
        os.chmod(PG_DATA, 0o700)
        if not (PG_DATA / "PG_VERSION").exists():
            _LOGGER.info("Initialising a new PostgreSQL cluster in %s", PG_DATA)
            await self._run("su-exec", "postgres", initdb, "-D", str(PG_DATA), "-E", "UTF8", "--auth-local=trust", "--auth-host=scram-sha-256")
            with open(PG_DATA / "pg_hba.conf", "a", encoding="utf-8") as fh:
                fh.write(f"\nhost all all {HASSIO_NET} scram-sha-256\n")
        self._proc = await asyncio.create_subprocess_exec(
            "su-exec", "postgres", postgres, "-D", str(PG_DATA), "-c", "listen_addresses=*", "-c", f"unix_socket_directories={PG_SOCK}",
        )
        pg_isready = find_binary("pg_isready") or "pg_isready"
        await self._wait_ready([pg_isready, "-h", PG_SOCK, "-q"])
        psql = find_binary("psql") or "psql"
        base = ["su-exec", "postgres", psql, "-h", PG_SOCK, "-U", "postgres", "-d", "postgres", "-v", "ON_ERROR_STOP=1"]
        pw = self.creds["password"]
        await self._run(*base, "-c", f"DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='{DB_USER}') THEN CREATE ROLE {DB_USER} LOGIN; END IF; END $$;")
        await self._run(*base, "-c", f"ALTER ROLE {DB_USER} WITH LOGIN PASSWORD '{pw}'")
        exists = await self._run(*base, "-tAc", f"SELECT 1 FROM pg_database WHERE datname='{DB_NAME}'")
        if exists.strip() != "1":
            await self._run(*base, "-c", f"CREATE DATABASE {DB_NAME} OWNER {DB_USER} ENCODING 'UTF8'")

    # ---- MariaDB ------------------------------------------------------
    async def _start_mariadb(self) -> None:
        mariadbd = shutil.which("mariadbd")
        if not mariadbd:
            raise RuntimeError("MariaDB is not installed in this image")
        os.makedirs(os.path.dirname(MY_SOCK), exist_ok=True)
        MY_DATA.mkdir(parents=True, exist_ok=True)
        await self._run("chown", "-R", "mysql:mysql", str(MY_DATA), os.path.dirname(MY_SOCK))
        if not (MY_DATA / "mysql").exists():
            _LOGGER.info("Initialising a new MariaDB data directory in %s", MY_DATA)
            await self._run("mariadb-install-db", "--user=mysql", f"--datadir={MY_DATA}", "--skip-test-db", "--auth-root-authentication-method=socket")
        self._proc = await asyncio.create_subprocess_exec(
            mariadbd, "--user=mysql", f"--datadir={MY_DATA}", f"--socket={MY_SOCK}", "--bind-address=0.0.0.0", "--skip-name-resolve",
            "--character-set-server=utf8mb4", "--collation-server=utf8mb4_unicode_ci",
        )
        await self._wait_ready(["mariadb-admin", f"--socket={MY_SOCK}", "ping", "--silent"])
        pw = self.creds["password"]
        sql = (
            f"CREATE DATABASE IF NOT EXISTS {DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
            f"CREATE USER IF NOT EXISTS '{DB_USER}'@'%' IDENTIFIED BY '{pw}';"
            f"ALTER USER '{DB_USER}'@'%' IDENTIFIED BY '{pw}';"
            f"GRANT ALL PRIVILEGES ON {DB_NAME}.* TO '{DB_USER}'@'%'; FLUSH PRIVILEGES;"
        )
        await self._run("mariadb", f"--socket={MY_SOCK}", "-uroot", "-e", sql)

    # ---- information --------------------------------------------------
    def info(self) -> dict[str, Any]:
        """Version and size, read from the server (blocking: call from a thread)."""
        out: dict[str, Any] = {"engine": self.engine, "state": self.state, "error": self.error, "port": self.port}
        if self.running:
            try:
                conn = self.connect()
                try:
                    out["version"] = db_stats_sql.version(conn, self.dialect)
                    out["size_bytes"] = db_stats_sql.db_size(conn, self.dialect)
                finally:
                    conn.close()
            except Exception as err:  # noqa: BLE001
                out["error"] = str(err)
        return out
