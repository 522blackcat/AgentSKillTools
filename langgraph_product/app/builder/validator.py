"""Validation for generated project artifacts."""

from __future__ import annotations

import hashlib
import py_compile
import subprocess
import sys
from pathlib import Path
from typing import Any

from app.config import settings


REQUIRED_FILES = {
    "README.md",
    "docs/ARCHITECTURE.md",
    "docs/RUNBOOK.md",
    ".env.example",
    "docker-compose.yml",
    "pyproject.toml",
    "app/main.py",
    "app/settings.py",
    "app/graph.py",
    "app/models.py",
    "app/llm/gateway.py",
    "app/auth/policy.py",
    "app/observability/events.py",
    "app/evals/cases.py",
    "app/prompts/answer.md",
    "app/prompts/review_summary.md",
    "app/prompts/domains/policy.md",
    "app/rag/embedding.py",
    "app/rag/repository.py",
    "app/rag/citations.py",
    "app/rag/service.py",
    "app/memory/service.py",
    "app/human_review/service.py",
    "tests/test_graph.py",
    "tests/test_rag.py",
    "tests/test_human_review.py",
}


def validate_generated_project(storage_path: str, manifest: dict[str, Any]) -> dict[str, Any]:
    root = Path(storage_path).resolve()
    checks: list[dict[str, Any]] = []
    manifest_files = manifest.get("files", [])
    paths = {item.get("path", "") for item in manifest_files}

    checks.append(_check("storage_path_exists", root.exists() and root.is_dir(), str(root)))
    missing = sorted(REQUIRED_FILES - paths)
    checks.append(_check("required_files", not missing, {"missing": missing}))

    for item in manifest_files:
        relative_path = item.get("path", "")
        target = (root / relative_path).resolve()
        if not _is_relative_to(target, root):
            checks.append(_check("path_safety", False, {"path": relative_path}))
            continue
        if not target.exists():
            checks.append(_check("file_exists", False, {"path": relative_path}))
            continue
        content = target.read_bytes()
        checks.append(
            _check(
                "file_hash",
                hashlib.sha256(content).hexdigest() == item.get("sha256"),
                {"path": relative_path},
            )
        )
        checks.append(
            _check(
                "file_size",
                len(content) == item.get("bytes"),
                {"path": relative_path, "bytes": len(content)},
            )
        )
        if relative_path.endswith(".py"):
            checks.append(_compile_check(target, root))

    checks.extend(_run_sandbox_commands(root))

    failed = [check for check in checks if not check["ok"]]
    return {
        "status": "passed" if not failed else "failed",
        "checks": checks,
        "summary": {
            "total": len(checks),
            "passed": len(checks) - len(failed),
            "failed": len(failed),
        },
    }


def _compile_check(path: Path, root: Path) -> dict[str, Any]:
    relative_path = path.relative_to(root).as_posix()
    try:
        py_compile.compile(str(path), doraise=True)
    except py_compile.PyCompileError as exc:
        return _check("python_compile", False, {"path": relative_path, "error": str(exc)})
    return _check("python_compile", True, {"path": relative_path})


def _run_sandbox_commands(root: Path) -> list[dict[str, Any]]:
    if not root.exists() or not root.is_dir():
        return [_check("sandbox_commands", False, {"error": "storage path missing"})]

    commands = [
        [sys.executable, "-m", "compileall", "app", "tests"],
        [sys.executable, "-m", "pytest", "tests"],
    ]
    return [_run_command(root, command) for command in commands]


def _run_command(root: Path, command: list[str]) -> dict[str, Any]:
    command_name = " ".join(_display_command(command))
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=settings.max_tool_timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return _check(
            "sandbox_command",
            False,
            {
                "command": command_name,
                "timeout_seconds": settings.max_tool_timeout_seconds,
                "stdout": _truncate(exc.stdout or ""),
                "stderr": _truncate(exc.stderr or ""),
            },
        )
    return _check(
        "sandbox_command",
        completed.returncode == 0,
        {
            "command": command_name,
            "returncode": completed.returncode,
            "stdout": _truncate(completed.stdout),
            "stderr": _truncate(completed.stderr),
        },
    )


def _display_command(command: list[str]) -> list[str]:
    if command and command[0] == sys.executable:
        return ["python", *command[1:]]
    return command


def _truncate(value: str, limit: int = 1200) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + "\n...[truncated]"


def _check(name: str, ok: bool, detail: Any) -> dict[str, Any]:
    return {"name": name, "ok": ok, "detail": detail}


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False
