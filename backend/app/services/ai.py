import json
from dataclasses import dataclass
from time import monotonic
from typing import Any

import httpx

from app.config import settings
from app.services.metrics import ai_cost, ai_latency, ai_requests, ai_tokens


@dataclass
class AIResult:
    content: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int


def enabled() -> bool:
    return settings.ai_provider.lower() in {"ollama", "openai"}


def _cost(input_tokens: int, output_tokens: int) -> float:
    return round(
        input_tokens * settings.ai_input_cost_per_million / 1_000_000
        + output_tokens * settings.ai_output_cost_per_million / 1_000_000,
        8,
    )


async def generate_text(operation: str, system: str, prompt: str) -> AIResult | None:
    provider = settings.ai_provider.lower()
    model = settings.ai_chat_model
    if not enabled():
        return None
    started = monotonic()
    status = "success"
    try:
        headers = {"Content-Type": "application/json"}
        if settings.ai_api_key:
            headers["Authorization"] = f"Bearer {settings.ai_api_key}"
        async with httpx.AsyncClient(timeout=45) as client:
            if provider == "ollama":
                response = await client.post(
                    f"{settings.ai_base_url.rstrip('/')}/api/chat",
                    headers=headers,
                    json={
                        "model": model,
                        "stream": False,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": prompt},
                        ],
                    },
                )
                response.raise_for_status()
                body = response.json()
                content = body.get("message", {}).get("content", "")
                input_tokens = int(body.get("prompt_eval_count", 0))
                output_tokens = int(body.get("eval_count", 0))
            else:
                response = await client.post(
                    f"{settings.ai_base_url.rstrip('/')}/chat/completions",
                    headers=headers,
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.2,
                    },
                )
                response.raise_for_status()
                body = response.json()
                content = body["choices"][0]["message"]["content"]
                usage = body.get("usage", {})
                input_tokens = int(usage.get("prompt_tokens", 0))
                output_tokens = int(usage.get("completion_tokens", 0))
        latency_ms = round((monotonic() - started) * 1000)
        estimated_cost = _cost(input_tokens, output_tokens)
        ai_requests.labels(operation, provider, model, status).inc()
        ai_tokens.labels(operation, provider, model, "input").inc(input_tokens)
        ai_tokens.labels(operation, provider, model, "output").inc(output_tokens)
        ai_cost.labels(operation, provider, model).inc(estimated_cost)
        ai_latency.labels(operation, provider, model).observe(latency_ms / 1000)
        return AIResult(content, provider, model, input_tokens, output_tokens, estimated_cost, latency_ms)
    except (httpx.HTTPError, KeyError, TypeError, ValueError):
        ai_requests.labels(operation, provider, model, "failure").inc()
        ai_latency.labels(operation, provider, model).observe(monotonic() - started)
        return None


async def generate_json(operation: str, system: str, prompt: str) -> tuple[dict[str, Any], AIResult] | None:
    result = await generate_text(operation, system + " Return only valid JSON.", prompt)
    if not result:
        return None
    raw = result.content.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0]
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return (value, result) if isinstance(value, dict) else None
