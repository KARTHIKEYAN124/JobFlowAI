import hashlib
import math
import re


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

