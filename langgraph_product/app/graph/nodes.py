"""LangGraph nodes."""

from __future__ import annotations

from app.builder.service import BuilderInput, build_agent_blueprint
from app.graph.routing import classify_route
from app.graph.state import AgentState
from app.model_gateway.gateway import ModelGateway, ModelRequest
from app.prompts import render_prompt


gateway = ModelGateway()


def input_guard(state: AgentState) -> dict:
    user_input = state.get("user_input", "")
    normalized = user_input.strip()
    trace = state.get("trace", [])
    trace.append({"node": "input_guard", "ok": bool(normalized)})
    if not normalized:
        return {
            "normalized_input": "",
            "route": "clarify",
            "errors": [{"type": "user_error", "message": "empty input"}],
            "trace": trace,
        }
    return {"normalized_input": normalized, "errors": [], "trace": trace}


def load_memory(state: AgentState) -> dict:
    trace = state.get("trace", [])
    trace.append(
        {
            "node": "load_memory",
            "ok": True,
            "recent_messages": len(state.get("messages", [])),
            "long_term_memories": len(state.get("memory_candidates", [])),
            "has_summary": "【会话摘要】" in state.get("memory_context", ""),
        }
    )
    return {"trace": trace}


def intent_router(state: AgentState) -> dict:
    route, intent, risk = classify_route(state.get("normalized_input", ""))
    trace = state.get("trace", [])
    trace.append({"node": "intent_router", "route": route, "intent": intent, "risk": risk})
    return {"route": route, "intent": intent, "risk_level": risk, "trace": trace}


def direct_answer(state: AgentState) -> dict:
    prompt = render_prompt(
        "answer",
        memory_context=state.get("memory_context", ""),
        rag_context=state.get("rag_context", ""),
        user_input=state.get("normalized_input", ""),
    )
    request = ModelRequest(
        role="cheap_chat",
        prompt=prompt,
        node_name="direct_answer",
        run_id=state.get("run_id"),
        model_provider=state.get("model_provider", "local_stub"),
        provider_type=state.get("model_provider_type", "stub"),
        model_id=state.get("model_id", "stub-chat"),
        base_url=state.get("model_base_url", ""),
        api_key=state.get("model_api_key", ""),
        input_cost_per_1k=float(state.get("model_input_cost_per_1k", 0.0) or 0.0),
        output_cost_per_1k=float(state.get("model_output_cost_per_1k", 0.0) or 0.0),
        fallback_models=tuple(state.get("model_fallbacks", [])),
    )
    response = gateway.complete(request)
    answer = response.text or f"已收到：{state.get('normalized_input', '')}"
    if state.get("memory_candidates"):
        answer += "\n\n已加载相关长期记忆。"
    usage = {
        "prompt_tokens": response.prompt_tokens,
        "completion_tokens": response.completion_tokens,
        "total_tokens": response.prompt_tokens + response.completion_tokens,
        "model_provider": response.model_provider,
        "provider_type": response.provider_type,
        "model_id": response.model_id,
        "estimated_cost": response.estimated_cost,
        "estimated": response.estimated,
        "failed_over": response.failed_over,
        "attempts": list(response.attempts),
    }
    trace = state.get("trace", [])
    trace.append({"node": "direct_answer", "ok": True, "tokens": usage["total_tokens"]})
    return {"final_answer": answer, "token_usage": usage, "trace": trace}


def retrieve_knowledge(state: AgentState) -> dict:
    query = state.get("normalized_input", "")
    trace = state.get("trace", [])
    results = state.get("rag_results", [])
    trace.append(
        {
            "node": "retrieve_knowledge",
            "ok": True,
            "knowledge_base_id": state.get("knowledge_base_id"),
            "result_count": len(results),
        }
    )
    if results:
        return {
            "rag_query": query,
            "rag_results": results,
            "rag_context": state.get("rag_context", ""),
            "trace": trace,
        }
    return {
        "rag_query": query,
        "rag_results": [],
        "rag_context": "",
        "trace": trace,
    }


def answer_with_evidence(state: AgentState) -> dict:
    trace = state.get("trace", [])
    results = state.get("rag_results", [])
    trace.append({"node": "answer_with_evidence", "ok": True, "citations": len(results)})
    if not results:
        return {
            "final_answer": "当前知识库没有检索到可引用证据，因此不能基于知识库回答。",
            "trace": trace,
        }
    citations = []
    for index, result in enumerate(results, start=1):
        citations.append(
            f"[{index}] {result.get('section_title', '')} {result.get('location', '')}"
        )
    answer = (
        "根据知识库检索结果，相关证据如下：\n"
        + "\n".join(citations)
        + "\n\n"
        + "请基于以上引用继续生成正式回答。"
    )
    return {
        "final_answer": answer,
        "trace": trace,
    }


def plan_tools(state: AgentState) -> dict:
    risk = state.get("risk_level", "medium")
    trace = state.get("trace", [])
    trace.append({"node": "plan_tools", "risk": risk})
    return {
        "tool_plan": [],
        "review_required": risk in {"medium", "high"},
        "trace": trace,
    }


def agent_builder_supervisor(state: AgentState) -> dict:
    text = state.get("normalized_input", "")
    requested_domain = state.get("builder_domain", "")
    inferred_domain = "hospital" if "医院" in text else "law_firm" if "律所" in text else "generic"
    domain = requested_domain or inferred_domain
    product_name = state.get("builder_product_name") or f"{domain}_agent"
    blueprint = build_agent_blueprint(
        BuilderInput(
            tenant_id=state.get("tenant_id", ""),
            user_id=state.get("user_id", ""),
            run_id=state.get("run_id", ""),
            product_name=product_name,
            domain=domain,
            requirements=text,
            domain_template=state.get("builder_domain_template"),
        )
    )
    trace = state.get("trace", [])
    trace.append(
        {
            "node": "agent_builder_supervisor",
            "domain": domain,
            "specialist_count": blueprint["validation"]["specialist_count"],
            "blueprint_ok": blueprint["validation"]["ok"],
        }
    )
    return {
        "builder_request": {"input": text, "domain": domain},
        "agent_blueprint": blueprint,
        "review_required": state.get("risk_level") == "high"
        or blueprint["human_review"]["default_required"],
        "final_answer": f"已生成 {domain} Agent blueprint，等待后续代码生成和验证。",
        "trace": trace,
    }


def clarify(state: AgentState) -> dict:
    trace = state.get("trace", [])
    trace.append({"node": "clarify", "ok": True})
    return {"final_answer": "请补充你要构建的 Agent 领域、用户角色和核心任务。", "trace": trace}


def reject(state: AgentState) -> dict:
    trace = state.get("trace", [])
    trace.append({"node": "reject", "ok": True})
    return {"final_answer": "该请求当前不能执行。", "trace": trace}


def persist_run(state: AgentState) -> dict:
    trace = state.get("trace", [])
    trace.append({"node": "persist_run", "ok": True})
    return {"trace": trace}
