"""Esquema inicial (usuarios, pacientes, seguimientos) tal como existía antes de las mejoras.

Revision ID: 0001
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("nombre", sa.String(), nullable=False),
        sa.Column("rol", sa.String()),
        sa.Column("fecha_creacion", sa.DateTime()),
    )
    op.create_index("ix_usuarios_id", "usuarios", ["id"])
    op.create_index("ix_usuarios_email", "usuarios", ["email"], unique=True)

    op.create_table(
        "pacientes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cedula", sa.String(), nullable=False),
        sa.Column("nombre", sa.String(), nullable=False),
        sa.Column("apellido", sa.String(), nullable=False),
        sa.Column("fecha_nacimiento", sa.Date()),
        sa.Column("sexo", sa.String()),
        sa.Column("telefono", sa.String()),
        sa.Column("antecedentes_medicos", sa.String()),
        sa.Column("observaciones", sa.String()),
        sa.Column("dermatologo_id", sa.Integer(), nullable=False),
        sa.Column("fecha_creacion", sa.DateTime()),
    )
    op.create_index("ix_pacientes_id", "pacientes", ["id"])
    op.create_index("ix_pacientes_cedula", "pacientes", ["cedula"], unique=True)

    op.create_table(
        "seguimientos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("paciente_id", sa.Integer(), sa.ForeignKey("pacientes.id"), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("fecha", sa.DateTime()),
        sa.Column("ruta_imagen_referencia", sa.String(), nullable=False),
        sa.Column("ruta_imagen_nueva", sa.String(), nullable=False),
        sa.Column("ruta_imagen_alineada", sa.String(), nullable=False),
        sa.Column("landmarks_referencia", sa.Integer(), nullable=False),
        sa.Column("landmarks_nueva", sa.Integer(), nullable=False),
        sa.Column("ruta_mapa_calor", sa.String(), nullable=False),
        sa.Column("delta_e_promedio", sa.Float(), nullable=False),
        sa.Column("l_referencia", sa.Float(), nullable=False),
        sa.Column("a_referencia", sa.Float(), nullable=False),
        sa.Column("b_referencia", sa.Float(), nullable=False),
        sa.Column("l_nueva", sa.Float(), nullable=False),
        sa.Column("a_nueva", sa.Float(), nullable=False),
        sa.Column("b_nueva", sa.Float(), nullable=False),
    )
    op.create_index("ix_seguimientos_id", "seguimientos", ["id"])


def downgrade() -> None:
    op.drop_table("seguimientos")
    op.drop_table("pacientes")
    op.drop_table("usuarios")
