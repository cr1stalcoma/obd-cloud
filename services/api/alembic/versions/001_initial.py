"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-07-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

scanner_state = postgresql.ENUM(
    "offline",
    "waiting",
    "on_car",
    "error",
    name="scannerstate",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    postgresql.ENUM(
        "offline",
        "waiting",
        "on_car",
        "error",
        name="scannerstate",
        create_type=True,
    ).create(bind, checkfirst=True)

    op.create_table(
        "scanners",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("secret_hash", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "scanner_status",
        sa.Column("scanner_id", sa.String(length=32), nullable=False),
        sa.Column("state", scanner_state, nullable=False, server_default="offline"),
        sa.Column("bitrate", sa.String(length=16), nullable=True),
        sa.Column("vin", sa.String(length=32), nullable=True),
        sa.Column("manufacturer", sa.String(length=128), nullable=True),
        sa.Column("rpm", sa.Integer(), nullable=True),
        sa.Column("speed_kmh", sa.Integer(), nullable=True),
        sa.Column("coolant_c", sa.Integer(), nullable=True),
        sa.Column("dtc_stored", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("dtc_pending", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["scanner_id"], ["scanners.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("scanner_id"),
    )
    op.create_table(
        "telegram_users",
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("first_name", sa.String(length=128), nullable=True),
        sa.Column("scanner_id", sa.String(length=32), nullable=True),
        sa.Column("cursor_key_enc", sa.Text(), nullable=True),
        sa.Column("cursor_key_valid", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["scanner_id"], ["scanners.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("telegram_id"),
    )
    op.create_table(
        "obd_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scanner_id", sa.String(length=32), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["scanner_id"], ["scanners.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_obd_snapshots_scanner_id", "obd_snapshots", ["scanner_id"])
    op.create_index("ix_obd_snapshots_created_at", "obd_snapshots", ["created_at"])
    op.create_table(
        "vehicle_wmi",
        sa.Column("wmi", sa.String(length=3), nullable=False),
        sa.Column("manufacturer", sa.String(length=128), nullable=False),
        sa.Column("country", sa.String(length=64), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("wmi"),
    )


def downgrade() -> None:
    op.drop_table("vehicle_wmi")
    op.drop_index("ix_obd_snapshots_created_at", table_name="obd_snapshots")
    op.drop_index("ix_obd_snapshots_scanner_id", table_name="obd_snapshots")
    op.drop_table("obd_snapshots")
    op.drop_table("telegram_users")
    op.drop_table("scanner_status")
    op.drop_table("scanners")
    postgresql.ENUM(name="scannerstate").drop(op.get_bind(), checkfirst=True)
