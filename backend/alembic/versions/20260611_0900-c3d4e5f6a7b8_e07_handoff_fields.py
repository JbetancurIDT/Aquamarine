"""e07_handoff_fields

Revision ID: c3d4e5f6a7b8
Revises: 9e45011e26e0
Create Date: 2026-06-11 09:00:00.000000

Agrega campos de takeover humano y notificaciones escalonadas al modelo Lead.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = '9e45011e26e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('leads', sa.Column(
        'atendido_por_humano', sa.Boolean(), nullable=False, server_default='false'
    ))
    op.add_column('leads', sa.Column(
        'asignado_en', sa.DateTime(timezone=True), nullable=True
    ))
    op.add_column('leads', sa.Column(
        'ultima_notificacion_en', sa.DateTime(timezone=True), nullable=True
    ))
    op.add_column('leads', sa.Column(
        'notificaciones_count', sa.Integer(), nullable=False, server_default='0'
    ))


def downgrade() -> None:
    op.drop_column('leads', 'notificaciones_count')
    op.drop_column('leads', 'ultima_notificacion_en')
    op.drop_column('leads', 'asignado_en')
    op.drop_column('leads', 'atendido_por_humano')
