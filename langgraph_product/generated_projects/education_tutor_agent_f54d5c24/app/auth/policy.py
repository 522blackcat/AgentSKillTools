"""RBAC policy contract."""

ROLES = ['owner', 'admin', 'reviewer', 'user']


def can_review(role: str) -> bool:
    return role in {"owner", "admin", "reviewer"}


def can_admin(role: str) -> bool:
    return role in {"owner", "admin"}
