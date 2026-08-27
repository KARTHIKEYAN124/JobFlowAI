# Terraform deployment boundary

The application is provider-neutral, but infrastructure state cannot be honestly created without choosing a cloud account, region, DNS zone, budgets, and managed-service credentials. The checked-in deployment contracts are:

- `vercel.json` for the public Next.js/FastAPI services and Neon Postgres.
- `docker-compose.yml` for the complete n8n main/worker, Redis queue, pgvector, Qdrant, Ollama, Prometheus, and Grafana stack.
- Environment-only secrets, n8n encrypted credentials, health checks, persistent volumes, and the repeatable workflow importer.

Before adding Terraform, select AWS, Railway, Render, or another target and create provider-specific modules for networking, managed Postgres/Redis, container services, object storage/backups, secret storage, TLS/DNS, monitoring, and budgets. Do not commit generated state or credentials. A fake provider-neutral Terraform file would not be deployable and is intentionally not presented as completed infrastructure.
