from prometheus_client import Counter, Histogram

jobs_ingested = Counter("jobflow_jobs_ingested_total", "Jobs accepted by source", ["source", "duplicate"])
matches_computed = Counter("jobflow_matches_computed_total", "Job matches computed")
matching_latency = Histogram("jobflow_matching_duration_seconds", "Match calculation latency")
workflow_executions = Counter(
    "jobflow_workflow_executions_total", "Workflow executions", ["workflow", "status"]
)
notifications_sent = Counter("jobflow_notifications_sent_total", "Notifications sent", ["channel", "status"])
ai_requests = Counter(
    "jobflow_ai_requests_total", "AI provider calls", ["operation", "provider", "model", "status"]
)
ai_tokens = Counter("jobflow_ai_tokens_total", "AI tokens", ["operation", "provider", "model", "direction"])
ai_cost = Counter("jobflow_ai_cost_usd_total", "Estimated AI cost in USD", ["operation", "provider", "model"])
ai_latency = Histogram(
    "jobflow_ai_request_duration_seconds", "AI provider latency", ["operation", "provider", "model"]
)
