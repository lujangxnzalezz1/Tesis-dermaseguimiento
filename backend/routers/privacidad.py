from fastapi import APIRouter

from core.config import settings

router = APIRouter(tags=["Privacidad"])


def texto_politica() -> dict:
    return {
        "version": settings.POLITICA_VERSION,
        "titulo": "Política de Privacidad de DermaSeguimiento",
        "secciones": [
            {"titulo": "Qué datos recopilamos",
             "texto": "De los profesionales: nombre, correo electrónico, contraseña (almacenada solo como hash) y registros de uso. "
                      "De los pacientes, cargados por el dermatólogo: cédula, nombre, apellido, fecha de nacimiento, sexo, teléfono, "
                      "antecedentes médicos, observaciones y fotografías clínicas del rostro con sus métricas de color."},
            {"titulo": "Para qué los usamos",
             "texto": "Exclusivamente para el seguimiento fotográfico dermatológico: alinear imágenes, medir cambios de color de la piel "
                      "y mostrar la evolución al profesional. No se usan para otros fines distintos a los declarados al paciente. "
                      "Los resultados son informativos y de apoyo; la interpretación clínica corresponde únicamente al profesional habilitado."},
            {"titulo": "Quién es responsable del tratamiento", "texto": f"{settings.RESPONSABLE_TRATAMIENTO}. Contacto: {settings.CONTACTO_PRIVACIDAD}."},
            {"titulo": "Por cuánto tiempo los conservamos",
             "texto": f"Mientras la cuenta del profesional esté activa y hasta {settings.RETENCION_DATOS_ANIOS} años después de la última "
                      "consulta, salvo obligación legal o de auditoría. Las bajas de pacientes son lógicas: el historial se conserva "
                      "con acceso restringido."},
            {"titulo": "Con quién los compartimos",
             "texto": "No vendemos ni compartimos datos con terceros. Solo intervienen proveedores técnicos necesarios (alojamiento, "
                      "correo electrónico y pasarela de pago, que recibe únicamente datos del pago del profesional, nunca datos clínicos)."},
            {"titulo": "Medidas de seguridad",
             "texto": "Contraseñas con hash bcrypt, sesiones con vencimiento y cierre por inactividad, permisos verificados en el servidor, "
                      "imágenes clínicas sin acceso público y guardadas con nombres aleatorios, comunicaciones cifradas (HTTPS) en producción "
                      "y bitácora de auditoría de las operaciones."},
            {"titulo": "Tus derechos",
             "texto": f"Podés pedir acceso, actualización, corrección o eliminación de tus datos, y retirar tu consentimiento, escribiendo a "
                      f"{settings.CONTACTO_PRIVACIDAD}. Los registros que deban conservarse por razones legales, contractuales o de auditoría "
                      "no pueden eliminarse."},
            {"titulo": "Consentimiento del paciente",
             "texto": "Antes de registrar a un paciente o sus fotos, el profesional debe obtener su consentimiento informado. El sistema "
                      "guarda quién lo registró, la fecha y hora, la versión de esta política y la finalidad autorizada, y permite revocarlo."},
        ],
    }


@router.get("/politica-privacidad")
def politica_privacidad():
    return texto_politica()
