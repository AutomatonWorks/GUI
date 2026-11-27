from __future__ import annotations


def T(strings: dict[str, str] | None, key: str, default: str, **kwargs) -> str:
    value = (strings or {}).get(key, default)
    return value.format(**kwargs) if kwargs else value
