"""Validation of the user-editable manual filter rules."""
from __future__ import annotations

from typing import Any

import yaml

EXCLUDE_KEYS = ("domains", "entity_globs", "event_types")
INCLUDE_KEYS = ("domains", "entity_globs")
ALLOWED = {"exclude": EXCLUDE_KEYS, "include": INCLUDE_KEYS}


def parse_manual_rules(text: str) -> dict[str, dict[str, list[str]]]:
    """Parse the manual rules block. Raises ValueError with a user-facing message.

    Individual entities are deliberately not allowed here: they are owned by the
    entity toggles so the two sources can never fight over the same list.
    """
    text = (text or "").strip()
    if not text:
        return {}
    try:
        loaded: Any = yaml.safe_load(text)
    except yaml.YAMLError as err:
        raise ValueError(f"Invalid YAML: {err}") from err
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ValueError("Rules must be a YAML mapping with 'exclude' and/or 'include'.")

    result: dict[str, dict[str, list[str]]] = {}
    for top, body in loaded.items():
        if top not in ALLOWED:
            raise ValueError(f"Unsupported key '{top}'. Use 'exclude' or 'include'.")
        if not isinstance(body, dict):
            raise ValueError(f"'{top}' must be a mapping.")
        section: dict[str, list[str]] = {}
        for sub, items in body.items():
            if sub == "entities":
                raise ValueError(f"'{top}.entities' is managed by the entity toggles, not here.")
            if sub not in ALLOWED[top]:
                raise ValueError(f"Unsupported key '{top}.{sub}'. Allowed: {', '.join(ALLOWED[top])}.")
            if not isinstance(items, list) or not all(isinstance(i, str) for i in items):
                raise ValueError(f"'{top}.{sub}' must be a list of strings.")
            cleaned = sorted({i.strip() for i in items if i.strip()})
            if cleaned:
                section[sub] = cleaned
        if section:
            result[top] = section
    return result


def rules_to_text(rules: dict[str, dict[str, list[str]]]) -> str:
    if not rules:
        return ""
    return yaml.safe_dump(rules, sort_keys=False, default_flow_style=False)
