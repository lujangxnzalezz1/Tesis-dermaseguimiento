import { WebView } from 'react-native-webview';
import { API_URL } from '../lib/auth';
import { SCRIPTS, type ConfigCaptcha } from '../lib/captcha';

/** Widget del CAPTCHA en la app nativa: una vista web mínima carga el script del proveedor y
 *  devuelve el token a la app con postMessage. La página se sirve con el origen del backend, así
 *  el proveedor valida ese dominio (debe estar autorizado en la configuración del sitio). */
export function CaptchaNativo({ config, onToken }: { config: ConfigCaptcha; onToken: (token: string | null) => void }) {
  const { url, global } = SCRIPTS[config.proveedor];
  const html = `<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<script src="${url}" async defer></script></head>
<body style="margin:0;display:flex;justify-content:center;background:transparent">
<div id="c"></div>
<script>
  function enviar(t) { window.ReactNativeWebView.postMessage(JSON.stringify({ token: t })); }
  function iniciar() {
    var g = window[${JSON.stringify(global)}];
    if (!g || !g.render) return setTimeout(iniciar, 200);
    g.render(document.getElementById('c'), {
      sitekey: ${JSON.stringify(config.site_key)},
      callback: function (t) { enviar(t); },
      'expired-callback': function () { enviar(null); },
      'error-callback': function () { enviar(null); }
    });
  }
  iniciar();
</script></body></html>`;
  return (
    <WebView
      originWhitelist={['*']}
      source={{ html, baseUrl: new URL(API_URL).origin }}
      onMessage={(e) => {
        try { onToken(JSON.parse(e.nativeEvent.data).token ?? null); } catch { onToken(null); }
      }}
      onError={() => onToken(null)}
      javaScriptEnabled
      scrollEnabled={false}
      style={{ height: 80, backgroundColor: 'transparent' }}
      accessibilityLabel="Verificación de seguridad"
    />
  );
}
