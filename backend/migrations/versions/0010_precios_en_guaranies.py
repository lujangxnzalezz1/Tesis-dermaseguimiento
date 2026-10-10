"""precios de los planes en guaraníes (validados con la encuesta)

Revision ID: 0010
Revises: 0009
"""
from alembic import op


revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE planes SET moneda = 'PYG'")
    op.execute("UPDATE planes SET precio = 149000, condiciones = 'Gs. 149.000 cada 30 días, IVA incluido. Cancelás cuando quieras y "
               "conservás el acceso hasta el fin del período pagado. Sin reembolsos proporcionales.' WHERE codigo = 'premium_mensual'")
    op.execute("UPDATE planes SET precio = 1190000, condiciones = 'Gs. 1.190.000 por 365 días, IVA incluido (unos 4 meses gratis). Al "
               "mejorar desde el mensual se acredita el tiempo no usado. Sin reembolsos proporcionales.' WHERE codigo = 'premium_anual'")
    op.execute("""UPDATE planes SET funcionalidades = '["Todo lo del plan Gratuito", "Comparación alineada de fotografías (antes/después con capas)", "Análisis de color por zona, manchas, textura y ojeras", "Detección de lesiones de acné (YOLOv8)", "Valoración clínica (IGA, mMASI) y foto con luz UV", "Informe en PDF para el paciente e indicaciones con plantillas", "Gráfico de evolución y reportes CSV ilimitados"]' WHERE codigo = 'premium_mensual'""")
    op.alter_column('planes', 'moneda', server_default='PYG')


def downgrade() -> None:
    op.execute("UPDATE planes SET precio = 9.99, moneda = 'USD' WHERE codigo = 'premium_mensual'")
    op.execute("UPDATE planes SET precio = 79.99, moneda = 'USD' WHERE codigo = 'premium_anual'")
    op.execute("UPDATE planes SET moneda = 'USD' WHERE codigo = 'gratuito'")
