import sqlite3

import pytest

from studio.core import history_copy as hc

DDL = """
CREATE TABLE states_meta (metadata_id INTEGER PRIMARY KEY AUTOINCREMENT, entity_id TEXT UNIQUE);
CREATE TABLE event_types (event_type_id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT UNIQUE);
CREATE TABLE state_attributes (attributes_id INTEGER PRIMARY KEY AUTOINCREMENT, hash INTEGER, shared_attrs TEXT);
CREATE TABLE event_data (data_id INTEGER PRIMARY KEY AUTOINCREMENT, hash INTEGER, shared_data TEXT);
CREATE TABLE states (state_id INTEGER PRIMARY KEY AUTOINCREMENT, state TEXT, last_changed_ts REAL, last_reported_ts REAL,
  last_updated_ts REAL, old_state_id INTEGER, attributes_id INTEGER, origin_idx INTEGER, context_id_bin BLOB,
  context_user_id_bin BLOB, context_parent_id_bin BLOB, metadata_id INTEGER, last_updated TEXT);
CREATE TABLE events (event_id INTEGER PRIMARY KEY AUTOINCREMENT, event_type_id INTEGER, data_id INTEGER, origin_idx INTEGER,
  time_fired_ts REAL, context_id_bin BLOB, context_user_id_bin BLOB, context_parent_id_bin BLOB);
CREATE TABLE statistics_meta (id INTEGER PRIMARY KEY AUTOINCREMENT, statistic_id TEXT UNIQUE, source TEXT, unit_of_measurement TEXT,
  unit_class TEXT, has_mean INTEGER, has_sum INTEGER, name TEXT, mean_type INTEGER);
CREATE TABLE statistics (id INTEGER PRIMARY KEY AUTOINCREMENT, created_ts REAL, metadata_id INTEGER, start_ts REAL, mean REAL,
  mean_weight REAL, min REAL, max REAL, last_reset_ts REAL, state REAL, sum REAL, UNIQUE (metadata_id, start_ts));
CREATE TABLE statistics_short_term (id INTEGER PRIMARY KEY AUTOINCREMENT, created_ts REAL, metadata_id INTEGER, start_ts REAL, mean REAL,
  mean_weight REAL, min REAL, max REAL, last_reset_ts REAL, state REAL, sum REAL, UNIQUE (metadata_id, start_ts));
"""


def make(path):
    c = sqlite3.connect(path)
    c.executescript(DDL)
    return c


def build_source(path):
    c = make(path)
    c.execute("INSERT INTO states_meta (metadata_id, entity_id) VALUES (7, 'sensor.a'), (8, 'sensor.b')")
    c.execute("INSERT INTO event_types (event_type_id, event_type) VALUES (3, 'state_changed')")
    c.execute("INSERT INTO state_attributes (attributes_id, hash, shared_attrs) VALUES (1, 11, '{}'), (2, 22, '{\"x\":1}')")
    c.execute("INSERT INTO event_data (data_id, hash, shared_data) VALUES (5, 1, '{}')")
    c.execute("INSERT INTO states (state_id, state, last_updated_ts, old_state_id, attributes_id, metadata_id, last_updated) VALUES "
              "(10, '1', 100.0, NULL, 1, 7, 'legacy'), (11, '2', 200.0, 10, 2, 7, 'legacy'), (12, '3', 300.0, 999, 77, 8, 'legacy')")
    c.execute("INSERT INTO events (event_id, event_type_id, data_id, time_fired_ts, context_id_bin) VALUES (20, 3, 5, 100.0, x'01')")
    c.execute("INSERT INTO statistics_meta (id, statistic_id, source, has_mean, has_sum, name) VALUES (1, 'sensor.a', 'recorder', 1, 0, 'A'), (2, 'sensor.gone', 'recorder', 0, 1, 'G')")
    c.execute("INSERT INTO statistics (created_ts, metadata_id, start_ts, mean) VALUES (1, 1, 3600, 1.5), (1, 1, 7200, 2.5), (1, 2, 3600, 9)")
    c.execute("INSERT INTO statistics_short_term (created_ts, metadata_id, start_ts, mean) VALUES (1, 1, 300, 1.0)")
    c.commit()
    c.close()


def build_target(path):
    """Home Assistant already ran on the target and wrote a few rows of its own."""
    c = make(path)
    c.execute("INSERT INTO states_meta (entity_id) VALUES ('sensor.new'), ('sensor.a')")  # sensor.a exists with another id
    c.execute("INSERT INTO event_types (event_type) VALUES ('state_changed')")
    c.execute("INSERT INTO state_attributes (hash, shared_attrs) VALUES (99, '{}')")
    c.execute("INSERT INTO states (state, last_updated_ts, attributes_id, metadata_id) VALUES ('new', 900.0, 1, 1)")
    c.execute("INSERT INTO statistics_meta (statistic_id, source, has_mean, has_sum, name) VALUES ('sensor.a', 'recorder', 1, 0, 'A')")
    c.execute("INSERT INTO statistics (created_ts, metadata_id, start_ts, mean) VALUES (1, 1, 7200, 42)")  # same hour as an old row
    c.commit()
    c.close()


def run_copy(tmp_path):
    src, dst = tmp_path / "src.db", tmp_path / "dst.db"
    build_source(src)
    build_target(dst)
    progress = hc.Progress()
    copied = hc.copy_history(str(src), lambda: sqlite3.connect(dst), "sqlite", progress, batch=2)
    return dst, copied, progress


def test_copy_remaps_and_keeps_existing_rows(tmp_path):
    dst, copied, progress = run_copy(tmp_path)
    c = sqlite3.connect(dst)
    assert c.execute("SELECT COUNT(*) FROM states").fetchone()[0] == 4
    assert c.execute("SELECT state FROM states WHERE state = 'new'").fetchone()  # Home Assistant's own row untouched
    # sensor.a was already known: reused, sensor.b added
    assert c.execute("SELECT COUNT(*) FROM states_meta").fetchone()[0] == 3
    meta_a = c.execute("SELECT metadata_id FROM states_meta WHERE entity_id = 'sensor.a'").fetchone()[0]
    assert c.execute("SELECT COUNT(*) FROM states WHERE metadata_id = ? AND state IN ('1', '2')", (meta_a,)).fetchone()[0] == 2
    assert c.execute("SELECT COUNT(*) FROM event_types").fetchone()[0] == 1
    assert progress.copied["states"] == 3 and copied["events"] == 1
    assert progress.done == progress.total


def test_references_follow_the_offset(tmp_path):
    dst, _, _ = run_copy(tmp_path)
    c = sqlite3.connect(dst)
    rows = {r[0]: r for r in c.execute("SELECT state, state_id, old_state_id, attributes_id FROM states")}
    assert rows["2"][2] == rows["1"][1]  # old_state_id points at the copied predecessor
    assert rows["1"][1] > hc.MARGIN
    assert rows["3"][2] is None and rows["3"][3] is None  # dangling references are dropped, not copied
    attr = c.execute("SELECT shared_attrs FROM state_attributes WHERE attributes_id = ?", (rows["2"][3],)).fetchone()[0]
    assert attr == '{"x":1}'
    ev = c.execute("SELECT data_id, event_type_id FROM events").fetchone()
    assert c.execute("SELECT shared_data FROM event_data WHERE data_id = ?", (ev[0],)).fetchone()
    assert c.execute("SELECT event_type FROM event_types WHERE event_type_id = ?", (ev[1],)).fetchone()[0] == "state_changed"
    assert c.execute("SELECT COUNT(*) FROM states WHERE last_updated IS NOT NULL").fetchone()[0] == 0  # legacy column not copied


def test_statistics_merge_skips_duplicates(tmp_path):
    dst, _, _ = run_copy(tmp_path)
    c = sqlite3.connect(dst)
    assert c.execute("SELECT COUNT(*) FROM statistics_meta").fetchone()[0] == 2
    mid = c.execute("SELECT id FROM statistics_meta WHERE statistic_id = 'sensor.a'").fetchone()[0]
    means = dict(c.execute("SELECT start_ts, mean FROM statistics WHERE metadata_id = ?", (mid,)).fetchall())
    assert means == {3600.0: 1.5, 7200.0: 42.0}  # Home Assistant's value wins for the hour both have
    assert c.execute("SELECT COUNT(*) FROM statistics_short_term").fetchone()[0] == 1


def test_target_without_tables_is_refused(tmp_path):
    src = tmp_path / "src.db"
    build_source(src)
    empty = tmp_path / "empty.db"
    sqlite3.connect(empty).close()
    with pytest.raises(hc.CopyError):
        hc.copy_history(str(src), lambda: sqlite3.connect(empty), "sqlite")


def test_run_reports_errors_instead_of_raising(tmp_path):
    src = tmp_path / "src.db"
    build_source(src)
    empty = tmp_path / "empty.db"
    sqlite3.connect(empty).close()
    p = hc.Progress()
    hc.run(str(src), lambda: sqlite3.connect(empty), "sqlite", p)
    assert p.state == "error" and "Home Assistant tables" in p.error and p.finished


def test_failed_copy_removes_what_it_inserted(tmp_path):
    src, dst = tmp_path / "src.db", tmp_path / "dst.db"
    build_source(src)
    build_target(dst)
    c = sqlite3.connect(dst)
    c.execute("CREATE TRIGGER boom BEFORE INSERT ON events BEGIN SELECT RAISE(ABORT, 'boom'); END")
    c.commit()
    c.close()
    before = {t: sqlite3.connect(dst).execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("states", "state_attributes", "statistics")}
    with pytest.raises(sqlite3.Error):
        hc.copy_history(str(src), lambda: sqlite3.connect(dst), "sqlite", batch=2)
    c = sqlite3.connect(dst)
    for t, n in before.items():
        assert c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] == n  # the copy left nothing behind, Home Assistant's rows stay
    p = hc.Progress()
    hc.run(str(src), lambda: sqlite3.connect(dst), "sqlite", p)
    assert p.state == "error" and "boom" in p.error
