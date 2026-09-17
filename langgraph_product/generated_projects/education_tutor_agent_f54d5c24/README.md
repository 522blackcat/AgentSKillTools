# education_tutor_agent

Domain: `education`

This project was generated from a production agent blueprint.

## Capabilities

- LangGraph runtime
- PostgreSQL + pgvector design
- RAG with citations
- Short-term, summary, and long-term memory
- Human review gates
- Token usage tracking
- Audit events
- Versioned prompts
- Domain safety policy
- Eval cases

## Specialist Agents

- Requirements Agent
- Architecture Agent
- Data Architect Agent
- RAG Engineer Agent
- Memory Engineer Agent
- Tooling Agent
- Human Review Agent
- Security Agent
- Test Engineer Agent
- Code Generator Agent

## Run Locally

```bash
docker compose up -d
uvicorn app.main:app --reload
pytest
```

## Important Files

- `app/main.py`: API entrypoint.
- `app/graph.py`: routing contract.
- `app/llm/gateway.py`: model provider boundary.
- `app/rag/service.py`: RAG orchestration.
- `app/rag/repository.py`: PostgreSQL + pgvector retrieval.
- `app/rag/citations.py`: citation building and validation.
- `app/memory/service.py`: three-layer memory contract.
- `app/human_review/service.py`: review gate contract.
- `app/prompts/`: prompt assets.
- `app/evals/cases.py`: generated eval cases from the domain template.
- `docs/ARCHITECTURE.md`: architecture notes.
- `docs/RUNBOOK.md`: local operation checklist.
