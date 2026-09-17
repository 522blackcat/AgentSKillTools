# Architecture

Domain: `education`

## Runtime

- FastAPI API boundary
- LangGraph-style routing contract
- RAG with citations
- PostgreSQL + pgvector retrieval boundary
- Three-layer memory
- Human review for medium/high risk actions

## Data

Expected production storage:

- PostgreSQL
- pgvector
- Redis for queue/cache

## RAG retrieval path

```text
query
  -> app/rag/embedding.py
  -> app/rag/repository.py search_similar_chunks(...)
  -> app/rag/citations.py build_evidence_context(...)
  -> app/rag/service.py answer_with_citations(...)
```

## Safety

Compliance profile:

```text
{'risk_level': 'medium'}
```
