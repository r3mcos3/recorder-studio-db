import json
import os
from pathlib import Path

ADDON_VERSION = "0.2.0"
def _config_dir() -> Path:
    """`homeassistant_config` is mounted at /homeassistant (the add-on's own /config is a different folder)."""
    if os.environ.get("CONFIG_DIR"):
        return Path(os.environ["CONFIG_DIR"])
    for cand in ("/homeassistant", "/config"):
        if (Path(cand) / "configuration.yaml").exists():
            return Path(cand)
    return Path("/homeassistant")


CONFIG_DIR = _config_dir()
DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
OPTIONS_FILE = DATA_DIR / "options.json"
STORE_FILE = DATA_DIR / "studio.json"
PORT = int(os.environ.get("PORT", "8099"))
WWW_DIR = Path(__file__).resolve().parent.parent / "www"

GENERATED_FILE = "recorder_studio.yaml"
LEGACY_FILE = "gui_recorder.yaml"
CONFIG_FILE = "configuration.yaml"

DEFAULT_DATA = {
    "options": {"purge_keep_days": 10, "auto_purge": True, "auto_repack": True, "commit_interval": 5},
    "excluded_entities": [],
    "rescued_entities": [],
    "rules_text": "",
    "stats": None,
    "history": [],
    "dismissed": [],
    "alerts": {"enabled": True, "free_percent": 10, "growth_percent": 25},
}

ALERT_INTERVAL_HOURS = 6
ATTR_REFRESH_SECONDS = 3600
READ_ONLY_MODE = False


DEFAULT_SQLITE_FILE = "home-assistant_v2.db"
ACTIVE_WINDOW = 900  # seconds: Home Assistant counts as "writing to this database" when its newest state is this recent


def sqlite_file() -> str:
    name = str(addon_options().get("sqlite_file") or DEFAULT_SQLITE_FILE).strip().lstrip("/")
    return name if name and ".." not in name else DEFAULT_SQLITE_FILE


def addon_options() -> dict:
    try:
        return json.loads(OPTIONS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"engine": "sqlite"}
