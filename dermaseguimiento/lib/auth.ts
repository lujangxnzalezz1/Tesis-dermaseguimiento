import { Platform } from 'react-native';

// Guarda el token de sesión mientras la app está abierta.
// Es una solución simple para empezar: si cerrás la app, se pierde
// y hay que loguearse de nuevo. Más adelante lo hacemos persistente
// con AsyncStorage o SecureStore.

// Para probar en un dispositivo físico por WiFi, poné la IP local
// de la Mac (ej: 'http://192.168.100.72:8000'). Para simulador/emulador
// en la misma Mac (sin red/internet), dejá null: cada plataforma resuelve
// su propia forma de llegar a "localhost" del host.
const IP_DISPOSITIVO_FISICO: string | null = null;

const HOST_EMULADOR = Platform.select({
  ios: 'localhost', // el simulador de iOS comparte la red del Mac
  android: '10.0.2.2', // alias que usa el emulador de Android para el host
  default: 'localhost',
});

export const API_URL = IP_DISPOSITIVO_FISICO
  ? `http://${IP_DISPOSITIVO_FISICO}:8000`
  : `http://${HOST_EMULADOR}:8000`;

let tokenActual: string | null = null;

export function guardarToken(token: string) {
  tokenActual = token;
}

export function obtenerToken(): string | null {
  return tokenActual;
}

export function cerrarSesion() {
  tokenActual = null;
}
