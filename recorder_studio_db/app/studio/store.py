"""JSON persistence for the studio settings (replaces the Home Assistant Store)."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path

from .const import DEFAULT_DATA


def merge(loaded: dict | None) -> dict:
    data = copy.deepcopy(DEFAULT_DATA)
    if loaded:
        opts = {**data["options"], **loaded.get("options", {})}
        alerts = {**data["alerts"], **(loaded.get("alerts") or {})}
        data.update({k: v for k, v in loaded.items() if k in data})
        data["options"] = opts
        data["alerts"] = alerts
    data["dismissed"] = sorted({str(e).strip() for e in data["dismissed"] if str(e).strip()})
    for key in ("excluded_entities", "rescued_entities"):
        data[key] = sorted({str(e).strip() for e in data[key] if str(e).strip()})
    return data


def load(path: Path) -> dict:
    try:
        return merge(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return merge(None)


def save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    os.replace(tmp, path)
