from __future__ import annotations

from app.database.session import SessionLocal, init_db
from app.schemas import ChatRunCreate, TenantCreate, TokenUsageCreate, UserCreate
from app.services import create_chat_run, create_tenant, create_user, read_quota, record_token_usage


def main() -> None:
    init_db()
    with SessionLocal() as db:
        tenant = create_tenant(db, TenantCreate(name="Service Smoke"))
        user = create_user(
            db,
            UserCreate(
                tenant_id=tenant.id,
                email="service-smoke@example.com",
                username="service-smoke",
            ),
        )
        run = create_chat_run(
            db,
            ChatRunCreate(
                tenant_id=tenant.id,
                user_id=user.id,
                message="hello",
            ),
        )
        usage = record_token_usage(
            db,
            TokenUsageCreate(
                tenant_id=tenant.id,
                user_id=user.id,
                run_id=run.id,
                call_type="chat_completion",
                prompt_tokens=10,
                completion_tokens=5,
            ),
        )
        quota = read_quota(db, tenant.id, user.id)
        assert usage.total_tokens == 15
        assert quota["token_used"] >= 15
    print("phase1 service smoke passed")


if __name__ == "__main__":
    main()
