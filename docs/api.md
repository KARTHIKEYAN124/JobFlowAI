# API reference

All routes are under `/api/v1`. Interactive OpenAPI documentation is available at `/docs`.

## Authentication

| Method | Path | Purpose |
|---|---|---|
| POST | `/auth/register` | Create user and empty profile |
| POST | `/auth/login` | Return bearer JWT |

Authenticated endpoints require `Authorization: Bearer <token>`.

## Candidate

| Method | Path | Purpose |
|---|---|---|
| GET/PUT | `/profile` | Read/update structured profile and searchable text |
| POST/GET | `/resume` | Validate, parse, store/read latest PDF extraction |

## Jobs and matching

| Method | Path | Purpose |
|---|---|---|
| GET | `/jobs` | Filter by search, location, category, remote type, or minimum match |
| POST | `/jobs/scan` | Import and match Arbeitnow public-feed jobs using resume skills |
| GET | `/jobs/{id}` | Job details |
| POST | `/jobs/{id}/save` | Save to tracker |
| POST | `/jobs/{id}/match` | Compute and persist explainable score |
| GET | `/matches` | Ranked user matches |

## Applications and AI assistance

| Method | Path | Purpose |
|---|---|---|
| POST/GET | `/applications` | Create/list tracked applications |
| PATCH | `/applications/{id}` | Approve, update notes, or transition status |
| POST | `/ai/application` | Resume suggestions, cover letter, answer, recruiter draft |
| POST | `/ai/interview` | Job-specific preparation plus sourced accepted Stack Overflow answers |
| POST | `/ai/skills` | User-specific top gaps |

The `APPLIED` transition returns HTTP 409 until `approved=true` has been recorded.

## Analytics and orchestration

| Method | Path | Purpose |
|---|---|---|
| GET | `/analytics/dashboard` | New jobs, high matches, applications, interviews, offers |
| GET | `/analytics/skills` | Demand and gap frequency |
| POST | `/webhooks/n8n/job` | Normalize/classify/deduplicate/insert posting |
| POST | `/webhooks/n8n/application` | Record application workflow event |
| POST | `/webhooks/n8n/status` | Record workflow status/error |

Webhook routes require `X-Webhook-Secret` and have stricter rate limits.
