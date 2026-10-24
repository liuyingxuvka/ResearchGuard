"""Shared lazy loading for the member package APIs."""
from __future__ import annotations
from importlib import import_module
from typing import Any, Mapping


def lazy_exports(public_api: Mapping[str, tuple[str, ...]], namespace: dict[str, Any]):
    exports = {name: module for module, names in public_api.items() for name in names}

    def get_attribute(name: str):
        if name not in exports:
            raise AttributeError(f"module {namespace['__name__']!r} has no attribute {name!r}")
        value = getattr(import_module(exports[name]), name)
        namespace[name] = value
        return value

    def list_attributes():
        return sorted(set(namespace) | set(exports))

    return get_attribute, list_attributes
