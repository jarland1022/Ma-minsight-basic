"""Judgment case retrieval for Agent context."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.defense_assets.config import DefenseAssetConfig
from app.defense_assets.embedding import EmbeddingService, cosine_similarity
from app.models.defense_assets import JudgmentCase
from app.models.investigation import Event


async def fetch_reference_cases(
    session: AsyncSession,
    *,
    event: Event,
    config: DefenseAssetConfig,
) -> list[dict[str, Any]]:
    if config.embedding_search_enabled and config.embedding_enabled:
        vector_cases = await _fetch_by_embedding(session, event, config)
        if vector_cases:
            return vector_cases

    result = await session.execute(
        select(JudgmentCase)
        .where(
            JudgmentCase.is_active.is_(True),
            JudgmentCase.alert_category == event.primary_category,
        )
        .order_by(JudgmentCase.usage_count.desc())
        .limit(3)
    )
    return [_case_dict(case) for case in result.scalars().all()]


async def _fetch_by_embedding(
    session: AsyncSession,
    event: Event,
    config: DefenseAssetConfig,
) -> list[dict[str, Any]]:
    query_text = " ".join(
        filter(
            None,
            [
                event.primary_category,
                event.title,
                event.aggregate_host_name,
                event.aggregate_user_name,
            ],
        )
    )
    embedder = EmbeddingService(model=config.embedding_model)
    query_vector = await embedder.embed(query_text)
    if query_vector is None:
        return []

    result = await session.execute(
        select(JudgmentCase).where(
            JudgmentCase.is_active.is_(True),
            JudgmentCase.embedding.is_not(None),
        )
    )
    scored: list[tuple[float, JudgmentCase]] = []
    for case in result.scalars().all():
        if case.embedding and len(case.embedding) == len(query_vector):
            scored.append((cosine_similarity(query_vector, case.embedding), case))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [_case_dict(case) for _, case in scored[:3]]


def _case_dict(case: JudgmentCase) -> dict[str, Any]:
    return {
        "feature_summary": case.feature_summary,
        "verdict": case.verdict.value,
        "reasoning_excerpt": case.reasoning[:300],
        "trace_summary": case.investigation_trace[:5] if case.investigation_trace else [],
        "reference_only": True,
    }
