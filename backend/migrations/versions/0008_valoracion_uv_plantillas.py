"""valoración clínica, foto UV (porfirinas) y plantillas de indicaciones

Revision ID: 0008
Revises: 0007
"""
from alembic import op
import sqlalchemy as sa


revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('seguimientos', sa.Column('valoracion_clinica', sa.Text(), nullable=True))
    op.add_column('seguimientos', sa.Column('porfirinas', sa.Text(), nullable=True))
    op.add_column('seguimientos', sa.Column('ruta_imagen_uv', sa.String(), nullable=True))
    op.add_column('seguimientos', sa.Column('ruta_imagen_uv_analisis', sa.String(), nullable=True))
    op.create_table(
        'plantillas_indicacion',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('usuario_id', sa.Integer(), sa.ForeignKey('usuarios.id'), nullable=False),
        sa.Column('titulo', sa.String(length=60), nullable=False),
        sa.Column('texto', sa.Text(), nullable=False),
        sa.Column('creada_en', sa.DateTime(), nullable=False),
    )
    op.create_index(op.f('ix_plantillas_indicacion_usuario_id'), 'plantillas_indicacion', ['usuario_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_plantillas_indicacion_usuario_id'), table_name='plantillas_indicacion')
    op.drop_table('plantillas_indicacion')
    op.drop_column('seguimientos', 'ruta_imagen_uv_analisis')
    op.drop_column('seguimientos', 'ruta_imagen_uv')
    op.drop_column('seguimientos', 'porfirinas')
    op.drop_column('seguimientos', 'valoracion_clinica')
