import os
import stat

import pytest
import yaml

from studio.core import secrets_file as sf
from studio.core import yaml_writer

URL = "mysql://homeassistant:p4ss_w0rd-x@455b5752-recorder-studio-db:3306/homeassistant?charset=utf8mb4"


def test_creates_the_file_private(tmp_path):
    path = tmp_path / "secrets.yaml"
    assert sf.set_secret(path, sf.SECRET_KEY, URL) is True
    assert yaml.safe_load(path.read_text()) == {sf.SECRET_KEY: URL}
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


def test_other_entries_comments_and_permissions_stay(tmp_path):
    path = tmp_path / "secrets.yaml"
    original = '# my secrets\nwifi_password: "abc: def #1"\nota_password: plain\n'
    path.write_text(original)
    os.chmod(path, 0o644)
    assert sf.set_secret(path, sf.SECRET_KEY, URL, backup=tmp_path / "bak" / "secrets.yaml.bak") is True
    text = path.read_text()
    assert text.startswith(original)  # everything that was there is untouched, ours is appended
    assert yaml.safe_load(text) == {"wifi_password": "abc: def #1", "ota_password": "plain", sf.SECRET_KEY: URL}
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o644
    assert (tmp_path / "bak" / "secrets.yaml.bak").read_text() == original  # outside the config folder in real use


def test_no_trailing_newline_is_handled(tmp_path):
    path = tmp_path / "secrets.yaml"
    path.write_text("a: 1")
    sf.set_secret(path, sf.SECRET_KEY, URL)
    assert yaml.safe_load(path.read_text()) == {"a": 1, sf.SECRET_KEY: URL}


def test_changed_value_replaces_only_its_own_line(tmp_path):
    path = tmp_path / "secrets.yaml"
    path.write_text(f'before: 1\n{sf.SECRET_KEY}: "old"\n# after\nafter: 2\n')
    assert sf.set_secret(path, sf.SECRET_KEY, URL) is True
    text = path.read_text()
    assert "# after" in text and yaml.safe_load(text) == {"before": 1, "after": 2, sf.SECRET_KEY: URL}


def test_same_value_does_not_touch_the_file(tmp_path):
    path = tmp_path / "secrets.yaml"
    sf.set_secret(path, sf.SECRET_KEY, URL)
    mtime = os.stat(path).st_mtime_ns
    assert sf.set_secret(path, sf.SECRET_KEY, URL) is False
    assert os.stat(path).st_mtime_ns == mtime


@pytest.mark.parametrize("content", ["a: [unclosed\n", "- just\n- a list\n", f"{sf.SECRET_KEY}: 1\n{sf.SECRET_KEY}: 2\n"])
def test_a_file_that_is_not_what_we_expect_is_left_alone(tmp_path, content):
    path = tmp_path / "secrets.yaml"
    path.write_text(content)
    with pytest.raises(sf.SecretsError):
        sf.set_secret(path, sf.SECRET_KEY, URL)
    assert path.read_text() == content


def test_a_write_that_does_not_read_back_is_undone(tmp_path, monkeypatch):
    path = tmp_path / "secrets.yaml"
    path.write_text("a: 1\n")
    real = sf._write

    def broken(p, content):
        real(p, content.replace(URL, "x") if URL in content else content)  # corrupt only the new content

    monkeypatch.setattr(sf, "_write", broken)
    with pytest.raises(sf.SecretsError, match="restored"):
        sf.set_secret(path, sf.SECRET_KEY, URL)
    assert yaml.safe_load(path.read_text()) == {"a": 1}


def test_password_detection():
    assert sf.has_password(URL) and not sf.has_password("sqlite:////config/x.db") and not sf.has_password("mysql://u@h/db") and not sf.has_password(None)


def test_plain_db_url_is_found_and_replaced_in_place():
    text = f"auto_purge: true\ndb_url: {URL}\n\nexclude: {{}}\n"
    assert sf.plain_db_url(text) == URL
    assert sf.replace_with_secret(text) == "auto_purge: true\ndb_url: !secret recorder_studio_db_url\n\nexclude: {}\n"
    quoted = f"db_url: '{URL}'\n"
    assert sf.plain_db_url(quoted) == URL
    assert sf.plain_db_url("db_url: !secret recorder_studio_db_url\n") is None  # already done
    assert sf.plain_db_url("db_url: sqlite:////config/x.db\n") is None  # nothing secret in it
    assert sf.plain_db_url("auto_purge: true\n") is None


def test_rendered_yaml_refers_to_the_secret_not_the_password():
    options = {"purge_keep_days": 14, "db_url": URL}
    plain = yaml_writer.render_yaml(options, [], [])
    secret = yaml_writer.render_yaml(options, [], [], db_url_secret="recorder_studio_db_url")
    assert "p4ss_w0rd" in plain
    assert "db_url: !secret recorder_studio_db_url" in secret and "p4ss_w0rd" not in secret
    assert "db_url" not in yaml_writer.render_yaml({"purge_keep_days": 14}, [], [], db_url_secret="x")  # no URL, no line
