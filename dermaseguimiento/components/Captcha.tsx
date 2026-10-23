import { useCallback, useEffect, useRef, useState } from 'react';
import { Platform, Text, View } from 'react-native';
import { api } from '../lib/api';
import { CaptchaNativo } from './CaptchaNativo';
import { SCRIPTS, type ConfigCaptcha, type Proveedor } from '../lib/captcha';
import { COLOR, FUENTE } from './ui';

export type { ConfigCaptcha };

/** Verificación anti-robots (CAPTCHA). El servidor indica en GET /config-publica si está activa, el
 *  proveedor (Cloudflare Turnstile, hCaptcha o reCAPTCHA) y la clave pública.
 *
 *  - Web: se inserta el script del proveedor y se dibuja su widget.
 *  - App nativa: el widget se dibuja en una vista web (CaptchaNativo.native.tsx, react-native-webview).
 *    Si el servidor tiene CAPTCHA_EXIMIR_APP_NATIVA=true no se muestra (la app envía X-Cliente: app-nativa). */

let configCache: Promise<ConfigCaptcha | null> | null = null;

/** Configuración pública del CAPTCHA (se pide una sola vez; si falla se vuelve a pedir la próxima). */
export function cargarConfigCaptcha(): Promise<ConfigCaptcha | null> {
  if (!configCache) {
    configCache = api('/config-publica', { auth: false }).then((r) => {
      if (!r.ok) configCache = null;
      return r.ok ? (r.data.captcha as ConfigCaptcha) : null;
    });
  }
  return configCache;
}

/** Carga el script del proveedor una sola vez y espera a que su objeto global esté listo. */
function cargarScript(p: Proveedor): Promise<any> {
  const { url, global } = SCRIPTS[p];
  const w = window as any;
  if (!document.querySelector(`script[data-captcha="${p}"]`)) {
    const s = document.createElement('script');
    s.src = url;
    s.async = true;
    s.defer = true;
    s.dataset.captcha = p;
    document.head.appendChild(s);
  }
  return new Promise((resolve, reject) => {
    const inicio = Date.now();
    const revisar = () => {
      if (w[global]?.render) return resolve(w[global]);
      if (Date.now() - inicio > 15000) return reject(new Error('CAPTCHA no disponible'));
      setTimeout(revisar, 200);
    };
    revisar();
  });
}

export function Captcha({ onToken }: { onToken: (token: string | null) => void }) {
  const contenedor = useRef<any>(null);
  const [config, setConfig] = useState<ConfigCaptcha | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => { cargarConfigCaptcha().then(setConfig); }, []);

  useEffect(() => {
    if (Platform.OS !== 'web' || !config?.activo || !contenedor.current) return;
    let widgetId: any = null;
    let sdk: any = null;
    let cancelado = false;
    cargarScript(config.proveedor)
      .then((s) => {
        if (cancelado || !contenedor.current) return;
        sdk = s;
        // En la versión web, la referencia de un <View> es el elemento del DOM
        widgetId = s.render(contenedor.current, {
          sitekey: config.site_key,
          callback: (t: string) => onToken(t),
          'expired-callback': () => onToken(null),
          'error-callback': () => onToken(null),
        });
      })
      .catch(() => !cancelado && setError(true));
    return () => {
      cancelado = true;
      try { if (sdk && widgetId != null) (sdk.remove ?? sdk.reset)?.(widgetId); } catch { /* el widget ya no existe */ }
    };
  }, [config, onToken]);

  if (!config?.activo) return null;
  if (Platform.OS !== 'web') {
    return config.eximir_app_nativa ? null : (
      <View style={{ marginVertical: 8 }}>
        <CaptchaNativo config={config} onToken={onToken} />
      </View>
    );
  }
  return (
    <View style={{ marginVertical: 8 }}>
      <View ref={contenedor} accessibilityLabel="Verificación de seguridad" style={{ minHeight: 65 }} />
      {error && (
        <Text style={{ fontFamily: FUENTE.texto, fontSize: 13, color: COLOR.error }}>
          No se pudo cargar la verificación de seguridad. Revisá tu conexión y recargá la página.
        </Text>
      )}
    </View>
  );
}

/** Estado del CAPTCHA para un formulario. Los tokens son de un solo uso: llamar a `reiniciar()`
 *  después de cada envío para que el usuario resuelva uno nuevo. */
export function useCaptcha() {
  const [token, setToken] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const [requerido, setRequerido] = useState(false);

  useEffect(() => {
    cargarConfigCaptcha().then((c) => setRequerido(!!c?.activo && (Platform.OS === 'web' || !c.eximir_app_nativa)));
  }, []);

  const alCambiar = useCallback((t: string | null) => setToken(t), []);
  const reiniciar = useCallback(() => { setToken(null); setVersion((v) => v + 1); }, []);
  const widget = <Captcha key={version} onToken={alCambiar} />;
  return { token, widget, reiniciar, falta: requerido && !token };
}

export const MSG_FALTA_CAPTCHA = 'Completá la verificación de seguridad para continuar.';
