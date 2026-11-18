import json
from pathlib import Path

import pytest

from studio import integration

ROOT = Path(__file__).resolve().parent.parent / "recorder_studio_db"


def test_install_update_and_current(tmp_path):
    assert integration.install(tmp_path) == "installed"
    target = integration.target_dir(tmp_path)
    assert (target / "manifest.json").exists() and (target / "live.py").exists()
    assert integration.install(tmp_path) == "current"
    (target / "live.py").write_text("# an old version")
    assert integration.install(tmp_path) == "updated"
    assert "async_apply_live" in (target / "live.py").read_text()
    (target / "__pycache__").mkdir()
    (target / "__pycache__" / "x.pyc").write_bytes(b"cache")
    assert integration.install(tmp_path) == "current"  # Home Assistant's bytecode cache does not count as a change
    assert not (target.parent / ".recorder_studio_db.new").exists()


def test_missing_bundle_is_an_error(tmp_path):
    with pytest.raises(OSError):
        integration.install(tmp_path, source=tmp_path / "nothing")


def test_version_matches_the_add_on():
    import re

    addon = re.search(r'^version: "(.+)"', (ROOT / "config.yaml").read_text(), re.M).group(1)
    assert integration.source_version() == addon


def test_shared_code_is_identical_to_the_panel_copy():
    """The integration is self-contained, so these two files exist twice; they must not drift apart."""
    for name in ("migration.py", "rules.py"):
        assert (integration.SOURCE / name).read_text() == (ROOT / "app" / "studio" / "core" / name).read_text(), name


def test_manifest_is_valid():
    m = json.loads((integration.SOURCE / "manifest.json").read_text())
    assert m["domain"] == "recorder_studio_db" and m["config_flow"] is True and "recorder" in m["dependencies"]


def test_brand_images_are_bundled_and_installed(tmp_path):
    """Home Assistant (2026.3+) shows custom_components/<domain>/brand/icon.png as the integration's logo."""
    for name in ("icon.png", "icon@2x.png", "logo.png", "logo@2x.png"):
        assert (integration.SOURCE / "brand" / name).read_bytes()[:4] == b"\x89PNG"
    integration.install(tmp_path)
    assert (integration.target_dir(tmp_path) / "brand" / "icon.png").exists()
