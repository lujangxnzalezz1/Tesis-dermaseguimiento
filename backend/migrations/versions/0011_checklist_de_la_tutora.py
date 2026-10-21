"""recomendaciones de la tutora: seguridad, privacidad, pagos, comprobantes, plantillas e índices

Revision ID: 0011
Revises: 0010
"""
from alembic import op
import sqlalchemy as sa


revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('configuracion_seguridad',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('longitud_minima', sa.Integer(), nullable=True),
    sa.Column('requiere_mayuscula', sa.Boolean(), nullable=True),
    sa.Column('requiere_minuscula', sa.Boolean(), nullable=True),
    sa.Column('requiere_numero', sa.Boolean(), nullable=True),
    sa.Column('requiere_especial', sa.Boolean(), nullable=True),
    sa.Column('max_dias_vigencia', sa.Integer(), nullable=True),
    sa.Column('comunes_adicionales', sa.Text(), nullable=True),
    sa.Column('actualizado_en', sa.DateTime(), nullable=True),
    sa.Column('actualizado_por', sa.Integer(), nullable=True),
    sa.CheckConstraint('id = 1', name='ck_config_seguridad_unica'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('intentos_limitados',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('clave', sa.String(), nullable=False),
    sa.Column('fecha', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_intentos_limitados_clave'), 'intentos_limitados', ['clave'], unique=False)
    op.create_index(op.f('ix_intentos_limitados_fecha'), 'intentos_limitados', ['fecha'], unique=False)
    op.create_table('consentimientos_usuario',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('version_politica', sa.String(), nullable=False),
    sa.Column('finalidad', sa.String(), nullable=False),
    sa.Column('fecha', sa.DateTime(), nullable=False),
    sa.Column('ip', sa.String(), nullable=True),
    sa.Column('revocado_en', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_consentimientos_usuario_usuario_id'), 'consentimientos_usuario', ['usuario_id'], unique=False)
    op.create_index(op.f('ix_auditoria_usuario_email'), 'auditoria', ['usuario_email'], unique=False)
    op.add_column('comprobantes', sa.Column('pagador_documento', sa.String(), nullable=True))
    op.add_column('comprobantes', sa.Column('pagador_telefono', sa.String(), nullable=True))
    op.add_column('comprobantes', sa.Column('subtotal', sa.Numeric(precision=10, scale=2), nullable=True))
    op.add_column('comprobantes', sa.Column('credito', sa.Numeric(precision=10, scale=2), nullable=True))
    op.add_column('comprobantes', sa.Column('iva', sa.Numeric(precision=10, scale=2), nullable=True))
    op.add_column('comprobantes', sa.Column('reimpreso_en', sa.DateTime(), nullable=True))
    op.drop_constraint(op.f('comprobantes_pago_id_key'), 'comprobantes', type_='unique')
    op.create_index(op.f('ix_comprobantes_pago_id'), 'comprobantes', ['pago_id'], unique=False)
    op.create_index('uq_comprobante_pago_vigente', 'comprobantes', ['pago_id'], unique=True, postgresql_where=sa.text("estado <> 'anulado'"), sqlite_where=sa.text("estado <> 'anulado'"))
    op.add_column('consentimientos', sa.Column('motivo_revocacion', sa.String(), nullable=True))
    op.create_index(op.f('ix_consentimientos_revocado_en'), 'consentimientos', ['revocado_en'], unique=False)
    op.add_column('pagos', sa.Column('credito', sa.Numeric(precision=10, scale=2), nullable=True))
    op.add_column('pagos', sa.Column('transaccion_id', sa.String(), nullable=True))
    op.add_column('pagos', sa.Column('pagador_documento', sa.String(), nullable=True))
    op.add_column('pagos', sa.Column('pagador_telefono', sa.String(), nullable=True))
    # Si quedaron varios pagos pendientes para la misma suscripción y plan, se conserva el más reciente
    op.execute("""
        UPDATE pagos SET estado = 'cancelado'
        WHERE estado = 'pendiente' AND id NOT IN (
            SELECT MAX(id) FROM pagos WHERE estado = 'pendiente' GROUP BY suscripcion_id, plan_id)
    """)
    op.create_index('uq_pago_pendiente_por_plan', 'pagos', ['suscripcion_id', 'plan_id'], unique=True, postgresql_where=sa.text("estado = 'pendiente'"), sqlite_where=sa.text("estado = 'pendiente'"))
    op.add_column('plantillas_indicacion', sa.Column('eliminada_en', sa.DateTime(), nullable=True))
    # Títulos repetidos de un mismo profesional: se numeran para poder crear el índice único
    op.execute("""
        UPDATE plantillas_indicacion SET titulo = titulo || ' (' || r.n || ')'
        FROM (SELECT id, ROW_NUMBER() OVER (PARTITION BY usuario_id, lower(titulo) ORDER BY id) AS n
              FROM plantillas_indicacion) r
        WHERE plantillas_indicacion.id = r.id AND r.n > 1
    """)
    op.create_index('uq_plantilla_usuario_titulo', 'plantillas_indicacion', ['usuario_id', sa.literal_column('lower(titulo)')], unique=True, postgresql_where=sa.text('eliminada_en IS NULL'), sqlite_where=sa.text('eliminada_en IS NULL'))
    op.create_index(op.f('ix_seguimientos_ruta_imagen_alineada'), 'seguimientos', ['ruta_imagen_alineada'], unique=False)
    op.create_index(op.f('ix_seguimientos_ruta_imagen_lesiones'), 'seguimientos', ['ruta_imagen_lesiones'], unique=False)
    op.create_index(op.f('ix_seguimientos_ruta_imagen_manchas'), 'seguimientos', ['ruta_imagen_manchas'], unique=False)
    op.create_index(op.f('ix_seguimientos_ruta_imagen_nueva'), 'seguimientos', ['ruta_imagen_nueva'], unique=False)
    op.create_index(op.f('ix_seguimientos_ruta_imagen_periorbital'), 'seguimientos', ['ruta_imagen_periorbital'], unique=False)
    op.create_index(op.f('ix_seguimientos_ruta_imagen_referencia'), 'seguimientos', ['ruta_imagen_referencia'], unique=False)
    op.create_index(op.f('ix_seguimientos_ruta_imagen_textura'), 'seguimientos', ['ruta_imagen_textura'], unique=False)
    op.create_index(op.f('ix_seguimientos_ruta_imagen_uv'), 'seguimientos', ['ruta_imagen_uv'], unique=False)
    op.create_index(op.f('ix_seguimientos_ruta_imagen_uv_analisis'), 'seguimientos', ['ruta_imagen_uv_analisis'], unique=False)
    op.create_index(op.f('ix_seguimientos_ruta_mapa_calor'), 'seguimientos', ['ruta_mapa_calor'], unique=False)
    op.create_index(op.f('ix_seguimientos_ruta_mapa_luminosidad'), 'seguimientos', ['ruta_mapa_luminosidad'], unique=False)
    op.create_index(op.f('ix_seguimientos_ruta_mapa_rojez'), 'seguimientos', ['ruta_mapa_rojez'], unique=False)
    op.create_index(op.f('ix_seguimientos_usuario_id'), 'seguimientos', ['usuario_id'], unique=False)
    duplicadas = op.get_bind().execute(sa.text(
        "SELECT COUNT(*) FROM (SELECT usuario_id FROM suscripciones GROUP BY usuario_id HAVING COUNT(*) > 1) d")).scalar()
    if duplicadas:
        raise RuntimeError(f"{duplicadas} usuarios tienen más de una suscripción: revisalas antes de migrar.")
    op.drop_index(op.f('ix_suscripciones_usuario_id'), table_name='suscripciones')
    op.create_index(op.f('ix_suscripciones_usuario_id'), 'suscripciones', ['usuario_id'], unique=True)
    op.add_column('usuarios', sa.Column('politica_finalidad', sa.String(), nullable=True))
    op.add_column('usuarios', sa.Column('consentimiento_revocado_en', sa.DateTime(), nullable=True))
    op.add_column('usuarios', sa.Column('anonimizado_en', sa.DateTime(), nullable=True))

    # Consentimientos ya aceptados: se registran con su finalidad en la tabla nueva
    op.execute("UPDATE usuarios SET politica_finalidad = 'uso del sistema' WHERE politica_aceptada_version IS NOT NULL")
    op.execute("""
        INSERT INTO consentimientos_usuario (usuario_id, version_politica, finalidad, fecha)
        SELECT id, politica_aceptada_version, 'uso del sistema', COALESCE(politica_aceptada_en, fecha_creacion)
        FROM usuarios WHERE politica_aceptada_version IS NOT NULL
    """)
    # La reimpresión ya no cambia el estado del comprobante
    op.execute("UPDATE comprobantes SET estado = 'emitido' WHERE estado = 'reimpreso'")


def downgrade() -> None:
    op.drop_column('usuarios', 'anonimizado_en')
    op.drop_column('usuarios', 'consentimiento_revocado_en')
    op.drop_column('usuarios', 'politica_finalidad')
    op.drop_index(op.f('ix_suscripciones_usuario_id'), table_name='suscripciones')
    op.create_index(op.f('ix_suscripciones_usuario_id'), 'suscripciones', ['usuario_id'], unique=False)
    op.drop_index(op.f('ix_seguimientos_usuario_id'), table_name='seguimientos')
    op.drop_index(op.f('ix_seguimientos_ruta_mapa_rojez'), table_name='seguimientos')
    op.drop_index(op.f('ix_seguimientos_ruta_mapa_luminosidad'), table_name='seguimientos')
    op.drop_index(op.f('ix_seguimientos_ruta_mapa_calor'), table_name='seguimientos')
    op.drop_index(op.f('ix_seguimientos_ruta_imagen_uv_analisis'), table_name='seguimientos')
    op.drop_index(op.f('ix_seguimientos_ruta_imagen_uv'), table_name='seguimientos')
    op.drop_index(op.f('ix_seguimientos_ruta_imagen_textura'), table_name='seguimientos')
    op.drop_index(op.f('ix_seguimientos_ruta_imagen_referencia'), table_name='seguimientos')
    op.drop_index(op.f('ix_seguimientos_ruta_imagen_periorbital'), table_name='seguimientos')
    op.drop_index(op.f('ix_seguimientos_ruta_imagen_nueva'), table_name='seguimientos')
    op.drop_index(op.f('ix_seguimientos_ruta_imagen_manchas'), table_name='seguimientos')
    op.drop_index(op.f('ix_seguimientos_ruta_imagen_lesiones'), table_name='seguimientos')
    op.drop_index(op.f('ix_seguimientos_ruta_imagen_alineada'), table_name='seguimientos')
    op.drop_index('uq_plantilla_usuario_titulo', table_name='plantillas_indicacion', postgresql_where=sa.text('eliminada_en IS NULL'), sqlite_where=sa.text('eliminada_en IS NULL'))
    op.drop_column('plantillas_indicacion', 'eliminada_en')
    op.drop_index('uq_pago_pendiente_por_plan', table_name='pagos', postgresql_where=sa.text("estado = 'pendiente'"), sqlite_where=sa.text("estado = 'pendiente'"))
    op.drop_column('pagos', 'pagador_telefono')
    op.drop_column('pagos', 'pagador_documento')
    op.drop_column('pagos', 'transaccion_id')
    op.drop_column('pagos', 'credito')
    op.drop_index(op.f('ix_consentimientos_revocado_en'), table_name='consentimientos')
    op.drop_column('consentimientos', 'motivo_revocacion')
    op.drop_index('uq_comprobante_pago_vigente', table_name='comprobantes', postgresql_where=sa.text("estado <> 'anulado'"), sqlite_where=sa.text("estado <> 'anulado'"))
    op.drop_index(op.f('ix_comprobantes_pago_id'), table_name='comprobantes')
    op.create_unique_constraint(op.f('comprobantes_pago_id_key'), 'comprobantes', ['pago_id'], postgresql_nulls_not_distinct=False)
    op.drop_column('comprobantes', 'reimpreso_en')
    op.drop_column('comprobantes', 'iva')
    op.drop_column('comprobantes', 'credito')
    op.drop_column('comprobantes', 'subtotal')
    op.drop_column('comprobantes', 'pagador_telefono')
    op.drop_column('comprobantes', 'pagador_documento')
    op.drop_index(op.f('ix_auditoria_usuario_email'), table_name='auditoria')
    op.drop_index(op.f('ix_consentimientos_usuario_usuario_id'), table_name='consentimientos_usuario')
    op.drop_table('consentimientos_usuario')
    op.drop_index(op.f('ix_intentos_limitados_fecha'), table_name='intentos_limitados')
    op.drop_index(op.f('ix_intentos_limitados_clave'), table_name='intentos_limitados')
    op.drop_table('intentos_limitados')
    op.drop_table('configuracion_seguridad')
