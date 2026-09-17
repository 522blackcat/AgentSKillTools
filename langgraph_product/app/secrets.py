"""Tenant-scoped secret storage.

The local implementation uses an HMAC-derived XOR stream so secrets are not
stored as plaintext in the development database. Production deployments should
replace this adapter with KMS or Vault while keeping the same service boundary.
"""

from __future__ import annotations

import base64
import hashlib
import hmac

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database.models import SecretRecord
from app.schemas import SecretCreate


def create_secret(db: Session, data: SecretCreate) -> SecretRecord:
    version = int(
        db.scalar(
            select(func.coalesce(func.max(SecretRecord.version), 0)).where(
                SecretRecord.tenant_id == data.tenant_id,
                SecretRecord.name == data.name,
            )
        )
        or 0
    ) + 1
    for existing in db.scalars(
        select(SecretRecord).where(
            SecretRecord.tenant_id == data.tenant_id,
            SecretRecord.name == data.name,
            SecretRecord.status == "active",
        )
    ).all():
        existing.status = "rotated"
    record = SecretRecord(
        tenant_id=data.tenant_id,
        name=data.name,
        version=version,
        encrypted_value=_encrypt(data.value),
        value_sha256=hashlib.sha256(data.value.encode("utf-8")).hexdigest(),
        status="active",
        created_by_user_id=data.created_by_user_id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def list_secrets(db: Session, tenant_id: str) -> list[SecretRecord]:
    return list(
        db.scalars(
            select(SecretRecord)
            .where(SecretRecord.tenant_id == tenant_id)
            .order_by(SecretRecord.name, SecretRecord.version)
        ).all()
    )


def get_secret_value(db: Session, tenant_id: str, name: str) -> str:
    record = db.scalars(
        select(SecretRecord).where(
            SecretRecord.tenant_id == tenant_id,
            SecretRecord.name == name,
            SecretRecord.status == "active",
        )
    ).first()
    if record is None:
        raise ValueError("secret not found")
    return _decrypt(record.encrypted_value)


def _encrypt(value: str) -> str:
    raw = value.encode("utf-8")
    key_stream = _key_stream(len(raw))
    encrypted = bytes(byte ^ key_stream[index] for index, byte in enumerate(raw))
    return base64.urlsafe_b64encode(encrypted).decode("ascii")


def _decrypt(value: str) -> str:
    encrypted = base64.urlsafe_b64decode(value.encode("ascii"))
    key_stream = _key_stream(len(encrypted))
    raw = bytes(byte ^ key_stream[index] for index, byte in enumerate(encrypted))
    return raw.decode("utf-8")


def _key_stream(length: int) -> bytes:
    chunks: list[bytes] = []
    counter = 0
    while sum(len(chunk) for chunk in chunks) < length:
        counter_bytes = counter.to_bytes(8, "big")
        chunks.append(
            hmac.new(
                settings.app_secret_key.encode("utf-8"),
                counter_bytes,
                hashlib.sha256,
            ).digest()
        )
        counter += 1
    return b"".join(chunks)[:length]
