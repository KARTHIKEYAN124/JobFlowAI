import hashlib
import math
import re

import httpx

from app.config import settings


def embed(text: str, dimensions: int = 64) -> list[float]:
    """Deterministic local embedding fallback; replaceable by Ollama/OpenAI/Qdrant adapters."""
    vector = [0.0] * dimensions
    for token in re.findall(r"[a-z0-9+#.]+", text.lower()):
        digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        vector[index] += 1 if digest[4] % 2 else -1
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [round(value / norm, 6) for value in vector]


def cosine(left: list[float], right: list[float]) -> float:
    if not left or len(left) != len(right):
        return 0.0
    return max(0.0, min(1.0, sum(a * b for a, b in zip(left, right, strict=True))))


async def embed_text(text: str) -> tuple[list[float], str]:
    """Use a configured real embedding provider, with an offline deterministic fallback."""
    provider = settings.ai_provider.lower()
    if provider not in {"ollama", "openai"}:
        return embed(text), "local-hash"
    headers = {"Content-Type": "application/json"}
    if settings.ai_api_key:
        headers["Authorization"] = f"Bearer {settings.ai_api_key}"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            if provider == "ollama":
                response = await client.post(
                    f"{settings.ai_base_url.rstrip('/')}/api/embed",
                    headers=headers,
                    json={"model": settings.ai_embedding_model, "input": text},
                )
                response.raise_for_status()
                vector = response.json()["embeddings"][0]
            else:
                response = await client.post(
                    f"{settings.ai_base_url.rstrip('/')}/embeddings",
                    headers=headers,
                    json={"model": settings.ai_embedding_model, "input": text},
                )
                response.raise_for_status()
                vector = response.json()["data"][0]["embedding"]
        return [float(value) for value in vector], f"{provider}:{settings.ai_embedding_model}"
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
        return embed(text), "local-hash-fallback"
