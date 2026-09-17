"""Structured training records for generated prompts."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Any

from prompt_product.evaluator import evaluate_prompt


DEFAULT_RECORDS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "prompt_records.jsonl"
)


def infer_variable_name(prompt: str) -> str:
    match = re.search(r"^\s*([A-Z][A-Z0-9_]*_AGENT_PROMPT)\s*=", prompt, flags=re.M)
    return match.group(1) if match else "UNKNOWN_AGENT_PROMPT"


def infer_prompt_body(prompt: str) -> str:
    match = re.search(r"=\s*([\"']{3})(.*)\1", prompt, flags=re.S)
    return match.group(2).strip() if match else prompt.strip()


def infer_keyword(variable_name: str) -> str:
    return variable_name.removesuffix("_AGENT_PROMPT").lower()


def append_prompt_record(
    prompt: str,
    prompt_type: str = "agent",
    source: str = "tool_call",
    file_path: str = DEFAULT_RECORDS_PATH,
) -> dict[str, Any]:
    variable_name = infer_variable_name(prompt)
    body = infer_prompt_body(prompt)
    evaluation = evaluate_prompt(body)
    record = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source": source,
        "prompt_type": prompt_type,
        "keyword": infer_keyword(variable_name),
        "variable_name": variable_name,
        "evaluation": evaluation.to_dict(),
        "prompt": prompt,
    }
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record
