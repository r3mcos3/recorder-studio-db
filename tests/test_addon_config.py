"""The add-on's config.yaml must parse (Supervisor silently ignores a version it cannot read) and match the code."""
from pathlib import Path

import yaml

from studio.const import ADDON_VERSION

CONFIG = Path(__file__).resolve().parents[1] / "recorder_studio_db" / "config.yaml"


def test_config_yaml_parses_and_matches_code_version():
    data = yaml.safe_load(CONFIG.read_text())
    assert data["slug"] == "recorder_studio_db"
    assert str(data["version"]) == ADDON_VERSION
    assert isinstance(data["description"], str) and data["description"]
