import { router, useLocalSearchParams } from 'expo-router';
import { useCallback, useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Text, View } from 'react-native';
import { Aviso, Boton, BotonInforme, COLOR, ComparadorAntesDespues, FUENTE, GraficoEvolucion, ImagenProtegida, Iniciales, Indicadores, Interpretacion, Pantalla, ResumenLesiones, ResumenManchas, ResumenTextura, ResumenOjeras, Subtitulo, Tarjeta } from '../components/ui';
import { FotoUV, Recomendaciones, ValoracionClinica } from '../components/clinico';
import { api, fechaCorta, mensaje } from '../lib/api';
import { CampoFecha, hoyTexto } from '../components/CampoFecha';

const TAM = 10;

export default function HistorialScreen() {
  const { pacienteId, nombre, apellido } = useLocalSearchParams<{ pacienteId: string; nombre: string; apellido: string }>();
  const [items, setItems] = useState<any[]>([]);

  const [pagina, setPagina] = useState(1);
  const [desde, setDesde] = useState('');
  const [hasta, setHasta] = useState('');
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [verFiltros, setVerFiltros] = useState(false);
  const [detalle, setDetalle] = useState<Set<number>>(new Set());
  const actualizar = (nuevo: any) => setItems((xs) => xs.map((x) => (x.id === nuevo.id ? nuevo : x)));
  const pacienteActual = useRef(pacienteId);
  pacienteActual.current = pacienteId;

  const cargar = useCallback(async (p: number) => {
    const re = /^\d{4}-\d{2}-\d{2}$/;
    if ((desde && !re.test(desde)) || (hasta && !re.test(hasta))) return setError('Las fechas deben tener el formato AAAA-MM-DD.');
    setError(null); setCargando(true);
    const qs = `pagina=${p}&tamano=${TAM}${desde ? `&desde=${desde}` : ''}${hasta ? `&hasta=${hasta}` : ''}`;
    const pedido = pacienteId;
    const r = await api(`/pacientes/${pedido}/seguimientos?${qs}`);
    if (pedido !== pacienteActual.current) return; // respuesta de un paciente anterior: se descarta
    setCargando(false);
    if (!r.ok) return setError(mensaje(r, 'No se pudo cargar el historial.'));
    setItems((prev) => (p === 1 ? r.data : [...prev, ...r.data]));
    setPagina(p);
  }, [pacienteId, desde, hasta]);

  // Al cambiar de paciente se vacía la lista antes de cargar la del nuevo (nunca mostrar datos de otro paciente).
  useEffect(() => {
    setItems([]);
    setDesde('');
    setHasta('');
    cargar(1);
  }, [pacienteId]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <Pantalla>
      <View style={{ backgroundColor: COLOR.primario, borderRadius: 28, padding: 20, overflow: 'hidden' }}>
        <View style={{ position: 'absolute', right: -40, top: -40, width: 150, height: 150, borderRadius: 75, backgroundColor: '#3E7C60' }} />
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 14 }}>
          <Iniciales nombre={nombre ?? ''} apellido={apellido ?? ''} tam={58} claro />
          <View style={{ flex: 1 }}>
            <Text style={{ fontFamily: FUENTE.titulo, fontSize: 22, color: COLOR.tarjeta }}>{nombre} {apellido}</Text>
            <Text style={{ fontFamily: FUENTE.texto, fontSize: 13, color: '#D9E8DF' }}>
              {items.length ? `${items.length}${items.length % TAM === 0 ? '+' : ''} seguimientos` : 'Sin seguimientos todavía'}
            </Text>
          </View>
        </View>
        <Boton texto="Nuevo seguimiento" icono="camera-outline" estilo={{ marginTop: 16, backgroundColor: COLOR.fondo }}
          onPress={() => router.push({ pathname: '/procesamiento', params: { pacienteId, nombre, apellido } })} />
      </View>

      {items.length > 0 && <GraficoEvolucion seguimientos={items} />}

      <Boton texto={verFiltros ? 'Ocultar filtro de fechas' : 'Filtrar por fechas'} icono="calendar-outline" variante="texto" onPress={() => setVerFiltros(!verFiltros)} estilo={{ alignSelf: 'flex-start', marginTop: 6 }} />
      {verFiltros && (
        <Tarjeta>
          <CampoFecha etiqueta="Desde (opcional)" valor={desde} onCambio={setDesde} maximo={hasta || hoyTexto()} />
          <CampoFecha etiqueta="Hasta (opcional)" valor={hasta} onCambio={setHasta} minimo={desde || undefined} maximo={hoyTexto()} />
          <Boton texto="Aplicar filtro" icono="filter-outline" variante="secundario" onPress={() => cargar(1)} />
        </Tarjeta>
      )}
      {error && <Aviso tipo="error" texto={error} />}
      {cargando && <ActivityIndicator size="large" color={COLOR.primario} style={{ marginVertical: 16 }} />}
      {!cargando && !error && items.length === 0 && <Text style={{ textAlign: 'center', color: COLOR.textoSuave, marginTop: 24, fontFamily: FUENTE.texto }}>No hay seguimientos para mostrar.</Text>}
      {items.map((s) => (
        <View key={s.id} style={{ marginTop: 18 }}>
          <Subtitulo>{fechaCorta(s.fecha)}</Subtitulo>
          <ComparadorAntesDespues urlReferencia={s.url_imagen_referencia} urlActual={s.url_imagen_alineada} alto={300} />
          <Interpretacion s={s} />
          <Indicadores s={s} />
          <ValoracionClinica alGuardar={actualizar} seguimientoId={s.id} inicial={s.valoracion_clinica} />
          <FotoUV alGuardar={actualizar} seguimientoId={s.id} s={s} />
          <Recomendaciones seguimientoId={s.id} inicial={s.recomendaciones} />
          <BotonInforme seguimientoId={s.id} />
          <Boton texto={detalle.has(s.id) ? 'Ocultar detalle técnico' : 'Ver detalle técnico'} icono={detalle.has(s.id) ? 'chevron-up' : 'chevron-down'} variante="texto"
            onPress={() => setDetalle((d) => { const n = new Set(d); if (n.has(s.id)) n.delete(s.id); else n.add(s.id); return n; })} />
          {detalle.has(s.id) && (
            <Tarjeta>
              <Text style={{ color: COLOR.textoSuave, fontFamily: FUENTE.texto }}>Puntos faciales: {s.landmarks_referencia} / {s.landmarks_nueva}</Text>
              <Subtitulo>Análisis colorimétrico (CIE L*a*b*)</Subtitulo>
              <Text style={{ fontFamily: FUENTE.texto, color: COLOR.texto }}>Delta E promedio (CIE76): {s.delta_e_promedio.toFixed(2)} — cambio {s.interpretacion?.magnitud_color ?? ''}</Text>
              <ImagenProtegida url={s.url_mapa_calor} />
              <ResumenLesiones s={s} />
              <ResumenOjeras s={s} />
              <ResumenManchas s={s} />
              <ResumenTextura s={s} />
            </Tarjeta>
          )}
        </View>
      ))}
      {items.length > 0 && items.length % TAM === 0 && !cargando && (
        <Boton texto="Cargar más" icono="chevron-down" variante="secundario" onPress={() => cargar(pagina + 1)} />
      )}
    </Pantalla>
  );
}
