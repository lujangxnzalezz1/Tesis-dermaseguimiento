import { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { API_URL, obtenerToken } from '../lib/auth';

type PacienteEncontrado = {
  id: number;
  cedula: string;
  nombre: string;
  apellido: string;
  telefono: string | null;
} | null;

export default function PacientesScreen() {
  const [cedula, setCedula] = useState('');
  const [buscando, setBuscando] = useState(false);
  const [yaSeBusco, setYaSeBusco] = useState(false);
  const [pacienteEncontrado, setPacienteEncontrado] = useState<PacienteEncontrado>(null);

  // Campos del formulario de registro (solo se muestran si el paciente no existe)
  const [nombre, setNombre] = useState('');
  const [apellido, setApellido] = useState('');
  const [telefono, setTelefono] = useState('');
  const [guardando, setGuardando] = useState(false);

  const buscarPaciente = async () => {
    if (!cedula) {
      Alert.alert('Falta la cédula', 'Ingresá un número de cédula para buscar.');
      return;
    }

    setBuscando(true);
    setYaSeBusco(false);

    try {
      const token = obtenerToken();
      const response = await fetch(`${API_URL}/pacientes/buscar/${cedula}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await response.json();

      if (data.existe) {
        setPacienteEncontrado(data.paciente);
      } else {
        setPacienteEncontrado(null);
      }
      setYaSeBusco(true);
    } catch (error) {
      console.error(error);
      Alert.alert('Error', 'No se pudo conectar con el servidor.');
    } finally {
      setBuscando(false);
    }
  };

  const registrarPaciente = async () => {
    if (!nombre || !apellido) {
      Alert.alert('Faltan datos', 'Nombre y apellido son obligatorios.');
      return;
    }

    setGuardando(true);

    try {
      const token = obtenerToken();
      const response = await fetch(`${API_URL}/pacientes`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          cedula,
          nombre,
          apellido,
          telefono: telefono || null,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        Alert.alert('Error', data.detail || 'No se pudo registrar el paciente.');
        return;
      }

      Alert.alert('¡Listo!', 'Paciente registrado correctamente.');
      setPacienteEncontrado(data);
      setNombre('');
      setApellido('');
      setTelefono('');
    } catch (error) {
      console.error(error);
      Alert.alert('Error', 'No se pudo conectar con el servidor.');
    } finally {
      setGuardando(false);
    }
  };

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.title}>Registro de Pacientes</Text>

      <Text style={styles.label}>Número de cédula</Text>
      <View style={styles.filaBusqueda}>
        <TextInput
          style={[styles.input, { flex: 1 }]}
          placeholder="Ej: 5649752"
          value={cedula}
          onChangeText={setCedula}
          keyboardType="numeric"
        />
        <TouchableOpacity style={styles.botonBuscar} onPress={buscarPaciente} disabled={buscando}>
          {buscando ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>Buscar</Text>}
        </TouchableOpacity>
      </View>

      {yaSeBusco && pacienteEncontrado && (
        <View style={styles.tarjetaEncontrado}>
          <Text style={styles.tarjetaTitulo}>Paciente encontrado</Text>
          <Text>Nombre: {pacienteEncontrado.nombre} {pacienteEncontrado.apellido}</Text>
          <Text>Teléfono: {pacienteEncontrado.telefono || 'No registrado'}</Text>
        </View>
      )}

      {yaSeBusco && !pacienteEncontrado && (
        <View style={styles.formularioNuevo}>
          <Text style={styles.tarjetaTitulo}>Paciente nuevo — completá los datos</Text>

          <Text style={styles.label}>Nombre</Text>
          <TextInput style={styles.input} value={nombre} onChangeText={setNombre} />

          <Text style={styles.label}>Apellido</Text>
          <TextInput style={styles.input} value={apellido} onChangeText={setApellido} />

          <Text style={styles.label}>Teléfono (opcional)</Text>
          <TextInput
            style={styles.input}
            value={telefono}
            onChangeText={setTelefono}
            keyboardType="phone-pad"
          />

          <TouchableOpacity style={styles.button} onPress={registrarPaciente} disabled={guardando}>
            {guardando ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.buttonText}>Registrar paciente</Text>
            )}
          </TouchableOpacity>
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flexGrow: 1, padding: 24, backgroundColor: '#fff' },
  title: { fontSize: 24, fontWeight: 'bold', color: '#1D3D47', marginBottom: 24 },
  label: { fontSize: 14, color: '#444', marginBottom: 6, marginTop: 12 },
  input: {
    borderWidth: 1,
    borderColor: '#ccc',
    borderRadius: 8,
    paddingHorizontal: 16,
    paddingVertical: 12,
    fontSize: 16,
  },
  filaBusqueda: { flexDirection: 'row', gap: 8, alignItems: 'stretch' },
  botonBuscar: {
    backgroundColor: '#1D3D47',
    borderRadius: 8,
    paddingHorizontal: 20,
    justifyContent: 'center',
    alignItems: 'center',
  },
  button: {
    backgroundColor: '#1D3D47',
    borderRadius: 8,
    paddingVertical: 14,
    alignItems: 'center',
    marginTop: 20,
  },
  buttonText: { color: '#fff', fontSize: 16, fontWeight: '600' },
  tarjetaEncontrado: {
    marginTop: 24,
    padding: 16,
    backgroundColor: '#E6F4FE',
    borderRadius: 8,
  },
  formularioNuevo: {
    marginTop: 24,
    padding: 16,
    backgroundColor: '#f7f7f7',
    borderRadius: 8,
  },
  tarjetaTitulo: { fontSize: 16, fontWeight: '600', marginBottom: 8, color: '#1D3D47' },
});
