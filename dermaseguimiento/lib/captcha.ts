/** Datos del CAPTCHA compartidos por la versión web y la nativa. */
export type Proveedor = 'turnstile' | 'hcaptcha' | 'recaptcha';
export type ConfigCaptcha = { activo: boolean; proveedor: Proveedor; site_key: string; eximir_app_nativa: boolean };

export const SCRIPTS: Record<Proveedor, { url: string; global: string }> = {
  turnstile: { url: 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit', global: 'turnstile' },
  hcaptcha: { url: 'https://js.hcaptcha.com/1/api.js?render=explicit', global: 'hcaptcha' },
  recaptcha: { url: 'https://www.google.com/recaptcha/api.js?render=explicit', global: 'grecaptcha' },
};
