// Foto tomada con la cámara guiada, pendiente de que la recoja la pantalla de seguimiento.
export type FotoCapturada = { uri: string; nombre: string; tipo: string };
let pendiente: { destino: 'referencia' | 'nueva'; foto: FotoCapturada } | null = null;

export function dejarFoto(destino: 'referencia' | 'nueva', foto: FotoCapturada) {
  pendiente = { destino, foto };
}

export function tomarFotoPendiente() {
  const p = pendiente;
  pendiente = null;
  return p;
}
