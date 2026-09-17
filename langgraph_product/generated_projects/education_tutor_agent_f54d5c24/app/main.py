"""FastAPI entrypoint for education_tutor_agent."""

from typing import Any
from contextlib import asynccontextmanager

from fastapi import Body, Depends, FastAPI, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app.domain.routes import router as domain_router
from app.knowledge.service import create_knowledge_base, ingest_document, search_knowledge_base
from app.memory.service import load_memory_context, save_turn
from app.graph import invoke_graph
from app.schemas import AgentInvokeRequest, DocumentIngest, KnowledgeBaseCreate, KnowledgeSearchRequest


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="education_tutor_agent", lifespan=lifespan)
app.include_router(domain_router)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/knowledge-bases")
def post_knowledge_base(data: KnowledgeBaseCreate, db: Session = Depends(get_db)) -> dict[str, Any]:
    kb = create_knowledge_base(db, data)
    return {"id": kb.id, "tenant_id": kb.tenant_id, "name": kb.name, "domain": kb.domain}


@app.post("/v1/knowledge-bases/{knowledge_base_id}/documents")
def post_document(
    knowledge_base_id: str,
    data: DocumentIngest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        return ingest_document(db, knowledge_base_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/v1/knowledge-bases/{knowledge_base_id}/search")
def post_knowledge_search(
    knowledge_base_id: str,
    data: KnowledgeSearchRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return search_knowledge_base(db, knowledge_base_id, data)


@app.post("/v1/knowledge-bases/{knowledge_base_id}/documents/upload")
def upload_document(
    knowledge_base_id: str,
    tenant_id: str = Query(...),
    title: str = Query(...),
    filename: str = Query(...),
    source_uri: str = Query(default=""),
    db: Session = Depends(get_db),
    payload: bytes = Body(..., media_type="application/octet-stream"),
) -> dict[str, Any]:
    try:
        return ingest_document(
            db,
            knowledge_base_id,
            DocumentIngest(
                tenant_id=tenant_id,
                title=title,
                content_bytes=payload,
                filename=filename,
                source_uri=source_uri or filename,
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/v1/agent/invoke")
def post_agent_invoke(data: AgentInvokeRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    memory_context = load_memory_context(
        db=db,
        tenant_id=data.tenant_id,
        user_id=data.user_id,
        session_id=data.session_id,
        query=data.message,
    )
    chunks = None
    if data.knowledge_base_id:
        search = search_knowledge_base(
            db,
            data.knowledge_base_id,
            KnowledgeSearchRequest(
                tenant_id=data.tenant_id,
                query=data.message,
                top_k=data.top_k,
            ),
        )
        chunks = [
            {
                "chunk_id": item["chunk_id"],
                "document_id": item["document_id"],
                "content": item["text"],
                "source_title": item["metadata"].get("title", ""),
                "source_uri": item["metadata"].get("source_uri", ""),
                "section_title": item["section_title"],
                "page_number": item["metadata"].get("page_number"),
            }
            for item in search["results"]
        ]
    result = invoke_graph(
        user_input=data.message,
        tenant_id=data.tenant_id,
        knowledge_base_id=data.knowledge_base_id or "",
        chunks=chunks,
        risk_level=data.risk_level,
        memory_context=memory_context,
    )
    save_turn(
        db=db,
        tenant_id=data.tenant_id,
        user_id=data.user_id,
        session_id=memory_context.get("session_id") or data.session_id,
        user_input=data.message,
        assistant_output=result.get("answer", ""),
    )
    return {
        "tenant_id": data.tenant_id,
        "knowledge_base_id": data.knowledge_base_id,
        "route": result.get("route"),
        "answer": result.get("answer", ""),
        "citations": result.get("citations", []),
        "review_required": result.get("review_required", False),
        "audit_nodes": result.get("audit_nodes", []),
        "memory": result.get("memory_context", {}),
    }
