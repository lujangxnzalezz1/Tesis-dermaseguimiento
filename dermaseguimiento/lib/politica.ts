import { useEffect, useState } from 'react';
import { api } from './api';

type Politica = {
  longitud_minima: number; requiere_mayuscula: boolean; requiere_minuscula: boolean;
  requiere_numero: boolean; requiere_especial: boolean;
};
const POR_DEFECTO: Politica = { longitud_minima: 10, requiere_mayuscula: true, requiere_minuscula: true, requiere_numero: true, requiere_especial: true };

/** Reglas de contraseña que el servidor tiene configuradas (el servidor siempre las vuelve a verificar). */
export function usePoliticaPassword(password: string) {
  const [pol, setPol] = useState<Politica>(POR_DEFECTO);
  useEffect(() => {
    api('/politica-contrasenas', { auth: false }).then((r) => r.ok && setPol(r.data));
  }, []);
  const reglas = [
    { texto: `Al menos ${pol.longitud_minima} caracteres`, cumple: password.length >= pol.longitud_minima },
    ...(pol.requiere_mayuscula ? [{ texto: 'Una letra mayúscula', cumple: /[A-ZÁÉÍÓÚÑ]/.test(password) }] : []),
    ...(pol.requiere_minuscula ? [{ texto: 'Una letra minúscula', cumple: /[a-záéíóúñ]/.test(password) }] : []),
    ...(pol.requiere_numero ? [{ texto: 'Un número', cumple: /\d/.test(password) }] : []),
    ...(pol.requiere_especial ? [{ texto: 'Un carácter especial (! ? # $ %)', cumple: /[^A-Za-z0-9\sáéíóúñÁÉÍÓÚÑ]/.test(password) }] : []),
  ];
  return { reglas, cumple: reglas.every((r) => r.cumple) };
}

export const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
