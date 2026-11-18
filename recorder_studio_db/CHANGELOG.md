# Changelog

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
