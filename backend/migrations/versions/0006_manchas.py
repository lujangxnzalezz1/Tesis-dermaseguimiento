"""manchas (zonas hiperpigmentadas)

Revision ID: 0006
Revises: 0005
"""
from alembic import op
import sqlalchemy as sa


revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('seguimientos', sa.Column('manchas_pct_referencia', sa.Float(), nullable=True))
    op.add_column('seguimientos', sa.Column('manchas_pct_nueva', sa.Float(), nullable=True))
    op.add_column('seguimientos', sa.Column('manchas_detalle', sa.Text(), nullable=True))
    op.add_column('seguimientos', sa.Column('ruta_imagen_manchas', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('seguimientos', 'ruta_imagen_manchas')
    op.drop_column('seguimientos', 'manchas_detalle')
    op.drop_column('seguimientos', 'manchas_pct_nueva')
    op.drop_column('seguimientos', 'manchas_pct_referencia')
