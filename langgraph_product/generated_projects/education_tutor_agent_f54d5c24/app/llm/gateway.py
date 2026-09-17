"""LLM provider boundary for the generated agent.

生产环境把所有模型调用集中到这里，避免业务节点直接依赖供应商 SDK。
本地默认使用 stub；配置 API_KEY 后可切换到 OpenAI-compatible provider。
"""

from __future__ import annotations

from app import settings


def complete(prompt: str, max_tokens: int = 1024) -> dict:
    if settings.MODEL_PROVIDER == "stub":
        return {
            "text": f"stub answer: {prompt}",
            "provider": settings.MODEL_PROVIDER,
            "model_id": settings.MODEL_ID,
            "estimated": True,
        }
    if settings.MODEL_PROVIDER == "openai_compatible":
        if not settings.API_KEY and settings.APP_ENV == "local":
            return {
                "text": f"local stub answer: {prompt}",
                "provider": "local_stub",
                "model_id": settings.MODEL_ID or "stub-chat",
                "estimated": True,
                "fallback_reason": "missing local API_KEY",
            }
        return _complete_openai_compatible(prompt, max_tokens)
    raise ValueError(f"unsupported model provider: {settings.MODEL_PROVIDER}")


def _complete_openai_compatible(prompt: str, max_tokens: int) -> dict:
    if not settings.API_KEY:
        raise ValueError("API_KEY is required for openai_compatible provider")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("openai package is required for openai_compatible provider") from exc

    client = OpenAI(api_key=settings.API_KEY, base_url=settings.BASE_URL or None)
    response = client.chat.completions.create(
        model=settings.MODEL_ID,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0,
    )
    return {
        "text": response.choices[0].message.content or "",
        "provider": settings.MODEL_PROVIDER,
        "model_id": settings.MODEL_ID,
        "estimated": False,
    }
