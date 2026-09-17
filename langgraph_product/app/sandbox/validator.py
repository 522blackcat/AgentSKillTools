"""Safe validation command planning."""

from __future__ import annotations

from dataclasses import dataclass


ALLOWED_COMMANDS = {
    ("pytest",),
    ("ruff", "check"),
    ("mypy",),
    ("python", "-m", "compileall"),
}


@dataclass(frozen=True)
class SandboxCommand:
    argv: tuple[str, ...]
    timeout_seconds: int


def validate_command(argv: list[str], timeout_seconds: int = 120) -> SandboxCommand:
    command = tuple(argv)
    if not any(command[: len(allowed)] == allowed for allowed in ALLOWED_COMMANDS):
        raise ValueError(f"command not allowed: {' '.join(argv)}")
    if timeout_seconds <= 0 or timeout_seconds > 300:
        raise ValueError("timeout_seconds must be between 1 and 300")
    return SandboxCommand(argv=command, timeout_seconds=timeout_seconds)
