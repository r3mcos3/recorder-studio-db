"""Real recorder (HA's recorder_mock must be created before `hass`, so no autouse fixture may use `hass` here)."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "recorder_studio_db" / "app" / "integration"))


@pytest.fixture
def config_dir(hass, tmp_path):
    hass.config.config_dir = str(tmp_path)
    return tmp_path
