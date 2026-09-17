"""Self-checks for the long-document RAG pipeline."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass

from rag_product.pipeline import RagEngine
from rag_product.vector_store import JsonVectorStore


@dataclass(frozen=True)
class ValidationCase:
    query: str
    expected_section: str


VALIDATION_CASES = [
    ValidationCase(query="如何处理跨章节的证据召回？", expected_section="长文本检索流程"),
    ValidationCase(query="上线以后应该记录哪些 RAG 调用日志？", expected_section="观测与验证"),
    ValidationCase(query="什么时候应该使用章节摘要路由？", expected_section="章节路由策略"),
]


def build_demo_long_text(repeats: int = 140) -> str:
    filler = (
        "这是一段用于模拟长文档背景信息的文字，包含流程说明、业务上下文、实现约束和边界条件。"
        "它故意重复多次，用来验证切分器不会只依赖单个超大 chunk。"
    )
    sections = [
        (
            "# 章节路由策略",
            "章节摘要路由用于先判断问题落在哪些章节，再进入具体段落检索。"
            "当文档超过三万字时，直接把所有叶子 chunk 扔进 top-k 容易被背景噪声冲淡。",
        ),
        (
            "# 长文本检索流程",
            "跨章节证据召回应该先扩大章节候选，再在候选章节内精确召回叶子 chunk。"
            "如果答案需要多个来源，最终上下文必须保留 section、chunk 和 source 引用。",
        ),
        (
            "# 观测与验证",
            "上线以后需要记录 query、命中的 chunk_id、section_title、score、latency_ms 和最终答案。"
            "验证脚本应该覆盖能命中、不能命中、跨章节命中和引用格式。",
        ),
    ]
    blocks = []
    for title, key_text in sections:
        blocks.append(title)
        blocks.append(key_text)
        blocks.extend(filler for _ in range(repeats))
    return "\n\n".join(blocks)


def run_validation() -> dict:
    with tempfile.TemporaryDirectory() as temp_dir:
        document_path = os.path.join(temp_dir, "long_rag_demo.md")
        store_path = os.path.join(temp_dir, "vectors.json")
        with open(document_path, "w", encoding="utf-8") as f:
            f.write(build_demo_long_text())

        engine = RagEngine(vector_store=JsonVectorStore(store_path))
        ingest_result = engine.ingest_file(document_path)
        failures = []
        checks = []

        for case in VALIDATION_CASES:
            context = engine.search(case.query, top_k=4)
            sections = [item.chunk.metadata.get("section_title", "") for item in context.results]
            route_sections = [item.chunk.metadata.get("section_title", "") for item in context.route]
            passed = case.expected_section in sections or case.expected_section in route_sections
            checks.append(
                {
                    "query": case.query,
                    "expected_section": case.expected_section,
                    "route_sections": route_sections,
                    "result_sections": sections,
                    "passed": passed,
                }
            )
            if not passed:
                failures.append(case.query)

        return {
            "passed": not failures,
            "ingest": ingest_result,
            "checks": checks,
            "failure_count": len(failures),
        }
