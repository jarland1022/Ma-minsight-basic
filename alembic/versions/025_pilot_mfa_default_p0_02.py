"""P0-02 / D-MFA-02: existing Pilot Viewer accounts require MFA.

Does not wipe mfa_secret or passwords. Pilots without a secret get setup
challenge on next login (same as admin MFA upgrade path).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "025_pilot_mfa_default_p0_02"
down_revision = "024_scoped_api_keys_p0_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE users
            SET mfa_required = true
            WHERE role = 'pilot_readonly'
              AND mfa_required = false
            """
        )
    )


def downgrade() -> None:
    # Non-destructive: do not force mfa_required back to false (would weaken security).
    # Operators who need the old default must update rows manually.
    pass
