"""Tool gateway credential registry (references only, not plaintext secrets)."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin


class ToolGatewayCredential(Base, CreatedAtMixin):
    """External integration credential reference — value lives in env/Vault."""

    __tablename__ = "tool_gateway_credentials"
    __table_args__ = (
        UniqueConstraint("adapter_name", "credential_ref", name="uq_tool_gateway_cred"),
        Index("ix_tool_gateway_credentials_adapter", "adapter_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    adapter_name: Mapped[str] = mapped_column(String(64), nullable=False)
    credential_ref: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
