"""tenants nombre unique

Revision ID: faf8f65e853e
Revises: 344795bfdab6
Create Date: 2026-06-10 16:15:13.024182

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'faf8f65e853e'
down_revision: Union[str, None] = '344795bfdab6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint("uq_tenants_nombre", "tenants", ["nombre"])


def downgrade() -> None:
    op.drop_constraint("uq_tenants_nombre", "tenants", type_="unique")
