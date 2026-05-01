from __future__ import annotations

from typing import Any

from attrs import asdict, has


def to_plain_data(value: Any) -> Any:
    if value is None:
        return None
    if has(type(value)):
        return {
            key: to_plain_data(item)
            for key, item in asdict(value, recurse=False).items()
        }
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, list):
        return [to_plain_data(item) for item in value]
    if isinstance(value, tuple):
        return [to_plain_data(item) for item in value]
    if isinstance(value, dict):
        return {key: to_plain_data(item) for key, item in value.items()}
    return value
