import { Ionicons } from '@expo/vector-icons';
import * as ImagePicker from 'expo-image-picker';
import { useEffect, useState } from 'react';
import { Platform, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { api, mensaje } from '../lib/api';
import { elegirOrigenFoto } from '../lib/dialogo';
import { Boton, COLOR, Confirmar, estilos, FUENTE, ImagenProtegida, num } from './ui';

const IGA = ['Sin lesiones', 'Casi limpio', 'Leve', 'Moderado', 'Severo'];
const REGIONES_MASI: [string, string][] = [['frente', 'Frente'], ['malar_derecha', 'Mejilla derecha'], ['malar_izquierda', 'Mejilla izquierda'], ['menton', 'Mentón']];
const PESOS: Record<string, number> = { frente: 0.3, malar_derecha: 0.3, malar_izquierda: 0.3, menton: 0.1 };
type Masi = Record<string, { area: number; oscuridad: number }>;
const MASI_VACIO: Masi = Object.fromEntries(REGIONES_MASI.map(([k]) => [k, { area: 0, oscuridad: 0 }]));

function Caja({ titulo, ayuda, children, abierta, onAlternar }: { titulo: string; ayuda: string; children: React.ReactNode; abierta: boolean; onAlternar: () => void }) {
  return (
    <View style={{ backgroundColor: COLOR.tarjeta, borderRadius: 24, padding: 16, marginTop: 12 }}>
      <TouchableOpacity accessibilityRole="button" accessibilityState={{ expanded: abierta }} onPress={onAlternar}
        style={{ flexDirection: 'row', alignItems: 'center', gap: 8, minHeight: 44 }}>
        <View style={{ flex: 1 }}>
          <Text style={{ fontFamily: FUENTE.titulo, fontSize: 16, color: COLOR.texto }}>{titulo}</Text>
          <Text style={{ fontFamily: FUENTE.texto, fontSize: 13, color: COLOR.textoSuave }}>{ayuda}</Text>
        </View>
        <Ionicons name={abierta ? 'chevron-up' : 'chevron-down'} size={22} color={COLOR.primario} />
      </TouchableOpacity>
      {abierta && <View style={{ marginTop: 10 }}>{children}</View>}
    </View>
  );
}

function Selector({ etiqueta, valor, max, onCambio }: { etiqueta: string; valor: number; max: number; onCambio: (v: number) => void }) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
      <Text style={{ fontFamily: FUENTE.texto, fontSize: 13, color: COLOR.textoSuave, width: 74 }}>{etiqueta}</Text>
      <TouchableOpacity accessibilityRole="button" accessibilityLabel={`Bajar ${etiqueta}`} disabled={valor <= 0} onPress={() => onCambio(valor - 1)}
        style={{ width: 36, height: 36, borderRadius: 12, backgroundColor: COLOR.suave, alignItems: 'center', justifyContent: 'center', opacity: valor <= 0 ? 0.4 : 1 }}>
        <Ionicons name="remove" size={18} color={COLOR.primario} />
      </TouchableOpacity>
      <Text style={{ fontFamily: FUENTE.titulo, fontSize: 16, color: COLOR.texto, width: 22, textAlign: 'center' }}>{valor}</Text>
      <TouchableOpacity accessibilityRole="button" accessibilityLabel={`Subir ${etiqueta}`} disabled={valor >= max} onPress={() => onCambio(valor + 1)}
        style={{ width: 36, height: 36, borderRadius: 12, backgroundColor: COLOR.suave, alignItems: 'center', justifyContent: 'center', opacity: valor >= max ? 0.4 : 1 }}>
        <Ionicons name="add" size={18} color={COLOR.primario} />
      </TouchableOpacity>
    </View>
  );
}

const aNumero = (t: string) => (t.trim() === '' ? undefined : Number(t.replace(',', '.')));

/** Escalas clínicas y mediciones con equipo que carga la profesional (la app no las estima). */
export function ValoracionClinica({ seguimientoId, inicial, alGuardar }: { seguimientoId: number; inicial?: any; alGuardar?: (s: any) => void }) {
  const [abierta, setAbierta] = useState(!!inicial);
  const [iga, setIga] = useState<number | null>(inicial?.iga ?? null);
  const [usarMasi, setUsarMasi] = useState(!!inicial?.masi);
  const [masi, setMasi] = useState<Masi>(inicial?.masi ?? MASI_VACIO);
  const [humedad, setHumedad] = useState(inicial?.humedad != null ? String(inicial.humedad) : '');
  const [ph, setPh] = useState(inicial?.ph != null ? String(inicial.ph) : '');
  const [firmeza, setFirmeza] = useState(inicial?.firmeza != null ? String(inicial.firmeza) : '');
  const [equipo, setEquipo] = useState(inicial?.equipo ?? '');
  const [estado, setEstado] = useState<{ cargando?: boolean; error?: string; ok?: boolean }>({});
  const total = REGIONES_MASI.reduce((acc, [k]) => acc + PESOS[k] * masi[k].area * masi[k].oscuridad, 0);

  const guardar = async () => {
    const valores = { humedad: aNumero(humedad), ph: aNumero(ph), firmeza: aNumero(firmeza) };
    if (Object.values(valores).some((v) => v !== undefined && Number.isNaN(v))) return setEstado({ error: 'Escribí solo números (por ejemplo 5,4).' });
    setEstado({ cargando: true });
    const r = await api(`/seguimientos/${seguimientoId}/valoracion`, {
      method: 'PUT', json: { iga, masi: usarMasi ? masi : null, ...valores, equipo: equipo.trim() || null },
    });
    if (!r.ok) return setEstado({ error: r.status === 422 ? 'Revisá los valores: pH entre 3 y 9, hidratación entre 0 y 150, firmeza entre 0 y 100.' : mensaje(r) });
    setEstado({ ok: true });
    alGuardar?.(r.data);
  };
  const cambio = () => setEstado({});

  return (
    <Caja titulo="Valoración clínica" ayuda="Escalas y mediciones que cargás vos; salen en el informe." abierta={abierta} onAlternar={() => setAbierta(!abierta)}>
      <Text style={estilos.etiqueta}>IGA · acné (0 a 4)</Text>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
        {IGA.map((t, i) => {
          const sel = iga === i;
          return (
            <TouchableOpacity key={t} accessibilityRole="radio" accessibilityState={{ checked: sel }} onPress={() => { setIga(sel ? null : i); cambio(); }}
              style={{ paddingHorizontal: 12, minHeight: 40, justifyContent: 'center', borderRadius: 999, backgroundColor: sel ? COLOR.primario : COLOR.suave }}>
              <Text style={{ fontFamily: FUENTE.textoFuerte, fontSize: 13, color: sel ? COLOR.tarjeta : COLOR.primario }}>{i} · {t}</Text>
            </TouchableOpacity>
          );
        })}
      </View>

      <TouchableOpacity accessibilityRole="checkbox" accessibilityState={{ checked: usarMasi }} onPress={() => { setUsarMasi(!usarMasi); cambio(); }}
        style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 14, minHeight: 44 }}>
        <Ionicons name={usarMasi ? 'checkbox' : 'square-outline'} size={24} color={COLOR.primario} />
        <Text style={{ fontFamily: FUENTE.textoFuerte, color: COLOR.texto }}>mMASI · melasma</Text>
        {usarMasi && <Text style={{ marginLeft: 'auto', fontFamily: FUENTE.titulo, fontSize: 18, color: COLOR.primario }}>{num(total)} / 24</Text>}
      </TouchableOpacity>
      {usarMasi && REGIONES_MASI.map(([k, nombre]) => (
        <View key={k} style={{ marginTop: 8, gap: 6 }}>
          <Text style={{ fontFamily: FUENTE.textoFuerte, color: COLOR.texto, fontSize: 14 }}>{nombre}</Text>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 12 }}>
            <Selector etiqueta="Área 0-6" valor={masi[k].area} max={6} onCambio={(v) => { setMasi({ ...masi, [k]: { ...masi[k], area: v } }); cambio(); }} />
            <Selector etiqueta="Oscuridad 0-4" valor={masi[k].oscuridad} max={4} onCambio={(v) => { setMasi({ ...masi, [k]: { ...masi[k], oscuridad: v } }); cambio(); }} />
          </View>
        </View>
      ))}

      <Text style={[estilos.etiqueta, { marginTop: 14 }]}>Mediciones con tu equipo (opcional)</Text>
      <View style={{ flexDirection: 'row', gap: 8 }}>
        {([['Hidratación', humedad, setHumedad], ['pH', ph, setPh], ['Firmeza', firmeza, setFirmeza]] as const).map(([et, val, set]) => (
          <View key={et} style={{ flex: 1 }}>
            <Text style={{ fontFamily: FUENTE.texto, fontSize: 12, color: COLOR.textoSuave, marginBottom: 4 }}>{et}</Text>
            <TextInput value={val} onChangeText={(t) => { set(t); cambio(); }} keyboardType="decimal-pad" accessibilityLabel={et} maxLength={6} style={estilos.input} />
          </View>
        ))}
      </View>
      <Text style={{ fontFamily: FUENTE.texto, fontSize: 12, color: COLOR.textoSuave, marginTop: 8, marginBottom: 4 }}>Equipo usado (para comparar con las mismas unidades)</Text>
      <TextInput value={equipo} onChangeText={(t) => { setEquipo(t); cambio(); }} maxLength={120} placeholder="Ej.: Corneometer CM 825" placeholderTextColor="#8A968F" accessibilityLabel="Equipo usado" style={estilos.input} />
      {estado.error && <Text style={estilos.error}>{estado.error}</Text>}
      <Boton texto={estado.ok ? 'Guardado' : 'Guardar valoración'} icono={estado.ok ? 'checkmark' : 'save-outline'} cargando={estado.cargando} onPress={guardar} estilo={{ marginTop: 12 }} />
    </Caja>
  );
}

/** Foto con luz UV (lámpara de Wood): la app cuenta las porfirinas, que se ven como puntitos naranjas. */
export function FotoUV({ seguimientoId, s, alGuardar }: { seguimientoId: number; s: any; alGuardar?: (s: any) => void }) {
  const [abierta, setAbierta] = useState(!!s.porfirinas);
  const [estado, setEstado] = useState<{ cargando?: boolean; error?: string }>({});
  const [datos, setDatos] = useState<any>(s);
  useEffect(() => setDatos(s), [s]);

  const subir = () => elegirOrigenFoto(async (origen) => {
    const permiso = origen === 'galeria' ? await ImagePicker.requestMediaLibraryPermissionsAsync() : await ImagePicker.requestCameraPermissionsAsync();
    if (!permiso.granted) return setEstado({ error: 'Necesitamos permiso para usar tus fotos o la cámara.' });
    const opciones: ImagePicker.ImagePickerOptions = { mediaTypes: ['images'], quality: 0.9 };
    const res = origen === 'galeria' ? await ImagePicker.launchImageLibraryAsync(opciones) : await ImagePicker.launchCameraAsync(opciones);
    if (res.canceled || !res.assets?.length) return;
    const a = res.assets[0];
    const fd = new FormData();
    if (Platform.OS === 'web') fd.append('imagen', await (await fetch(a.uri)).blob(), a.fileName || 'uv.jpg');
    else fd.append('imagen', { uri: a.uri, name: a.fileName || 'uv.jpg', type: a.mimeType || 'image/jpeg' } as any);
    setEstado({ cargando: true });
    const r = await api(`/seguimientos/${seguimientoId}/foto-uv`, { method: 'POST', multipart: fd });
    if (!r.ok) return setEstado({ error: mensaje(r) });
    setEstado({});
    setDatos(r.data);
    alGuardar?.(r.data);
  });

  const po = datos.porfirinas;
  return (
    <Caja titulo="Porfirinas (foto con luz UV)" ayuda="Necesitás una lámpara de Wood o una linterna UV." abierta={abierta} onAlternar={() => setAbierta(!abierta)}>
      <Text style={{ fontFamily: FUENTE.texto, color: COLOR.texto, lineHeight: 20 }}>
        Apagá la luz del consultorio, iluminá el rostro con la luz UV y sacá la foto de frente. Las porfirinas se ven como puntitos naranjas y la app los cuenta.
      </Text>
      {po && (
        <View style={{ marginTop: 10 }}>
          <Text style={{ fontFamily: FUENTE.titulo, fontSize: 22, color: COLOR.texto }}>
            {po.por_cm2 != null ? `${num(po.por_cm2, 2)} por cm²` : `${po.cantidad} puntos`}
          </Text>
          <Text style={{ fontFamily: FUENTE.texto, fontSize: 13, color: COLOR.textoSuave }}>
            {po.cantidad} puntos fluorescentes{po.rostro_detectado ? '' : ' (no se encontró el rostro: se contó en toda la foto)'}
          </Text>
          {datos.url_imagen_uv_analisis && <ImagenProtegida url={datos.url_imagen_uv_analisis} />}
        </View>
      )}
      {estado.error && <Text style={estilos.error}>{estado.error}</Text>}
      <Boton texto={po ? 'Reemplazar foto UV' : 'Agregar foto con luz UV'} icono="flashlight-outline" variante="secundario" cargando={estado.cargando} onPress={subir} estilo={{ marginTop: 10 }} />
      <Text style={{ fontFamily: FUENTE.texto, fontSize: 12, color: COLOR.textoSuave, marginTop: 6 }}>Índice para comparar consultas, no diagnóstico.</Text>
    </Caja>
  );
}

/** Indicaciones del profesional para el paciente, con plantillas que ella misma escribe y reutiliza. Salen en el informe PDF. */
export function Recomendaciones({ seguimientoId, inicial }: { seguimientoId: number; inicial?: string | null }) {
  const [texto, setTexto] = useState(inicial ?? '');
  const [guardado, setGuardado] = useState(inicial ?? '');
  const [estado, setEstado] = useState<{ cargando?: boolean; error?: string; ok?: boolean }>({});
  const [plantillas, setPlantillas] = useState<{ id: number; titulo: string; texto: string }[]>([]);
  const [nombrando, setNombrando] = useState(false);
  const [titulo, setTitulo] = useState('');
  const [errorTitulo, setErrorTitulo] = useState<string | null>(null);
  const [aBorrar, setABorrar] = useState<{ id: number; titulo: string } | null>(null);

  const cargarPlantillas = () => api('/plantillas-indicaciones').then((r) => { if (r.ok) setPlantillas(r.data); });
  useEffect(() => { cargarPlantillas(); }, []);

  const guardar = async () => {
    setEstado({ cargando: true });
    const r = await api(`/seguimientos/${seguimientoId}/recomendaciones`, { method: 'PUT', json: { texto } });
    if (!r.ok) return setEstado({ error: mensaje(r) });
    setGuardado(r.data.recomendaciones ?? ''); setTexto(r.data.recomendaciones ?? ''); setEstado({ ok: true });
  };
  const insertar = (t: string) => { setTexto((x) => (x.trim() ? `${x.trimEnd()}\n${t}` : t)); setEstado({}); };
  const guardarPlantilla = async () => {
    const t = titulo.trim();
    if (!t || !texto.trim()) return;
    // El título no se repite entre tus plantillas (sin distinguir mayúsculas); el servidor también lo controla.
    if (plantillas.some((p) => p.titulo.trim().toLowerCase() === t.toLowerCase())) {
      return setErrorTitulo(`Ya tenés una plantilla llamada «${t}». Elegí otro nombre.`);
    }
    const r = await api('/plantillas-indicaciones', { method: 'POST', json: { titulo: t, texto: texto.trim() } });
    if (!r.ok) return setErrorTitulo(mensaje(r));
    setNombrando(false); setTitulo(''); setErrorTitulo(null); cargarPlantillas();
  };
  const borrarPlantilla = async () => {
    const p = aBorrar!; setABorrar(null);
    const r = await api(`/plantillas-indicaciones/${p.id}`, { method: 'DELETE' });
    if (!r.ok) setEstado({ error: mensaje(r, 'No se pudo borrar la plantilla. Intentá de nuevo.') });
    cargarPlantillas();
  };

  return (
    <View style={{ backgroundColor: COLOR.tarjeta, borderRadius: 24, padding: 16, marginTop: 12, borderWidth: 1.5, borderColor: COLOR.dorado }}>
      <Text style={{ fontFamily: FUENTE.titulo, fontSize: 16, color: COLOR.texto }}>Indicaciones para el paciente</Text>
      <Text style={{ fontFamily: FUENTE.texto, fontSize: 13, color: COLOR.textoSuave, marginBottom: 8 }}>Las escribís vos; salen en el informe PDF.</Text>
      {plantillas.length > 0 && (
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 8 }}>
          {plantillas.map((p) => (
            <View key={p.id} style={{ flexDirection: 'row', alignItems: 'center', backgroundColor: COLOR.suave, borderRadius: 999 }}>
              <TouchableOpacity accessibilityRole="button" accessibilityLabel={`Insertar plantilla ${p.titulo}`} onPress={() => insertar(p.texto)}
                style={{ paddingLeft: 12, paddingRight: 6, minHeight: 36, justifyContent: 'center' }}>
                <Text style={{ fontFamily: FUENTE.textoFuerte, fontSize: 13, color: COLOR.primario }}>+ {p.titulo}</Text>
              </TouchableOpacity>
              <TouchableOpacity accessibilityRole="button" accessibilityLabel={`Borrar plantilla ${p.titulo}`} onPress={() => setABorrar(p)}
                style={{ paddingRight: 10, paddingLeft: 4, minHeight: 36, justifyContent: 'center' }}>
                <Ionicons name="close" size={14} color={COLOR.textoSuave} />
              </TouchableOpacity>
            </View>
          ))}
        </View>
      )}
      <TextInput value={texto} onChangeText={(t) => { setTexto(t); setEstado({}); }} multiline maxLength={2000}
        placeholder="Ej.: protector solar FPS 50 cada 3 horas; control en 30 días." placeholderTextColor="#8A968F" accessibilityLabel="Indicaciones para el paciente"
        style={[estilos.input, { minHeight: 90, textAlignVertical: 'top' }]} />
      {estado.error && <Text style={estilos.error}>{estado.error}</Text>}
      <Boton texto={estado.ok && texto === guardado ? 'Guardado' : 'Guardar indicaciones'} icono={estado.ok && texto === guardado ? 'checkmark' : 'save-outline'}
        variante="secundario" cargando={estado.cargando} deshabilitado={texto === guardado} onPress={guardar} estilo={{ marginTop: 10 }} />
      {nombrando ? (
        <View style={{ flexDirection: 'row', gap: 8, marginTop: 8, alignItems: 'center' }}>
          <TextInput value={titulo} onChangeText={(t) => { setTitulo(t); setErrorTitulo(null); }} maxLength={60} placeholder="Nombre de la plantilla" placeholderTextColor="#8A968F"
            accessibilityLabel="Nombre de la plantilla" style={[estilos.input, { flex: 1 }, errorTitulo ? { borderColor: COLOR.error } : null]} />
          <Boton texto="Guardar" variante="texto" deshabilitado={!titulo.trim()} onPress={guardarPlantilla} />
        </View>
      ) : (
        <Boton texto="Guardar este texto como plantilla" icono="bookmark-outline" variante="texto" deshabilitado={!texto.trim()} onPress={() => setNombrando(true)} />
      )}
      {nombrando && errorTitulo && <Text style={estilos.error}>{errorTitulo}</Text>}
      <Confirmar visible={!!aBorrar} peligro titulo="¿Borrar la plantilla?"
        mensaje={`La plantilla «${aBorrar?.titulo ?? ''}» dejará de aparecer en tu lista. Las indicaciones ya guardadas en los informes no cambian.`}
        textoConfirmar="Sí, borrar" onConfirmar={borrarPlantilla} onCancelar={() => setABorrar(null)} />
    </View>
  );
}
