"""Enable pgvector extension for judgment case embeddings (optional ops step)."""

from __future__ import annotations

from alembic import op

revision = "008_pgvector_extension"
down_revision = "007_defense_asset_seed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Embedding vectors are stored in judgment_cases.embedding (FLOAT[]) by default.
    # Enable pgvector for future HNSW/IVFFlat indexes when ops migrates column type.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS vector")
