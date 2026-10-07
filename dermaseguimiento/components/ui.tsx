import { Ionicons } from '@expo/vector-icons';
import { ComponentProps, ReactNode, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Image,
  Modal,
  Platform,
  ScrollView,
  StyleProp,
  StyleSheet,
  Text,
  TextInput,
  TextInputProps,
  TouchableOpacity,
  View,
  ViewStyle,
} from 'react-native';
import { API_URL, obtenerToken } from '../lib/auth';

export const COLOR = { primario: '#1D3D47', fondo: '#fff', suave: '#E6F4FE', error: '#B3261E', ok: '#2E7D32', aviso: '#B26A00' };

type IconName = ComponentProps<typeof Ionicons>['name'];

/** Contenedor con desplazamiento y ancho máximo: se ve bien en celular, tableta y web (diseño adaptable). */
export function Pantalla({ children }: { children: ReactNode }) {
  return (
    <ScrollView contentContainerStyle={estilos.scroll} keyboardShouldPersistTaps="handled">
      <View style={estilos.columna}>{children}</View>
    </ScrollView>
  );
}

/** Botón SIEMPRE con texto; el ícono es un apoyo visual (nunca reemplaza la descripción). */
export function Boton({
  texto, onPress, icono, variante = 'primario', cargando, deshabilitado, estilo,
}: {
  texto: string; onPress: () => void; icono?: IconName; variante?: 'primario' | 'secundario' | 'peligro' | 'texto';
  cargando?: boolean; deshabilitado?: boolean; estilo?: StyleProp<ViewStyle>;
}) {
  const sec = variante === 'secundario';
  const txt = variante === 'texto';
  const fondo = variante === 'peligro' ? COLOR.error : sec || txt ? 'transparent' : COLOR.primario;
  const color = sec || txt ? (variante === 'texto' ? COLOR.primario : COLOR.primario) : '#fff';
  return (
    <TouchableOpacity
      accessibilityRole="button"
      accessibilityLabel={texto}
      onPress={onPress}
      disabled={cargando || deshabilitado}
      style={[estilos.boton, { backgroundColor: fondo, borderWidth: sec ? 1 : 0, borderColor: COLOR.primario, opacity: cargando || deshabilitado ? 0.6 : 1 }, txt && { paddingVertical: 8 }, estilo]}
    >
      {cargando ? (
        <ActivityIndicator color={color} />
      ) : (
        <View style={estilos.filaBoton}>
          {icono && <Ionicons name={icono} size={18} color={color} />}
          <Text style={[estilos.textoBoton, { color }]}>{texto}</Text>
        </View>
      )}
    </TouchableOpacity>
  );
}

export function Campo({ etiqueta, error, ayuda, ...props }: TextInputProps & { etiqueta: string; error?: string | null; ayuda?: string }) {
  return (
    <View style={{ marginBottom: 12 }}>
      <Text style={estilos.etiqueta}>{etiqueta}</Text>
      <TextInput
        placeholderTextColor="#999"
        accessibilityLabel={etiqueta}
        {...props}
        style={[estilos.input, error ? { borderColor: COLOR.error } : null, props.multiline ? { minHeight: 80, textAlignVertical: 'top' } : null]}
      />
      {ayuda && !error ? <Text style={estilos.ayuda}>{ayuda}</Text> : null}
      {error ? <Text style={estilos.error}>{error}</Text> : null}
    </View>
  );
}

export function Casilla({ marcada, onCambio, children }: { marcada: boolean; onCambio: (v: boolean) => void; children: ReactNode }) {
  return (
    <TouchableOpacity
      accessibilityRole="checkbox"
      accessibilityState={{ checked: marcada }}
      onPress={() => onCambio(!marcada)}
      style={{ flexDirection: 'row', gap: 10, alignItems: 'flex-start', marginVertical: 8 }}
    >
      <Ionicons name={marcada ? 'checkbox' : 'square-outline'} size={26} color={COLOR.primario} />
      <View style={{ flex: 1 }}>{children}</View>
    </TouchableOpacity>
  );
}

export function Tarjeta({ children, color = COLOR.suave }: { children: ReactNode; color?: string }) {
  return <View style={[estilos.tarjeta, { backgroundColor: color }]}>{children}</View>;
}

export function Aviso({ tipo, texto }: { tipo: 'error' | 'ok' | 'aviso' | 'info'; texto: string }) {
  const c = { error: '#FDECEA', ok: '#E8F5E9', aviso: '#FFF4E0', info: COLOR.suave }[tipo];
  const i: IconName = { error: 'alert-circle', ok: 'checkmark-circle', aviso: 'warning', info: 'information-circle' }[tipo] as IconName;
  const col = { error: COLOR.error, ok: COLOR.ok, aviso: COLOR.aviso, info: COLOR.primario }[tipo];
  return (
    <View style={[estilos.aviso, { backgroundColor: c }]}>
      <Ionicons name={i} size={20} color={col} />
      <Text style={{ flex: 1, color: '#222' }}>{texto}</Text>
    </View>
  );
}

export const Titulo = ({ children }: { children: ReactNode }) => <Text style={estilos.titulo}>{children}</Text>;
export const Subtitulo = ({ children }: { children: ReactNode }) => <Text style={estilos.subtitulo}>{children}</Text>;

/** Confirmación para acciones críticas, con motivo opcional u obligatorio (punto 29). */
export function Confirmar({
  visible, titulo, mensaje, pedirMotivo, motivoObligatorio, textoConfirmar = 'Confirmar', peligro, onConfirmar, onCancelar,
}: {
  visible: boolean; titulo: string; mensaje: string; pedirMotivo?: boolean; motivoObligatorio?: boolean; textoConfirmar?: string;
  peligro?: boolean; onConfirmar: (motivo: string) => void; onCancelar: () => void;
}) {
  const [motivo, setMotivo] = useState('');
  const invalido = !!motivoObligatorio && motivo.trim().length < 5;
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onCancelar}>
      <View style={estilos.fondoModal}>
        <View style={estilos.modal}>
          <Text style={estilos.subtitulo}>{titulo}</Text>
          <Text style={{ marginBottom: 12, color: '#333' }}>{mensaje}</Text>
          {pedirMotivo && (
            <Campo etiqueta={motivoObligatorio ? 'Motivo (obligatorio, mínimo 5 letras)' : 'Motivo (opcional)'} value={motivo} onChangeText={setMotivo} maxLength={300} />
          )}
          <Boton texto={textoConfirmar} variante={peligro ? 'peligro' : 'primario'} icono="checkmark" deshabilitado={invalido} onPress={() => { const m = motivo; setMotivo(''); onConfirmar(m.trim()); }} />
          <Boton texto="Cancelar" variante="secundario" icono="close" estilo={{ marginTop: 8 }} onPress={() => { setMotivo(''); onCancelar(); }} />
        </View>
      </View>
    </Modal>
  );
}

/** Imagen clínica: el servidor la entrega solo con el token de sesión (no son públicas).
 *  En web <img> no puede enviar cabeceras, así que se descarga con fetch y se muestra como blob. */
export function ImagenProtegida({ url, estilo }: { url: string; estilo?: StyleProp<any> }) {
  const token = obtenerToken();
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  useEffect(() => {
    if (Platform.OS !== 'web') return;
    let creado: string | null = null;
    fetch(`${API_URL}${url}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      .then((r) => (r.ok ? r.blob() : null))
      .then((b) => { if (b) { creado = URL.createObjectURL(b); setBlobUrl(creado); } })
      .catch(() => null);
    return () => { if (creado) URL.revokeObjectURL(creado); };
  }, [url, token]);
  const source = Platform.OS === 'web'
    ? (blobUrl ? { uri: blobUrl } : undefined)
    : { uri: `${API_URL}${url}`, headers: token ? { Authorization: `Bearer ${token}` } : undefined };
  return <Image source={source} style={[estilos.imagen, estilo]} resizeMode="contain" />;
}

const estilos = StyleSheet.create({
  scroll: { flexGrow: 1, backgroundColor: COLOR.fondo, alignItems: 'center' },
  columna: { width: '100%', maxWidth: 640, padding: 20 },
  boton: { borderRadius: 8, paddingVertical: 14, paddingHorizontal: 16, alignItems: 'center', justifyContent: 'center', minHeight: 48 },
  filaBoton: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  textoBoton: { fontSize: 16, fontWeight: '600' },
  etiqueta: { fontSize: 14, color: '#444', marginBottom: 6 },
  input: { borderWidth: 1, borderColor: '#ccc', borderRadius: 8, paddingHorizontal: 14, paddingVertical: 12, fontSize: 16, backgroundColor: '#fff' },
  ayuda: { fontSize: 12, color: '#666', marginTop: 4 },
  error: { fontSize: 13, color: COLOR.error, marginTop: 4 },
  tarjeta: { padding: 16, borderRadius: 8, marginVertical: 8 },
  aviso: { flexDirection: 'row', gap: 10, padding: 12, borderRadius: 8, marginVertical: 6, alignItems: 'center' },
  titulo: { fontSize: 24, fontWeight: 'bold', color: COLOR.primario, marginBottom: 8 },
  subtitulo: { fontSize: 17, fontWeight: '600', color: COLOR.primario, marginBottom: 8, marginTop: 8 },
  fondoModal: { flex: 1, backgroundColor: '#0008', justifyContent: 'center', padding: 20 },
  modal: { backgroundColor: '#fff', borderRadius: 12, padding: 20, width: '100%', maxWidth: 480, alignSelf: 'center' },
  imagen: { width: '100%', height: 220, borderRadius: 8, backgroundColor: '#eee', marginTop: 10 },
});

export function ReglasPassword({ reglas }: { reglas: { texto: string; cumple: boolean }[] }) {
  return (
    <View style={{ marginBottom: 12 }}>
      {reglas.map((r) => (
        <View key={r.texto} style={{ flexDirection: 'row', gap: 6, alignItems: 'center' }}>
          <Ionicons name={r.cumple ? 'checkmark-circle' : 'ellipse-outline'} size={16} color={r.cumple ? COLOR.ok : '#888'} />
          <Text style={{ fontSize: 13, color: r.cumple ? COLOR.ok : '#666' }}>{r.texto}</Text>
        </View>
      ))}
    </View>
  );
}

/** Resultado de la detección de lesiones (RF-14/15) y de la similitud antes/después de alinear (RF-13). */
export function ResumenLesiones({ s }: { s: any }) {
  return (
    <View style={{ marginTop: 12 }}>
      {s.ssim_antes != null && s.ssim_despues != null && (
        <Text style={{ color: '#444' }}>
          Similitud estructural (SSIM): {s.ssim_antes.toFixed(3)} sin alinear → {s.ssim_despues.toFixed(3)} alineada
        </Text>
      )}
      {s.lesiones_nueva == null ? (
        <Text style={{ color: '#666', marginTop: 6 }}>Esta consulta no tiene análisis de lesiones (se procesó sin el modelo de detección).</Text>
      ) : (
        <>
          <Text style={{ fontSize: 17, fontWeight: '600', color: COLOR.primario, marginTop: 12, marginBottom: 8 }}>Regiones de lesión (YOLOv8)</Text>
          <Text>Consulta de referencia: {s.lesiones_referencia} · Esta consulta: {s.lesiones_nueva}</Text>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 12, marginTop: 6 }}>
            <Text style={{ color: COLOR.error, fontWeight: '600' }}>■ Nuevas: {s.lesiones_nuevas}</Text>
            <Text style={{ color: COLOR.ok, fontWeight: '600' }}>■ Persisten: {s.lesiones_persistentes}</Text>
            <Text style={{ color: COLOR.aviso, fontWeight: '600' }}>▢ Ya no aparecen: {s.lesiones_resueltas}</Text>
          </View>
          {s.url_imagen_lesiones && <ImagenProtegida url={s.url_imagen_lesiones} />}
          <Text style={{ color: '#666', fontSize: 12, marginTop: 6 }}>
            El modelo marca regiones con aspecto de lesión; no clasifica ni diagnostica. La interpretación es del profesional.
          </Text>
        </>
      )}
    </View>
  );
}

/** RF-16: ojeras. Contraste = cuánto más oscura es la zona bajo el ojo que la mejilla (mayor = más marcada). */
export function ResumenOjeras({ s }: { s: any }) {
  if (s.ojeras_contraste_nueva == null) return null;
  const dif = s.ojeras_contraste_nueva - s.ojeras_contraste_referencia;
  const tendencia = Math.abs(dif) < 1.5 ? 'sin cambios relevantes' : dif > 0 ? 'más marcadas que en la referencia' : 'más atenuadas que en la referencia';
  const ojo = (d: any) => (d ? `${d.contraste_L.toFixed(1)}` : '—');
  return (
    <View style={{ marginTop: 12 }}>
      <Text style={{ fontSize: 17, fontWeight: '600', color: COLOR.primario, marginBottom: 6 }}>Región periorbital (ojeras)</Text>
      <Text>Contraste: {s.ojeras_contraste_referencia.toFixed(1)} en la referencia → {s.ojeras_contraste_nueva.toFixed(1)} ahora ({tendencia})</Text>
      {s.ojeras_detalle?.nueva && (
        <Text style={{ color: '#444' }}>Ojo derecho: {ojo(s.ojeras_detalle.nueva.derecho)} · Ojo izquierdo: {ojo(s.ojeras_detalle.nueva.izquierdo)}</Text>
      )}
      {s.url_imagen_periorbital && <ImagenProtegida url={s.url_imagen_periorbital} />}
      <Text style={{ color: '#666', fontSize: 12, marginTop: 6 }}>
        Contraste = diferencia de luminosidad (L*) entre la mejilla y la zona bajo el ojo. Al compararse dentro de la misma foto,
        es menos sensible a los cambios de iluminación.
      </Text>
    </View>
  );
}

/** Descarga el informe en PDF para entregar al paciente (fotos comparadas, resumen en palabras e índices). */
export function BotonInforme({ seguimientoId }: { seguimientoId: number }) {
  const [estado, setEstado] = useState<{ cargando?: boolean; error?: string }>({});
  const descargar = async () => {
    if (Platform.OS !== 'web') return setEstado({ error: 'El informe en PDF se descarga desde la versión web de la app.' });
    setEstado({ cargando: true });
    try {
      const r = await fetch(`${API_URL}/seguimientos/${seguimientoId}/informe.pdf`, { headers: { Authorization: `Bearer ${obtenerToken()}` } });
      if (!r.ok) return setEstado({ error: r.status === 402 ? 'El informe en PDF es parte del plan Premium.' : 'No pudimos generar el informe. Intentá de nuevo.' });
      const nombre = /filename="([^"]+)"/.exec(r.headers.get('content-disposition') || '')?.[1] || 'informe.pdf';
      const url = URL.createObjectURL(await r.blob());
      const a = document.createElement('a');
      a.href = url; a.download = nombre; a.click();
      setTimeout(() => URL.revokeObjectURL(url), 5000);
      setEstado({});
    } catch {
      setEstado({ error: 'No pudimos conectarnos con el servidor para generar el informe.' });
    }
  };
  return (
    <View style={{ marginTop: 8 }}>
      <Boton texto="Descargar informe para el paciente (PDF)" icono="document-text-outline" variante="secundario" cargando={estado.cargando} onPress={descargar} />
      {estado.error && <Text style={{ color: COLOR.error, marginTop: 4 }}>{estado.error}</Text>}
    </View>
  );
}

/** Manchas: % de la piel analizada que es claramente más oscura que la piel de alrededor (misma superficie en ambas fotos). */
export function ResumenManchas({ s }: { s: any }) {
  if (s.manchas_pct_nueva == null) return null;
  const dif = s.manchas_pct_nueva - s.manchas_pct_referencia;
  const tendencia = Math.abs(dif) < 0.5 ? 'sin cambios relevantes' : dif > 0 ? 'más superficie que en la referencia' : 'menos superficie que en la referencia';
  const pct = (v: number) => `${v.toFixed(2).replace('.', ',')} %`;
  const ref = s.manchas_detalle?.referencia, act = s.manchas_detalle?.nueva;
  return (
    <View style={{ marginTop: 12 }}>
      <Text style={{ fontSize: 17, fontWeight: '600', color: COLOR.primario, marginBottom: 6 }}>Manchas</Text>
      <Text>Superficie con manchas: {pct(s.manchas_pct_referencia)} en la referencia → {pct(s.manchas_pct_nueva)} ahora ({tendencia})</Text>
      {ref && act && (
        <Text style={{ color: '#444' }}>Zonas: {ref.cantidad} → {act.cantidad} · Contraste promedio: {ref.contraste_medio} % → {act.contraste_medio} %</Text>
      )}
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 12, marginTop: 6 }}>
        <Text style={{ color: '#28a8e6', fontWeight: '600' }}>▢ Referencia</Text>
        <Text style={{ color: '#ff8c00', fontWeight: '600' }}>▢ Esta consulta</Text>
        <Text style={{ color: '#888', fontWeight: '600' }}>▢ Piel analizada</Text>
      </View>
      {s.url_imagen_manchas && <ImagenProtegida url={s.url_imagen_manchas} />}
      <Text style={{ color: '#666', fontSize: 12, marginTop: 6 }}>
        Índice para comparar consultas, no diagnóstico: marca zonas al menos un 10 % más oscuras que la piel de alrededor. No analiza ojos,
        ojeras, nariz, labios ni el borde del rostro, y descarta surcos y pliegues. Una sombra fuerte o el maquillaje pueden afectar el resultado.
      </Text>
    </View>
  );
}

/** Resumen en lenguaje natural (lo primero que lee el dermatólogo). Los números quedan como detalle técnico. */
export function Interpretacion({ s }: { s: any }) {
  const i = s.interpretacion;
  if (!i) return null;
  return (
    <View style={{ backgroundColor: '#fff', borderRadius: 8, padding: 12, marginTop: 8, borderLeftWidth: 4, borderLeftColor: COLOR.primario }}>
      <Text style={{ fontSize: 16, fontWeight: '700', color: COLOR.primario, marginBottom: 6 }}>Qué cambió</Text>
      {i.resumen.map((f: string) => <Text key={f} style={{ marginBottom: 4, lineHeight: 20 }}>• {f}</Text>)}
      {i.advertencias.map((a: string) => <Aviso key={a} tipo="aviso" texto={a} />)}
      <Text style={{ color: '#666', fontSize: 12, marginTop: 4 }}>{i.aclaracion}</Text>
    </View>
  );
}
