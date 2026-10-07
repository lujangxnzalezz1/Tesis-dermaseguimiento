import { useLocalSearchParams } from 'expo-router';
import { useCallback, useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Text } from 'react-native';
import { Aviso, Boton, BotonInforme, COLOR, ImagenProtegida, Pantalla, Interpretacion, ResumenLesiones, ResumenManchas, ResumenOjeras, Subtitulo, Tarjeta, Titulo } from '../components/ui';
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
      <Titulo>Historial de seguimiento</Titulo>
      <Text style={{ color: '#666', marginBottom: 12 }}>Paciente: {nombre} {apellido}</Text>
      <CampoFecha etiqueta="Desde (opcional)" valor={desde} onCambio={setDesde} maximo={hasta || hoyTexto()} />
      <CampoFecha etiqueta="Hasta (opcional)" valor={hasta} onCambio={setHasta} minimo={desde || undefined} maximo={hoyTexto()} />
      <Boton texto="Filtrar" icono="filter-outline" variante="secundario" onPress={() => cargar(1)} />
      {error && <Aviso tipo="error" texto={error} />}
      {cargando && <ActivityIndicator size="large" color={COLOR.primario} style={{ marginVertical: 16 }} />}
      {!cargando && !error && items.length === 0 && <Text style={{ textAlign: 'center', color: '#666', marginTop: 24 }}>No hay seguimientos para mostrar.</Text>}
      {items.map((s) => (
        <Tarjeta key={s.id}>
          <Text style={{ fontWeight: '600', color: COLOR.primario }}>{fechaCorta(s.fecha)}</Text>
          <Interpretacion s={s} />
          <BotonInforme seguimientoId={s.id} />
          <ImagenProtegida url={s.url_imagen_alineada} />
          <Text style={{ marginTop: 8, color: '#444' }}>Puntos faciales: {s.landmarks_referencia} / {s.landmarks_nueva}</Text>
          <Subtitulo>Análisis colorimétrico (CIE L*a*b*)</Subtitulo>
          <Text>Delta E promedio (CIE76): {s.delta_e_promedio.toFixed(2)} — cambio {s.interpretacion?.magnitud_color ?? ''}</Text>
          <ImagenProtegida url={s.url_mapa_calor} />
          <ResumenLesiones s={s} />
          <ResumenOjeras s={s} />
          <ResumenManchas s={s} />
        </Tarjeta>
      ))}
      {items.length > 0 && items.length % TAM === 0 && !cargando && (
        <Boton texto="Cargar más" icono="chevron-down" variante="secundario" onPress={() => cargar(pagina + 1)} />
      )}
    </Pantalla>
  );
}
