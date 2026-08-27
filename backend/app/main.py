from collections import defaultdict, deque
from contextlib import asynccontextmanager
from time import monotonic

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from app.config import settings
from app.database import create_schema, seed_demo_jobs
from app.routes import router


@asynccontextmanager
async def lifespan(_: FastAPI):
    await create_schema()
    await seed_demo_jobs()
    yield


app = FastAPI(title="JobFlow AI API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
windows = defaultdict(deque)
http_requests = Counter("jobflow_http_requests_total", "HTTP requests", ["method", "path", "status"])
http_latency = Histogram("jobflow_http_request_duration_seconds", "HTTP latency", ["method", "path"])


@app.middleware("http")
async def limits(request: Request, call_next):
    path = request.scope.get("path", "")
    if path == "/backend" or path.startswith("/backend/"):
        request.scope["root_path"] = "/backend"
        request.scope["path"] = path.removeprefix("/backend") or "/"
    if request.url.path.startswith("/api/"):
        key = f"{request.client.host if request.client else 'unknown'}:{request.url.path.split('/')[3:5]}"
        window = windows[key]
        now = monotonic()
        while window and window[0] < now - 60:
            window.popleft()
        limit = 20 if "/auth/" in request.url.path or "/webhooks/" in request.url.path else 120
        if len(window) >= limit:
            return JSONResponse(
                status_code=429, content={"detail": "Rate limit exceeded"}, headers={"Retry-After": "60"}
            )
        window.append(now)
    started = monotonic()
    response = await call_next(request)
    route = request.scope.get("route")
    route_path = getattr(route, "path", request.url.path)
    http_requests.labels(request.method, route_path, response.status_code).inc()
    http_latency.labels(request.method, route_path).observe(monotonic() - started)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.get("/health")
async def health():
    return {"status": "ok", "service": "jobflow-api"}


@app.get("/metrics", include_in_schema=False)
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
