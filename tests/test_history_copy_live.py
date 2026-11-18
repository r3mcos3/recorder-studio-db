"""The history copy against real PostgreSQL/MariaDB servers (CI service containers). Skipped without them."""
import os
import sqlite3

import pytest

from studio.core import history_copy as hc
from test_history_copy import build_source

PG = os.environ.get("TEST_PG_DSN")
MY = os.environ.get("TEST_MARIADB")

TABLES = ["states", "events", "state_attributes", "event_data", "states_meta", "event_types", "statistics", "statistics_short_term", "statistics_meta"]


def ddl(dialect):
    pg = dialect == "postgresql"
    pk = "BIGSERIAL PRIMARY KEY" if pg else "BIGINT AUTO_INCREMENT PRIMARY KEY"
    blob, dbl, txt = ("BYTEA", "DOUBLE PRECISION", "TEXT") if pg else ("BLOB", "DOUBLE", "LONGTEXT")
    flag = "BOOLEAN" if pg else "TINYINT(1)"
    stat = f"id {pk}, created_ts {dbl}, metadata_id BIGINT, start_ts {dbl}, mean {dbl}, mean_weight {dbl}, min {dbl}, max {dbl}, last_reset_ts {dbl}, state {dbl}, sum {dbl}, UNIQUE (metadata_id, start_ts)"
    return [
        f"CREATE TABLE states_meta (metadata_id {pk}, entity_id VARCHAR(255) UNIQUE)",
        f"CREATE TABLE event_types (event_type_id {pk}, event_type VARCHAR(255) UNIQUE)",
        f"CREATE TABLE state_attributes (attributes_id {pk}, hash BIGINT, shared_attrs {txt})",
        f"CREATE TABLE event_data (data_id {pk}, hash BIGINT, shared_data {txt})",
        f"CREATE TABLE states (state_id {pk}, state VARCHAR(255), last_changed_ts {dbl}, last_reported_ts {dbl}, last_updated_ts {dbl}, old_state_id BIGINT REFERENCES states (state_id), attributes_id BIGINT REFERENCES state_attributes (attributes_id), origin_idx SMALLINT, context_id_bin {blob}, context_user_id_bin {blob}, context_parent_id_bin {blob}, metadata_id BIGINT REFERENCES states_meta (metadata_id))",
        f"CREATE TABLE events (event_id {pk}, event_type_id BIGINT, data_id BIGINT, origin_idx SMALLINT, time_fired_ts {dbl}, context_id_bin {blob}, context_user_id_bin {blob}, context_parent_id_bin {blob})",
        f"CREATE TABLE statistics_meta (id {pk}, statistic_id VARCHAR(255) UNIQUE, source VARCHAR(32), unit_of_measurement VARCHAR(255), unit_class VARCHAR(255), has_mean {flag}, has_sum {flag}, name VARCHAR(255), mean_type SMALLINT)",
        f"CREATE TABLE statistics ({stat})",
        f"CREATE TABLE statistics_short_term ({stat})",
    ]


def pg_connect():
    import psycopg2

    return psycopg2.connect(PG)


def my_connect():
    import pymysql

    host, port, user, pw, db = MY.split(":")
    return pymysql.connect(host=host, port=int(port), user=user, password=pw, database=db)


CASES = [
    pytest.param("postgresql", pg_connect, id="postgresql", marks=pytest.mark.skipif(not PG, reason="no TEST_PG_DSN")),
    pytest.param("mariadb", my_connect, id="mariadb", marks=pytest.mark.skipif(not MY, reason="no TEST_MARIADB")),
]


@pytest.mark.parametrize("dialect,connect", CASES)
def test_copy_into_real_server(dialect, connect, tmp_path):
    conn = connect()
    cur = conn.cursor()
    for t in TABLES:
        cur.execute(f"DROP TABLE IF EXISTS {t} CASCADE" if dialect == "postgresql" else f"DROP TABLE IF EXISTS {t}")
    if dialect == "mariadb":
        cur.execute("SET FOREIGN_KEY_CHECKS = 1")
    for stmt in ddl(dialect):
        cur.execute(stmt)
    ph = "%s"
    cur.execute(f"INSERT INTO states_meta (entity_id) VALUES ({ph})", ("sensor.a",))  # Home Assistant already knows this one
    cur.execute(f"INSERT INTO statistics_meta (statistic_id, source, has_mean, has_sum, name) VALUES ({ph}, {ph}, {ph}, {ph}, {ph})", ("sensor.a", "recorder", True if dialect == "postgresql" else 1, False if dialect == "postgresql" else 0, "A"))
    cur.execute(f"INSERT INTO statistics (created_ts, metadata_id, start_ts, mean) VALUES (1, 1, 7200, 42)")
    conn.commit()
    conn.close()

    src = tmp_path / "src.db"
    build_source(src)
    progress = hc.Progress()
    copied = hc.copy_history(str(src), connect, dialect, progress, batch=2)
    assert copied["states"] == 3 and progress.done == progress.total

    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM states")
    assert cur.fetchone()[0] == 3
    cur.execute("SELECT COUNT(*) FROM states_meta")
    assert cur.fetchone()[0] == 2  # sensor.a reused, sensor.b added
    cur.execute("SELECT s.state, o.state FROM states s LEFT JOIN states o ON o.state_id = s.old_state_id WHERE s.state = '2'")
    assert cur.fetchone() == ("2", "1")
    cur.execute("SELECT COUNT(*) FROM statistics")
    assert cur.fetchone()[0] == 3  # 7200 kept as Home Assistant has it, 3600 added, sensor.gone's row added
    cur.execute("SELECT mean FROM statistics WHERE start_ts = 7200 AND metadata_id = 1")
    assert cur.fetchone()[0] == 42
    # Home Assistant keeps writing afterwards: new ids must not collide with the copied ones
    cur.execute("INSERT INTO state_attributes (hash, shared_attrs) VALUES (5, '{}')")
    cur.execute("INSERT INTO states (state, last_updated_ts) VALUES ('later', 1000.0)")
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM states")
    assert cur.fetchone()[0] == 4
    conn.close()
