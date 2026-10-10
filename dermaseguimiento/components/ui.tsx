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
export const SOMBRA = { shadowColor: '#2E6B4F', shadowOpacity: 0.08, shadowRadius: 18, shadowOffset: { width: 0, height: 8 }, elevation: 2 };

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
  texto: string; onPress: () => void; icono?: IconName; variante?: 'primario' | 'secundario' | 'peligro' | 'texto' | 'claro';
  cargando?: boolean; deshabilitado?: boolean; estilo?: StyleProp<ViewStyle>;
}) {
  const sec = variante === 'secundario';
  const txt = variante === 'texto';
  const claro = variante === 'claro'; // botón crema sobre fondo verde
  const fondo = variante === 'peligro' ? COLOR.error : claro ? COLOR.fondo : sec || txt ? 'transparent' : COLOR.primario;
  const color = sec || txt || claro ? COLOR.primario : COLOR.tarjeta;
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
  // Los campos de contraseña llevan un botón con un ojo para mostrar u ocultar lo escrito
  const esClave = !!props.secureTextEntry;
  const [visible, setVisible] = useState(false);
  return (
    <View style={{ marginBottom: 12 }}>
      <Text style={estilos.etiqueta}>{etiqueta}</Text>
      <View style={{ justifyContent: 'center' }}>
        <TextInput
          placeholderTextColor="#8A968F"
          accessibilityLabel={etiqueta}
          {...props}
          secureTextEntry={esClave && !visible}
          style={[estilos.input, error ? { borderColor: COLOR.error } : null, props.multiline ? { minHeight: 80, textAlignVertical: 'top' } : null,
            esClave ? { paddingRight: 52 } : null]}
        />
        {esClave && (
          <TouchableOpacity accessibilityRole="button" accessibilityLabel={visible ? 'Ocultar contraseña' : 'Mostrar contraseña'}
            onPress={() => setVisible(!visible)} {...(Platform.OS === 'web' ? { title: visible ? 'Ocultar contraseña' : 'Mostrar contraseña' } as any : {})}
            style={{ position: 'absolute', right: 4, width: 44, height: 44, alignItems: 'center', justifyContent: 'center' }}>
            <Ionicons name={visible ? 'eye-off-outline' : 'eye-outline'} size={22} color={COLOR.textoSuave} />
          </TouchableOpacity>
        )}
      </View>
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

export const estilos = StyleSheet.create({
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

type Capa = { clave: string; nombre: string; url: string; leyenda: string };

/** Capas que se pueden dibujar sobre la foto de hoy: todas salen de los análisis del seguimiento. */
function capasDe(s: any): Capa[] {
  const c: Capa[] = [{ clave: 'foto', nombre: 'Foto', url: s.url_imagen_alineada, leyenda: 'Foto de hoy, alineada con la de referencia.' }];
  if (s.url_mapa_calor) c.push({ clave: 'color', nombre: 'Color', url: s.url_mapa_calor, leyenda: 'Diferencia de color ENTRE las dos fotos (no el color de una sola): azul = igual, amarillo = cambio medio, rojo = cambio grande.' });
  if (s.url_mapa_rojez) c.push({ clave: 'rojez', nombre: 'Rojez', url: s.url_mapa_rojez, leyenda: 'Rojo = zona más enrojecida que en la referencia; verde azulado = menos enrojecida. Sin color = sin cambio.' });
  if (s.url_mapa_luminosidad) c.push({ clave: 'luz', nombre: 'Luz y pigmento', url: s.url_mapa_luminosidad, leyenda: 'Marrón = zona más oscura que en la referencia; blanco = más clara. Muestra solo cambios locales (el cambio parejo de luz se explica abajo).' });
  if (s.url_imagen_manchas) c.push({ clave: 'manchas', nombre: 'Manchas', url: s.url_imagen_manchas, leyenda: 'Manchas: celeste = en la referencia, naranja = hoy.' });
  if (s.url_imagen_lesiones) c.push({ clave: 'lesiones', nombre: 'Lesiones', url: s.url_imagen_lesiones, leyenda: 'Lesiones: rojo = nuevas, verde = persisten, amarillo punteado = ya no aparecen.' });
  if (s.url_imagen_textura) c.push({ clave: 'textura', nombre: 'Textura', url: s.url_imagen_textura, leyenda: 'Textura: líneas en naranja, poros en celeste, brillo en blanco.' });
  if (s.url_imagen_periorbital) c.push({ clave: 'ojeras', nombre: 'Ojeras', url: s.url_imagen_periorbital, leyenda: 'Ojeras: zona bajo el ojo (violeta) comparada con la mejilla (celeste).' });
  return c;
}

/** Comparador antes/después: la referencia queda encima, recortada; se arrastra (o se toca) para mover el corte.
 *  Capas: dibuja sobre la foto de hoy el resultado de cada análisis. Parpadeo: alterna antes/después para notar cambios sutiles. */
export function ComparadorAntesDespues({ s, alto = 340 }: { s: any; alto?: number }) {
  const capas = capasDe(s);
  const [capa, setCapa] = useState('foto');
  const actual = capas.find((c) => c.clave === capa) ?? capas[0];
  const [ancho, setAncho] = useState(0);
  const [pos, setPos] = useState(0.5);
  const [parpadeo, setParpadeo] = useState(false);
  const anchoRef = useRef(0);
  const mover = (x: number) => { setParpadeo(false); if (anchoRef.current) setPos(Math.min(1, Math.max(0, x / anchoRef.current))); };
  const responder = useMemo(() => PanResponder.create({
    onStartShouldSetPanResponder: () => true,
    onMoveShouldSetPanResponder: () => true,
    onPanResponderGrant: (e) => mover(e.nativeEvent.locationX),
    onPanResponderMove: (e) => mover(e.nativeEvent.locationX),
    onPanResponderTerminationRequest: () => false,
  }), []);
  // Parpadeo a ≈ 1,4 cambios por segundo (lejos de los 3 Hz que pueden molestar a personas fotosensibles)
  useEffect(() => {
    if (!parpadeo) return;
    setPos(1);
    const t = setInterval(() => setPos((p) => (p > 0.5 ? 0 : 1)), 700);
    return () => { clearInterval(t); setPos(0.5); };
  }, [parpadeo]);
  const alMedir = (e: LayoutChangeEvent) => { anchoRef.current = e.nativeEvent.layout.width; setAncho(e.nativeEvent.layout.width); };
  const img = { width: ancho || 1, height: alto, marginTop: 0, borderRadius: 0, backgroundColor: COLOR.arena };
  const mostrando = parpadeo ? (pos > 0.5 ? 'Referencia' : `Hoy · ${actual.nombre.toLowerCase()}`) : null;
  return (
    <View style={{ backgroundColor: COLOR.tarjeta, borderRadius: 28, padding: 10, marginTop: 8, ...SOMBRA }}>
      <View onLayout={alMedir} {...responder.panHandlers} accessibilityLabel="Comparador antes y después: arrastrá para mover el corte"
        style={{ height: alto, borderRadius: 20, overflow: 'hidden', backgroundColor: COLOR.arena }}>
        <View pointerEvents="none" style={{ position: 'absolute', inset: 0 } as any}><ImagenProtegida url={actual.url} estilo={img} /></View>
        <View pointerEvents="none" style={{ position: 'absolute', top: 0, bottom: 0, left: 0, width: ancho * pos, overflow: 'hidden' }}>
          <ImagenProtegida url={s.url_imagen_referencia} estilo={img} />
        </View>
        {!parpadeo && (
          <>
            <View pointerEvents="none" style={{ position: 'absolute', top: 0, bottom: 0, left: ancho * pos - 1.5, width: 3, backgroundColor: COLOR.tarjeta }} />
            <View pointerEvents="none" style={{ position: 'absolute', top: alto / 2 - 20, left: ancho * pos - 20, width: 40, height: 40, borderRadius: 20, backgroundColor: COLOR.tarjeta, alignItems: 'center', justifyContent: 'center', ...SOMBRA }}>
              <Ionicons name="swap-horizontal" size={20} color={COLOR.primario} />
            </View>
            <View pointerEvents="none" style={{ position: 'absolute', left: 10, top: 10 }}><Pildora texto="Referencia" fondo="#FFFDF8E6" /></View>
            <View pointerEvents="none" style={{ position: 'absolute', right: 10, top: 10 }}><Pildora texto={`Hoy · ${actual.nombre.toLowerCase()}`} fondo={COLOR.primario} color={COLOR.tarjeta} /></View>
          </>
        )}
        {mostrando && (
          <View pointerEvents="none" style={{ position: 'absolute', left: 0, right: 0, top: 10, alignItems: 'center' }}>
            <Pildora texto={mostrando} fondo={pos > 0.5 ? '#FFFDF8E6' : COLOR.primario} color={pos > 0.5 ? COLOR.primario : COLOR.tarjeta} />
          </View>
        )}
      </View>

      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6, paddingVertical: 10 }} accessibilityRole="tablist">
        {capas.map((c) => {
          const sel = c.clave === actual.clave;
          return (
            <TouchableOpacity key={c.clave} accessibilityRole="tab" accessibilityState={{ selected: sel }} onPress={() => setCapa(c.clave)}
              style={{ paddingHorizontal: 14, minHeight: 38, borderRadius: 999, justifyContent: 'center', backgroundColor: sel ? COLOR.primario : COLOR.suave }}>
              <Text style={{ fontFamily: FUENTE.textoFuerte, fontSize: 13, color: sel ? COLOR.tarjeta : COLOR.primario }}>{c.nombre}</Text>
            </TouchableOpacity>
          );
        })}
      </ScrollView>
      <Text style={{ fontFamily: FUENTE.texto, fontSize: 12, color: COLOR.textoSuave, lineHeight: 17 }}>{actual.leyenda}</Text>
      {['color', 'rojez', 'luz'].includes(actual.clave) && <ColorPorZona s={s} />}
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 4 }}>
        <Text style={{ fontFamily: FUENTE.texto, fontSize: 12, color: COLOR.textoSuave, flex: 1 }}>
          {parpadeo ? 'Alternando antes y después: mirá qué cambia.' : 'Deslizá sobre la foto para comparar.'}
        </Text>
        <Boton texto={parpadeo ? 'Detener' : 'Parpadeo'} icono={parpadeo ? 'pause' : 'repeat'} variante="texto" onPress={() => setParpadeo(!parpadeo)} />
      </View>
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

export const num = (v: number, d = 1) => v.toFixed(d).replace('.', ',');

/** Indicadores en tarjetas con anillo. El anillo solo ilustra la magnitud; el número es el dato. */
export function Indicadores({ s }: { s: any }) {
  const items: { nombre: string; valor: string; fraccion: number; detalle: string }[] = [
    { nombre: 'Color', valor: num(s.delta_e_promedio), fraccion: s.delta_e_promedio / 10, detalle: `Delta E · cambio ${s.interpretacion?.magnitud_color ?? ''}` },
  ];
  if (s.manchas_pct_nueva != null) items.push({ nombre: 'Manchas', valor: `${num(s.manchas_pct_nueva)} %`, fraccion: s.manchas_pct_nueva / 5, detalle: `Antes ${num(s.manchas_pct_referencia, 2)} % de la piel` });
  if (s.ojeras_contraste_nueva != null) items.push({ nombre: 'Ojeras', valor: num(s.ojeras_contraste_nueva), fraccion: s.ojeras_contraste_nueva / 30, detalle: `Antes ${num(s.ojeras_contraste_referencia)} (contraste)` });
  const tr = s.textura_referencia, tn = s.textura_nueva;
  if (tn?.lineas_mm_cm2 != null && tr?.lineas_mm_cm2 != null) items.push({ nombre: 'Líneas', valor: num(tn.lineas_mm_cm2), fraccion: tn.lineas_mm_cm2 / 20, detalle: `mm por cm² · antes ${num(tr.lineas_mm_cm2)}` });
  if (tn?.poros_cm2 != null && tr?.poros_cm2 != null) items.push({ nombre: 'Poros', valor: num(tn.poros_cm2, 0), fraccion: tn.poros_cm2 / 60, detalle: `por cm² en mejillas · antes ${num(tr.poros_cm2, 0)}` });
  if (tn?.brillo_pct != null && tr?.brillo_pct != null) items.push({ nombre: 'Brillo', valor: `${num(tn.brillo_pct)} %`, fraccion: tn.brillo_pct / 15, detalle: `de la zona T · antes ${num(tr.brillo_pct)} %` });
  if (s.porfirinas) items.push({ nombre: 'Porfirinas', valor: s.porfirinas.por_cm2 != null ? num(s.porfirinas.por_cm2, 2) : String(s.porfirinas.cantidad), fraccion: (s.porfirinas.por_cm2 ?? 0) / 2, detalle: s.porfirinas.por_cm2 != null ? 'por cm² (foto con luz UV)' : 'puntos (foto con luz UV)' });
  if (s.valoracion_clinica?.iga != null) items.push({ nombre: 'IGA', valor: String(s.valoracion_clinica.iga), fraccion: s.valoracion_clinica.iga / 4, detalle: `${s.valoracion_clinica.iga_texto} · cargado por vos` });
  if (s.valoracion_clinica?.mmasi != null) items.push({ nombre: 'mMASI', valor: num(s.valoracion_clinica.mmasi), fraccion: s.valoracion_clinica.mmasi / 24, detalle: 'melasma, de 0 a 24 · cargado por vos' });
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
  { clave: 'lineas', nombre: 'Líneas', titulo: 'Líneas de expresión (mm por cm²)', valor: (s) => s.textura_nueva?.lineas_mm_cm2 ?? null, fmt: (v) => num(v) },
  { clave: 'poros', nombre: 'Poros', titulo: 'Poros visibles por cm²', valor: (s) => s.textura_nueva?.poros_cm2 ?? null, fmt: (v) => num(v, 0) },
  { clave: 'brillo', nombre: 'Brillo', titulo: 'Brillo de la zona T', valor: (s) => s.textura_nueva?.brillo_pct ?? null, fmt: (v) => `${num(v)} %` },
  { clave: 'porfirinas', nombre: 'Porfirinas', titulo: 'Porfirinas por cm² (luz UV)', valor: (s) => s.porfirinas?.por_cm2 ?? null, fmt: (v) => num(v, 2) },
  { clave: 'iga', nombre: 'IGA', titulo: 'IGA · acné (0 a 4, cargado por la profesional)', valor: (s) => s.valoracion_clinica?.iga ?? null, fmt: (v) => String(Math.round(v * 10) / 10) },
  { clave: 'mmasi', nombre: 'mMASI', titulo: 'mMASI · melasma (0 a 24, cargado por la profesional)', valor: (s) => s.valoracion_clinica?.mmasi ?? null, fmt: (v) => num(v) },
  { clave: 'humedad', nombre: 'Hidratación', titulo: 'Hidratación (equipo de la profesional)', valor: (s) => s.valoracion_clinica?.humedad ?? null, fmt: (v) => num(v) },
  { clave: 'ph', nombre: 'pH', titulo: 'pH (equipo de la profesional)', valor: (s) => s.valoracion_clinica?.ph ?? null, fmt: (v) => num(v) },
  { clave: 'firmeza', nombre: 'Firmeza', titulo: 'Firmeza (equipo de la profesional)', valor: (s) => s.valoracion_clinica?.firmeza ?? null, fmt: (v) => num(v) },
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
  // Tendencia (solo para la profesional): recta de mínimos cuadrados de las últimas consultas, un paso adelante
  const ult = datos.slice(-5);
  let proyeccion: number | null = null;
  if (ult.length >= 3) {
    const n = ult.length, xs = ult.map((_, i) => i), mx = (n - 1) / 2, my = ult.reduce((a, d) => a + d.v, 0) / n;
    const pend = xs.reduce((a, x, i) => a + (x - mx) * (ult[i].v - my), 0) / xs.reduce((a, x) => a + (x - mx) ** 2, 0);
    proyeccion = Math.max(0, my + pend * (n - mx));
  }
  const pasos = datos.length - 1 + (proyeccion != null ? 1 : 0);
  const max = Math.max(...datos.map((d) => d.v), proyeccion ?? 0, 0.0001);
  const xDe = (i: number) => (pasos === 0 ? ancho / 2 : margen + (i * (ancho - 2 * margen)) / pasos);
  const yDe = (v: number) => alto - 12 - (v / max) * (alto - 36);
  const pts = datos.map((d, i) => ({ x: xDe(i), y: yDe(d.v) }));
  const linea = pts.map((p) => `${p.x},${p.y}`).join(' ');
  const corta = (f: Date) => f.toLocaleDateString('es-PY', { day: 'numeric', month: 'short' });
  return (
    <View style={{ marginTop: 12 }}>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} accessibilityRole="tablist"
        contentContainerStyle={{ gap: 6, padding: 5 }} style={{ backgroundColor: COLOR.tarjeta, borderRadius: 18, flexGrow: 0 }}>
        {disponibles.map((x) => {
          const activa = x.clave === serie.clave;
          return (
            <TouchableOpacity key={x.clave} accessibilityRole="tab" accessibilityState={{ selected: activa }} onPress={() => setSel(x.clave)}
              style={{ minHeight: 40, paddingHorizontal: 14, borderRadius: 14, alignItems: 'center', justifyContent: 'center', backgroundColor: activa ? COLOR.primario : 'transparent' }}>
              <Text style={{ fontFamily: FUENTE.textoFuerte, fontSize: 13, color: activa ? COLOR.tarjeta : COLOR.primario }}>{x.nombre}</Text>
            </TouchableOpacity>
          );
        })}
      </ScrollView>
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
              {proyeccion != null && (
                <Line x1={pts[pts.length - 1].x} y1={pts[pts.length - 1].y} x2={xDe(datos.length)} y2={yDe(proyeccion)}
                  stroke={COLOR.dorado} strokeWidth={3} strokeDasharray="6 6" strokeLinecap="round" />
              )}
              {proyeccion != null && <Circle cx={xDe(datos.length)} cy={yDe(proyeccion)} r={6} fill={COLOR.tarjeta} stroke={COLOR.dorado} strokeWidth={3} strokeDasharray="3 3" />}
              {pts.map((p, i) => <Circle key={i} cx={p.x} cy={p.y} r={6} fill={COLOR.tarjeta} stroke={COLOR.primario} strokeWidth={3} />)}
            </Svg>
          )}
        </View>
        <View style={{ flexDirection: 'row', justifyContent: datos.length === 1 ? 'center' : 'space-between', marginTop: 4 }}>
          {datos.map((d, i) => <Text key={i} style={{ fontFamily: FUENTE.texto, fontSize: 12, color: COLOR.textoSuave }}>{corta(d.fecha)}</Text>)}
          {proyeccion != null && <Text style={{ fontFamily: FUENTE.textoFuerte, fontSize: 12, color: '#8A6D2F' }}>Próxima</Text>}
        </View>
        {proyeccion != null && (
          <Text style={{ fontFamily: FUENTE.texto, fontSize: 12, color: COLOR.textoSuave, marginTop: 8, lineHeight: 17 }}>
            Tendencia: si sigue como en las últimas {ult.length} consultas, en la próxima rondaría {serie.fmt(proyeccion)}. Es una proyección
            matemática para orientarte, no un pronóstico clínico; no se incluye en el informe del paciente.
          </Text>
        )}
      </View>
    </View>
  );
}

/** Textura: líneas por zona, poros y brillo, con la imagen de las zonas analizadas. */
export function ResumenTextura({ s }: { s: any }) {
  const tr = s.textura_referencia, tn = s.textura_nueva;
  if (!tn || !tr) return null;
  const zona: Record<string, string> = { frente: 'Frente', entrecejo: 'Entrecejo', patas_de_gallo: 'Contorno de ojos' };
  const v = (x: number | null | undefined, d = 1) => (x == null ? '—' : num(x, d));
  return (
    <View style={{ marginTop: 12 }}>
      <Text style={{ fontSize: 17, fontFamily: FUENTE.titulo, color: COLOR.texto, marginBottom: 6 }}>Textura</Text>
      {Object.keys(zona).map((k) => (
        <Text key={k} style={{ fontFamily: FUENTE.texto, color: COLOR.texto }}>
          Líneas en {zona[k].toLowerCase()}: {v(tr.lineas_por_zona?.[k])} → {v(tn.lineas_por_zona?.[k])} mm/cm²
        </Text>
      ))}
      <Text style={{ fontFamily: FUENTE.texto, color: COLOR.texto }}>
        Poros (mejillas): {tn.poros_cm2 == null ? 'la foto no tiene detalle suficiente; acercá más la cámara' : `${v(tr.poros_cm2, 0)} → ${v(tn.poros_cm2, 0)} por cm²`}
      </Text>
      <Text style={{ fontFamily: FUENTE.texto, color: COLOR.texto }}>Brillo de la zona T: {v(tr.brillo_pct)} % → {v(tn.brillo_pct)} %</Text>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 12, marginTop: 6 }}>
        <Text style={{ color: '#C76A00', fontFamily: FUENTE.textoFuerte }}>— Líneas</Text>
        <Text style={{ color: '#1F8FB8', fontFamily: FUENTE.textoFuerte }}>● Poros</Text>
        <Text style={{ color: COLOR.textoSuave, fontFamily: FUENTE.textoFuerte }}>▢ Zonas analizadas</Text>
      </View>
      {s.url_imagen_textura && <ImagenProtegida url={s.url_imagen_textura} />}
      <Text style={{ color: COLOR.textoSuave, fontSize: 12, marginTop: 6, fontFamily: FUENTE.texto, lineHeight: 17 }}>
        Índices para comparar consultas, no diagnóstico. La escala usa la distancia entre pupilas (63 mm promedio). Los poros se miden solo
        si la foto tiene detalle suficiente; el brillo depende mucho de la luz.
      </Text>
    </View>
  );
}


/** Tono de la piel por zona (referencia → hoy), qué cambió en cada una y posibles explicaciones generales. */
function ColorPorZona({ s }: { s: any }) {
  const cr = s.color_regiones;
  if (!cr?.zonas) return null;
  const zonas: any[] = Object.values(cr.zonas);
  const etiquetas = (z: any) => {
    const e: string[] = [];
    if (z.da_local >= 2) e.push('más roja'); else if (z.da_local <= -2) e.push('menos roja');
    if (z.dL_local <= -2) e.push('más oscura'); else if (z.dL_local >= 2) e.push('más clara');
    if (z.db_local >= 2) e.push('más amarilla'); else if (z.db_local <= -2) e.push('menos amarilla');
    return e;
  };
  const causas: string[] = s.interpretacion?.causas_color ?? [];
  return (
    <View style={{ marginTop: 12, gap: 8 }}>
      <Text style={{ fontFamily: FUENTE.titulo, fontSize: 15, color: COLOR.texto }}>Tono por zona</Text>
      {zonas.map((z) => {
        const e = etiquetas(z);
        return (
          <View key={z.nombre} style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
            <Text style={{ fontFamily: FUENTE.textoFuerte, fontSize: 13, color: COLOR.texto, width: 112 }}>{z.nombre}</Text>
            <View accessibilityLabel={`Tono en la referencia de ${z.nombre}`} style={{ width: 28, height: 28, borderRadius: 9, backgroundColor: z.color_referencia, borderWidth: 1, borderColor: '#0001' }} />
            <Ionicons name="arrow-forward" size={14} color={COLOR.textoSuave} />
            <View accessibilityLabel={`Tono hoy de ${z.nombre}`} style={{ width: 28, height: 28, borderRadius: 9, backgroundColor: z.color_nueva, borderWidth: 1, borderColor: '#0001' }} />
            <Text style={{ fontFamily: e.length ? FUENTE.textoFuerte : FUENTE.texto, fontSize: 12, color: e.length ? COLOR.aviso : COLOR.textoSuave, flex: 1 }}>
              {e.length ? e.join(' · ') : 'sin cambio propio'}
            </Text>
          </View>
        );
      })}
      <Text style={{ fontFamily: FUENTE.texto, fontSize: 11, color: COLOR.textoSuave }}>
        Cuadrito izquierdo = tono promedio en la referencia; derecho = hoy. «Sin cambio propio» significa que la zona cambió igual que el resto del rostro.
      </Text>
      {causas.length > 0 && (
        <View style={{ backgroundColor: COLOR.fondo, borderRadius: 18, padding: 14, marginTop: 4, gap: 6 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
            <Ionicons name="help-circle-outline" size={18} color={COLOR.primario} />
            <Text style={{ fontFamily: FUENTE.titulo, fontSize: 15, color: COLOR.texto }}>Por qué pudo cambiar</Text>
          </View>
          {causas.map((c, i) => (
            <Text key={i} style={{ fontFamily: i === causas.length - 1 ? FUENTE.textoMedio : FUENTE.texto, fontSize: 13, lineHeight: 19,
              color: i === causas.length - 1 ? COLOR.textoSuave : COLOR.texto }}>{i === causas.length - 1 ? c : `• ${c}`}</Text>
          ))}
        </View>
      )}
    </View>
  );
}
