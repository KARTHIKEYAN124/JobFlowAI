# n8n workflow runbook

The JSON files are versioned, separate, and intentionally inactive on import. Configure credentials and test before activation.

| ID | Workflow | Trigger | Responsibility |
|---|---|---|---|
| WF-01 | Candidate Profile Processor | Webhook | Validate profile, build search text, update candidate |
| WF-02 | Job Ingestion | Hourly | Get enabled sources, fetch, normalize, Germany/role/freshness filters, deduplicate |
| WF-03 | Requirement Extractor | Sub-workflow | Structured requirements and language extraction |
| WF-04 | Job Matcher | Sub-workflow | Call FastAPI score service and route high/medium/low matches |
| WF-05 | High-match Notification | Sub-workflow | Generate safe summary, notify, record delivery |
| WF-06 | Application Generator | Webhook | Generate verified documents, enforce review, and prepare a short-lived browser-companion handoff |
| WF-07 | Follow-up | Daily | Find applications older than seven days and notify user |
| WF-08 | Interview Prep | Webhook | Generate interview pack after `INTERVIEW` transition |
| WF-09 | Skill Analytics | Nightly | Aggregate demand and gap statistics |
| WF-10 | Global Error Handler | Error trigger | Log failure, classify, retry at 30s/2m, dead-letter/admin alert |

## Initial setup

1. Import all ten files.
2. Set WF-10 as the error workflow by ID for WF-01 through WF-09 (n8n replaces export-time names with instance IDs).
3. Create Postgres, API bearer/header, and SMTP credentials in the encrypted credential store.
4. Configure approved `job_sources`; do not add sources whose terms prohibit automation.
5. Test each workflow manually with pinned non-sensitive data.
6. Activate from downstream to upstream: WF-10, WF-05–09, WF-03–04, WF-01–02.

## Retry and dead-letter policy

External requests use three total attempts: immediate, after 30 seconds, and after two minutes. WF-10 records the workflow, execution ID, message, timestamp, and safe input snapshot. Exhausted critical failures create an admin alert. Do not log resumes, access tokens, or provider secrets in input snapshots.

## Operations

Monitor executions/failures, ingested jobs, notification outcomes, API/match latency, and—when a paid provider is enabled—token usage and estimated cost. Scale `n8n-worker` horizontally while keeping a single main instance; Redis coordinates the queue and PostgreSQL stores execution state.
