import { router } from 'expo-router';
import { avisar } from './dialogo';
import { API_URL, borrarToken, obtenerToken } from './auth';

export type RespuestaApi<T = any> = { ok: boolean; status: number; data: T };

// Token que ya se dio por vencido: evita avisar varias veces cuando varias consultas simultáneas
// vuelven con 401, y evita que una respuesta atrasada cierre una sesión NUEVA.
let tokenVencido: string | null = null;

/** Llamada al backend con el token de sesión. Nunca lanza: devuelve ok/status/data con mensajes
 *  ya redactados para el usuario (qué pasó, por qué y qué hacer). */
export async function api<T = any>(
  ruta: string,
  opciones: { method?: string; json?: unknown; form?: URLSearchParams; multipart?: FormData; auth?: boolean } = {}
): Promise<RespuestaApi<T>> {
  const { method = 'GET', json, form, multipart, auth = true } = opciones;
  const headers: Record<string, string> = {};
  const token = obtenerToken();
  if (auth && token) headers.Authorization = `Bearer ${token}`;
  let body: any;
  if (json !== undefined) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(json);
  } else if (form) {
    headers['Content-Type'] = 'application/x-www-form-urlencoded';
    body = form.toString();
  } else if (multipart) {
    body = multipart;
  }

  try {
    const r = await fetch(`${API_URL}${ruta}`, { method, headers, body });
    let data: any = null;
    try {
      data = await r.json();
    } catch {
      data = null;
    }
    if (r.status === 401 && auth) {
      await sesionExpirada(token, data?.detail);
    }
    return { ok: r.ok, status: r.status, data };
  } catch {
    return {
      ok: false,
      status: 0,
      data: {
        detail:
          'No pudimos conectarnos con el servidor. Revisá tu conexión a internet e intentá de nuevo en unos minutos.',
      } as any,
    };
  }
}

/** Vuelve al login descartando las pantallas anteriores, para que «atrás» no muestre datos sin sesión. */
function irAlLogin() {
  if (router.canDismiss()) router.dismissAll();
  router.replace('/');
}

async function sesionExpirada(tokenUsado: string | null, detalle?: string) {
  if (!tokenUsado) {
    // Se llamó sin sesión (por ejemplo, tras recargar): volver al login sin aviso.
    irAlLogin();
    return;
  }
  if (tokenUsado === tokenVencido) return;        // ya se avisó por este mismo token
  if (obtenerToken() !== tokenUsado) return;      // ya hay otra sesión: esta respuesta es vieja
  tokenVencido = tokenUsado;
  await borrarToken();
  avisar('Sesión cerrada', detalle ?? 'Tu sesión terminó. Iniciá sesión de nuevo.', irAlLogin);
}

export function mensaje(r: RespuestaApi, porDefecto = 'No se pudo completar la operación. Intentá de nuevo.'): string {
  const d = r.data?.detail;
  return typeof d === 'string' && d ? d : porDefecto;
}

export async function cerrarSesion() {
  await api('/logout', { method: 'POST' });
  await borrarToken();
  irAlLogin();
}

export function fechaCorta(iso?: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : iso + 'Z'); // el servidor guarda UTC
  return d.toLocaleString('es-PY', { dateStyle: 'short', timeStyle: 'short' });
}

/** Importe para mostrar: «Gs. 149.000» (el guaraní no tiene centavos) o «USD 9,99». */
export function formatoMonto(monto: string | number, moneda: string): string {
  const n = Number(monto);
  if (moneda === 'PYG') return `Gs. ${Math.round(n).toLocaleString('es-PY').replace(/,/g, '.')}`;
  return `${moneda} ${n.toLocaleString('es-PY', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}
