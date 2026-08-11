import { useState } from 'react';
import {
  View,
  Text,
  Image,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  Alert,
  ActivityIndicator,
} from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import { useLocalSearchParams } from 'expo-router';
import { API_URL, obtenerToken } from '../lib/auth';

type ImagenSeleccionada = {
  uri: string;
  nombre: string;
  tipo: string;
} | null;

function extraerImagenSeleccionada(
  resultado: ImagePicker.ImagePickerResult
): ImagenSeleccionada {
  if (resultado.canceled || !resultado.assets?.length) {
    return null;
  }

  const asset = resultado.assets[0];
  const nombre = asset.fileName || asset.uri.split('/').pop() || 'foto.jpg';
  const tipo = asset.mimeType || 'image/jpeg';

  return { uri: asset.uri, nombre, tipo };
}

async function elegirDeGaleria(): Promise<ImagenSeleccionada> {
  const permiso = await ImagePicker.requestMediaLibraryPermissionsAsync();
  if (!permiso.granted) {
    Alert.alert('Permiso necesario', 'Necesitamos acceso a tus fotos para continuar.');
    return null;
  }

  const resultado = await ImagePicker.launchImageLibraryAsync({
    mediaTypes: ['images'],
    quality: 0.8,
  });

  return extraerImagenSeleccionada(resultado);
}

async function tomarFoto(): Promise<ImagenSeleccionada> {
  const permiso = await ImagePicker.requestCameraPermissionsAsync();
  if (!permiso.granted) {
    Alert.alert('Permiso necesario', 'Necesitamos acceso a la cámara para continuar.');
    return null;
  }

  const resultado = await ImagePicker.launchCameraAsync({
    mediaTypes: ['images'],
    quality: 0.8,
  });

  return extraerImagenSeleccionada(resultado);
}

function elegirOrigenImagen(
  onElegido: (imagen: ImagenSeleccionada) => void
) {
  Alert.alert('Seleccionar imagen', '¿De dónde querés obtener la foto?', [
    { text: 'Cancelar', style: 'cancel' },
    { text: 'Galería', onPress: async () => onElegido(await elegirDeGaleria()) },
    { text: 'Cámara', onPress: async () => onElegido(await tomarFoto()) },
  ]);
}

export default function ProcesamientoScreen() {
  const { pacienteId, nombre, apellido } = useLocalSearchParams<{
    pacienteId: string;
    nombre: string;
    apellido: string;
  }>();

  const [imagenReferencia, setImagenReferencia] = useState<ImagenSeleccionada>(null);
  const [imagenNueva, setImagenNueva] = useState<ImagenSeleccionada>(null);
  const [procesando, setProcesando] = useState(false);
  const [resultado, setResultado] = useState<{
    landmarksReferencia: number;
    landmarksNueva: number;
    urlImagenAlineada: string;
    urlMapaCalor: string;
    deltaEPromedio: number;
  } | null>(null);

  const procesarImagenes = async () => {
    if (!imagenReferencia || !imagenNueva) {
      Alert.alert('Faltan imágenes', 'Seleccioná la imagen de referencia y la nueva captura.');
      return;
    }

    setProcesando(true);
    setResultado(null);

    try {
      const token = obtenerToken();
      const formData = new FormData();
      formData.append('paciente_id', pacienteId);
      formData.append('imagen_referencia', {
        uri: imagenReferencia.uri,
        name: imagenReferencia.nombre,
        type: imagenReferencia.tipo,
      } as any);
      formData.append('imagen_nueva', {
        uri: imagenNueva.uri,
        name: imagenNueva.nombre,
        type: imagenNueva.tipo,
      } as any);

      const response = await fetch(`${API_URL}/procesar-seguimiento`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'multipart/form-data',
        },
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        Alert.alert('Error al procesar', data.detail || 'Intentá de nuevo.');
        return;
      }

      setResultado({
        landmarksReferencia: data.landmarks_referencia,
        landmarksNueva: data.landmarks_nueva,
        urlImagenAlineada: `${API_URL}${data.url_imagen_alineada}`,
        urlMapaCalor: `${API_URL}${data.url_mapa_calor}`,
        deltaEPromedio: data.delta_e_promedio,
      });
    } catch (error) {
      console.error(error);
      Alert.alert('No se pudo conectar', 'Revisá que el backend esté corriendo y accesible.');
    } finally {
      setProcesando(false);
    }
  };

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.title}>Nuevo seguimiento</Text>
      <Text style={styles.subtitle}>
        Paciente: {nombre} {apellido}
      </Text>

      <Text style={styles.label}>Imagen de referencia</Text>
      <TouchableOpacity
        style={styles.botonImagen}
        onPress={() => elegirOrigenImagen(setImagenReferencia)}
      >
        <Text style={styles.buttonText}>
          {imagenReferencia ? 'Cambiar imagen' : 'Elegir imagen de referencia'}
        </Text>
      </TouchableOpacity>
      {imagenReferencia && (
        <Image source={{ uri: imagenReferencia.uri }} style={styles.preview} />
      )}

      <Text style={styles.label}>Nueva captura</Text>
      <TouchableOpacity
        style={styles.botonImagen}
        onPress={() => elegirOrigenImagen(setImagenNueva)}
      >
        <Text style={styles.buttonText}>
          {imagenNueva ? 'Cambiar imagen' : 'Elegir nueva captura'}
        </Text>
      </TouchableOpacity>
      {imagenNueva && <Image source={{ uri: imagenNueva.uri }} style={styles.preview} />}

      <TouchableOpacity style={styles.button} onPress={procesarImagenes} disabled={procesando}>
        {procesando ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.buttonText}>Procesar imágenes</Text>
        )}
      </TouchableOpacity>

      {resultado && (
        <View style={styles.tarjetaResultado}>
          <Text style={styles.tarjetaTitulo}>Resultado</Text>
          <Text>Landmarks referencia: {resultado.landmarksReferencia}</Text>
          <Text>Landmarks nueva: {resultado.landmarksNueva}</Text>
          <Image source={{ uri: resultado.urlImagenAlineada }} style={styles.preview} />

          <Text style={styles.tarjetaTitulo}>Análisis colorimétrico (CIE L*a*b*)</Text>
          <Text>Delta E promedio: {resultado.deltaEPromedio.toFixed(2)}</Text>
          <Image source={{ uri: resultado.urlMapaCalor }} style={styles.preview} />
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flexGrow: 1, padding: 24, backgroundColor: '#fff' },
  title: { fontSize: 24, fontWeight: 'bold', color: '#1D3D47', marginBottom: 4 },
  subtitle: { fontSize: 16, color: '#666', marginBottom: 24 },
  label: { fontSize: 14, color: '#444', marginBottom: 6, marginTop: 16 },
  botonImagen: {
    backgroundColor: '#1D3D47',
    borderRadius: 8,
    paddingVertical: 12,
    alignItems: 'center',
  },
  button: {
    backgroundColor: '#1D3D47',
    borderRadius: 8,
    paddingVertical: 14,
    alignItems: 'center',
    marginTop: 24,
  },
  buttonText: { color: '#fff', fontSize: 16, fontWeight: '600' },
  preview: {
    width: '100%',
    height: 220,
    borderRadius: 8,
    marginTop: 12,
    backgroundColor: '#eee',
  },
  tarjetaResultado: {
    marginTop: 24,
    padding: 16,
    backgroundColor: '#E6F4FE',
    borderRadius: 8,
  },
  tarjetaTitulo: { fontSize: 16, fontWeight: '600', marginBottom: 8, color: '#1D3D47' },
});
