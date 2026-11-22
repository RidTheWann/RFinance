"""Create the initial application settings table."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_initial_settings"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "application_settings",
        sa.Column("key", sa.String(length=128), primary_key=True),
        sa.Column("value_json", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("application_settings")
