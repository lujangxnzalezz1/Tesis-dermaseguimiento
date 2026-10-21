import * as WebBrowser from 'expo-web-browser';
import { Platform } from 'react-native';
import { api, mensaje } from './api';
import { API_URL, obtenerToken } from './auth';

/** Descarga el PDF del comprobante. En web se baja como archivo; en la app nativa se abre en el
 *  navegador del sistema (desde ahí se guarda o se comparte) con un enlace firmado que vale unos
 *  minutos, porque el navegador no puede enviar el token de sesión. Devuelve un mensaje de error o null. */
export async function descargarComprobante(id: number, numero: string): Promise<string | null> {
  if (Platform.OS !== 'web') {
    const r = await api(`/comprobantes/${id}/enlace`, { method: 'POST' });
    if (!r.ok) return mensaje(r, 'No pudimos preparar la descarga del comprobante. Intentá de nuevo.');
    try {
      await WebBrowser.openBrowserAsync(r.data.url);
      return null;
    } catch {
      return 'No pudimos abrir el comprobante en el navegador. Intentá de nuevo.';
    }
  }
  try {
    const r = await fetch(`${API_URL}/comprobantes/${id}/pdf`, { headers: { Authorization: `Bearer ${obtenerToken()}` } });
    if (!r.ok) return 'No pudimos descargar el comprobante. Intentá de nuevo.';
    const url = URL.createObjectURL(await r.blob());
    const a = document.createElement('a');
    a.href = url; a.download = `${numero}.pdf`; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 5000);
    return null;
  } catch {
    return 'No pudimos conectarnos con el servidor para descargar el comprobante.';
  }
}
