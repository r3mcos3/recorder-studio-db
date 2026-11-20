# Changelog

## 0.8.9
- **Integration 0.8.4: restart Home Assistant once** after updating. While the add-on is being replaced, Docker briefly forgets its name and the recorder logged "Unknown server host" (error 2005). That is now hidden together with the other planned-restart connection errors.

## 0.8.8
- Automatic monthly release with updated database packages: MariaDB 11.8.9-r0 -> 11.8.10-r0. Back up first if you want to be careful; the add-on restarts its database once on update.

## 0.8.7
- **Integration 0.8.3: restart Home Assistant once** after updating. Only the count in the one-line summary of hidden connection errors was wrong (it counted every error once per log handler); hiding itself was already correct. Not urgent.

## 0.8.6
- **Integration 0.8.2: restart Home Assistant once** after updating.
- A planned database restart (add-on update, restart or backup) no longer fills the Home Assistant log with errors. While the recorder is paused for it, and for 30 seconds after, "Can't connect" / "Lost connection" errors from the recorder and from other integrations that read the database (for example Spook) are hidden, and one line afterwards says how many. Only connection errors are hidden, and only in that window: a database that goes away at any other moment is still logged as an error.

## 0.8.5
- Same as 0.8.4 (phone layout, data loss warning), with a fix: `config.yaml` of 0.8.4 was not valid YAML, so Home Assistant never offered that version. Tests now check that the file parses.

## 0.8.4
- Database tab on a phone: the table with table sizes was wider than the screen and pushed the page sideways. It now fits (the Share bars are hidden on narrow screens) and scrolls sideways if it is still too wide.
- A clear warning in the README and the add-on documentation: use at your own risk, the author is not responsible for data loss, make a backup first.

## 0.8.3
- PostgreSQL is no longer labelled experimental. It was tested on a real Home Assistant: recording, live apply without a restart, an add-on restart without losing a value (240 of 240), copying 2.8 million rows of history (statistics identical to the source), all 16 sensors and a repack (VACUUM FULL).
- PostgreSQL log: the start check no longer logs `FATAL: role "root" does not exist` (cosmetic, it was only the readiness probe).

## 0.8.2
- **Integration 0.8.1: restart Home Assistant once** after updating. The integration now resolves the `!secret` in `recorder_studio.yaml` (Home Assistant's YAML loader only does that when it is given the secrets of the config folder); without this, changes would have asked for a restart every time.
- **The database password no longer sits in `recorder_studio.yaml`.** That file is often under version control. The add-on now stores the URL in your `secrets.yaml` (key `recorder_studio_db_url`) and writes `db_url: !secret recorder_studio_db_url`. An existing plain-text password is moved automatically when the add-on starts; only that one line of `recorder_studio.yaml` is changed.
- Safe by design: the secret is written first and read back, and only then does `recorder_studio.yaml` refer to it. If `secrets.yaml` is not plain YAML or cannot be written, nothing in it is touched, the URL stays in `recorder_studio.yaml` (Home Assistant keeps working) and the Database tab shows why. A copy of the previous `secrets.yaml` is kept in the add-on's own data folder, not next to the original.
- Keep the `recorder_studio_db_url` entry in `secrets.yaml`: without it Home Assistant cannot read `recorder_studio.yaml`.

## 0.8.1
- Fix for 0.8.0: the pause came too late. When a container stops, every process gets SIGTERM at the same instant, so the database was already gone before the add-on could ask the recorder to wait (live test: 3 of 240 values lost). A small service now runs first on a stop: it lets the recorder wait and stops the database gracefully, and only then does the container-wide SIGTERM come. No Home Assistant restart needed for this one (the integration is unchanged).

## 0.8.0
- **No history lost when the add-on restarts.** Before the add-on stops the database (update, restart, backup), it asks Home Assistant's recorder to wait: the recorder keeps its events in memory and writes them once the database is back, after renewing its connections. Until now a commit that happened to run at the moment the server went down could be lost (a few seconds of history).
- The pause is protected: the recorder continues by itself after 3 minutes, when its queue gets long, when Home Assistant stops or the integration is unloaded.
- Needs the integration of this version: **restart Home Assistant once** after updating (the add-on says so).

## 0.7.3
- Engine sensor: "MariaDB 11.8.9" instead of "MariaDB 11.8.9-MariaDB" (cosmetic).

## 0.7.2
- Fix: the engine sensor said "SQLite 11.8.9-MariaDB" right after the add-on started. The engine name is now stored with the measurement.
- Row counts for PostgreSQL/MariaDB are counted exactly (time-limited) instead of using the catalog estimate, which was up to 9% off. The "States" figure is the exact total.

## 0.7.1
- The sensors get their first values within a minute after Home Assistant has restarted (the add-on offers the figures again every minute while they cannot be delivered, instead of waiting for the next 30-minute round).

## 0.7.0
- **Database details** (Database tab): size, growth per day, how far the history goes back, unused space / fragmentation, free disk with a days-until-full forecast, and rows + size + share per table. Works for SQLite, PostgreSQL and MariaDB (PostgreSQL shows its share of dead rows instead of free pages; row counts of PostgreSQL/MariaDB are estimates).
- **16 sensors** in Home Assistant (device *Recorder Studio DB*, category diagnostic): database size, states / attributes / events / statistics table sizes and counts, records per day, oldest record, growth per day, unused space, reclaimable space, disk free, days until full and the engine. They refresh every 30 minutes, also while the panel is closed, and keep their last value across restarts.
- The integration changed (sensors): **restart Home Assistant once** after updating.

## 0.6.6
- The integration has its own version number now (0.6.5): a Home Assistant restart is only asked when the integration code changes, not for every add-on release.
- The panel notices by itself (within ~15 s) that Home Assistant runs the integration after a restart; the "restart needed" banner disappears without pressing *Check again*.

## 0.6.5
- The integration now has a logo in Settings > Devices & services.

## 0.6.4
- The add-on only uses its own integration. The fallback to the Recorder Studio integration from the Marketplace/HACS is removed.

## 0.6.3
- The live apply also works with Home Assistant versions whose recorder has no queued-states index (the guard against a changed recorder was too strict about it).

## 0.6.2
- Fix: after applying a change live, Home Assistant logged `Error running job ... _queued_state_listener ... 'NoneType' object has no attribute 'setdefault'` on every state change (data was still recorded). The integration now removes that listener again. **Restart Home Assistant once** after updating to load the fixed integration.
- The add-on's check of the integration no longer applies the configuration itself; it uses a new side-effect free service `recorder_studio_db.status`.

## 0.6.1
- Fix: the integration was installed but never activated, because Home Assistant answers an unknown service with a bare `400: Bad Request` and the add-on mistook that for "Home Assistant not reachable". It now creates the integration entry itself.

## 0.6.0
- **The add-on now brings its own Home Assistant integration** (`recorder_studio_db`) and installs it into your `custom_components` folder itself. You no longer need the Recorder Studio integration from the Marketplace/HACS; if you have it, it keeps working as a fallback and you can remove it once this one runs.
- After installing or updating the add-on, Home Assistant needs **one restart** to load the integration. The panel shows a banner with a Restart button and a *Check again* button; the entry is created automatically, there is nothing to set up under Integrations.
- New card **Home Assistant integration** on the Database tab: status, installed and running version.
- Updates of the integration code (new add-on versions) are installed automatically; the panel tells you when a restart is needed to load them.

## 0.5.0
- **No more restarts for most changes.** Excluding entities, retention (`purge_keep_days`), auto purge and auto repack are applied to the running recorder right after you save. Only the database URL, the commit interval and the very first activation still need a Home Assistant restart; the panel says exactly which.
- This needs the **Recorder Studio integration 0.5.0 or newer** (Marketplace / HACS) next to the add-on; it provides the service `recorder_studio.apply_config`. It also works when the recorder uses PostgreSQL/MariaDB. Without it the add-on behaves as before (restart needed) and says so.

## 0.4.1
- Fix: copying history failed with `Duplicate entry ... for key 'PRIMARY'` while Home Assistant was recording into the same database (Home Assistant took ids the copy still needed). The id range is now reserved up front.
- A failed copy now removes everything it inserted, so you can simply try again.

## 0.4.0
- New: **Copy history** (Database tab). Copies the history of a SQLite file (states, events, statistics) into the add-on's PostgreSQL/MariaDB, so graphs and statistics continue after switching.
- The SQLite source is only read and stays untouched as your backup. Home Assistant may keep recording while copying; existing rows are never overwritten.
- A second copy of the same file is refused unless you confirm it (it would duplicate the history).

## 0.3.2
- An already stored `mysql+pymysql://` URL is converted to `mysql://` on start.

## 0.3.1
- Fix: MariaDB URL now uses `mysql://` (the `mysqlclient` driver Home Assistant ships). `mysql+pymysql://` made the recorder fail with `No module named 'pymysql'`. If you already activated MariaDB, click **Use this database for the recorder** again (or deactivate) and restart HA.

## 0.3.0
- Choose the database engine (SQLite, PostgreSQL, MariaDB) and the SQLite file from the **Database** tab; no add-on restart needed. The add-on option `engine` is only the starting value.
- The add-on refuses to stop the database server Home Assistant is recording into.

## 0.2.1
- MariaDB: network access is now enabled (Alpine ships it with `skip-networking`), so Home Assistant can connect.
- The database server only counts as running after a real TCP login works.

## 0.2.0
- New: run **PostgreSQL** or **MariaDB** inside the add-on (option `engine`), experimental.
- New: option `sqlite_file` for a separate SQLite file next to Home Assistant's default one.
- New **Database** tab: status, version, size, and a button to point the recorder at the chosen database.
- Statistics follow the database Home Assistant actually writes to.
- Add-on backups are cold (the add-on stops while it is backed up).

## 0.1.3
- Fix: the Home Assistant config folder is mounted at `/homeassistant`, not `/config`.

## 0.1.2
- Fix: the Supervisor token was not passed to the server, so Home Assistant data stayed empty.

## 0.1.1
- Fix: the add-on crashed on start because a YAML library was missing from the image.

## 0.1.0
- First release: Recorder Studio inside an add-on (SQLite, read-only analysis, sidebar panel).
