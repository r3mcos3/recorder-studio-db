"""Keeps one entry in Home Assistant's secrets.yaml, without disturbing anything else in that file.

The database URL of the add-on contains a password. recorder_studio.yaml lives in a folder people put under version
control, so it refers to the secret (`db_url: !secret recorder_studio_db_url`) and the URL itself goes into secrets.yaml,
which is the file Home Assistant users already keep out of git.

Pure Python (no Home Assistant). Safety rules:
  * the file is only touched when its content parses as a plain YAML mapping and stays identical apart from our key
  * a copy of the previous content is kept outside the config folder (a backup next to it would not be git-ignored)
  * the write is atomic and keeps the file's permissions
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from urllib.parse import urlsplit

import yaml

SECRET_KEY = "recorder_studio_db_url"


class SecretsError(Exception):
    """secrets.yaml could not be updated safely; nothing was changed."""


def has_password(url: str | None) -> bool:
    try:
        return bool(url and urlsplit(url).password)
    except ValueError:
        return False


def _parse(text: str) -> dict:
    try:
        data = yaml.safe_load(text) if text.strip() else {}
    except yaml.YAMLError as err:
        raise SecretsError(f"secrets.yaml is not plain YAML ({err}); leaving it alone") from None
    if not isinstance(data, dict):
        raise SecretsError("secrets.yaml is not a mapping; leaving it alone")
    return data


def _line(key: str, value: str) -> str:
    return f"{key}: {json.dumps(value)}"  # a JSON string is a valid double-quoted YAML scalar


def set_secret(path: Path, key: str, value: str, backup: Path | None = None) -> bool:
    """Make `key: value` part of the secrets file. Returns True when the file was changed."""
    path = Path(path)
    try:
        old = path.read_text(encoding="utf-8") if path.exists() else ""
    except OSError as err:
        raise SecretsError(f"cannot read {path}: {err}") from None
    before = _parse(old)
    if before.get(key) == value:
        return False
    pattern = re.compile(rf"^{re.escape(key)}[ \t]*:.*$", re.M)
    if len(pattern.findall(old)) == 1:
        new = pattern.sub(lambda _m: _line(key, value), old, count=1)
    elif not pattern.search(old):
        new = old + ("" if not old or old.endswith("\n") else "\n") + _line(key, value) + "\n"
    else:
        raise SecretsError(f"{key} appears more than once in secrets.yaml; leaving it alone")
    expected = {**before, key: value}
    if _parse(new) != expected:
        raise SecretsError("the updated secrets.yaml would not match what was expected; leaving it alone")
    if backup and old:
        try:
            Path(backup).parent.mkdir(parents=True, exist_ok=True)
            Path(backup).write_text(old, encoding="utf-8")
            os.chmod(backup, 0o600)
        except OSError:
            pass  # a missing backup must not stop the update; the change is verified below
    _write(path, new)
    if _parse(path.read_text(encoding="utf-8")) != expected:  # read back what is really on disk
        if old:
            _write(path, old)
        raise SecretsError("secrets.yaml did not read back correctly; restored")
    return True


def _write(path: Path, content: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        if path.exists():
            shutil.copymode(path, tmp)
        else:
            os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


PLAIN_DB_URL = re.compile(r"^db_url:[ \t]*(?P<value>[^\s!#][^\n]*?)[ \t]*$", re.M)


def plain_db_url(yaml_text: str) -> str | None:
    """The URL when recorder_studio.yaml still holds it as plain text with a password (None otherwise)."""
    match = PLAIN_DB_URL.search(yaml_text)
    if not match:
        return None
    value = match.group("value").strip("'\"")
    return value if has_password(value) else None


def replace_with_secret(yaml_text: str, key: str = SECRET_KEY) -> str:
    """Swap the plain-text db_url line for a reference to the secret."""
    return PLAIN_DB_URL.sub(f"db_url: !secret {key}", yaml_text, count=1)
