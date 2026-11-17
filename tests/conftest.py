import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "recorder_studio_db" / "app"))


@pytest.fixture
def synthetic_db(tmp_path):
    """Small SQLite file with the modern HA schema (states + states_meta). Never the real DB."""
    path = tmp_path / "test.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE states_meta (metadata_id INTEGER PRIMARY KEY, entity_id TEXT);
        CREATE TABLE states (state_id INTEGER PRIMARY KEY, metadata_id INTEGER, state TEXT);
        """
    )
    rows = {"sensor.a": 50, "sensor.b_uptime": 30, "light.kitchen": 15, "sensor.gone": 5}
    for i, (eid, n) in enumerate(rows.items(), start=1):
        conn.execute("INSERT INTO states_meta VALUES (?, ?)", (i, eid))
        conn.executemany("INSERT INTO states (metadata_id, state) VALUES (?, 'x')", [(i,)] * n)
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def rich_db(tmp_path):
    """Modern-schema database with timestamps and shared attributes (never the real DB)."""
    import time

    path = tmp_path / "rich.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE states_meta (metadata_id INTEGER PRIMARY KEY, entity_id TEXT);
        CREATE TABLE state_attributes (attributes_id INTEGER PRIMARY KEY, shared_attrs TEXT);
        CREATE TABLE states (state_id INTEGER PRIMARY KEY, metadata_id INTEGER, state TEXT, attributes_id INTEGER, last_updated_ts REAL);
        CREATE INDEX ix_states_last_updated_ts ON states (last_updated_ts);
        """
    )
    now = time.time()
    # entity -> (records in the last hour, records two days ago, attribute blob length)
    spec = {"sensor.chatty_rssi": (60, 40, 400), "sensor.quiet": (5, 5, 20), "light.kitchen": (3, 2, 100)}
    for i, (eid, (new, old, alen)) in enumerate(spec.items(), start=1):
        conn.execute("INSERT INTO states_meta VALUES (?, ?)", (i, eid))
        conn.execute("INSERT INTO state_attributes VALUES (?, ?)", (i, "x" * alen))
        rows = [(i, "1", i, now - 600)] * new + [(i, "1", i, now - 2 * 86400)] * old
        conn.executemany("INSERT INTO states (metadata_id, state, attributes_id, last_updated_ts) VALUES (?, ?, ?, ?)", rows)
    conn.commit()
    conn.close()
    return path
