# Architecture

## Responsibility boundaries

| Layer | Owns | Does not own |
|---|---|---|
| Next.js | Product UI, navigation, filters, review/approval experience | Secrets, scoring rules, provider credentials |
| FastAPI | Authentication, validation, resume parsing, normalization, matching, application state, AI-service contracts, analytics | Schedules and integration choreography |
| n8n | Schedules, feed calls, workflow branching, notifications, reminders, integration retries | Core score calculation or authorization |
| PostgreSQL | Transactional source of truth and pgvector-compatible storage | Ephemeral queues |
| Qdrant | Optional dedicated semantic index | Application state |
| Redis | n8n queue and cache | Durable business records |

This division keeps the portfolio credible as a software-engineering system: n8n orchestrates stable APIs rather than hiding business logic in large Code nodes.

## Data model

The SQLAlchemy schema implements `users`, `profiles`, `resumes`, `resume_files`, `job_sources`, `companies`, `jobs`, `job_matches`, `applications`, `application_documents`, `portal_sessions`, `workflow_runs`, `notifications`, and `skill_statistics`. `resume_files` preserves the exact authenticated PDF separately from extracted metadata. `portal_sessions` stores hashes of short-lived launch tokens rather than browser or employer credentials. Skills are represented as normalized JSON arrays in the MVP; pgvector is enabled for production embeddings, and the Compose stack also includes Qdrant for a dedicated index.

## Matching model

Deterministic points total 100:

| Signal | Points |
|---|---:|
| Technical skills | 40 |
| Role similarity | 20 |
| Experience | 10 |
| Education | 10 |
| Location | 5 |
| Language | 5 |
| Freshness | 5 |
| Employment type | 5 |

The final score is `0.65 × deterministic + 0.35 × semantic`. The local semantic fallback uses normalized token similarity so the project remains runnable without paid credentials. The service boundary permits replacing it with pgvector/Qdrant cosine similarity without moving score logic into n8n.

## Security controls

- Argon2 password hashing and signed, expiring JWTs
- User-scoped queries and role field for RBAC extension
- Signed n8n webhooks using a separate secret
- Tight CORS allowlist and security response headers
- Per-client API, authentication, and webhook rate limits
- Pydantic validation and SQLAlchemy parameterization
- PDF MIME/extension checks, 5 MB limit, parser rejection, authenticated storage, and verified-content-only tailoring
- Whitelisted Greenhouse, Lever, Ashby, and SmartRecruiters public APIs, short-lived portal tokens, and explicit candidate confirmation before submission
- Credentials stored in environment variables or n8n's encrypted credential store
- Human approval invariant before `APPLIED`

For production, enforce TLS and edge WAF/rate limiting in Cloudflare/Traefik, rotate secrets, use managed secret storage, isolate internal services, enable database backups and point-in-time recovery, and replace the single-process limiter with Redis-backed limits.

## Observability

FastAPI exports Prometheus HTTP request count, status, and latency metrics at `/metrics`. Business data records workflow runs, errors, notification delivery, ingestion count, matches, and application state. Grafana is provisioned with Prometheus. Provider adapters should add token and cost counters before enabling a paid LLM.

## Production evolution

Use Cloudflare → reverse proxy → Next.js/FastAPI, managed PostgreSQL and Redis, Qdrant Cloud or pgvector, one n8n main plus horizontally scaled workers, external object storage for resumes, and distinct staging/production credentials. CI builds and tests both application layers before deployment.
