import io

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from models.suscripcion import Comprobante
from services.letras import formato_monto


def generar_pdf(c: Comprobante, reimpreso: bool = False) -> bytes:
    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    y = h - 25 * mm
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(20 * mm, y, "RECIBO ELECTRÓNICO DE PAGO")
    y -= 8 * mm
    pdf.setFont("Helvetica", 10)
    estado = c.estado.upper() + (" (REIMPRESIÓN)" if reimpreso else "")
    pdf.drawString(20 * mm, y, f"N.º {c.numero}    Estado: {estado}")
    y -= 6 * mm
    pdf.drawString(20 * mm, y, f"Fecha y hora de emisión (servidor, UTC): {c.fecha_emision:%Y-%m-%d %H:%M:%S}")

    def bloque(titulo, lineas):
        nonlocal y
        y -= 10 * mm
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(20 * mm, y, titulo)
        pdf.setFont("Helvetica", 10)
        for linea in lineas:
            y -= 5.5 * mm
            pdf.drawString(24 * mm, y, linea[:110])

    bloque("Emisor", [c.emisor_nombre, f"RUC: {c.emisor_ruc or 'No aplica'}", f"Correo: {c.emisor_email or '-'}"])
    bloque("Pagador", [c.pagador_nombre, f"Correo: {c.pagador_email}"])
    bloque("Detalle", [f"Concepto: {c.concepto}", f"Referencia de la transacción: {c.referencia}",
                       f"Período: {c.periodo or 'No aplica'}"])
    bloque("Importe", [f"Total recibido: {formato_monto(c.monto, c.moneda)}", f"En letras: {c.monto_letras}", f"Forma de pago: {c.forma_pago}"])
    if c.estado == "anulado":
        bloque("ANULADO", [f"Anulado el {c.anulado_en:%Y-%m-%d %H:%M:%S}", f"Motivo: {c.motivo_anulacion or '-'}"])
    y -= 14 * mm
    pdf.setFont("Helvetica-Oblique", 8.5)
    texto = c.leyenda
    while texto:
        pdf.drawString(20 * mm, y, texto[:120])
        texto = texto[120:]
        y -= 4.5 * mm
    pdf.showPage()
    pdf.save()
    return buf.getvalue()
