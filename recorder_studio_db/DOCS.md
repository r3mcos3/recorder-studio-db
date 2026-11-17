# Recorder Studio DB

Recorder Studio (what the recorder stores, what fills the database, purge and repack) as a sidebar panel,
plus an optional database server run by this add-on.

## Configuration

| Option | Meaning |
| --- | --- |
| `engine` | `sqlite` (Home Assistant's own file, read by the add-on), `postgresql` or `mariadb` (run by this add-on, experimental). |
| `sqlite_file` | SQLite file in your Home Assistant config folder. Keep the default `home-assistant_v2.db`, or use a separate file such as `recorder_studio.db`. |
| `log_level` | Add-on log verbosity. |

## Using PostgreSQL or MariaDB

1. Set `engine`, save and restart the add-on.
2. Open the **Database** tab and wait for the status to say *Running*.
3. Click *Use this database for the recorder* and restart Home Assistant.

Home Assistant then starts with an **empty** history in the new database. Your old history stays in the SQLite file;
moving it over is planned. To go back, use *Back to default SQLite* and restart Home Assistant.

The database lives in the add-on's data folder. Add-on backups stop the add-on first, so the copy is consistent.

## Safety

The add-on only reads your SQLite database. Purging and repacking go through Home Assistant's own recorder services
and always ask for confirmation. Settings are written to `recorder_studio.yaml`; a Home Assistant restart applies them.
If you also run the Recorder Studio integration, use only one of the two, since both write that file.
