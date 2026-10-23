import type { ConfigCaptcha } from '../lib/captcha';

/** En la versión web el CAPTCHA se dibuja directamente en Captcha.tsx; este archivo solo existe para
 *  que la web no cargue react-native-webview (la app nativa usa CaptchaNativo.native.tsx). */
export function CaptchaNativo(_: { config: ConfigCaptcha; onToken: (token: string | null) => void }) {
  return null;
}
