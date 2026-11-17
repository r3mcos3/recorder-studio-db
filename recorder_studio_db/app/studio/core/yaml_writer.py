"""Rendering and atomic writing of the generated recorder YAML."""
from __future__ import annotations

import os
from pathlib import Path
import tempfile
from typing import Any

import yaml

from .rules import EXCLUDE_KEYS, INCLUDE_KEYS, parse_manual_rules

HEADER = (
    "# Managed by Recorder Studio. Manual edits will be overwritten.\n"
    "# Include from configuration.yaml with:  recorder: !include recorder_studio.yaml\n"
)


def _dump(data: dict) -> str:
    return yaml.safe_dump(data, sort_keys=False, default_flow_style=False).rstrip()


def render_yaml(options: dict[str, Any], excluded: list[str], rescued: list[str], rules_text: str = "") -> str:
    """Render the recorder configuration. Invalid stored rules are ignored, never written."""
    try:
        rules = parse_manual_rules(rules_text)
    except ValueError:
        rules = {}

    out: list[str] = [HEADER]
    out.append(f"auto_purge: {'true' if options.get('auto_purge', True) else 'false'}")
    out.append(f"auto_repack: {'true' if options.get('auto_repack', True) else 'false'}")
    out.append(f"purge_keep_days: {int(options.get('purge_keep_days', 10))}")
    out.append(f"commit_interval: {int(options.get('commit_interval', 5))}")
    for key in ("db_url", "db_max_retries", "db_retry_wait"):
        value = options.get(key)
        if value not in (None, ""):
            out.append(_dump({key: value}))
    out.append("")

    exc_rules = rules.get("exclude", {})
    inc_rules = rules.get("include", {})

    exclude: dict[str, list[str]] = {}
    if excluded:
        exclude["entities"] = sorted(set(excluded))
    for key in EXCLUDE_KEYS:
        if exc_rules.get(key):
            exclude[key] = exc_rules[key]

    # include.entities outranks domain/glob excludes, but on its own it would turn the
    # whole config into an allowlist. Only emit it while a domain/glob filter exists.
    has_filter = any(exc_rules.get(k) or inc_rules.get(k) for k in ("domains", "entity_globs"))
    include: dict[str, list[str]] = {}
    if rescued and has_filter:
        include["entities"] = sorted(set(rescued))
    for key in INCLUDE_KEYS:
        if inc_rules.get(key):
            include[key] = inc_rules[key]

    out.append(_dump({"exclude": exclude}) if exclude else "exclude: {}")
    if include:
        out += ["", _dump({"include": include})]
    return "\n".join(out) + "\n"


def atomic_write(path: Path, content: str) -> None:
    """Write via temp file + rename so HA never reads a half-written config."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise
