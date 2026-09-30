import { router } from 'expo-router';
import { Alert } from 'react-native';
import { API_URL, borrarToken, obtenerToken } from './auth';

export type RespuestaApi<T = any> = { ok: boolean; status: number; data: T };

let avisandoSesion = false;

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
    if (r.status === 401 && auth && token) {
      await sesionExpirada(data?.detail);
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

async function sesionExpirada(detalle?: string) {
  await borrarToken();
  if (avisandoSesion) return;
  avisandoSesion = true;
  Alert.alert('Sesión cerrada', detalle ?? 'Tu sesión terminó. Iniciá sesión de nuevo.', [
    {
      text: 'Aceptar',
      onPress: () => {
        avisandoSesion = false;
        router.replace('/');
      },
    },
  ]);
}

export function mensaje(r: RespuestaApi, porDefecto = 'No se pudo completar la operación. Intentá de nuevo.'): string {
  const d = r.data?.detail;
  return typeof d === 'string' && d ? d : porDefecto;
}

export async function cerrarSesion() {
  await api('/logout', { method: 'POST' });
  await borrarToken();
  router.replace('/');
}

export function fechaCorta(iso?: string | null): string {
  if (!iso) return '—';
  const d = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : iso + 'Z'); // el servidor guarda UTC
  return d.toLocaleString('es-PY', { dateStyle: 'short', timeStyle: 'short' });
}
