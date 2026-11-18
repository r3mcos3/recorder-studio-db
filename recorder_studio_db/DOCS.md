# Recorder Studio DB

> **⚠️ Use at your own risk.** This add-on replaces the database your Home Assistant history lives in, and it is new software. The author is not responsible for lost or damaged data, history, statistics or anything else. **Make a full backup first**, keep your old SQLite file until you are sure everything works, and do not rely on it for anything you cannot afford to lose.

Recorder Studio (what the recorder stores, what fills the database, purge and repack) as a sidebar panel,
plus an optional database server run by this add-on.

## Configuration

| Option | Meaning |
| --- | --- |
| `engine` | Starting value; you can change it later in the panel (Database tab). `sqlite` (Home Assistant's own file, read by the add-on), `postgresql` or `mariadb` (run by this add-on, experimental). |
| `sqlite_file` | SQLite file in your Home Assistant config folder. Keep the default `home-assistant_v2.db`, or use a separate file such as `recorder_studio.db`. |
| `log_level` | Add-on log verbosity. |

## Using PostgreSQL or MariaDB

1. Open the **Database** tab, choose the engine and press *Switch engine*.
2. Wait for the status to say *Running*.
3. Click *Use this database for the recorder* and restart Home Assistant (it creates its tables).
4. Optional: in the card *Copy history*, choose your old SQLite file and press *Copy history*.

Without step 4 Home Assistant starts with an **empty** history in the new database. The copy only reads the SQLite file,
so it stays as your backup, and Home Assistant may keep recording meanwhile. A large database (millions of rows) takes
several minutes; the panel shows the progress. To go back, use *Back to default SQLite* and restart Home Assistant.

The database lives in the add-on's data folder. Add-on backups stop the add-on first, so the copy is consistent.

## Changes without a restart

The add-on installs a small integration of its own (`custom_components/recorder_studio_db`) and creates its entry
automatically. After the first installation, and after add-on updates that change the integration, restart Home
Assistant once; the panel shows a banner with a *Restart* button and the card *Home Assistant integration* on the
Database tab shows the status.

After you save, the add-on writes `recorder_studio.yaml` and calls the service `recorder_studio_db.apply_config`,
which updates the running recorder: entity filter, retention, auto purge and auto repack apply immediately. A restart
is only needed for the database URL, the commit interval and the first time `configuration.yaml` is pointed at
`recorder_studio.yaml`. The panel shows when. The Recorder Studio integration from the Marketplace/HACS is not used and not needed.

To remove it completely, uninstall the add-on and delete `custom_components/recorder_studio_db` yourself.

## Database password

The database URL contains a password. The add-on keeps it in your `secrets.yaml` (entry `recorder_studio_db_url`) and
`recorder_studio.yaml` only says `db_url: !secret recorder_studio_db_url`, so you can keep `recorder_studio.yaml` under
version control. Do not delete that entry from `secrets.yaml`. If `secrets.yaml` cannot be updated safely, the URL stays in
`recorder_studio.yaml` and the Database tab tells you why.

## Safety

The add-on only reads your SQLite database. Purging and repacking go through Home Assistant's own recorder services
and always ask for confirmation. Settings are written to `recorder_studio.yaml`; a Home Assistant restart applies them.
If you also run the Recorder Studio integration, use only one of the two, since both write that file.
