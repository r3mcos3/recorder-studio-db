import sqlite3
import time

from studio.core import db_stats, metrics


def stats(**kw):
    base = {
        "db_size_bytes": 1000, "total_records": 500, "recent_total": 40, "free_bytes": 100, "generated_at": "2026-11-18T08:00:00+00:00",
        "tables": [{"name": "states", "bytes": 500}, {"name": "state_attributes", "bytes": 200}, {"name": "events", "bytes": 100},
                   {"name": "event_data", "bytes": 50}, {"name": "statistics", "bytes": 80}, {"name": "statistics_short_term", "bytes": 40}],
        "extra": {"table_rows": {"states": 480, "events": 70, "statistics": 300, "statistics_short_term": 900}, "oldest_ts": 1_700_000_000.0, "dead_ratio": None, "rows_estimated": False},
    }
    base.update(kw)
    return base


def test_sizes_are_grouped_for_the_sensors():
    m = metrics.build(stats(), {"growth_per_day": 12.7, "disk_free": 5000, "days_to_full": 400}, "SQLite", "3.46")
    s = m["sensors"]
    assert s["engine"] == "SQLite 3.46" and s["database_size"] == 1000
    assert (s["states_size"], s["attributes_size"], s["events_size"], s["statistics_size"]) == (500, 200, 150, 120)
    assert (s["states_count"], s["events_count"], s["statistics_count"]) == (480, 70, 1200)
    assert s["growth_per_day"] == 12 and s["disk_free"] == 5000 and s["days_to_full"] == 400
    assert s["oldest_record"].startswith("2023-11-14")
    assert m["tables"][0] == {"name": "states", "bytes": 500, "rows": 480, "share": 50.0}


def test_fragmentation_from_free_space_or_dead_tuples():
    assert metrics.fragmentation(stats()) == (10.0, 100)
    pg = stats(free_bytes=0, extra={"dead_ratio": 0.25, "table_rows": {}})
    assert metrics.fragmentation(pg) == (25.0, 250)
    assert metrics.build(pg, {}, "PostgreSQL")["fragmentation_kind"] == "dead_tuples"
    assert metrics.fragmentation(stats(free_bytes=None)) == (None, None)


def test_missing_figures_stay_none_not_zero():
    m = metrics.build({"db_size_bytes": 0, "total_records": 0}, {}, "MariaDB")
    assert all(v is None for k, v in m["sensors"].items() if k != "engine")
    assert m["tables"] == []


def test_growth_falls_back_to_the_estimate_without_a_trend():
    m = metrics.build(stats(), {"growth_per_day": None, "bytes_per_day": 2048}, "SQLite")
    assert m["sensors"]["growth_per_day"] == 2048


def test_sqlite_extras_count_rows_and_find_the_oldest_record(tmp_path):
    from test_history_copy import build_source

    path = tmp_path / "h.db"
    build_source(path)
    conn = sqlite3.connect(path)
    present = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    ex = db_stats.extras(conn, present)
    assert ex["table_rows"]["states"] == 3 and ex["table_rows"]["events"] == 1 and ex["table_rows"]["statistics"] == 3
    assert ex["oldest_ts"] == 100.0 and ex["rows_estimated"] is False


def test_full_analysis_carries_extra_and_version(rich_db):
    res = db_stats.analyze(rich_db, full=True)
    assert res["extra"]["oldest_ts"] is not None and res["version"] == sqlite3.sqlite_version
    assert db_stats.analyze(rich_db, full=False)["extra"] is None  # the light run leaves it to the previous full result


def test_old_table_names_do_not_break_extras(synthetic_db):
    conn = sqlite3.connect(synthetic_db)
    ex = db_stats.extras(conn, {"states"})
    assert ex["table_rows"] == {"states": 100} and ex["oldest_ts"] is None  # no timestamp column in this old schema
