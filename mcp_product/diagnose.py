"""Diagnose the local MCP learning project environment.

Run with the same Python interpreter that you use to start the MCP client:
    python -m mcp_product.diagnose
"""

from __future__ import annotations

import importlib
import os
import sys

from dotenv import load_dotenv


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(ROOT_DIR, ".env")


def check_env() -> None:
    loaded = load_dotenv(ENV_PATH)
    print(f"[env] path={ENV_PATH}")
    print(f"[env] loaded={loaded}")
    for key in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL_ID", "SERPER_API_KEY"):
        value = os.getenv(key)
        if not value:
            display = "<missing>"
        elif "KEY" in key:
            display = "<set>"
        else:
            display = value
        print(f"[env] {key}={display}")


def check_import(module_name: str) -> None:
    try:
        module = importlib.import_module(module_name)
        location = getattr(module, "__file__", "<built-in>")
        print(f"[import] {module_name}=ok ({location})")
    except Exception as exc:
        print(f"[import] {module_name}=failed ({type(exc).__name__}: {exc})")


def main() -> None:
    print(f"[python] executable={sys.executable}")
    print(f"[python] version={sys.version}")
    check_env()
    for module_name in (
        "mcp",
        "mcp.server.mcpserver",
        "mcp.client.stdio",
        "openai",
        "dotenv",
        "pywintypes",
    ):
        check_import(module_name)


if __name__ == "__main__":
    main()
