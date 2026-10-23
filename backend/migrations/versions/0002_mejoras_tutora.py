"""mejoras tutora

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa


revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('auditoria',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('fecha', sa.DateTime(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=True),
    sa.Column('usuario_email', sa.String(), nullable=True),
    sa.Column('ip', sa.String(), nullable=True),
    sa.Column('modulo', sa.String(), nullable=False),
    sa.Column('accion', sa.String(), nullable=False),
    sa.Column('entidad', sa.String(), nullable=True),
    sa.Column('entidad_id', sa.String(), nullable=True),
    sa.Column('datos_antes', sa.Text(), nullable=True),
    sa.Column('datos_despues', sa.Text(), nullable=True),
    sa.Column('resultado', sa.String(), nullable=False),
    sa.Column('detalle', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_auditoria_accion'), 'auditoria', ['accion'], unique=False)
    op.create_index(op.f('ix_auditoria_fecha'), 'auditoria', ['fecha'], unique=False)
    op.create_index(op.f('ix_auditoria_modulo'), 'auditoria', ['modulo'], unique=False)
    op.create_index(op.f('ix_auditoria_usuario_id'), 'auditoria', ['usuario_id'], unique=False)
    op.create_table('configuracion_correo',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('habilitado', sa.Boolean(), nullable=False),
    sa.Column('host', sa.String(), nullable=False),
    sa.Column('puerto', sa.Integer(), nullable=False),
    sa.Column('seguridad', sa.String(), nullable=False),
    sa.Column('usuario', sa.String(), nullable=False),
    sa.Column('password_cifrada', sa.Text(), nullable=True),
    sa.Column('remitente_email', sa.String(), nullable=False),
    sa.Column('remitente_nombre', sa.String(), nullable=False),
    sa.Column('timeout_segundos', sa.Integer(), nullable=False),
    sa.Column('actualizado_en', sa.DateTime(), nullable=True),
    sa.CheckConstraint('id = 1', name='ck_config_correo_unica'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('planes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('codigo', sa.String(), nullable=False),
    sa.Column('nombre', sa.String(), nullable=False),
    sa.Column('precio', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('moneda', sa.String(), nullable=False),
    sa.Column('periodicidad', sa.String(), nullable=False),
    sa.Column('duracion_dias', sa.Integer(), nullable=False),
    sa.Column('funcionalidades', sa.Text(), nullable=False),
    sa.Column('limites', sa.Text(), nullable=False),
    sa.Column('condiciones', sa.Text(), nullable=False),
    sa.Column('incluye_procesamiento', sa.Boolean(), nullable=False),
    sa.Column('activo', sa.Boolean(), nullable=False),
    sa.Column('orden', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('codigo')
    )
    op.create_table('plantillas_correo',
    sa.Column('codigo', sa.String(), nullable=False),
    sa.Column('asunto', sa.String(), nullable=False),
    sa.Column('cuerpo', sa.Text(), nullable=False),
    sa.PrimaryKeyConstraint('codigo')
    )
    op.create_table('respuestas_sus',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('fecha', sa.DateTime(), nullable=False),
    sa.Column('respuestas', sa.String(), nullable=False),
    sa.Column('puntaje', sa.Integer(), nullable=False),
    sa.Column('comentario', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_respuestas_sus_usuario_id'), 'respuestas_sus', ['usuario_id'], unique=False)
    op.create_table('notificaciones',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('clave', sa.String(), nullable=False),
    sa.Column('tipo', sa.String(), nullable=False),
    sa.Column('mensaje', sa.String(), nullable=False),
    sa.Column('fecha', sa.DateTime(), nullable=False),
    sa.Column('leida', sa.Boolean(), nullable=False),
    sa.Column('correo_enviado', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('usuario_id', 'clave', name='uq_notificacion_clave')
    )
    op.create_index(op.f('ix_notificaciones_usuario_id'), 'notificaciones', ['usuario_id'], unique=False)
    op.create_table('sesiones',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('creada_en', sa.DateTime(), nullable=False),
    sa.Column('ultimo_uso', sa.DateTime(), nullable=False),
    sa.Column('expira_en', sa.DateTime(), nullable=False),
    sa.Column('revocada', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('ip', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sesiones_usuario_id'), 'sesiones', ['usuario_id'], unique=False)
    op.create_table('suscripciones',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('plan_id', sa.Integer(), nullable=False),
    sa.Column('estado', sa.String(), nullable=False),
    sa.Column('fecha_inicio', sa.DateTime(), nullable=False),
    sa.Column('fecha_vencimiento', sa.DateTime(), nullable=True),
    sa.Column('es_prueba', sa.Boolean(), nullable=False),
    sa.Column('cancelada_en', sa.DateTime(), nullable=True),
    sa.Column('motivo_cancelacion', sa.String(), nullable=True),
    sa.Column('plan_siguiente_id', sa.Integer(), nullable=True),
    sa.Column('creada_en', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['plan_id'], ['planes.id'], ),
    sa.ForeignKeyConstraint(['plan_siguiente_id'], ['planes.id'], ),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_suscripciones_estado'), 'suscripciones', ['estado'], unique=False)
    op.create_index(op.f('ix_suscripciones_fecha_vencimiento'), 'suscripciones', ['fecha_vencimiento'], unique=False)
    op.create_index(op.f('ix_suscripciones_usuario_id'), 'suscripciones', ['usuario_id'], unique=False)
    op.create_table('tokens_restablecimiento',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('token_hash', sa.String(), nullable=False),
    sa.Column('creado_en', sa.DateTime(), nullable=False),
    sa.Column('expira_en', sa.DateTime(), nullable=False),
    sa.Column('usado_en', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tokens_restablecimiento_token_hash'), 'tokens_restablecimiento', ['token_hash'], unique=True)
    op.create_index(op.f('ix_tokens_restablecimiento_usuario_id'), 'tokens_restablecimiento', ['usuario_id'], unique=False)
    op.create_table('consentimientos',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('paciente_id', sa.Integer(), nullable=False),
    sa.Column('registrado_por', sa.Integer(), nullable=False),
    sa.Column('fecha', sa.DateTime(), nullable=False),
    sa.Column('version_politica', sa.String(), nullable=False),
    sa.Column('finalidad', sa.String(), nullable=False),
    sa.Column('revocado_en', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['paciente_id'], ['pacientes.id'], ),
    sa.ForeignKeyConstraint(['registrado_por'], ['usuarios.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_consentimientos_paciente_id'), 'consentimientos', ['paciente_id'], unique=False)
    op.create_table('historial_suscripciones',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('suscripcion_id', sa.Integer(), nullable=False),
    sa.Column('fecha', sa.DateTime(), nullable=False),
    sa.Column('evento', sa.String(), nullable=False),
    sa.Column('plan_anterior_id', sa.Integer(), nullable=True),
    sa.Column('plan_nuevo_id', sa.Integer(), nullable=True),
    sa.Column('detalle', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['suscripcion_id'], ['suscripciones.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_historial_suscripciones_suscripcion_id'), 'historial_suscripciones', ['suscripcion_id'], unique=False)
    op.create_table('pagos',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('suscripcion_id', sa.Integer(), nullable=False),
    sa.Column('plan_id', sa.Integer(), nullable=False),
    sa.Column('tipo', sa.String(), nullable=False),
    sa.Column('monto', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('moneda', sa.String(), nullable=False),
    sa.Column('estado', sa.String(), nullable=False),
    sa.Column('proveedor', sa.String(), nullable=False),
    sa.Column('referencia_externa', sa.String(), nullable=False),
    sa.Column('forma_pago', sa.String(), nullable=True),
    sa.Column('creado_en', sa.DateTime(), nullable=False),
    sa.Column('actualizado_en', sa.DateTime(), nullable=True),
    sa.Column('ultimo_evento_id', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['plan_id'], ['planes.id'], ),
    sa.ForeignKeyConstraint(['suscripcion_id'], ['suscripciones.id'], ),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_pagos_estado'), 'pagos', ['estado'], unique=False)
    op.create_index(op.f('ix_pagos_referencia_externa'), 'pagos', ['referencia_externa'], unique=True)
    op.create_index(op.f('ix_pagos_suscripcion_id'), 'pagos', ['suscripcion_id'], unique=False)
    op.create_index(op.f('ix_pagos_usuario_id'), 'pagos', ['usuario_id'], unique=False)
    op.create_table('comprobantes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('numero', sa.String(), nullable=False),
    sa.Column('pago_id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('fecha_emision', sa.DateTime(), nullable=False),
    sa.Column('estado', sa.String(), nullable=False),
    sa.Column('emisor_nombre', sa.String(), nullable=False),
    sa.Column('emisor_ruc', sa.String(), nullable=True),
    sa.Column('emisor_email', sa.String(), nullable=True),
    sa.Column('pagador_nombre', sa.String(), nullable=False),
    sa.Column('pagador_email', sa.String(), nullable=False),
    sa.Column('concepto', sa.String(), nullable=False),
    sa.Column('referencia', sa.String(), nullable=False),
    sa.Column('periodo', sa.String(), nullable=True),
    sa.Column('monto', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('moneda', sa.String(), nullable=False),
    sa.Column('monto_letras', sa.String(), nullable=False),
    sa.Column('forma_pago', sa.String(), nullable=False),
    sa.Column('leyenda', sa.String(), nullable=False),
    sa.Column('anulado_en', sa.DateTime(), nullable=True),
    sa.Column('anulado_por', sa.Integer(), nullable=True),
    sa.Column('motivo_anulacion', sa.String(), nullable=True),
    sa.Column('reimpresiones', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['pago_id'], ['pagos.id'], ),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('pago_id')
    )
    op.create_index(op.f('ix_comprobantes_numero'), 'comprobantes', ['numero'], unique=True)
    op.create_index(op.f('ix_comprobantes_usuario_id'), 'comprobantes', ['usuario_id'], unique=False)
    op.add_column('pacientes', sa.Column('activo', sa.Boolean(), server_default='true', nullable=False))
    op.add_column('pacientes', sa.Column('eliminado_en', sa.DateTime(), nullable=True))
    op.add_column('pacientes', sa.Column('eliminado_por', sa.Integer(), nullable=True))
    op.add_column('pacientes', sa.Column('motivo_eliminacion', sa.String(), nullable=True))
    op.add_column('pacientes', sa.Column('fecha_modificacion', sa.DateTime(), nullable=True))
    op.add_column('pacientes', sa.Column('version', sa.Integer(), server_default='1', nullable=False))
    op.drop_index(op.f('ix_pacientes_cedula'), table_name='pacientes')
    op.create_index(op.f('ix_pacientes_cedula'), 'pacientes', ['cedula'], unique=False)
    op.create_index(op.f('ix_pacientes_activo'), 'pacientes', ['activo'], unique=False)
    op.create_index(op.f('ix_pacientes_dermatologo_id'), 'pacientes', ['dermatologo_id'], unique=False)
    op.create_unique_constraint('uq_paciente_dermatologo_cedula', 'pacientes', ['dermatologo_id', 'cedula'])
    op.create_foreign_key('fk_pacientes_dermatologo', 'pacientes', 'usuarios', ['dermatologo_id'], ['id'])
    op.add_column('seguimientos', sa.Column('tiempo_procesamiento_ms', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_seguimientos_fecha'), 'seguimientos', ['fecha'], unique=False)
    op.create_index(op.f('ix_seguimientos_paciente_id'), 'seguimientos', ['paciente_id'], unique=False)
    op.add_column('usuarios', sa.Column('activo', sa.Boolean(), server_default='true', nullable=False))
    op.add_column('usuarios', sa.Column('fecha_modificacion', sa.DateTime(), nullable=True))
    op.add_column('usuarios', sa.Column('fecha_inactivacion', sa.DateTime(), nullable=True))
    op.add_column('usuarios', sa.Column('fecha_reactivacion', sa.DateTime(), nullable=True))
    op.add_column('usuarios', sa.Column('motivo_inactivacion', sa.String(), nullable=True))
    op.add_column('usuarios', sa.Column('intentos_fallidos', sa.Integer(), server_default='0', nullable=False))
    op.add_column('usuarios', sa.Column('bloqueado_hasta', sa.DateTime(), nullable=True))
    op.add_column('usuarios', sa.Column('password_cambiada_en', sa.DateTime(), nullable=True))
    op.add_column('usuarios', sa.Column('ultimo_acceso', sa.DateTime(), nullable=True))
    op.add_column('usuarios', sa.Column('politica_aceptada_version', sa.String(), nullable=True))
    op.add_column('usuarios', sa.Column('politica_aceptada_en', sa.DateTime(), nullable=True))
    op.execute("UPDATE usuarios SET rol = 'dermatologo' WHERE rol IS NULL")
    op.alter_column('usuarios', 'rol',
               existing_type=sa.VARCHAR(),
               nullable=False)
    op.create_index(op.f('ix_usuarios_activo'), 'usuarios', ['activo'], unique=False)
    # La bitácora de auditoría es de solo inserción: PostgreSQL rechaza UPDATE y DELETE (punto 7).
    if op.get_bind().dialect.name == "postgresql":
        op.execute("""
            CREATE OR REPLACE FUNCTION auditoria_inmutable() RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'Los registros de auditoria no pueden modificarse ni eliminarse';
            END;
            $$ LANGUAGE plpgsql;
        """)
        op.execute("""
            CREATE TRIGGER trg_auditoria_inmutable BEFORE UPDATE OR DELETE ON auditoria
            FOR EACH ROW EXECUTE FUNCTION auditoria_inmutable();
        """)


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS trg_auditoria_inmutable ON auditoria")
        op.execute("DROP FUNCTION IF EXISTS auditoria_inmutable()")
    op.drop_index(op.f('ix_usuarios_activo'), table_name='usuarios')
    op.alter_column('usuarios', 'rol',
               existing_type=sa.VARCHAR(),
               nullable=True)
    op.drop_column('usuarios', 'politica_aceptada_en')
    op.drop_column('usuarios', 'politica_aceptada_version')
    op.drop_column('usuarios', 'ultimo_acceso')
    op.drop_column('usuarios', 'password_cambiada_en')
    op.drop_column('usuarios', 'bloqueado_hasta')
    op.drop_column('usuarios', 'intentos_fallidos')
    op.drop_column('usuarios', 'motivo_inactivacion')
    op.drop_column('usuarios', 'fecha_reactivacion')
    op.drop_column('usuarios', 'fecha_inactivacion')
    op.drop_column('usuarios', 'fecha_modificacion')
    op.drop_column('usuarios', 'activo')
    op.drop_index(op.f('ix_seguimientos_paciente_id'), table_name='seguimientos')
    op.drop_index(op.f('ix_seguimientos_fecha'), table_name='seguimientos')
    op.drop_column('seguimientos', 'tiempo_procesamiento_ms')
    op.drop_constraint('fk_pacientes_dermatologo', 'pacientes', type_='foreignkey')
    op.drop_constraint('uq_paciente_dermatologo_cedula', 'pacientes', type_='unique')
    op.drop_index(op.f('ix_pacientes_dermatologo_id'), table_name='pacientes')
    op.drop_index(op.f('ix_pacientes_activo'), table_name='pacientes')
    op.drop_index(op.f('ix_pacientes_cedula'), table_name='pacientes')
    op.create_index(op.f('ix_pacientes_cedula'), 'pacientes', ['cedula'], unique=True)
    op.drop_column('pacientes', 'version')
    op.drop_column('pacientes', 'fecha_modificacion')
    op.drop_column('pacientes', 'motivo_eliminacion')
    op.drop_column('pacientes', 'eliminado_por')
    op.drop_column('pacientes', 'eliminado_en')
    op.drop_column('pacientes', 'activo')
    op.drop_index(op.f('ix_comprobantes_usuario_id'), table_name='comprobantes')
    op.drop_index(op.f('ix_comprobantes_numero'), table_name='comprobantes')
    op.drop_table('comprobantes')
    op.drop_index(op.f('ix_pagos_usuario_id'), table_name='pagos')
    op.drop_index(op.f('ix_pagos_suscripcion_id'), table_name='pagos')
    op.drop_index(op.f('ix_pagos_referencia_externa'), table_name='pagos')
    op.drop_index(op.f('ix_pagos_estado'), table_name='pagos')
    op.drop_table('pagos')
    op.drop_index(op.f('ix_historial_suscripciones_suscripcion_id'), table_name='historial_suscripciones')
    op.drop_table('historial_suscripciones')
    op.drop_index(op.f('ix_consentimientos_paciente_id'), table_name='consentimientos')
    op.drop_table('consentimientos')
    op.drop_index(op.f('ix_tokens_restablecimiento_usuario_id'), table_name='tokens_restablecimiento')
    op.drop_index(op.f('ix_tokens_restablecimiento_token_hash'), table_name='tokens_restablecimiento')
    op.drop_table('tokens_restablecimiento')
    op.drop_index(op.f('ix_suscripciones_usuario_id'), table_name='suscripciones')
    op.drop_index(op.f('ix_suscripciones_fecha_vencimiento'), table_name='suscripciones')
    op.drop_index(op.f('ix_suscripciones_estado'), table_name='suscripciones')
    op.drop_table('suscripciones')
    op.drop_index(op.f('ix_sesiones_usuario_id'), table_name='sesiones')
    op.drop_table('sesiones')
    op.drop_index(op.f('ix_notificaciones_usuario_id'), table_name='notificaciones')
    op.drop_table('notificaciones')
    op.drop_index(op.f('ix_respuestas_sus_usuario_id'), table_name='respuestas_sus')
    op.drop_table('respuestas_sus')
    op.drop_table('plantillas_correo')
    op.drop_table('planes')
    op.drop_table('configuracion_correo')
    op.drop_index(op.f('ix_auditoria_usuario_id'), table_name='auditoria')
    op.drop_index(op.f('ix_auditoria_modulo'), table_name='auditoria')
    op.drop_index(op.f('ix_auditoria_fecha'), table_name='auditoria')
    op.drop_index(op.f('ix_auditoria_accion'), table_name='auditoria')
    op.drop_table('auditoria')
