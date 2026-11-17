"""Growth, attribute sizes, history, alerts and suggestions."""
import sqlite3
from datetime import datetime, timezone

from studio.core import alerts, db_stats, history, suggestions, tree


# ---- recent counts / attribute sizes -----------------------------------------
def test_recent_counts_only_last_24h(rich_db):
    conn = sqlite3.connect(f"file:{rich_db}?mode=ro", uri=True)
    assert db_stats.recent_counts(conn) == {"sensor.chatty_rssi": 60, "sensor.quiet": 5, "light.kitchen": 3}
    conn.close()


def test_recent_counts_old_schema_is_empty(synthetic_db):
    conn = sqlite3.connect(synthetic_db)
    assert db_stats.recent_counts(conn) == {}
    conn.close()


def test_attribute_bytes_counts_distinct_blobs_once(rich_db):
    conn = sqlite3.connect(f"file:{rich_db}?mode=ro", uri=True)
    assert db_stats.attribute_bytes(conn) == {"sensor.chatty_rssi": 400, "sensor.quiet": 20, "light.kitchen": 100}
    conn.close()


def test_attribute_bytes_none_without_table(synthetic_db):
    conn = sqlite3.connect(synthetic_db)
    assert db_stats.attribute_bytes(conn) is None
    conn.close()


def test_attribute_bytes_aborts_on_time_limit(rich_db):
    conn = sqlite3.connect(f"file:{rich_db}?mode=ro", uri=True)
    assert db_stats.attribute_bytes(conn, time_limit=-1, progress_ops=1) is None  # deadline already passed: query is interrupted
    conn.close()


def test_analyze_light_vs_full_attrs(rich_db):
    light = db_stats.analyze(rich_db, full=False)
    assert light["recent_total"] == 68 and light["attr_bytes"] is None and light["tables"] is None
    full = db_stats.analyze(rich_db, full=True, attrs=True)
    assert full["attr_bytes"]["sensor.chatty_rssi"] == 400
    assert db_stats.analyze(rich_db, full=True)["attr_bytes"] is None  # not asked for


def test_estimate_entity_bytes_includes_attributes():
    stats = {
        "entity_counts": {"a": 90, "b": 10},
        "total_records": 100,
        "tables": [{"name": "states", "bytes": 10000}, {"name": "state_attributes", "bytes": 2000}],
        "attr_bytes": {"a": 100, "b": 400},
    }
    sizes = db_stats.estimate_entity_bytes(stats)
    # per record 100 B; attribute table 2000 B spread over 500 raw bytes -> scale 4
    assert sizes == {"a": 90 * 100 + 400, "b": 10 * 100 + 1600}
    assert db_stats.estimate_entity_bytes({}) == {}


def test_estimate_without_tables_falls_back_to_file_size():
    sizes = db_stats.estimate_entity_bytes({"entity_counts": {"a": 50, "b": 50}, "total_records": 100, "db_size_bytes": 10000})
    assert sizes == {"a": 2500, "b": 2500}


def test_daily_bytes_uses_each_entitys_own_cost():
    stats = {"entity_counts": {"a": 100, "b": 100}, "recent_counts": {"a": 10, "ghost": 5}}
    assert db_stats.estimate_daily_bytes(stats, {"a": 1000, "b": 100}) == 100  # 1000/100*10; unknown entities ignored


def test_summarize_exposes_new_numbers(rich_db):
    stats = db_stats.analyze(rich_db, full=True, attrs=True)
    s = db_stats.summarize(stats, [], set())
    assert s["recent_total"] == 68 and s["top_recent"][0] == ["sensor.chatty_rssi", 60]
    assert s["top_sizes"][0][0] == "sensor.chatty_rssi" and s["has_attr_sizes"] is True


def test_tree_carries_sizes():
    t = tree.build_tree([], [{"entity_id": "sensor.a", "name": "A", "device_id": None}], set(), {"sensor.a": 3}, 3, {"sensor.a": 1234})
    assert t[0]["entities"][0]["bytes"] == 1234 and t[0]["bytes"] == 1234


# ---- history ---------------------------------------------------------------
def test_snapshot_upserts_per_day_and_trims():
    h, new = history.record_snapshot([], "2026-11-01", 100, 10, 1)
    assert new and len(h) == 1
    h, new = history.record_snapshot(h, "2026-11-01", 120, 12, 2)
    assert not new and h == [{"d": "2026-11-01", "size": 120, "records": 12, "recent": 2}]
    for i in range(500):
        h, _ = history.record_snapshot(h, f"2027-{1 + i // 28:02d}-{1 + i % 28:02d}" if i < 336 else "2028-01-01", 1, 1, 1)
    assert len(h) <= history.MAX_POINTS


def _hist(sizes, start=1):
    return [{"d": f"2026-11-{start + i:02d}", "size": s, "records": 0, "recent": 0} for i, s in enumerate(sizes)]


def test_trend_needs_enough_points():
    assert history.trend(_hist([100, 110]))["growth_per_day"] is None
    assert history.trend([])["points"] == []


def test_trend_linear_growth_and_forecast():
    t = history.trend(_hist([1000, 1100, 1200, 1300, 1400]), free_bytes=5000)
    assert t["growth_per_day"] == 100 and t["days_to_full"] == 50 and t["days_covered"] == 4


def test_trend_flat_and_shrinking_have_no_forecast():
    assert history.trend(_hist([1000] * 5), free_bytes=5000)["days_to_full"] is None
    shrinking = history.trend(_hist([1400, 1300, 1200, 1100, 1000]), free_bytes=5000)
    assert shrinking["growth_per_day"] == -100 and shrinking["days_to_full"] is None


def test_growth_over_a_week():
    h = _hist([1000, 1000, 1000, 1000, 1000, 1000, 1000, 1300])
    assert history.growth_over(h, 7) == 30.0
    assert history.growth_over(_hist([1000, 2000]), 7) is None  # too young to compare a week


# ---- alerts ----------------------------------------------------------------
CFG = {"enabled": True, "free_percent": 10, "growth_percent": 25}


def test_alert_disk_low_and_severity():
    one = alerts.evaluate(CFG, db_size=10, disk_total=1000, disk_free=80, history=[])
    assert [i["id"] for i in one] == ["disk_low"] and one[0]["severity"] == "warning"
    crit = alerts.evaluate(CFG, db_size=10, disk_total=1000, disk_free=40, history=[])
    assert crit[0]["severity"] == "error"
    assert alerts.evaluate(CFG, db_size=10, disk_total=1000, disk_free=500, history=[]) == []


def test_alert_disk_filling_uses_forecast():
    h = _hist([1000, 1100, 1200, 1300, 1400])  # +100/day
    ids = [i["id"] for i in alerts.evaluate(CFG, db_size=1400, disk_total=10000, disk_free=2000, history=h)]
    assert ids == ["disk_filling"]  # 20 days left
    assert alerts.evaluate(CFG, db_size=1400, disk_total=10000, disk_free=9000, history=h) == []


def test_alert_growth_and_disabled():
    h = _hist([1000, 1000, 1000, 1000, 1000, 1000, 1000, 1300])
    ids = [i["id"] for i in alerts.evaluate(CFG, db_size=1300, disk_total=None, disk_free=None, history=h)]
    assert ids == ["db_growth"]
    assert alerts.evaluate({**CFG, "enabled": False}, db_size=1, disk_total=1000, disk_free=1, history=h) == []
    assert alerts.evaluate({**CFG, "growth_percent": 50}, db_size=1300, disk_total=None, disk_free=None, history=h) == []


def test_fmt_bytes():
    assert alerts.fmt_bytes(512) == "512 B" and alerts.fmt_bytes(1536) == "1.5 KB" and alerts.fmt_bytes(5 * 1024**3) == "5.0 GB"


def test_backup_age():
    now = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)
    r = alerts.backup_age(["2026-11-15T06:00:00+00:00", "2026-11-10T06:00:00Z", "garbage"], now)
    assert r["count"] == 2 and round(r["age_hours"]) == 6
    assert alerts.backup_age([], now) == {"last": None, "age_hours": None, "count": 0}
    assert alerts.backup_age(["2026-11-15T10:00:00"], now)["age_hours"] == 2  # naive dates are taken as UTC


# ---- suggestions -----------------------------------------------------------
def _ents(*rows):
    base = {"name": "", "device": "Dev", "category": None, "state_class": None, "device_class": None}
    return [{**base, "entity_id": e, **extra} for e, extra in rows]


def _stats(counts, recent=None):
    return {"entity_counts": counts, "total_records": sum(counts.values()), "recent_counts": recent or {}}


def test_suggests_noisy_diagnostic_entities_first_and_skips_protected():
    counts = {"sensor.x_linkquality": 5000, "light.kitchen": 5000, "sensor.temp": 5000, "sensor.power": 5000, "sensor.other": 100}
    ents = _ents(
        ("sensor.x_linkquality", {"category": "diagnostic", "state_class": "measurement"}),
        ("light.kitchen", {}),
        ("sensor.temp", {"device_class": "temperature", "state_class": "measurement"}),
        ("sensor.power", {"state_class": "measurement", "name": "Heat pump power voltage"}),
        ("sensor.other", {}),
    )
    sizes = {k: v * 10 for k, v in counts.items()}
    res = suggestions.suggest(ents, _stats(counts), sizes, set(), set())
    ids = [s["entity_id"] for s in res["items"]]
    assert ids[0] == "sensor.x_linkquality"  # diagnostic + noisy name, no warning
    assert "light.kitchen" not in ids and "sensor.temp" not in ids  # protected domain / data worth keeping
    power = next(s for s in res["items"] if s["entity_id"] == "sensor.power")
    assert power["confidence"] == "check" and "long-term statistics" in power["warn"]
    assert res["items"][0]["confidence"] == "high"
    assert res["save_bytes"] == sizes["sensor.x_linkquality"]  # entities with a warning do not count towards the saving


def test_excluded_and_dismissed_are_left_out():
    counts = {"sensor.a_rssi": 1000, "sensor.b_rssi": 1000}
    ents = _ents(("sensor.a_rssi", {}), ("sensor.b_rssi", {}))
    res = suggestions.suggest(ents, _stats(counts), {"sensor.a_rssi": 1, "sensor.b_rssi": 1}, {"sensor.a_rssi"}, {"sensor.b_rssi"})
    assert res["items"] == [] and res["dismissed"] == 1


def test_small_or_weak_candidates_not_suggested():
    counts = {"sensor.plain": 50, "sensor.tiny_rssi": 1, "sensor.big_rssi": 9949}
    res = suggestions.suggest(_ents(("sensor.plain", {}), ("sensor.tiny_rssi", {}), ("sensor.big_rssi", {})), _stats(counts), {}, set(), set())
    assert [s["entity_id"] for s in res["items"]] == ["sensor.big_rssi"]


def test_limit_and_per_day_reason():
    counts = {f"sensor.n{i}_rssi": 1000 + i for i in range(20)}
    ents = _ents(*[(e, {}) for e in counts])
    res = suggestions.suggest(ents, _stats(counts, {"sensor.n19_rssi": 3000}), {e: c for e, c in counts.items()}, set(), set(), limit=5)
    assert len(res["items"]) == 5 and res["total_found"] == 20
    assert any("3,000 records" in r for r in res["items"][0]["reasons"])
