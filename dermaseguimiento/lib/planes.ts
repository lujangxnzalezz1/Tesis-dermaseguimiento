import { formatoMonto } from './api';

export type Plan = {
  codigo: string; nombre: string; precio: string; moneda: string; periodicidad: 'gratuito' | 'mensual' | 'anual' | string;
  duracion_dias: number; funcionalidades: string[]; limites: string[]; condiciones: string; incluye_procesamiento: boolean;
  activo?: boolean;
};

export const PERIODICIDAD: Record<string, string> = { gratuito: 'Sin vencimiento', mensual: 'Mensual (30 días)', anual: 'Anual (365 días)' };

/** «Gratis» o «Gs. 149.000 / mes (IVA incluido)». */
export function precioPlan(p: Plan): string {
  if (p.periodicidad === 'gratuito') return 'Gratis';
  return `${formatoMonto(p.precio, p.moneda)} / ${p.periodicidad === 'mensual' ? 'mes' : p.periodicidad === 'anual' ? 'año' : p.periodicidad} (IVA incluido)`;
}

export const EVENTO_HISTORIAL: Record<string, string> = {
  alta: 'Alta', renovacion: 'Renovación', cambio_plan: 'Cambio de plan', cancelacion: 'Cancelación', vencimiento: 'Vencimiento',
  baja_programada: 'Baja de plan programada',
};

export const ESTADO_PAGO: Record<string, string> = {
  pendiente: 'pendiente', aprobado: 'aprobado', rechazado: 'rechazado', cancelado: 'cancelado', vencido: 'vencido (no se pagó a tiempo)',
};
