import { Ionicons } from '@expo/vector-icons';
import { CameraView, useCameraPermissions } from 'expo-camera';
import * as ImagePicker from 'expo-image-picker';
import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Image, Platform, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { Aviso, Boton, COLOR, ImagenProtegida } from '../components/ui';
import { api, mensaje } from '../lib/api';
import { dejarFoto } from '../lib/capturaStore';

type Control = { codigo: string; nivel: 'ok' | 'aviso' | 'error'; mensaje: string };
type Resultado = { apta: boolean; controles: Control[] };

const OPACIDADES = [0, 0.35, 0.6];
const ICONO = { ok: 'checkmark-circle', aviso: 'warning', error: 'close-circle' } as const;
const COLOR_NIVEL = { ok: COLOR.ok, aviso: COLOR.aviso, error: COLOR.error };

/** En web, expo-camera guarda espejada la foto de la cámara frontal (como la vista previa). Para el análisis
 *  la foto tiene que estar en su orientación real: si no, se compararía la mejilla izquierda con la derecha. */
async function desespejar(uri: string): Promise<string> {
  const img = new window.Image();
  img.src = uri;
  await img.decode();
  const canvas = document.createElement('canvas');
  canvas.width = img.naturalWidth;
  canvas.height = img.naturalHeight;
  const ctx = canvas.getContext('2d');
  if (!ctx) return uri;
  ctx.setTransform(-1, 0, 0, 1, canvas.width, 0);
  ctx.drawImage(img, 0, 0);
  return canvas.toDataURL('image/jpeg', 0.9);
}

/** Cámara con guía de captura (RF-03): óvalo para encuadrar, silueta semitransparente de la
 *  primera consulta y control de calidad automático antes de usar la foto. */
export default function CapturaScreen() {
  const { pacienteId, destino = 'nueva' } = useLocalSearchParams<{ pacienteId: string; destino?: 'referencia' | 'nueva' }>();
  const [permiso, pedirPermiso] = useCameraPermissions();
  const camara = useRef<CameraView>(null);
  const [lista, setLista] = useState(false);
  const [referencia, setReferencia] = useState<string | null>(null);
  const [opacidad, setOpacidad] = useState(1);
  const [foto, setFoto] = useState<string | null>(null);
  const [verificando, setVerificando] = useState(false);
  const [resultado, setResultado] = useState<Resultado | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lado, setLado] = useState<'back' | 'front'>('back');

  useEffect(() => {
    if (destino !== 'nueva' || !pacienteId) return;
    api(`/pacientes/${pacienteId}/referencia`).then((r) => r.ok && r.data.existe && setReferencia(r.data.url));
  }, [pacienteId, destino]);

  const sacar = async () => {
    setError(null);
    try {
      const f = await camara.current?.takePictureAsync({ quality: 0.85 });
      if (!f?.uri) return setError('No se pudo tomar la foto. Intentá de nuevo.');
      const uri = Platform.OS === 'web' && lado === 'front' ? await desespejar(f.uri) : f.uri;
      setFoto(uri);
      verificar(uri);
    } catch {
      setError('La cámara no respondió. Cerrá esta pantalla y volvé a abrirla.');
    }
  };

  const verificar = async (uri: string) => {
    setVerificando(true);
    setResultado(null);
    const fd = new FormData();
    if (Platform.OS === 'web') {
      const blob = await (await fetch(uri)).blob();
      fd.append('imagen', blob, 'captura.jpg');
    } else {
      fd.append('imagen', { uri, name: 'captura.jpg', type: 'image/jpeg' } as any);
    }
    if (pacienteId && destino === 'nueva') fd.append('paciente_id', pacienteId);
    const r = await api('/verificar-captura', { method: 'POST', multipart: fd });
    setVerificando(false);
    if (!r.ok) return setError(mensaje(r, 'No pudimos revisar la foto. Podés repetirla o usarla igual.'));
    setResultado(r.data);
  };

  const usar = () => {
    if (!foto) return;
    dejarFoto(destino, { uri: foto, nombre: 'captura.jpg', tipo: 'image/jpeg' });
    router.back();
  };

  const repetir = () => {
    setFoto(null);
    setResultado(null);
    setError(null);
  };

  // En el navegador, la cámara en vivo solo funciona en páginas seguras (https o localhost). Desde el
  // celular por http://IP-de-la-red no está disponible: se usa la cámara nativa del teléfono.
  const sinCamaraEnVivo = Platform.OS === 'web' && typeof window !== 'undefined' && !window.isSecureContext;

  const camaraNativa = async () => {
    setError(null);
    const r = await ImagePicker.launchCameraAsync({
      mediaTypes: ['images'], quality: 0.85,
      cameraType: lado === 'front' ? ImagePicker.CameraType.front : ImagePicker.CameraType.back,
    });
    if (r.canceled || !r.assets?.length) return;
    setFoto(r.assets[0].uri);
    verificar(r.assets[0].uri);
  };

  if (sinCamaraEnVivo && !foto) {
    return (
      <ScrollView contentContainerStyle={{ padding: 20, maxWidth: 640, width: '100%', alignSelf: 'center' }}>
        <Aviso tipo="info" texto="En esta conexión el navegador no permite la vista de cámara con la guía. Se abre la cámara del celular; después la app revisa si la foto sirve." />
        <Text style={{ marginVertical: 12, lineHeight: 21 }}>
          Para una buena foto: el rostro completo y centrado, de frente, con el pelo recogido, sin flash y con la misma luz y lugar que la consulta anterior.
        </Text>
        {referencia && (
          <>
            <Text style={{ fontWeight: '600', color: COLOR.primario }}>Foto de la consulta anterior (repetí esta pose y distancia):</Text>
            <ImagenProtegida url={referencia} />
          </>
        )}
        {error && <Aviso tipo="error" texto={error} />}
        <Boton texto={lado === 'front' ? 'Cámara frontal (selfie) ✓' : 'Usar la cámara frontal (selfie)'} icono="camera-reverse-outline"
          variante="secundario" estilo={{ marginTop: 16 }} onPress={() => setLado((l) => (l === 'back' ? 'front' : 'back'))} />
        <Boton texto="Abrir la cámara del celular" icono="camera" estilo={{ marginTop: 8 }} onPress={camaraNativa} />
      </ScrollView>
    );
  }

  if (!permiso) return <View style={e.centro}><ActivityIndicator color={COLOR.primario} /></View>;
  if (!permiso.granted) {
    return (
      <View style={[e.centro, { padding: 24 }]}>
        <Text style={{ textAlign: 'center', marginBottom: 16 }}>Necesitamos acceso a la cámara para tomar la foto de seguimiento.</Text>
        <Boton texto="Permitir la cámara" icono="camera-outline" onPress={async () => {
          const r = await pedirPermiso();
          if (!r.granted) setError('No se pudo activar la cámara. Revisá los permisos del navegador o usá la cámara del celular.');
        }} />
        {error && <Aviso tipo="error" texto={error} />}
        <Boton texto="Usar la cámara del celular" icono="camera" variante="texto" onPress={camaraNativa} />
      </View>
    );
  }

  // ---------------------------------------------------------------- revisión de la foto tomada
  if (foto) {
    return (
      <ScrollView contentContainerStyle={{ padding: 20, maxWidth: 640, width: '100%', alignSelf: 'center' }}>
        <Image source={{ uri: foto }} style={{ width: '100%', height: 320, borderRadius: 8, backgroundColor: '#000' }} resizeMode="contain" />
        {verificando && <View style={{ marginTop: 16, alignItems: 'center' }}><ActivityIndicator color={COLOR.primario} /><Text>Revisando la foto…</Text></View>}
        {error && <Aviso tipo="error" texto={error} />}
        {resultado && (
          <>
            <Aviso tipo={resultado.apta ? 'ok' : 'error'} texto={resultado.apta
              ? 'La foto sirve para el seguimiento.'
              : 'Esta foto no es confiable para comparar. Corregí lo marcado en rojo y repetila.'} />
            {resultado.controles.map((c) => (
              <View key={c.codigo} style={e.control}>
                <Ionicons name={ICONO[c.nivel]} size={20} color={COLOR_NIVEL[c.nivel]} />
                <Text style={{ flex: 1 }}>{c.mensaje}</Text>
              </View>
            ))}
          </>
        )}
        {resultado?.apta || error ? (
          <>
            <Boton texto="Usar esta foto" icono="checkmark" estilo={{ marginTop: 16 }} onPress={usar} />
            <Boton texto="Repetir la foto" icono="refresh" variante="secundario" estilo={{ marginTop: 8 }} onPress={repetir} />
          </>
        ) : resultado ? (
          <>
            <Boton texto="Repetir la foto" icono="refresh" estilo={{ marginTop: 16 }} onPress={repetir} />
            <Boton texto="Usarla de todos modos" icono="alert-circle-outline" variante="texto" onPress={usar} />
          </>
        ) : null}
      </ScrollView>
    );
  }

  // ---------------------------------------------------------------- cámara con guía
  return (
    <View style={{ flex: 1, backgroundColor: '#000' }}>
      {/* mirror={false}: la foto guardada no sale espejada aunque la vista previa de la frontal sí lo esté */}
      <CameraView key={lado} ref={camara} style={StyleSheet.absoluteFill} facing={lado} mirror={false}
        onCameraReady={() => setLista(true)} />
      {referencia && opacidad > 0 && (
        <View pointerEvents="none" style={StyleSheet.absoluteFill}>
          <ImagenProtegida url={referencia} estilo={[StyleSheet.absoluteFill, {
            height: '100%', marginTop: 0, backgroundColor: 'transparent', opacity: OPACIDADES[opacidad],
            // la vista previa de la frontal es un espejo: la silueta se invierte para coincidir
            transform: lado === 'front' ? [{ scaleX: -1 }] : [],
          }]} />
        </View>
      )}
      <View pointerEvents="none" style={[StyleSheet.absoluteFill, e.centro]}>
        <View style={e.ovalo} />
      </View>
      <View style={e.instrucciones}>
        <Text style={e.textoGuia}>
          Encuadrá el rostro dentro del óvalo, de frente, con el pelo recogido y sin flash.
          {referencia ? ' Hacé coincidir la cara con la silueta de la consulta anterior.' : ''}
        </Text>
      </View>
      <View style={e.barra}>
        {referencia && (
          <TouchableOpacity accessibilityRole="button" accessibilityLabel="Cambiar la transparencia de la referencia"
            onPress={() => setOpacidad((o) => (o + 1) % OPACIDADES.length)} style={e.botonChico}>
            <Ionicons name="layers-outline" size={20} color="#fff" />
            <Text style={e.textoChico}>{opacidad === 0 ? 'Referencia: oculta' : `Referencia: ${Math.round(OPACIDADES[opacidad] * 100)} %`}</Text>
          </TouchableOpacity>
        )}
        <TouchableOpacity accessibilityRole="button" accessibilityLabel="Cambiar de cámara"
          onPress={() => { setLista(false); setLado((l) => (l === 'back' ? 'front' : 'back')); }} style={e.botonChico}>
          <Ionicons name="camera-reverse-outline" size={20} color="#fff" />
          <Text style={e.textoChico}>{lado === 'back' ? 'Cambiar a cámara frontal' : 'Cambiar a cámara trasera'}</Text>
        </TouchableOpacity>
        <TouchableOpacity accessibilityRole="button" accessibilityLabel="Tomar foto" onPress={sacar} disabled={!lista} style={[e.disparador, !lista && { opacity: 0.5 }]}>
          <Ionicons name="camera" size={30} color={COLOR.primario} />
          <Text style={{ color: COLOR.primario, fontWeight: '700', fontSize: 12 }}>Tomar foto</Text>
        </TouchableOpacity>
      </View>
      {error && <View style={{ position: 'absolute', top: 90, left: 16, right: 16 }}><Aviso tipo="error" texto={error} /></View>}
    </View>
  );
}

const e = StyleSheet.create({
  centro: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  ovalo: { width: '68%', maxWidth: 360, aspectRatio: 0.75, borderRadius: 999, borderWidth: 3, borderColor: '#fff', borderStyle: 'dashed' },
  instrucciones: { position: 'absolute', top: 16, left: 16, right: 16, backgroundColor: '#000a', borderRadius: 8, padding: 10 },
  textoGuia: { color: '#fff', textAlign: 'center', fontSize: 14 },
  barra: { position: 'absolute', bottom: 24, left: 0, right: 0, alignItems: 'center', gap: 12 },
  disparador: { width: 86, height: 86, borderRadius: 43, backgroundColor: '#fff', alignItems: 'center', justifyContent: 'center' },
  botonChico: { flexDirection: 'row', gap: 6, alignItems: 'center', backgroundColor: '#000a', paddingHorizontal: 12, paddingVertical: 8, borderRadius: 16 },
  textoChico: { color: '#fff', fontSize: 13 },
  control: { flexDirection: 'row', gap: 8, alignItems: 'flex-start', paddingVertical: 6, borderBottomWidth: 1, borderColor: '#eee' },
});
