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


# The integration's version is NOT the add-on's version: Home Assistant only has to be restarted to load a new add-on
# release if the integration code itself changed. So change the code => bump the manifest version and add its hash here.
KNOWN_CODE = {"0.8.4": "54dc28f507ec3e3990d042f09044e4041edc3aa4a1f586f5e0cc560c2405fd35", "0.8.3": "9bdd0dc9e70cfcff0e60cb84708064e31f72c18994572ca881cfe57f71091403", "0.8.2": "71a6b45cdd6615972dfffa09cab9bb7a256bb18ba4421681a38e8ccf85417b66", "0.8.1": "82c1419482404011aaff3bd5f05314551a36b67ce48d0162f65b8a8f277be87d", "0.8.0": "ef582ec68df1e2323d3dcf588115ec2d12c8099f8e68899731bc31e056fc4e7c", "0.7.0": "45bb08536f1988b4226943d4769f27c08447fa5da8e03e2c0226cd934cb5795f", "0.6.5": "0db90d5c4ec18cdef33b2f657a05009a5ddec20fa86c51b387e3fe4e77dd0a97"}


def _code_hash() -> str:
    import hashlib

    h = hashlib.sha256()
    for path in sorted(integration.SOURCE.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.name != "manifest.json":
            h.update(str(path.relative_to(integration.SOURCE)).encode())
            h.update(path.read_bytes())
    return h.hexdigest()


def test_version_is_bumped_whenever_the_integration_code_changes():
    version = integration.source_version()
    assert KNOWN_CODE.get(version) == _code_hash(), (
        f"The integration code changed. Bump the version in its manifest.json and add the new hash to KNOWN_CODE: {_code_hash()}"
    )


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
