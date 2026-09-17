"""模型网关。

业务代码不直接绑定某个供应商 SDK，而是通过这里统一处理 provider、fallback、
token usage 和 cost 估算。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class ModelGatewayError(RuntimeError):
    """Raised when every configured model candidate fails."""


@dataclass(frozen=True)
class ModelRequest:
    role: str
    prompt: str
    max_tokens: int = 1024
    node_name: str = ""
    run_id: str | None = None
    model_provider: str = "local_stub"
    provider_type: str = "stub"
    model_id: str = "stub-chat"
    base_url: str = ""
    api_key: str = ""
    timeout_seconds: int = 30
    input_cost_per_1k: float = 0.0
    output_cost_per_1k: float = 0.0
    fallback_models: tuple[dict[str, Any], ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ModelResponse:
    text: str
    model_provider: str
    provider_type: str
    model_id: str
    prompt_tokens: int
    completion_tokens: int
    estimated_cost: float = 0.0
    estimated: bool = True
    failed_over: bool = False
    attempts: tuple[dict[str, Any], ...] = field(default_factory=tuple)


class ModelGateway:
    """Small gateway stub.

    Phase 7 adds DB-backed model selection. The local stub remains the default
    provider so tests and local development do not need network credentials.
    The stub keeps graph code provider-neutral from day one.
    """

    def complete(self, request: ModelRequest) -> ModelResponse:
        attempts: list[dict[str, Any]] = []
        candidates = (
            {
                "model_provider": request.model_provider,
                "provider_type": request.provider_type,
                "model_id": request.model_id,
                "base_url": request.base_url,
                "api_key": request.api_key,
                "input_cost_per_1k": request.input_cost_per_1k,
                "output_cost_per_1k": request.output_cost_per_1k,
            },
            *request.fallback_models,
        )
        for index, candidate in enumerate(candidates):
            try:
                response = self._complete_one(request, candidate)
                cost = _estimate_cost(
                    response.prompt_tokens,
                    response.completion_tokens,
                    float(candidate.get("input_cost_per_1k", 0.0) or 0.0),
                    float(candidate.get("output_cost_per_1k", 0.0) or 0.0),
                )
                attempts.append(
                    {
                        "model_provider": response.model_provider,
                        "provider_type": response.provider_type,
                        "model_id": response.model_id,
                        "ok": True,
                    }
                )
                return ModelResponse(
                    text=response.text,
                    model_provider=response.model_provider,
                    provider_type=response.provider_type,
                    model_id=response.model_id,
                    prompt_tokens=response.prompt_tokens,
                    completion_tokens=response.completion_tokens,
                    estimated_cost=cost,
                    estimated=response.estimated,
                    failed_over=index > 0,
                    attempts=tuple(attempts),
                )
            except Exception as exc:  # noqa: BLE001 - gateway records and tries configured fallback.
                attempts.append(
                    {
                        "model_provider": candidate.get("model_provider", ""),
                        "provider_type": candidate.get("provider_type", ""),
                        "model_id": candidate.get("model_id", ""),
                        "ok": False,
                        "error": str(exc),
                    }
                )
        raise ModelGatewayError("all model candidates failed")

    def _complete_one(self, request: ModelRequest, candidate: dict[str, Any]) -> ModelResponse:
        provider_type = str(candidate.get("provider_type") or "stub")
        if provider_type == "stub":
            return self._complete_stub(request, candidate)
        if provider_type == "openai_compatible":
            return self._complete_openai_compatible(request, candidate)
        raise ModelGatewayError(f"unsupported provider type: {provider_type}")

    def _complete_stub(self, request: ModelRequest, candidate: dict[str, Any]) -> ModelResponse:
        prompt_tokens = _estimate_tokens(request.prompt)
        return ModelResponse(
            text="",
            model_provider=str(candidate.get("model_provider") or request.model_provider),
            provider_type="stub",
            model_id=str(candidate.get("model_id") or request.model_id or f"stub:{request.role}"),
            prompt_tokens=prompt_tokens,
            completion_tokens=0,
            estimated=True,
        )

    def _complete_openai_compatible(
        self,
        request: ModelRequest,
        candidate: dict[str, Any],
    ) -> ModelResponse:
        api_key = str(candidate.get("api_key") or request.api_key)
        if not api_key:
            raise ModelGatewayError("missing API key")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ModelGatewayError("openai package is not installed") from exc

        client = OpenAI(
            api_key=api_key,
            base_url=str(candidate.get("base_url") or request.base_url) or None,
            timeout=request.timeout_seconds,
        )
        completion = client.chat.completions.create(
            model=str(candidate.get("model_id") or request.model_id),
            messages=[{"role": "user", "content": request.prompt}],
            max_tokens=request.max_tokens,
            temperature=0,
        )
        text = completion.choices[0].message.content or ""
        usage = completion.usage
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or _estimate_tokens(request.prompt))
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or _estimate_tokens(text))
        return ModelResponse(
            text=text,
            model_provider=str(candidate.get("model_provider") or request.model_provider),
            provider_type="openai_compatible",
            model_id=str(candidate.get("model_id") or request.model_id),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            estimated=False,
        )


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _estimate_cost(
    prompt_tokens: int,
    completion_tokens: int,
    input_cost_per_1k: float,
    output_cost_per_1k: float,
) -> float:
    return (prompt_tokens / 1000 * input_cost_per_1k) + (
        completion_tokens / 1000 * output_cost_per_1k
    )
