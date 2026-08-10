// Guarda el token de sesión mientras la app está abierta.
// Es una solución simple para empezar: si cerrás la app, se pierde
// y hay que loguearse de nuevo. Más adelante lo hacemos persistente
// con AsyncStorage o SecureStore.

export const API_URL = 'http://192.168.100.72:8000';

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
