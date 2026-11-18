import json

from studio import engines


def test_credentials_are_generated_once(tmp_path):
    path = tmp_path / "c.json"
    a = engines.load_credentials(path)
    b = engines.load_credentials(path)
    assert a == b and len(a["password"]) >= 24 and a["user"] == "homeassistant"
    assert oct(path.stat().st_mode & 0o777) == "0o600"


def test_db_urls_and_masking():
    creds = {"user": "homeassistant", "database": "homeassistant", "password": "p@ss/w:rd"}
    pg = engines.build_db_url("postgresql", "abc-recorder-studio-db", creds)
    assert pg == "postgresql://homeassistant:p%40ss%2Fw%3Ard@abc-recorder-studio-db:5432/homeassistant"
    my = engines.build_db_url("mariadb", "h", creds)
    assert my.startswith("mysql://") and my.endswith(":3306/homeassistant?charset=utf8mb4")
    assert "p%40ss" not in engines.mask_url(pg) and "***" in engines.mask_url(pg)
    assert engines.mask_url("sqlite:////config/x.db") == "sqlite:////config/x.db"


def test_credentials_file_corrupt_is_replaced(tmp_path):
    path = tmp_path / "c.json"
    path.write_text("not json")
    assert engines.load_credentials(path)["password"]
    assert json.loads(path.read_text())["password"]
