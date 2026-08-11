import { useCallback, useState } from 'react';
import {
  View,
  Text,
  Image,
  StyleSheet,
  FlatList,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { useFocusEffect, useLocalSearchParams } from 'expo-router';
import { API_URL, obtenerToken } from '../lib/auth';

type Seguimiento = {
  id: number;
  fecha: string;
  landmarks_referencia: number;
  landmarks_nueva: number;
  url_imagen_alineada: string;
  url_mapa_calor: string;
  delta_e_promedio: number;
};

export default function HistorialScreen() {
  const { pacienteId, nombre, apellido } = useLocalSearchParams<{
    pacienteId: string;
    nombre: string;
    apellido: string;
  }>();

  const [seguimientos, setSeguimientos] = useState<Seguimiento[]>([]);
  const [cargando, setCargando] = useState(true);

  const cargarHistorial = useCallback(async () => {
    setCargando(true);
    try {
      const token = obtenerToken();
      const response = await fetch(`${API_URL}/pacientes/${pacienteId}/seguimientos`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await response.json();

      if (!response.ok) {
        Alert.alert('Error', 'No se pudo cargar el historial.');
        return;
      }

      setSeguimientos(data);
    } catch (error) {
      console.error(error);
      Alert.alert('No se pudo conectar', 'Revisá que el backend esté corriendo y accesible.');
    } finally {
      setCargando(false);
    }
  }, [pacienteId]);

  useFocusEffect(
    useCallback(() => {
      cargarHistorial();
    }, [cargarHistorial])
  );

  if (cargando) {
    return (
      <View style={styles.centrado}>
        <ActivityIndicator size="large" color="#1D3D47" />
      </View>
    );
  }

  return (
    <FlatList
      contentContainerStyle={styles.container}
      data={seguimientos}
      keyExtractor={(item) => String(item.id)}
      ListHeaderComponent={
        <>
          <Text style={styles.title}>Historial de seguimiento</Text>
          <Text style={styles.subtitle}>
            Paciente: {nombre} {apellido}
          </Text>
        </>
      }
      ListEmptyComponent={
        <Text style={styles.vacio}>Todavía no hay seguimientos registrados para este paciente.</Text>
      }
      renderItem={({ item }) => (
        <View style={styles.tarjeta}>
          <Text style={styles.fecha}>{new Date(item.fecha).toLocaleString()}</Text>
          <Image source={{ uri: `${API_URL}${item.url_imagen_alineada}` }} style={styles.preview} />
          <Text style={styles.detalle}>
            Landmarks: {item.landmarks_referencia} (referencia) / {item.landmarks_nueva} (nueva)
          </Text>

          <Text style={styles.subtitulo}>Análisis colorimétrico (CIE L*a*b*)</Text>
          <Text style={styles.detalle}>Delta E promedio: {item.delta_e_promedio.toFixed(2)}</Text>
          <Image source={{ uri: `${API_URL}${item.url_mapa_calor}` }} style={styles.preview} />
        </View>
      )}
    />
  );
}

const styles = StyleSheet.create({
  container: { flexGrow: 1, padding: 24, backgroundColor: '#fff' },
  centrado: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#fff' },
  title: { fontSize: 24, fontWeight: 'bold', color: '#1D3D47', marginBottom: 4 },
  subtitle: { fontSize: 16, color: '#666', marginBottom: 24 },
  vacio: { fontSize: 15, color: '#666', textAlign: 'center', marginTop: 32 },
  tarjeta: {
    marginBottom: 20,
    padding: 16,
    backgroundColor: '#E6F4FE',
    borderRadius: 8,
  },
  fecha: { fontSize: 14, fontWeight: '600', color: '#1D3D47', marginBottom: 8 },
  subtitulo: { fontSize: 14, fontWeight: '600', color: '#1D3D47', marginTop: 16, marginBottom: 4 },
  preview: {
    width: '100%',
    height: 220,
    borderRadius: 8,
    backgroundColor: '#eee',
  },
  detalle: { fontSize: 13, color: '#444', marginTop: 8 },
});
