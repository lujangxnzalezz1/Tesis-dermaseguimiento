"""textura (líneas, poros, brillo) e indicaciones del profesional

Revision ID: 0007
Revises: 0006
"""
from alembic import op
import sqlalchemy as sa


revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('seguimientos', sa.Column('textura_referencia', sa.Text(), nullable=True))
    op.add_column('seguimientos', sa.Column('textura_nueva', sa.Text(), nullable=True))
    op.add_column('seguimientos', sa.Column('ruta_imagen_textura', sa.String(), nullable=True))
    op.add_column('seguimientos', sa.Column('recomendaciones', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('seguimientos', 'recomendaciones')
    op.drop_column('seguimientos', 'ruta_imagen_textura')
    op.drop_column('seguimientos', 'textura_nueva')
    op.drop_column('seguimientos', 'textura_referencia')
