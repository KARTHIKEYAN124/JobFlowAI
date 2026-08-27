from typing import Any

import httpx

from app.config import settings


def enabled() -> bool:
    return bool(settings.qdrant_url)


def _headers() -> dict[str, str]:
    return {"api-key": settings.qdrant_api_key} if settings.qdrant_api_key else {}


async def upsert(kind: str, record_id: str, vector: list[float], payload: dict[str, Any]) -> bool:
    if not enabled() or not vector:
        return False
    collection = settings.qdrant_collection
    base = settings.qdrant_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            check = await client.get(f"{base}/collections/{collection}", headers=_headers())
            if check.status_code == 404:
                created = await client.put(
                    f"{base}/collections/{collection}",
                    headers=_headers(),
                    json={"vectors": {"size": len(vector), "distance": "Cosine"}},
                )
                created.raise_for_status()
            elif check.is_error:
                check.raise_for_status()
            response = await client.put(
                f"{base}/collections/{collection}/points?wait=true",
                headers=_headers(),
                json={"points": [{"id": record_id, "vector": vector, "payload": {"kind": kind, **payload}}]},
            )
            response.raise_for_status()
        return True
    except httpx.HTTPError:
        return False


async def search(vector: list[float], kind: str, limit: int = 20) -> list[dict[str, Any]]:
    if not enabled() or not vector:
        return []
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{settings.qdrant_url.rstrip('/')}/collections/{settings.qdrant_collection}/points/search",
                headers=_headers(),
                json={
                    "vector": vector,
                    "limit": limit,
                    "filter": {"must": [{"key": "kind", "match": {"value": kind}}]},
                },
            )
            response.raise_for_status()
            return list(response.json().get("result", []))
    except httpx.HTTPError:
        return []
