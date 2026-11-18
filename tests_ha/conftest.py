"""Tests of the integration this add-on installs into Home Assistant (needs pytest-homeassistant-custom-component).

Run with:  python -m pytest tests_ha      (and python -m pytest tests_ha_recorder for the real-recorder test)
"""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "recorder_studio_db" / "app" / "integration"))


@pytest.fixture(autouse=True)
def _enable_custom_integrations(enable_custom_integrations):
    return


@pytest.fixture
def config_dir(hass, tmp_path):
    hass.config.config_dir = str(tmp_path)
    return tmp_path


@pytest.fixture(autouse=True)
def _no_real_dependencies():
    """`recorder` is a dependency in the manifest; these tests use a fake recorder, so do not start the real one."""
    from unittest.mock import patch

    from homeassistant import setup

    original = setup._async_process_dependencies

    async def fake(hass, config, integration):
        return [] if integration.domain == "recorder_studio_db" else await original(hass, config, integration)

    with patch("homeassistant.setup._async_process_dependencies", fake):
        yield
