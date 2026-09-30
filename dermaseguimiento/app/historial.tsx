import { useLocalSearchParams } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Text } from 'react-native';
import { Aviso, Boton, Campo, COLOR, ImagenProtegida, Pantalla, Subtitulo, Tarjeta, Titulo } from '../components/ui';
import { api, fechaCorta, mensaje } from '../lib/api';

const TAM = 10;

export default function HistorialScreen() {
  const { pacienteId, nombre, apellido } = useLocalSearchParams<{ pacienteId: string; nombre: string; apellido: string }>();
  const [items, setItems] = useState<any[]>([]);

  const [pagina, setPagina] = useState(1);
  const [desde, setDesde] = useState('');
  const [hasta, setHasta] = useState('');
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const cargar = useCallback(async (p: number) => {
    const re = /^\d{4}-\d{2}-\d{2}$/;
    if ((desde && !re.test(desde)) || (hasta && !re.test(hasta))) return setError('Las fechas deben tener el formato AAAA-MM-DD.');
    setError(null); setCargando(true);
    const qs = `pagina=${p}&tamano=${TAM}${desde ? `&desde=${desde}` : ''}${hasta ? `&hasta=${hasta}` : ''}`;
    const r = await api(`/pacientes/${pacienteId}/seguimientos?${qs}`);
    setCargando(false);
    if (!r.ok) return setError(mensaje(r, 'No se pudo cargar el historial.'));
    setItems((prev) => (p === 1 ? r.data : [...prev, ...r.data]));
    setPagina(p);
  }, [pacienteId, desde, hasta]);

  useEffect(() => { cargar(1); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <Pantalla>
      <Titulo>Historial de seguimiento</Titulo>
      <Text style={{ color: '#666', marginBottom: 12 }}>Paciente: {nombre} {apellido}</Text>
      <Campo etiqueta="Desde (opcional)" value={desde} onChangeText={setDesde} placeholder="AAAA-MM-DD" maxLength={10} />
      <Campo etiqueta="Hasta (opcional)" value={hasta} onChangeText={setHasta} placeholder="AAAA-MM-DD" maxLength={10} />
      <Boton texto="Filtrar" icono="filter-outline" variante="secundario" onPress={() => cargar(1)} />
      {error && <Aviso tipo="error" texto={error} />}
      {cargando && <ActivityIndicator size="large" color={COLOR.primario} style={{ marginVertical: 16 }} />}
      {!cargando && !error && items.length === 0 && <Text style={{ textAlign: 'center', color: '#666', marginTop: 24 }}>No hay seguimientos para mostrar.</Text>}
      {items.map((s) => (
        <Tarjeta key={s.id}>
          <Text style={{ fontWeight: '600', color: COLOR.primario }}>{fechaCorta(s.fecha)}</Text>
          <ImagenProtegida url={s.url_imagen_alineada} />
          <Text style={{ marginTop: 8, color: '#444' }}>Puntos faciales: {s.landmarks_referencia} / {s.landmarks_nueva}</Text>
          <Subtitulo>Análisis colorimétrico (CIE L*a*b*)</Subtitulo>
          <Text>Delta E promedio: {s.delta_e_promedio.toFixed(2)}</Text>
          <ImagenProtegida url={s.url_mapa_calor} />
        </Tarjeta>
      ))}
      {items.length > 0 && items.length % TAM === 0 && !cargando && (
        <Boton texto="Cargar más" icono="chevron-down" variante="secundario" onPress={() => cargar(pagina + 1)} />
      )}
    </Pantalla>
  );
}
