# Runbook

## Local Start

```bash
docker compose up -d
uvicorn app.main:app --reload
pytest
```

## Before Production

- Replace local secrets with a real secret manager.
- Configure PostgreSQL + pgvector.
- Configure model provider credentials.
- Ingest real documents into `document_chunks`.
- Verify vector search with `app/rag/repository.py`.
- Review prompt files under `app/prompts`.
- Review domain policy for `education`.
