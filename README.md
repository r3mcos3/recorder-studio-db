# Recorder Studio DB

A Home Assistant **add-on** that runs and manages the recorder database, with [Recorder Studio](https://github.com/r3mcos3/recorder-studio)
built in: see what fills the database, choose what is recorded, purge and repack safely.

**Status: phase 2 (0.2.x).** SQLite mode and experimental PostgreSQL/MariaDB engines run by the add-on itself. The old history is not moved yet (phase 3).
offers the full Recorder Studio panel (statistics, per-device/entity choices, suggestions, growth, alerts, migration, purge/repack)
through the sidebar.

## Roadmap

1. ✅ **SQLite mode + panel via ingress**
2. ✅ **PostgreSQL and MariaDB engines** run by the add-on, with a Database tab (experimental, tested in CI with real servers)
3. Database-specific statistics and migration between engines, with a backup first
4. Extra database info: table sizes, growth, fragmentation

## Install

Home Assistant > Settings > Add-ons > Add-on store > ⋮ > Repositories, add `https://github.com/r3mcos3/recorder-studio-db`,
then install **Recorder Studio DB**.

## Development

```bash
python -m venv .venv && .venv/bin/pip install aiohttp pytest pytest-aiohttp pyyaml
.venv/bin/pytest
```

`recorder_studio_db/app/studio/core/` and `recorder_studio_db/app/www/` are derived from the Recorder Studio integration
(MIT, same author); the add-on talks to Home Assistant through the Supervisor API instead of Home Assistant internals.

MIT licensed.
