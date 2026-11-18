"""Import an existing recorder config and switch configuration.yaml over to our file."""
from __future__ import annotations

import difflib
import os
import re
from pathlib import Path
from typing import Any

import yaml

from .rules import rules_to_text

SIMPLE_OPTIONS = ("auto_purge", "auto_repack", "purge_keep_days", "commit_interval", "db_url", "db_max_retries", "db_retry_wait")
KNOWN_TOP = set(SIMPLE_OPTIONS) | {"exclude", "include"}
MAX_FILE_BYTES = 1_000_000
MAX_FILES_SCANNED = 600
MAX_DEPTH = 3
SKIP_DIRS = {
    ".storage", ".git", ".cloud", ".venv", "custom_components", "www", "deps", "tts", "backups", "blueprints",
    "themes", "node_modules", "__pycache__", "zigbee2mqtt", "esphome", "image", "media", "tmp",
}
SKIP_FILES = {"secrets.yaml", "known_devices.yaml"}
MARKER = "# [recorder_studio] previous recorder config, replaced by the include below:"


class _Loader(yaml.SafeLoader):
    """SafeLoader that tolerates HA tags such as !include / !secret (kept as plain strings)."""


def _any_tag(loader: yaml.SafeLoader, suffix: str, node: yaml.Node) -> str:
    return f"!{suffix} {getattr(node, 'value', '')}"


_Loader.add_multi_constructor("!", _any_tag)


def find_block(lines: list[str], key: str = "recorder") -> tuple[int, int] | None:
    """Return [start, end) line range of a top-level `key:` block (comments after it excluded)."""
    start = next(
        (i for i, ln in enumerate(lines) if re.match(rf"^{re.escape(key)}\s*:", ln)),
        None,
    )
    if start is None:
        return None
    end = start + 1
    last_content = start + 1
    while end < len(lines):
        ln = lines[end]
        if ln.strip() and not ln.startswith((" ", "\t", "#", "-")):
            break
        if ln.strip() and not ln.lstrip().startswith("#"):
            last_content = end + 1
        end += 1
    return start, last_content


def parse_recorder_config(data: dict[str, Any]) -> dict[str, Any]:
    """Map a recorder: mapping onto Recorder Studio's data model."""
    warnings: list[str] = []
    options = {k: data[k] for k in SIMPLE_OPTIONS if k in data}
    for key, value in list(options.items()):
        if isinstance(value, str) and value.startswith("!"):
            del options[key]
            warnings.append(f"'{key}' uses a YAML tag ({value}); set it manually, it was not imported.")
    for key in data:
        if key not in KNOWN_TOP:
            warnings.append(f"Option '{key}' is not supported and was left out.")

    exclude = data.get("exclude") or {}
    include = data.get("include") or {}
    excluded = [str(e) for e in exclude.get("entities", []) or []]
    rules: dict[str, dict[str, list[str]]] = {}
    for section, body, keys in (
        ("exclude", exclude, ("domains", "entity_globs", "event_types")),
        ("include", include, ("domains", "entity_globs")),
    ):
        picked = {k: [str(v) for v in body[k]] for k in keys if body.get(k)}
        if picked:
            rules[section] = picked

    rescued: list[str] = []
    inc_entities = [str(e) for e in include.get("entities", []) or []]
    if inc_entities:
        if exclude.get("domains") or exclude.get("entity_globs") or include.get("domains") or include.get("entity_globs"):
            rescued = inc_entities
        else:
            warnings.append(
                "include.entities without a domain/glob filter acts as an allowlist; "
                "this is not supported and was left out."
            )
    if include.get("event_types"):
        warnings.append("include.event_types is not supported and was left out.")

    return {
        "options": options,
        "excluded_entities": sorted(set(excluded)),
        "rescued_entities": sorted(set(rescued)),
        "rules_text": rules_to_text(rules),
        "warnings": warnings,
    }


def read_legacy_file(text: str) -> dict[str, Any]:
    """Parse a standalone recorder yaml (e.g. gui_recorder.yaml)."""
    data = yaml.load(text, Loader=_Loader) or {}
    if not isinstance(data, dict):
        raise ValueError("File does not contain a recorder mapping.")
    return parse_recorder_config(data)


def inspect_configuration(config_text: str, target_file: str) -> dict[str, Any]:
    """Describe how recorder is currently configured in configuration.yaml."""
    lines = config_text.splitlines()
    rng = find_block(lines)
    if rng is None:
        return {"state": "absent", "block": "", "imported": None}
    start, end = rng
    block = "\n".join(lines[start:end])
    first = lines[start].partition(":")[2].strip()
    if first.startswith("!include"):
        target = first.split(None, 1)[1].strip() if " " in first else ""
        state = "active" if target == target_file else "other_include"
        return {"state": state, "block": block, "include_target": target, "imported": None}
    body = "\n".join(lines[start:end])
    try:
        parsed = yaml.load(body, Loader=_Loader) or {}
        data = parsed.get("recorder") or {}
        if not isinstance(data, dict):
            data = {}
    except yaml.YAMLError as err:
        return {"state": "invalid", "block": block, "imported": None, "error": str(err)}
    return {"state": "inline", "block": block, "imported": parse_recorder_config(data)}


def activate(config_text: str, target_file: str) -> str:
    """Return configuration.yaml text with recorder replaced by an include of target_file."""
    lines = config_text.splitlines()
    include_line = f"recorder: !include {target_file}"
    rng = find_block(lines)
    if rng is None:
        sep = [] if not lines or not lines[-1].strip() else [""]
        return "\n".join(lines + sep + [include_line]) + "\n"
    start, end = rng
    old = lines[start:end]
    if len(old) == 1 and old[0].partition(":")[2].strip().startswith("!include"):
        new = [include_line]
    else:
        new = [MARKER] + [f"# {ln}" if ln.strip() else "#" for ln in old] + [include_line]
    return "\n".join(lines[:start] + new + lines[end:]) + "\n"


def diff_text(before: str, after: str, name: str = "configuration.yaml") -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True), after.splitlines(keepends=True), f"{name} (now)", f"{name} (after)"
        )
    )


# ---- more migration sources ------------------------------------------------

def _looks_like_recorder(data: dict[str, Any]) -> bool:
    """A bare mapping is only accepted as recorder config when it uses recorder keys exclusively."""
    return bool(data) and set(data) <= KNOWN_TOP and bool(set(data) & {"exclude", "include"})


def _find_recorder_mapping(data: Any, depth: int = 0) -> dict[str, Any] | None:
    """Find a `recorder:` mapping at the top level, or nested in e.g. homeassistant.packages (depth <= 3)."""
    if not isinstance(data, dict) or depth > 3:
        return None
    if isinstance(data.get("recorder"), dict):
        return data["recorder"]
    for value in data.values():
        if (found := _find_recorder_mapping(value, depth + 1)) is not None:
            return found
    return None


def recorder_mapping(text: str) -> dict[str, Any] | None:
    """Return the recorder config contained in `text` (a `recorder:` key anywhere shallow, or a bare recorder mapping)."""
    try:
        data = yaml.load(text, Loader=_Loader)
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict):
        return None
    found = _find_recorder_mapping(data)
    if found is not None:
        return found
    return data if _looks_like_recorder(data) else None


def parse_text(text: str) -> dict[str, Any]:
    """Parse pasted/loaded YAML text into the import model; raises ValueError when it holds no recorder config."""
    mapping = recorder_mapping(text)
    if mapping is None:
        raise ValueError("No recorder configuration found (expected a recorder: block or recorder options such as exclude:).")
    return parse_recorder_config(mapping)


def safe_config_path(config_dir: Path, rel: str) -> Path:
    """Resolve a user-given relative yaml path strictly inside the config directory."""
    if not rel or rel.startswith(("/", "\\")) or ".." in Path(rel).parts:
        raise ValueError("Use a path relative to the configuration folder.")
    if Path(rel).suffix.lower() not in (".yaml", ".yml"):
        raise ValueError("Only .yaml and .yml files can be imported.")
    base = config_dir.resolve()
    path = (base / rel).resolve()
    if base != path and base not in path.parents:
        raise ValueError("The file must be inside the configuration folder.")
    if not path.is_file():
        raise ValueError(f"File not found: {rel}")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("The file is too large to import (limit 1 MB).")
    return path


def discover_sources(config_dir: Path, our_file: str, config_text: str, legacy_file: str = "gui_recorder.yaml") -> list[dict[str, Any]]:
    """List the places in the config folder that contain a recorder configuration that can be imported.

    Looks at configuration.yaml itself, the file it includes for recorder:, GUI Recorder's file, and any other yaml
    file (up to 3 folders deep, e.g. packages) with a recorder section. Read-only; secrets are never read.
    """
    info = inspect_configuration(config_text, our_file)
    include_target = info.get("include_target", "").strip().strip("'\"") if info["state"] == "other_include" else ""
    out: list[dict[str, Any]] = []
    if info["state"] == "inline" and info.get("imported"):
        out.append({"id": "configuration", "label": "configuration.yaml (inline recorder: block)", "path": "configuration.yaml",
                    "kind": "inline", "excluded": len(info["imported"]["excluded_entities"]), "note": ""})

    base = config_dir.resolve()
    scanned = 0
    found: list[dict[str, Any]] = []
    for root, dirs, files in os.walk(base):
        depth = len(Path(root).relative_to(base).parts)
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")) if depth < MAX_DEPTH else []
        for name in sorted(files):
            if not name.lower().endswith((".yaml", ".yml")) or name in SKIP_FILES or name in (our_file, "configuration.yaml"):
                continue
            path = Path(root) / name
            if path.is_symlink():
                continue
            rel = path.relative_to(base).as_posix()
            scanned += 1
            if scanned > MAX_FILES_SCANNED:
                break
            try:
                if path.stat().st_size > MAX_FILE_BYTES:
                    continue
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if "recorder" not in text and "exclude" not in text:
                continue
            mapping = recorder_mapping(text)
            if mapping is None:
                continue
            parsed = parse_recorder_config(mapping)
            if rel == include_target:
                kind, note = "included", "Included by configuration.yaml; it is replaced when you activate."
            elif rel == legacy_file:
                kind, note = "legacy", "GUI Recorder's file; it stays untouched and becomes inert after activation."
            else:
                kind, note = "other", (
                    "This file is not changed. After activation, remove its recorder: section yourself, otherwise Home Assistant "
                    "reports a duplicate recorder configuration."
                )
            found.append({"id": "legacy" if rel == legacy_file else f"file:{rel}", "label": rel, "path": rel, "kind": kind,
                          "excluded": len(parsed["excluded_entities"]), "note": note})
    order = {"included": 0, "legacy": 1, "other": 2}
    return out + sorted(found, key=lambda e: (order[e["kind"]], e["path"]))


def merge_import(existing: dict[str, Any], imported: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Combine an import with what Recorder Studio already has: entities are united, existing manual rules win."""
    warnings: list[str] = []
    rules = existing.get("rules_text", "")
    if imported.get("rules_text", "").strip():
        if not rules.strip():
            rules = imported["rules_text"]
        elif rules.strip() != imported["rules_text"].strip():
            warnings.append("The imported manual rules differ from your current rules; your current rules were kept.")
    return {
        "options": {**existing.get("options", {}), **imported.get("options", {})},
        "excluded_entities": sorted(set(existing.get("excluded_entities", [])) | set(imported.get("excluded_entities", []))),
        "rescued_entities": sorted(set(existing.get("rescued_entities", [])) | set(imported.get("rescued_entities", []))),
        "rules_text": rules,
    }, warnings
