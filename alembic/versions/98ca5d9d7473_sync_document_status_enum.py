"""Ensure document_status enum contains all required values.

This migration is idempotent: IF NOT EXISTS makes it safe to run on
databases created before the first migration was corrected.

Revision ID: 98ca5d9d7473
Revises: 7306cd212148
"""
from typing import Sequence, Union

from alembic import op

revision: str = '98ca5d9d7473'
down_revision: Union[str, Sequence[str], None] = '7306cd212148'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Postgres does not support removing enum values, so we only add missing ones.
    for value in ('uploaded', 'processing', 'ready', 'failed'):
        op.execute(f"ALTER TYPE document_status ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    # Postgres does not support removing enum values without recreating the type.
    pass
