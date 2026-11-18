# Changelog

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
