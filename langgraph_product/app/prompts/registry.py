"""Filesystem-backed prompt registry."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from string import Template


PROMPT_ROOT = Path(__file__).resolve().parent


@lru_cache(maxsize=128)
def load_prompt(name: str) -> str:
    path = _prompt_path(name)
    return path.read_text(encoding="utf-8")


def render_prompt(name: str, **values: object) -> str:
    template = Template(load_prompt(name))
    safe_values = {key: "" if value is None else str(value) for key, value in values.items()}
    return template.safe_substitute(safe_values)


def _prompt_path(name: str) -> Path:
    if name.startswith("/") or "\\" in name or ".." in name.split("/"):
        raise ValueError(f"unsafe prompt name: {name}")
    path = (PROMPT_ROOT / f"{name}.md").resolve()
    if not _is_relative_to(path, PROMPT_ROOT):
        raise ValueError(f"prompt path escapes registry: {name}")
    if not path.exists():
        raise FileNotFoundError(f"prompt not found: {name}")
    return path


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False
