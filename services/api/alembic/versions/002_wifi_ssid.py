"""add wifi_ssid to scanner_status

Revision ID: 002
Revises: 001
Create Date: 2026-07-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("scanner_status", sa.Column("wifi_ssid", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("scanner_status", "wifi_ssid")
