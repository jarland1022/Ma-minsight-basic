"""Profile applier tests."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.enums import ProfileUpdateStatus
from app.defense_assets.profile.applier import ProfileUpdateApplier
from app.models.defense_assets import ProfileUpdateSuggestion


@pytest.mark.asyncio
async def test_apply_creates_memory_not_whitelist() -> None:
    session = AsyncMock()
    suggestion = ProfileUpdateSuggestion(
        id=uuid.uuid4(),
        investigation_id=uuid.uuid4(),
        entity_profile_id=uuid.uuid4(),
        suggested_changes={
            "memory_type": "past_verdict",
            "content": "该 IP 为漏扫器",
        },
        status=ProfileUpdateStatus.PENDING,
    )
    session.get = AsyncMock(return_value=suggestion)
    session.add = MagicMock()
    applier = ProfileUpdateApplier(session)
    memory = await applier.apply(suggestion.id)
    assert memory is not None
    assert suggestion.status == ProfileUpdateStatus.APPLIED
    added = session.add.call_args[0][0]
    assert added.__class__.__name__ == "EntityProfileMemory"
