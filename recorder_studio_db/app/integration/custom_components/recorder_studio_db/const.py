"""Constants of the Recorder Studio DB integration (installed by the Recorder Studio DB add-on)."""
import json
from pathlib import Path

DOMAIN = "recorder_studio_db"
CONFIG_FILE = "configuration.yaml"
GENERATED_FILE = "recorder_studio.yaml"


def _manifest_version() -> str:
    try:
        return json.loads((Path(__file__).parent / "manifest.json").read_text(encoding="utf-8"))["version"]
    except (OSError, ValueError, KeyError):
        return "unknown"


VERSION = _manifest_version()
