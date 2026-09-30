// Foto tomada con la cámara guiada, pendiente de que la recoja la pantalla de seguimiento.
// Queda asociada al paciente: nunca se entrega a la pantalla de otro paciente.
export type FotoCapturada = { uri: string; nombre: string; tipo: string };
let pendiente: { pacienteId: string; destino: 'referencia' | 'nueva'; foto: FotoCapturada } | null = null;

export function dejarFoto(pacienteId: string, destino: 'referencia' | 'nueva', foto: FotoCapturada) {
  pendiente = { pacienteId, destino, foto };
}

export function tomarFotoPendiente(pacienteId: string) {
  const p = pendiente;
  pendiente = null;
  return p && p.pacienteId === pacienteId ? p : null;
}
