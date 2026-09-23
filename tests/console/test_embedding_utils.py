"""Cosine similarity tests."""

from app.defense_assets.embedding import cosine_similarity


def test_cosine_identical_vectors() -> None:
    v = [1.0, 2.0, 3.0]
    assert abs(cosine_similarity(v, v) - 1.0) < 1e-6
