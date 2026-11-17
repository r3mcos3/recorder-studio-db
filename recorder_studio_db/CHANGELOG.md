# Changelog

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
