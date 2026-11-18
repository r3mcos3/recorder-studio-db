"""Installs the small Home Assistant integration that ships with this add-on.

Home Assistant's recorder can only be changed from inside Home Assistant, so the add-on brings a tiny custom
integration (recorder_studio_db, service apply_config) and copies it into <config>/custom_components itself.
Home Assistant has to be restarted once to load a new or updated copy.
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
import shutil

DOMAIN = "recorder_studio_db"
SOURCE = Path(__file__).resolve().parent.parent / "integration" / "custom_components" / DOMAIN
_LOGGER = logging.getLogger(__name__)


def _files(root: Path) -> dict[str, str]:
    """relative path -> sha256, ignoring Python caches."""
    out: dict[str, str] = {}
    if not root.is_dir():
        return out
    for path in sorted(root.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            out[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def source_version(source: Path = SOURCE) -> str:
    try:
        return json.loads((source / "manifest.json").read_text(encoding="utf-8"))["version"]
    except (OSError, ValueError, KeyError):
        return "unknown"


def target_dir(config_dir: Path) -> Path:
    return Path(config_dir) / "custom_components" / DOMAIN


def install(config_dir: Path, source: Path = SOURCE) -> str:
    """Make <config>/custom_components/recorder_studio_db identical to the bundled copy.

    Returns "installed", "updated" or "current". Raises OSError when the config folder cannot be written.
    """
    wanted = _files(source)
    if not wanted:
        raise OSError(f"the bundled integration is missing ({source})")
    target = target_dir(config_dir)
    present = _files(target)
    if present == wanted:
        return "current"
    state = "updated" if present else "installed"
    staging = target.with_name(f".{DOMAIN}.new")
    shutil.rmtree(staging, ignore_errors=True)
    shutil.copytree(source, staging, ignore=shutil.ignore_patterns("__pycache__"))
    if target.exists():
        shutil.rmtree(target)
    staging.rename(target)
    _LOGGER.info("integration %s: %s version %s", state, DOMAIN, source_version(source))
    return state
