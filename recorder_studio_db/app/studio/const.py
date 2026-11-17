import json
import os
from pathlib import Path

ADDON_VERSION = "0.1.1"
CONFIG_DIR = Path(os.environ.get("CONFIG_DIR", "/config"))
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


def addon_options() -> dict:
    try:
        return json.loads(OPTIONS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"engine": "sqlite"}
