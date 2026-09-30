import * as ImagePicker from 'expo-image-picker';
import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Image, Text } from 'react-native';
import { avisar, elegirOrigenFoto } from '../lib/dialogo';
import { Aviso, Boton, ImagenProtegida, Pantalla, Subtitulo, Tarjeta, Titulo } from '../components/ui';
import { api, mensaje } from '../lib/api';

const MAX_MB = 10;
type Imagen = { uri: string; nombre: string; tipo: string } | null;

function extraer(resultado: ImagePicker.ImagePickerResult): { imagen: Imagen; error?: string } {
  if (resultado.canceled || !resultado.assets?.length) return { imagen: null };
  const a = resultado.assets[0];
  const tipo = (a.mimeType || 'image/jpeg').toLowerCase();
  if (!['image/jpeg', 'image/jpg', 'image/png', 'image/webp'].includes(tipo)) {
    return { imagen: null, error: 'Ese formato no está permitido. Usá una foto JPG, PNG o WEBP.' };
  }
  if (a.fileSize && a.fileSize > MAX_MB * 1024 * 1024) {
    return { imagen: null, error: `La foto pesa más de ${MAX_MB} MB. Sacala con menor resolución.` };
  }
  return { imagen: { uri: a.uri, nombre: a.fileName || a.uri.split('/').pop() || 'foto.jpg', tipo } };
}

async function elegir(origen: 'galeria' | 'camara') {
  const permiso = origen === 'galeria' ? await ImagePicker.requestMediaLibraryPermissionsAsync() : await ImagePicker.requestCameraPermissionsAsync();
  if (!permiso.granted) {
    avisar('Permiso necesario', origen === 'galeria' ? 'Necesitamos acceso a tus fotos para continuar.' : 'Necesitamos acceso a la cámara para continuar.');
    return { imagen: null };
  }
  const opciones: ImagePicker.ImagePickerOptions = { mediaTypes: ['images'], quality: 0.8 };
  return extraer(origen === 'galeria' ? await ImagePicker.launchImageLibraryAsync(opciones) : await ImagePicker.launchCameraAsync(opciones));
}

export default function ProcesamientoScreen() {
  const { pacienteId, nombre, apellido } = useLocalSearchParams<{ pacienteId: string; nombre: string; apellido: string }>();
  const [ref, setRef] = useState<Imagen>(null);
  const [nueva, setNueva] = useState<Imagen>(null);
  const [procesando, setProcesando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sinPlan, setSinPlan] = useState(false);
  const [res, setRes] = useState<any>(null);

  const pedir = (poner: (i: Imagen) => void) =>
    elegirOrigenFoto(async (origen) => {
      const r = await elegir(origen);
      if (r.error) setError(r.error);
      else if (r.imagen) { setError(null); poner(r.imagen); }
    });

  const procesar = async () => {
    setError(null); setSinPlan(false);
    if (!ref || !nueva) return setError('Seleccioná la imagen de referencia y la nueva captura antes de procesar.');
    setProcesando(true); setRes(null);
    const fd = new FormData();
    fd.append('paciente_id', pacienteId);
    fd.append('imagen_referencia', { uri: ref.uri, name: ref.nombre, type: ref.tipo } as any);
    fd.append('imagen_nueva', { uri: nueva.uri, name: nueva.nombre, type: nueva.tipo } as any);
    const r = await api('/procesar-seguimiento', { method: 'POST', multipart: fd });
    setProcesando(false);
    if (!r.ok) {
      setSinPlan(r.status === 402);
      return setError(mensaje(r, 'No se pudo procesar. Intentá de nuevo.'));
    }
    setRes(r.data);
  };

  return (
    <Pantalla>
      <Titulo>Nuevo seguimiento</Titulo>
      <Text style={{ color: '#666', marginBottom: 12 }}>Paciente: {nombre} {apellido}</Text>
      <Aviso tipo="info" texto="Los resultados son informativos y de apoyo a la documentación clínica. La interpretación clínica corresponde exclusivamente al profesional médico habilitado." />
      {error && <Aviso tipo="error" texto={error} />}
      {sinPlan && <Boton texto="Ver planes y suscripción" icono="card-outline" onPress={() => router.push('/suscripcion')} />}

      <Subtitulo>Imagen de referencia</Subtitulo>
      <Boton texto={ref ? 'Cambiar imagen' : 'Elegir imagen de referencia'} icono="image-outline" onPress={() => pedir(setRef)} />
      {ref && <Image source={{ uri: ref.uri }} style={{ width: '100%', height: 220, borderRadius: 8, marginTop: 10 }} />}
      <Subtitulo>Nueva captura</Subtitulo>
      <Boton texto={nueva ? 'Cambiar imagen' : 'Elegir nueva captura'} icono="camera-outline" onPress={() => pedir(setNueva)} />
      {nueva && <Image source={{ uri: nueva.uri }} style={{ width: '100%', height: 220, borderRadius: 8, marginTop: 10 }} />}

      <Boton texto="Procesar imágenes" icono="play-circle-outline" estilo={{ marginTop: 20 }} onPress={procesar} cargando={procesando} />

      {res && (
        <Tarjeta>
          <Subtitulo>Resultado</Subtitulo>
          <Text>Puntos faciales: {res.landmarks_referencia} (referencia) / {res.landmarks_nueva} (nueva)</Text>
          <ImagenProtegida url={res.url_imagen_alineada} />
          <Subtitulo>Análisis colorimétrico (CIE L*a*b*)</Subtitulo>
          <Text>Delta E promedio: {res.delta_e_promedio.toFixed(2)}</Text>
          {res.tiempo_procesamiento_ms != null && <Text style={{ color: '#666' }}>Procesado en {(res.tiempo_procesamiento_ms / 1000).toFixed(1)} s</Text>}
          <ImagenProtegida url={res.url_mapa_calor} />
        </Tarjeta>
      )}
    </Pantalla>
  );
}
