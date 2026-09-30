import { Platform } from 'react-native';
import * as SecureStore from 'expo-secure-store';

// Dirección del backend. Orden de prioridad:
//   0) Versión web: la misma computadora que sirve la página (ver URL_WEB)
//   1) EXPO_PUBLIC_API_URL (archivo .env de la app, solo app nativa), p. ej. http://192.168.1.20:8000
//   2) IP_DISPOSITIVO_FISICO, para probar en un celular real por WiFi
//   3) localhost / 10.0.2.2 para simulador o emulador en la misma computadora
// En producción debe ser una URL https:// (RNF-04).
const IP_DISPOSITIVO_FISICO: string | null = null;

const HOST_EMULADOR = Platform.select({
  ios: 'localhost',
  android: '10.0.2.2',
  default: 'localhost',
});

// En la versión web el backend está en la misma computadora que sirve la página: se usa esa
// dirección, así funciona en cualquier red (localhost en la Mac o la IP de la red desde el celular).
// Por https (para la cámara en vivo del iPhone) la API está en el puerto 8444; por http, en 8000.
const URL_WEB =
  Platform.OS === 'web' && typeof window !== 'undefined'
    ? window.location.protocol === 'https:'
      ? `https://${window.location.hostname}:8444`
      : `http://${window.location.hostname}:8000`
    : null;

export const API_URL: string =
  URL_WEB ??
  process.env.EXPO_PUBLIC_API_URL ??
  (IP_DISPOSITIVO_FISICO ? `http://${IP_DISPOSITIVO_FISICO}:8000` : `http://${HOST_EMULADOR}:8000`);

// El token se guarda cifrado en el llavero del sistema (SecureStore) para que la sesión
// sobreviva al cierre de la app. En web se usa sessionStorage (dura mientras la pestaña esté abierta).
const CLAVE_TOKEN = 'derma_token';
let tokenActual: string | null = null;

export async function cargarToken(): Promise<string | null> {
  try {
    tokenActual = Platform.OS === 'web' ? window.sessionStorage.getItem(CLAVE_TOKEN) : await SecureStore.getItemAsync(CLAVE_TOKEN);
  } catch {
    tokenActual = null;
  }
  return tokenActual;
}

export async function guardarToken(token: string) {
  tokenActual = token;
  try {
    if (Platform.OS === 'web') window.sessionStorage.setItem(CLAVE_TOKEN, token);
    else await SecureStore.setItemAsync(CLAVE_TOKEN, token);
  } catch {
    /* si el llavero falla, la sesión queda solo en memoria */
  }
}

export function obtenerToken(): string | null {
  return tokenActual;
}

export async function borrarToken() {
  tokenActual = null;
  try {
    if (Platform.OS === 'web') window.sessionStorage.removeItem(CLAVE_TOKEN);
    else await SecureStore.deleteItemAsync(CLAVE_TOKEN);
  } catch {
    /* nada que hacer */
  }
}
