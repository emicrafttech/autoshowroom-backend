from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

CATALOG_SOURCE = "json"
CATALOG_PATH = Path(__file__).resolve().parent / "data" / "vehicle_catalog.json"


@lru_cache(maxsize=1)
def _load_catalog() -> dict[str, Any]:
    with CATALOG_PATH.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict) or not isinstance(payload.get("makes"), list):
        raise ValueError(f"Invalid vehicle catalog at {CATALOG_PATH}")
    return payload


def reload_catalog() -> None:
    _load_catalog.cache_clear()


def _collapsed(value: str) -> str:
    return " ".join(value.strip().split())


def _make_index() -> dict[str, dict[str, Any]]:
    return {
        _collapsed(make["name"]).casefold(): make
        for make in _load_catalog()["makes"]
        if isinstance(make, dict) and make.get("name")
    }


def _model_index(make_entry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        _collapsed(model["name"]).casefold(): model
        for model in make_entry.get("models", [])
        if isinstance(model, dict) and model.get("name")
    }


def find_make(value: str) -> dict[str, Any] | None:
    collapsed = _collapsed(value)
    if not collapsed:
        return None
    return _make_index().get(collapsed.casefold())


def find_model(make: str, model: str) -> dict[str, Any] | None:
    make_entry = find_make(make)
    if not make_entry:
        return None
    collapsed = _collapsed(model)
    if not collapsed:
        return None
    return _model_index(make_entry).get(collapsed.casefold())


def normalize_make(value: str) -> str:
    collapsed = _collapsed(value)
    make = find_make(collapsed)
    if make:
        return str(make["name"])
    return collapsed.title() if collapsed else collapsed


def normalize_model(make: str, value: str) -> str:
    collapsed = _collapsed(value)
    model = find_model(make, collapsed)
    if model:
        return str(model["name"])
    return collapsed


def get_makes() -> list[dict[str, int | str]]:
    return [
        {"id": index, "name": str(make["name"])}
        for index, make in enumerate(_load_catalog()["makes"], start=1)
        if isinstance(make, dict) and make.get("name")
    ]


def get_models(make: str) -> list[dict[str, str]]:
    make_entry = find_make(make)
    if not make_entry:
        return []
    return [
        {"name": str(model["name"])}
        for model in make_entry.get("models", [])
        if isinstance(model, dict) and model.get("name")
    ]


def get_trims(make: str, model: str) -> list[dict[str, str]]:
    model_entry = find_model(make, model)
    if not model_entry:
        return []
    return [
        {"name": str(trim)}
        for trim in model_entry.get("trims", [])
        if isinstance(trim, str) and trim.strip()
    ]


def get_full_catalog() -> dict[str, Any]:
    catalog = _load_catalog()
    return {
        "version": catalog.get("version", 1),
        "updatedAt": catalog.get("updatedAt"),
        "makes": catalog.get("makes", []),
        "source": CATALOG_SOURCE,
    }
