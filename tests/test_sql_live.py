"""Runs the PostgreSQL/MariaDB statistics against real servers (CI service containers). Skipped without them."""
import os
import time

import pytest

from studio.core import db_stats_sql

PG = os.environ.get("TEST_PG_DSN")  # host=... dbname=... user=... password=...
MY = os.environ.get("TEST_MARIADB")  # host:port:user:password:database

SCHEMA = {
    "postgresql": [
        "DROP TABLE IF EXISTS states, states_meta, state_attributes",
        "CREATE TABLE states_meta (metadata_id SERIAL PRIMARY KEY, entity_id VARCHAR(255))",
        "CREATE TABLE state_attributes (attributes_id SERIAL PRIMARY KEY, shared_attrs TEXT)",
        "CREATE TABLE states (state_id SERIAL PRIMARY KEY, metadata_id INT, attributes_id INT, state VARCHAR(255), last_updated_ts DOUBLE PRECISION)",
    ],
    "mariadb": [
        "DROP TABLE IF EXISTS states, states_meta, state_attributes",
        "CREATE TABLE states_meta (metadata_id INT AUTO_INCREMENT PRIMARY KEY, entity_id VARCHAR(255))",
        "CREATE TABLE state_attributes (attributes_id INT AUTO_INCREMENT PRIMARY KEY, shared_attrs LONGTEXT)",
        "CREATE TABLE states (state_id INT AUTO_INCREMENT PRIMARY KEY, metadata_id INT, attributes_id INT, state VARCHAR(255), last_updated_ts DOUBLE)",
    ],
}


def _pg():
    import psycopg2

    conn = psycopg2.connect(PG)
    conn.autocommit = True
    return conn


def _my():
    import pymysql

    host, port, user, pw, db = MY.split(":")
    return pymysql.connect(host=host, port=int(port), user=user, password=pw, database=db, autocommit=True)


def _fill(connect, dialect):
    conn = connect()
    cur = conn.cursor()
    for stmt in SCHEMA[dialect]:
        cur.execute(stmt)
    cur.execute("INSERT INTO states_meta (entity_id) VALUES ('sensor.a'), ('light.b')")
    cur.execute("INSERT INTO state_attributes (shared_attrs) VALUES ('{\"unit\": \"W\"}')")
    now = time.time()
    for _ in range(30):
        cur.execute("INSERT INTO states (metadata_id, attributes_id, state, last_updated_ts) VALUES (1, 1, 'x', %s)", (now,))
    for _ in range(10):
        cur.execute("INSERT INTO states (metadata_id, attributes_id, state, last_updated_ts) VALUES (2, 1, 'y', %s)", (now - 3 * 86400,))
    cur.close()
    conn.close()


@pytest.mark.parametrize(
    "dialect,connect,enabled",
    [("postgresql", _pg, PG), ("mariadb", _my, MY)],
)
def test_analyze_against_real_server(dialect, connect, enabled):
    if not enabled:
        pytest.skip(f"no {dialect} test server configured")
    _fill(connect, dialect)
    res = db_stats_sql.analyze(connect, dialect, f"{dialect}:test", full=True, attrs=True)
    assert res["entity_counts"] == {"sensor.a": 30, "light.b": 10}
    assert res["total_records"] == 40
    assert res["recent_counts"] == {"sensor.a": 30}
    assert res["db_size_bytes"] > 0
    assert any(t["name"] == "states" for t in res["tables"])
    assert res["attr_bytes"] and res["attr_bytes"]["sensor.a"] > 0
    conn = connect()
    try:
        assert abs(db_stats_sql.latest_ts(conn) - time.time()) < 60
        assert db_stats_sql.version(conn, dialect)
    finally:
        conn.close()
