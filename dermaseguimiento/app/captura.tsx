import { Ionicons } from '@expo/vector-icons';
import { CameraView, useCameraPermissions } from 'expo-camera';
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

  useEffect(() => {
    if (destino !== 'nueva' || !pacienteId) return;
    api(`/pacientes/${pacienteId}/referencia`).then((r) => r.ok && r.data.existe && setReferencia(r.data.url));
  }, [pacienteId, destino]);

  const sacar = async () => {
    setError(null);
    try {
      const f = await camara.current?.takePictureAsync({ quality: 0.85 });
      if (!f?.uri) return setError('No se pudo tomar la foto. Intentá de nuevo.');
      setFoto(f.uri);
      verificar(f.uri);
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

  if (!permiso) return <View style={e.centro}><ActivityIndicator color={COLOR.primario} /></View>;
  if (!permiso.granted) {
    return (
      <View style={[e.centro, { padding: 24 }]}>
        <Text style={{ textAlign: 'center', marginBottom: 16 }}>Necesitamos acceso a la cámara para tomar la foto de seguimiento.</Text>
        <Boton texto="Permitir la cámara" icono="camera-outline" onPress={pedirPermiso} />
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
      <CameraView ref={camara} style={StyleSheet.absoluteFill} facing="back" onCameraReady={() => setLista(true)} />
      {referencia && opacidad > 0 && (
        <View pointerEvents="none" style={StyleSheet.absoluteFill}>
          <ImagenProtegida url={referencia} estilo={[StyleSheet.absoluteFill, { height: '100%', marginTop: 0, backgroundColor: 'transparent', opacity: OPACIDADES[opacidad] }]} />
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
