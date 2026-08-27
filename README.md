# JobFlow AI

AI-powered job intelligence and application automation platform built with n8n, FastAPI, Next.js, PostgreSQL, vector search, Redis, Qdrant, and local AI support.

Live deployment: <https://jobflow-ai-delta.vercel.app>

JobFlow AI continuously collects permitted public job feeds, normalizes and deduplicates postings, computes explainable matches, identifies skill gaps, prepares honest application materials, and tracks the application lifecycle. n8n orchestrates workflows; business rules remain in FastAPI, and every external application action requires human approval.

## What is implemented

- Next.js 15 + TypeScript dashboard with Jobs, Matches, Applications, Skills, Analytics, Automations, Profile, and Settings routes
- FastAPI REST API for registration, JWT login, profiles, validated PDF resumes, jobs, matching, applications, AI assistance, analytics, and signed n8n webhooks
- Multi-source discovery from Arbeitnow, Remotive, and Remote OK, plus Greenhouse, Lever, Ashby, and SmartRecruiters imports and reviewed portal autofill
- Deterministic 100-point match model combined with semantic similarity at a documented 65/35 weighting, configurable real embeddings, and Qdrant search
- Provider-neutral Ollama/OpenAI-compatible structured generation with offline fallbacks and per-user token/cost accounting
- Skill-gap and market-demand analytics
- Ten separate importable n8n workflows, including retry/error handling
- PostgreSQL/pgvector, Qdrant, Redis, Ollama, n8n queue worker, Prometheus, and Grafana in Docker Compose
- Persisted notification preferences, workflow/dead-letter history, document versions, and live dashboard analytics rather than sample counters
- Input validation, enforced admin RBAC, CORS, webhook authentication, rate limiting, parameterized SQL/ORM access, security headers, and safe file validation
- Backend tests, frontend lint/build gates, workflow JSON validation, and GitHub Actions CI

## Architecture

```text
Next.js UI ──REST/JWT──> FastAPI ──> PostgreSQL/pgvector
                           │  ├────> Qdrant
                           │  └────> Redis
                           │
n8n main ──Redis queue──> n8n worker ──signed webhooks──> FastAPI
   │                         │
public feeds               email / integrations

Prometheus <── /metrics ── FastAPI ──> Grafana
```

See [architecture](docs/architecture.md), [API reference](docs/api.md), and [workflow runbook](docs/workflows.md).

## Quick start

1. Copy `.env.example` to `.env` and replace every `replace-with-...` value with a unique secret.
2. Start the stack:

   ```bash
   docker compose up --build
   ```

3. Open:

   - Product: <http://localhost:3000>
   - API docs: <http://localhost:8000/docs>
   - n8n: <http://localhost:5678>
   - Grafana: <http://localhost:3001>
   - Prometheus: <http://localhost:9090>

4. Import `workflows/*.json` in n8n, add Postgres/SMTP/API bearer credentials in the encrypted n8n credential store, then activate workflows after testing them with pinned sample data. A repeatable importer is available:

   ```bash
   docker compose --profile setup run --rm n8n-import
   ```

   After testing, set `N8N_AUTO_ACTIVATE=true` and rerun the importer.

For local Ollama, start the optional profile:

```bash
docker compose --profile local-ai up --build
```

Then pull the configured models and set `AI_PROVIDER=ollama`:

```bash
docker compose exec ollama ollama pull llama3.2:3b
docker compose exec ollama ollama pull nomic-embed-text
```

No API keys are stored in source, workflow JSON, or frontend code.

## How to use JobFlow AI

Start at <http://localhost:3000/auth/sign-up> and create an account. The browser keeps your login for the current tab. Then use the product pages in this order:

| Page | What to do there |
|---|---|
| `/auth/sign-up` | Create an account with your name, email, and a password of at least 10 characters. |
| `/auth/sign-in` | Sign in to an existing account. Sign in again if a page says authentication is required. |
| `/profile` | Edit your name, headline, target roles, locations, salary, and remote preference. Click **Save profile**. Uploading a text-based PDF stores the original file, extracts skills, scans Arbeitnow, Remotive, and Remote OK, imports relevant jobs, and calculates matches. The stored PDF can be downloaded from the same card. |
| `/jobs` | Browse/filter imported opportunities, scan multiple public feeds, or paste a public Greenhouse, Lever, Ashby, or SmartRecruiters posting URL to fetch the employer's current description. **Prepare application** opens a detailed form for contact information, work authorization, availability, salary, links, experience, motivation, and review consent before generating a draft. |
| `/jobs/{id}` | Review one job, its source link, match score, skills, and gaps. **Prepare interview questions** searches the public Stack Exchange API and shows accepted Stack Overflow answers with citations. |
| `/matches` | View ranked match results produced by the matching workflow/API. |
| `/applications` | Review generated drafts, approve a READY application, and mark it APPLIED after you submit it externally. JobFlow never sends an application without you. |
| `/skills` | Review live skill demand and gaps calculated from your current matches. |
| `/analytics` | Review measured conversion rates, weekly discovery, and recorded AI token/cost usage. |
| `/automations` | See persisted execution state for all ten workflows and run public discovery. Manage/import workflows in n8n itself. |
| `/settings` | Save notification destinations and per-account automation preferences. |

### Local HTTP services

| Address | Purpose and usage |
|---|---|
| <http://localhost:3000> | The JobFlow product UI. This is the page most users should use. |
| <http://localhost:8000/health> | A simple API availability check. It should return `{"status":"ok",...}`. |
| <http://localhost:8000/docs> | Interactive Swagger API documentation. Authorize with a bearer token before trying protected endpoints. |
| <http://localhost:5678> | n8n workflow editor. Complete its owner setup, import `workflows/*.json`, configure credentials, test, and activate workflows. |
| <http://localhost:6333/dashboard> | Qdrant vector database administration and collection inspection. It is infrastructure, not a JobFlow user page. |
| <http://localhost:9090> | Prometheus metrics/query UI. Use it to inspect scraped service metrics and targets. |
| <http://localhost:3001> | Grafana dashboards. Sign in with the credentials from `.env` and inspect the provisioned Prometheus data source. |

PostgreSQL on port `5432` and Redis on `6379` use database protocols, so opening them in a browser will not show a web page. Ollama on `11434` is an optional HTTP API enabled by the `local-ai` Compose profile; it also has no product dashboard.

Internet discovery uses documented or public job APIs rather than arbitrary website scraping. Availability and coverage therefore depend on Arbeitnow, Remotive, Remote OK, the supported applicant-tracking APIs, their rate limits, and the skills extracted from the PDF. JobFlow stores the original posting URL and links every sourced interview answer back to Stack Overflow. Always verify community answers against current official documentation.

### Job portal companion

The unpacked extension in `companion/` supports public Greenhouse, Lever, Ashby, and SmartRecruiters application pages. Install it from `chrome://extensions` or `edge://extensions` using **Developer mode → Load unpacked**; after pulling an update, click **Reload** and confirm version **1.2.1**. After generating and reviewing an application, select **Fill on job portal**. A JobFlow bridge preserves the short-lived 20-minute token across employer redirects and displays installation help if the extension is not detected. The companion fills known fields, attaches an ATS-readable tailored PDF made only from verified resume text, and asks for every visible unanswered portal field using the employer's real options. It highlights missing required answers and waits for an explicit confirmation before clicking submit. It never bypasses CAPTCHA/MFA, invents qualifications, or stores employer credentials.

If a page shows `ERR_CONNECTION_REFUSED`, run `docker compose ps`. Then start or rebuild missing services with `docker compose up --build -d`. A first Docker image download can be retried after a TLS timeout with `docker compose pull` followed by the start command.

## Local development

Backend:

```bash
cd backend
uv sync --dev
uv run uvicorn app.main:app --reload
uv run pytest
```

Frontend:

```bash
cd frontend
npm install
npm run dev
npm run lint
npm run build
```

The API defaults to SQLite outside Docker so tests and local development do not require infrastructure. Docker configures PostgreSQL automatically.

## Vercel deployment

The repository includes a Vercel Services configuration that publishes the Next.js app at `/` and FastAPI at `/backend`. The current public deployment is <https://jobflow-ai-delta.vercel.app>.

For persistent production data, open the `jobflow-ai` project in Vercel, install **Neon Postgres** from **Storage / Marketplace**, and connect it to all environments. Confirm that Vercel creates `DATABASE_URL`, then redeploy the latest production deployment. Also add unique, randomly generated `JWT_SECRET` (at least 32 characters) and `WEBHOOK_SECRET` (at least 32 characters). These values must never be committed.

Without `DATABASE_URL`, the Vercel deployment uses SQLite in `/tmp` so the demonstration API can start, but data can reset whenever a serverless instance is recycled. Local Docker continues to use PostgreSQL from `.env`.

Production pages:

| URL | Use |
|---|---|
| <https://jobflow-ai-delta.vercel.app/> | Entry point. New visitors go to sign-up; an existing browser session goes to the dashboard. |
| <https://jobflow-ai-delta.vercel.app/auth/sign-up> | Create a JobFlow account. Successful registration opens the dashboard. |
| <https://jobflow-ai-delta.vercel.app/auth/sign-in> | Sign in, then open the dashboard. |
| <https://jobflow-ai-delta.vercel.app/dashboard> | Authenticated main page. Unauthenticated visitors are returned to sign-in. |
| <https://jobflow-ai-delta.vercel.app/backend/health> | API availability check. A healthy deployment returns HTTP 200 and `{"status":"ok","service":"jobflow-api"}`. |
| <https://jobflow-ai-delta.vercel.app/backend/docs> | Interactive Swagger documentation for exploring API routes. Protected routes require a bearer token. |

`/backend/healthAPI` is not a valid route; `/backend/health` and `/backend/docs` are two separate URLs.

## Responsible automation

- Sources must be public APIs, permitted feeds, supported ATS endpoints, RSS, or career pages whose terms allow automated access.
- LinkedIn scraping is intentionally not part of the system.
- Generated resume suggestions may reorder or emphasize verified experience, but never fabricate it.
- Application drafts always return `requires_human_approval: true`; transition to `APPLIED` is rejected until approval is recorded.

## Repository map

```text
frontend/       Next.js product UI
backend/        FastAPI API, models, services, tests
workflows/      WF-01 through WF-10 n8n exports
infrastructure/ Prometheus, Grafana, database bootstrap
docs/           Architecture, API, workflows, security/deployment notes
.github/        CI pipeline
```
