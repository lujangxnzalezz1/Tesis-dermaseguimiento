import { Ionicons } from '@expo/vector-icons';
import { ComponentProps, ReactNode, useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Image,
  LayoutChangeEvent,
  Modal,
  PanResponder,
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
import Svg, { Circle, Line, Polygon, Polyline } from 'react-native-svg';
import { API_URL, obtenerToken } from '../lib/auth';

/** Paleta verde y crema (diseño aprobado en el canvas «DermaSeguimiento — Interfaz»). */
export const COLOR = {
  primario: '#2E6B4F', primarioOscuro: '#1F4A36', fondo: '#F7F2E7', tarjeta: '#FFFDF8', suave: '#E3EEE7', arena: '#EFE6D2',
  dorado: '#C9B280', texto: '#1F3A2F', textoSuave: '#4E5F57', borde: '#DCE5DF',
  error: '#B3261E', ok: '#2E7D32', aviso: '#A3571B',
};
/** Tipografías: Outfit para títulos y cifras, Figtree para el texto (se cargan en app/_layout.tsx). */
export const FUENTE = {
  titulo: 'Outfit_600SemiBold', tituloFuerte: 'Outfit_700Bold', texto: 'Figtree_400Regular', textoMedio: 'Figtree_500Medium', textoFuerte: 'Figtree_600SemiBold',
};
const SOMBRA = { shadowColor: '#2E6B4F', shadowOpacity: 0.08, shadowRadius: 18, shadowOffset: { width: 0, height: 8 }, elevation: 2 };

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
  const color = sec || txt ? COLOR.primario : COLOR.tarjeta;
  return (
    <TouchableOpacity
      accessibilityRole="button"
      accessibilityLabel={texto}
      onPress={onPress}
      disabled={cargando || deshabilitado}
      style={[estilos.boton, { backgroundColor: fondo, borderWidth: sec ? 1.5 : 0, borderColor: '#C8D8CF', opacity: cargando || deshabilitado ? 0.6 : 1 }, txt && { paddingVertical: 8, minHeight: 44 }, estilo]}
    >
      {cargando ? (
        <ActivityIndicator color={color} />
      ) : (
        <View style={estilos.filaBoton}>
          {icono && <Ionicons name={icono} size={20} color={color} />}
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
        placeholderTextColor="#8A968F"
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

export function Tarjeta({ children, color = COLOR.tarjeta, estilo }: { children: ReactNode; color?: string; estilo?: StyleProp<ViewStyle> }) {
  return <View style={[estilos.tarjeta, { backgroundColor: color }, estilo]}>{children}</View>;
}

/** Botón cuadrado solo con ícono: SIEMPRE lleva etiqueta accesible (lectores de pantalla y tooltip en web). */
export function BotonIcono({ icono, etiqueta, onPress, marca }: { icono: IconName; etiqueta: string; onPress: () => void; marca?: boolean }) {
  return (
    <TouchableOpacity accessibilityRole="button" accessibilityLabel={etiqueta} onPress={onPress} {...(Platform.OS === 'web' ? { title: etiqueta } as any : {})}
      style={{ width: 46, height: 46, borderRadius: 16, backgroundColor: COLOR.tarjeta, alignItems: 'center', justifyContent: 'center', marginLeft: 6, ...SOMBRA }}>
      <Ionicons name={icono} size={22} color={COLOR.primario} />
      {marca && <View style={{ position: 'absolute', top: 9, right: 9, width: 9, height: 9, borderRadius: 5, backgroundColor: COLOR.aviso }} />}
    </TouchableOpacity>
  );
}

/** Etiqueta redondeada (estado, filtros, avisos breves). */
export function Pildora({ texto, icono, fondo = COLOR.suave, color = COLOR.primario }: { texto: string; icono?: IconName; fondo?: string; color?: string }) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 5, alignSelf: 'flex-start', backgroundColor: fondo, borderRadius: 999, paddingVertical: 6, paddingHorizontal: 11 }}>
      {icono && <Ionicons name={icono} size={14} color={color} />}
      <Text style={{ color, fontSize: 12, fontFamily: FUENTE.textoFuerte }}>{texto}</Text>
    </View>
  );
}

/** Cuadrado redondeado con las iniciales (avatar del paciente). */
export function Iniciales({ nombre, apellido, tam = 52, claro }: { nombre: string; apellido: string; tam?: number; claro?: boolean }) {
  const txt = `${(nombre || '?')[0] ?? ''}${(apellido || '')[0] ?? ''}`.toUpperCase();
  return (
    <View style={{ width: tam, height: tam, borderRadius: tam * 0.35, backgroundColor: claro ? COLOR.fondo : COLOR.suave, alignItems: 'center', justifyContent: 'center' }}>
      <Text style={{ color: COLOR.primario, fontFamily: FUENTE.titulo, fontSize: tam * 0.36 }}>{txt}</Text>
    </View>
  );
}

export function Aviso({ tipo, texto }: { tipo: 'error' | 'ok' | 'aviso' | 'info'; texto: string }) {
  const c = { error: '#FBE9E7', ok: '#E6F2EA', aviso: '#F8EBDD', info: COLOR.suave }[tipo];
  const i: IconName = { error: 'alert-circle', ok: 'checkmark-circle', aviso: 'warning', info: 'information-circle' }[tipo] as IconName;
  const col = { error: COLOR.error, ok: COLOR.ok, aviso: COLOR.aviso, info: COLOR.primario }[tipo];
  return (
    <View style={[estilos.aviso, { backgroundColor: c }]}>
      <Ionicons name={i} size={20} color={col} />
      <Text style={{ flex: 1, color: COLOR.texto, fontFamily: FUENTE.texto, lineHeight: 20 }}>{texto}</Text>
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
          <Text style={{ marginBottom: 12, color: COLOR.texto, fontFamily: FUENTE.texto, lineHeight: 21 }}>{mensaje}</Text>
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
  scroll: { flexGrow: 1, backgroundColor: COLOR.fondo, alignItems: 'center', overflow: 'hidden' },
  columna: { width: '100%', maxWidth: 640, paddingHorizontal: 20, paddingTop: 16, paddingBottom: 40 },
  boton: { borderRadius: 18, paddingVertical: 14, paddingHorizontal: 18, alignItems: 'center', justifyContent: 'center', minHeight: 52 },
  filaBoton: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  textoBoton: { fontSize: 16, fontFamily: FUENTE.titulo },
  etiqueta: { fontSize: 13, color: '#3B4A43', marginBottom: 6, fontFamily: FUENTE.textoFuerte },
  input: { borderWidth: 1.5, borderColor: COLOR.borde, borderRadius: 16, paddingHorizontal: 16, paddingVertical: 13, fontSize: 16, backgroundColor: COLOR.tarjeta, color: COLOR.texto, fontFamily: FUENTE.texto },
  ayuda: { fontSize: 12, color: COLOR.textoSuave, marginTop: 4, fontFamily: FUENTE.texto },
  error: { fontSize: 13, color: COLOR.error, marginTop: 4, fontFamily: FUENTE.textoMedio },
  tarjeta: { padding: 18, borderRadius: 24, marginVertical: 8, ...SOMBRA },
  aviso: { flexDirection: 'row', gap: 10, padding: 14, borderRadius: 18, marginVertical: 6, alignItems: 'center' },
  titulo: { fontSize: 28, fontFamily: FUENTE.titulo, color: COLOR.texto, marginBottom: 8, letterSpacing: -0.4 },
  subtitulo: { fontSize: 18, fontFamily: FUENTE.titulo, color: COLOR.texto, marginBottom: 8, marginTop: 10 },
  fondoModal: { flex: 1, backgroundColor: '#1F3A2F88', justifyContent: 'center', padding: 20 },
  modal: { backgroundColor: COLOR.tarjeta, borderRadius: 28, padding: 22, width: '100%', maxWidth: 480, alignSelf: 'center' },
  imagen: { width: '100%', height: 240, borderRadius: 20, backgroundColor: COLOR.arena, marginTop: 10 },
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
        <Text style={{ color: COLOR.textoSuave }}>
          Similitud estructural (SSIM): {s.ssim_antes.toFixed(3)} sin alinear → {s.ssim_despues.toFixed(3)} alineada
        </Text>
      )}
      {s.lesiones_nueva == null ? (
        <Text style={{ color: COLOR.textoSuave, marginTop: 6 }}>Esta consulta no tiene análisis de lesiones (se procesó sin el modelo de detección).</Text>
      ) : (
        <>
          <Text style={{ fontSize: 17, fontFamily: FUENTE.textoFuerte, color: COLOR.primario, marginTop: 12, marginBottom: 8 }}>Regiones de lesión (YOLOv8)</Text>
          <Text>Consulta de referencia: {s.lesiones_referencia} · Esta consulta: {s.lesiones_nueva}</Text>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 12, marginTop: 6 }}>
            <Text style={{ color: COLOR.error, fontFamily: FUENTE.textoFuerte }}>■ Nuevas: {s.lesiones_nuevas}</Text>
            <Text style={{ color: COLOR.ok, fontFamily: FUENTE.textoFuerte }}>■ Persisten: {s.lesiones_persistentes}</Text>
            <Text style={{ color: COLOR.aviso, fontFamily: FUENTE.textoFuerte }}>▢ Ya no aparecen: {s.lesiones_resueltas}</Text>
          </View>
          {s.url_imagen_lesiones && <ImagenProtegida url={s.url_imagen_lesiones} />}
          <Text style={{ color: COLOR.textoSuave, fontSize: 12, marginTop: 6 }}>
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
      <Text style={{ fontSize: 17, fontFamily: FUENTE.textoFuerte, color: COLOR.primario, marginBottom: 6 }}>Región periorbital (ojeras)</Text>
      <Text>Contraste: {s.ojeras_contraste_referencia.toFixed(1)} en la referencia → {s.ojeras_contraste_nueva.toFixed(1)} ahora ({tendencia})</Text>
      {s.ojeras_detalle?.nueva && (
        <Text style={{ color: COLOR.textoSuave }}>Ojo derecho: {ojo(s.ojeras_detalle.nueva.derecho)} · Ojo izquierdo: {ojo(s.ojeras_detalle.nueva.izquierdo)}</Text>
      )}
      {s.url_imagen_periorbital && <ImagenProtegida url={s.url_imagen_periorbital} />}
      <Text style={{ color: COLOR.textoSuave, fontSize: 12, marginTop: 6 }}>
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
      <Text style={{ fontSize: 17, fontFamily: FUENTE.textoFuerte, color: COLOR.primario, marginBottom: 6 }}>Manchas</Text>
      <Text>Superficie con manchas: {pct(s.manchas_pct_referencia)} en la referencia → {pct(s.manchas_pct_nueva)} ahora ({tendencia})</Text>
      {ref && act && (
        <Text style={{ color: COLOR.textoSuave }}>Zonas: {ref.cantidad} → {act.cantidad} · Contraste promedio: {ref.contraste_medio} % → {act.contraste_medio} %</Text>
      )}
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 12, marginTop: 6 }}>
        <Text style={{ color: '#28a8e6', fontFamily: FUENTE.textoFuerte }}>▢ Referencia</Text>
        <Text style={{ color: '#ff8c00', fontFamily: FUENTE.textoFuerte }}>▢ Esta consulta</Text>
        <Text style={{ color: COLOR.textoSuave, fontFamily: FUENTE.textoFuerte }}>▢ Piel analizada</Text>
      </View>
      {s.url_imagen_manchas && <ImagenProtegida url={s.url_imagen_manchas} />}
      <Text style={{ color: COLOR.textoSuave, fontSize: 12, marginTop: 6 }}>
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
    <View style={{ backgroundColor: COLOR.primario, borderRadius: 26, padding: 18, marginTop: 8 }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <Ionicons name="sparkles-outline" size={20} color={COLOR.dorado} />
        <Text style={{ fontSize: 17, fontFamily: FUENTE.titulo, color: COLOR.tarjeta }}>Qué cambió</Text>
      </View>
      {i.resumen.map((f: string) => <Text key={f} style={{ marginBottom: 6, lineHeight: 21, fontSize: 14, fontFamily: FUENTE.texto, color: '#E8F1EC' }}>• {f}</Text>)}
      {i.advertencias.map((a: string) => <Aviso key={a} tipo="aviso" texto={a} />)}
      <Text style={{ color: '#C9DCD1', fontSize: 12, marginTop: 4, fontFamily: FUENTE.texto, lineHeight: 17 }}>{i.aclaracion}</Text>
    </View>
  );
}

/** Comparador antes/después: la referencia queda encima, recortada; se arrastra (o se toca) para mover el corte. */
export function ComparadorAntesDespues({ urlReferencia, urlActual, alto = 340 }: { urlReferencia: string; urlActual: string; alto?: number }) {
  const [ancho, setAncho] = useState(0);
  const [pos, setPos] = useState(0.5);
  const anchoRef = useRef(0);
  const mover = (x: number) => { if (anchoRef.current) setPos(Math.min(1, Math.max(0, x / anchoRef.current))); };
  const responder = useMemo(() => PanResponder.create({
    onStartShouldSetPanResponder: () => true,
    onMoveShouldSetPanResponder: () => true,
    onPanResponderGrant: (e) => mover(e.nativeEvent.locationX),
    onPanResponderMove: (e) => mover(e.nativeEvent.locationX),
    onPanResponderTerminationRequest: () => false,
  }), []);
  const alMedir = (e: LayoutChangeEvent) => { anchoRef.current = e.nativeEvent.layout.width; setAncho(e.nativeEvent.layout.width); };
  const img = { width: ancho || 1, height: alto, marginTop: 0, borderRadius: 0, backgroundColor: COLOR.arena };
  return (
    <View style={{ backgroundColor: COLOR.tarjeta, borderRadius: 28, padding: 10, marginTop: 8, ...SOMBRA }}>
      <View onLayout={alMedir} {...responder.panHandlers} accessibilityLabel="Comparador antes y después: arrastrá para mover el corte"
        style={{ height: alto, borderRadius: 20, overflow: 'hidden', backgroundColor: COLOR.arena }}>
        <View pointerEvents="none" style={{ position: 'absolute', inset: 0 } as any}><ImagenProtegida url={urlActual} estilo={img} /></View>
        <View pointerEvents="none" style={{ position: 'absolute', top: 0, bottom: 0, left: 0, width: ancho * pos, overflow: 'hidden' }}>
          <ImagenProtegida url={urlReferencia} estilo={img} />
        </View>
        <View pointerEvents="none" style={{ position: 'absolute', top: 0, bottom: 0, left: ancho * pos - 1.5, width: 3, backgroundColor: COLOR.tarjeta }} />
        <View pointerEvents="none" style={{ position: 'absolute', top: alto / 2 - 20, left: ancho * pos - 20, width: 40, height: 40, borderRadius: 20, backgroundColor: COLOR.tarjeta, alignItems: 'center', justifyContent: 'center', ...SOMBRA }}>
          <Ionicons name="swap-horizontal" size={20} color={COLOR.primario} />
        </View>
        <View pointerEvents="none" style={{ position: 'absolute', left: 10, top: 10 }}><Pildora texto="Referencia" fondo="#FFFDF8E6" /></View>
        <View pointerEvents="none" style={{ position: 'absolute', right: 10, top: 10 }}><Pildora texto="Hoy · alineada" fondo={COLOR.primario} color={COLOR.tarjeta} /></View>
      </View>
      <Text style={{ fontFamily: FUENTE.texto, fontSize: 12, color: COLOR.textoSuave, textAlign: 'center', marginTop: 8 }}>Deslizá sobre la foto para comparar</Text>
    </View>
  );
}

function Anillo({ valor, fraccion }: { valor: string; fraccion: number }) {
  const r = 26, c = 2 * Math.PI * r, f = Math.max(0.04, Math.min(1, fraccion));
  return (
    <View style={{ width: 64, height: 64, alignItems: 'center', justifyContent: 'center' }}>
      <Svg width={64} height={64} viewBox="0 0 64 64" style={{ position: 'absolute' }}>
        <Circle cx={32} cy={32} r={r} fill="none" stroke={COLOR.suave} strokeWidth={7} />
        <Circle cx={32} cy={32} r={r} fill="none" stroke={COLOR.primario} strokeWidth={7} strokeLinecap="round"
          strokeDasharray={`${c * f} ${c}`} transform="rotate(-90 32 32)" />
      </Svg>
      <Text style={{ fontFamily: FUENTE.titulo, fontSize: 14, color: COLOR.texto }}>{valor}</Text>
    </View>
  );
}

const num = (v: number, d = 1) => v.toFixed(d).replace('.', ',');

/** Indicadores en tarjetas con anillo. El anillo solo ilustra la magnitud; el número es el dato. */
export function Indicadores({ s }: { s: any }) {
  const items: { nombre: string; valor: string; fraccion: number; detalle: string }[] = [
    { nombre: 'Color', valor: num(s.delta_e_promedio), fraccion: s.delta_e_promedio / 10, detalle: `Delta E · cambio ${s.interpretacion?.magnitud_color ?? ''}` },
  ];
  if (s.manchas_pct_nueva != null) items.push({ nombre: 'Manchas', valor: `${num(s.manchas_pct_nueva)} %`, fraccion: s.manchas_pct_nueva / 5, detalle: `Antes ${num(s.manchas_pct_referencia, 2)} % de la piel` });
  if (s.ojeras_contraste_nueva != null) items.push({ nombre: 'Ojeras', valor: num(s.ojeras_contraste_nueva), fraccion: s.ojeras_contraste_nueva / 30, detalle: `Antes ${num(s.ojeras_contraste_referencia)} (contraste)` });
  if (s.lesiones_nueva != null) items.push({ nombre: 'Lesiones', valor: String(s.lesiones_nueva), fraccion: s.lesiones_nueva / 10, detalle: `${s.lesiones_nuevas} nuevas · ${s.lesiones_resueltas} ya no aparecen` });
  return (
    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 12, marginTop: 12 }}>
      {items.map((it) => (
        <View key={it.nombre} style={{ flexGrow: 1, flexBasis: '45%', backgroundColor: COLOR.tarjeta, borderRadius: 24, padding: 16, gap: 8, ...SOMBRA }}>
          <Anillo valor={it.valor} fraccion={it.fraccion} />
          <Text style={{ fontFamily: FUENTE.textoFuerte, fontSize: 15, color: COLOR.texto }}>{it.nombre}</Text>
          <Text style={{ fontFamily: FUENTE.texto, fontSize: 12, color: COLOR.textoSuave, lineHeight: 17 }}>{it.detalle}</Text>
        </View>
      ))}
    </View>
  );
}

type Serie = { clave: string; nombre: string; titulo: string; valor: (s: any) => number | null; fmt: (v: number) => string };
const SERIES: Serie[] = [
  { clave: 'manchas', nombre: 'Manchas', titulo: 'Superficie con manchas', valor: (s) => s.manchas_pct_nueva, fmt: (v) => `${num(v, 2)} %` },
  { clave: 'color', nombre: 'Color', titulo: 'Cambio de color (Delta E)', valor: (s) => s.delta_e_promedio, fmt: (v) => num(v) },
  { clave: 'ojeras', nombre: 'Ojeras', titulo: 'Contraste de ojeras', valor: (s) => s.ojeras_contraste_nueva, fmt: (v) => num(v) },
  { clave: 'lesiones', nombre: 'Lesiones', titulo: 'Regiones con aspecto de lesión', valor: (s) => s.lesiones_nueva, fmt: (v) => String(v) },
];

/** Evolución de un indicador a lo largo de las consultas (`seguimientos` del más reciente al más antiguo, como los da la API). */
export function GraficoEvolucion({ seguimientos }: { seguimientos: any[] }) {
  const [sel, setSel] = useState('manchas');
  const [ancho, setAncho] = useState(0);
  const orden = [...seguimientos].reverse();
  const disponibles = SERIES.filter((x) => orden.some((s) => x.valor(s) != null));
  const serie = disponibles.find((x) => x.clave === sel) ?? disponibles[0];
  if (!serie || orden.length === 0) return null;
  const datos = orden.map((s) => ({ v: serie.valor(s), fecha: new Date(s.fecha) })).filter((d) => d.v != null) as { v: number; fecha: Date }[];
  const alto = 150, margen = 14;
  const max = Math.max(...datos.map((d) => d.v), 0.0001);
  const pts = datos.map((d, i) => ({
    x: datos.length === 1 ? ancho / 2 : margen + (i * (ancho - 2 * margen)) / (datos.length - 1),
    y: alto - 12 - (d.v / max) * (alto - 36),
  }));
  const linea = pts.map((p) => `${p.x},${p.y}`).join(' ');
  const corta = (f: Date) => f.toLocaleDateString('es-PY', { day: 'numeric', month: 'short' });
  return (
    <View style={{ marginTop: 12 }}>
      <View accessibilityRole="tablist" style={{ flexDirection: 'row', gap: 6, backgroundColor: COLOR.tarjeta, borderRadius: 18, padding: 5 }}>
        {disponibles.map((x) => {
          const activa = x.clave === serie.clave;
          return (
            <TouchableOpacity key={x.clave} accessibilityRole="tab" accessibilityState={{ selected: activa }} onPress={() => setSel(x.clave)}
              style={{ flex: 1, minHeight: 40, borderRadius: 14, alignItems: 'center', justifyContent: 'center', backgroundColor: activa ? COLOR.primario : 'transparent' }}>
              <Text style={{ fontFamily: FUENTE.textoFuerte, fontSize: 13, color: activa ? COLOR.tarjeta : COLOR.primario }}>{x.nombre}</Text>
            </TouchableOpacity>
          );
        })}
      </View>
      <View style={{ backgroundColor: COLOR.tarjeta, borderRadius: 26, padding: 18, marginTop: 10, ...SOMBRA }}>
        <Text style={{ fontFamily: FUENTE.texto, fontSize: 13, color: COLOR.textoSuave }}>{serie.titulo}</Text>
        <Text style={{ fontFamily: FUENTE.titulo, fontSize: 30, color: COLOR.texto, letterSpacing: -0.5 }}>{serie.fmt(datos[datos.length - 1].v)}</Text>
        <View onLayout={(e) => setAncho(e.nativeEvent.layout.width)} style={{ height: alto, marginTop: 8 }}
          accessibilityLabel={`${serie.titulo}: ${datos.map((d) => `${corta(d.fecha)} ${serie.fmt(d.v)}`).join(', ')}`}>
          {ancho > 0 && (
            <Svg width={ancho} height={alto}>
              {[0.25, 0.5, 0.75].map((f) => <Line key={f} x1={0} x2={ancho} y1={alto * f} y2={alto * f} stroke="#EDE7D9" strokeWidth={1} />)}
              {pts.length > 1 && <Polygon points={`${pts[0].x},${alto - 12} ${linea} ${pts[pts.length - 1].x},${alto - 12}`} fill={COLOR.suave} />}
              {pts.length > 1 && <Polyline points={linea} fill="none" stroke={COLOR.primario} strokeWidth={3} strokeLinecap="round" strokeLinejoin="round" />}
              {pts.map((p, i) => <Circle key={i} cx={p.x} cy={p.y} r={6} fill={COLOR.tarjeta} stroke={COLOR.primario} strokeWidth={3} />)}
            </Svg>
          )}
        </View>
        <View style={{ flexDirection: 'row', justifyContent: datos.length === 1 ? 'center' : 'space-between', marginTop: 4 }}>
          {datos.map((d, i) => <Text key={i} style={{ fontFamily: FUENTE.texto, fontSize: 12, color: COLOR.textoSuave }}>{corta(d.fecha)}</Text>)}
        </View>
      </View>
    </View>
  );
}
