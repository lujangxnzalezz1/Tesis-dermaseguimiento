"""cambio de color por zona y mapas de rojez y luminosidad

Revision ID: 0009
Revises: 0008
"""
from alembic import op
import sqlalchemy as sa


revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('seguimientos', sa.Column('color_regiones', sa.Text(), nullable=True))
    op.add_column('seguimientos', sa.Column('ruta_mapa_rojez', sa.String(), nullable=True))
    op.add_column('seguimientos', sa.Column('ruta_mapa_luminosidad', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('seguimientos', 'ruta_mapa_luminosidad')
    op.drop_column('seguimientos', 'ruta_mapa_rojez')
    op.drop_column('seguimientos', 'color_regiones')
