"""ssim y lesiones

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa


revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('seguimientos', sa.Column('ssim_antes', sa.Float(), nullable=True))
    op.add_column('seguimientos', sa.Column('ssim_despues', sa.Float(), nullable=True))
    op.add_column('seguimientos', sa.Column('lesiones_referencia', sa.Integer(), nullable=True))
    op.add_column('seguimientos', sa.Column('lesiones_nueva', sa.Integer(), nullable=True))
    op.add_column('seguimientos', sa.Column('lesiones_nuevas', sa.Integer(), nullable=True))
    op.add_column('seguimientos', sa.Column('lesiones_persistentes', sa.Integer(), nullable=True))
    op.add_column('seguimientos', sa.Column('lesiones_resueltas', sa.Integer(), nullable=True))
    op.add_column('seguimientos', sa.Column('lesiones_detalle', sa.Text(), nullable=True))
    op.add_column('seguimientos', sa.Column('ruta_imagen_lesiones', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('seguimientos', 'ruta_imagen_lesiones')
    op.drop_column('seguimientos', 'lesiones_detalle')
    op.drop_column('seguimientos', 'lesiones_resueltas')
    op.drop_column('seguimientos', 'lesiones_persistentes')
    op.drop_column('seguimientos', 'lesiones_nuevas')
    op.drop_column('seguimientos', 'lesiones_nueva')
    op.drop_column('seguimientos', 'lesiones_referencia')
    op.drop_column('seguimientos', 'ssim_despues')
    op.drop_column('seguimientos', 'ssim_antes')
