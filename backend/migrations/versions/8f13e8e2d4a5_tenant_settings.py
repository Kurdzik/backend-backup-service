"""add tenant log backup settings and encryption keys

Revision ID: 8f13e8e2d4a5
Revises: 6b4dbafc79c4
Create Date: 2026-05-12 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8f13e8e2d4a5"
down_revision: Union[str, Sequence[str], None] = "6b4dbafc79c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "tenant_log_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("log_retention_period_d", sa.Integer(), nullable=False),
        sa.Column("log_size", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id"),
    )
    op.create_index(
        op.f("ix_tenant_log_settings_tenant_id"),
        "tenant_log_settings",
        ["tenant_id"],
        unique=True,
    )
    op.create_table(
        "tenant_backup_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("compression_enabled", sa.Boolean(), nullable=False),
        sa.Column("encryption_enabled", sa.Boolean(), nullable=False),
        sa.Column("gotify_enabled", sa.Boolean(), nullable=False),
        sa.Column("gotify_url", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("gotify_token", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id"),
    )
    op.create_index(
        op.f("ix_tenant_backup_settings_tenant_id"),
        "tenant_backup_settings",
        ["tenant_id"],
        unique=True,
    )
    op.create_table(
        "tenant_encryption_keys",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("public_key", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("key_fingerprint", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id"),
    )
    op.create_index(
        op.f("ix_tenant_encryption_keys_key_fingerprint"),
        "tenant_encryption_keys",
        ["key_fingerprint"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tenant_encryption_keys_tenant_id"),
        "tenant_encryption_keys",
        ["tenant_id"],
        unique=True,
    )

    op.execute(
        """
        INSERT INTO tenant_log_settings
            (tenant_id, log_retention_period_d, log_size, created_at, updated_at)
        SELECT DISTINCT tenant_id, 30, 1000000, NOW(), NOW()
        FROM users
        ON CONFLICT (tenant_id) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO tenant_backup_settings
            (tenant_id, compression_enabled, encryption_enabled, gotify_enabled, created_at, updated_at)
        SELECT DISTINCT tenant_id, FALSE, FALSE, FALSE, NOW(), NOW()
        FROM users
        ON CONFLICT (tenant_id) DO NOTHING
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_tenant_encryption_keys_tenant_id"), table_name="tenant_encryption_keys")
    op.drop_index(op.f("ix_tenant_encryption_keys_key_fingerprint"), table_name="tenant_encryption_keys")
    op.drop_table("tenant_encryption_keys")
    op.drop_index(op.f("ix_tenant_backup_settings_tenant_id"), table_name="tenant_backup_settings")
    op.drop_table("tenant_backup_settings")
    op.drop_index(op.f("ix_tenant_log_settings_tenant_id"), table_name="tenant_log_settings")
    op.drop_table("tenant_log_settings")
