import { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  Alert,
  ActivityIndicator,
} from 'react-native';
import { router } from 'expo-router';
import { API_URL, guardarToken } from '../lib/auth';

export default function LoginScreen() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [cargando, setCargando] = useState(false);

  const handleLogin = async () => {
    if (!email || !password) {
      Alert.alert('Faltan datos', 'Completá correo y contraseña.');
      return;
    }

    setCargando(true);

    try {
      const body = new URLSearchParams();
      body.append('username', email);
      body.append('password', password);

      const response = await fetch(`${API_URL}/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: body.toString(),
      });

      const data = await response.json();

      if (!response.ok) {
        Alert.alert('Error al iniciar sesión', data.detail || 'Intentá de nuevo.');
        return;
      }

      guardarToken(data.access_token);
      router.replace('/pacientes');
    } catch (error) {
      console.error(error);
      Alert.alert(
        'No se pudo conectar',
        'Revisá que el backend esté corriendo y que el celular esté en la misma red WiFi que la Mac.'
      );
    } finally {
      setCargando(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <Text style={styles.title}>DermaSeguimiento</Text>
      <Text style={styles.subtitle}>Iniciá sesión para continuar</Text>

      <TextInput
        style={styles.input}
        placeholder="Correo electrónico"
        placeholderTextColor="#999"
        value={email}
        onChangeText={setEmail}
        autoCapitalize="none"
        keyboardType="email-address"
      />

      <TextInput
        style={styles.input}
        placeholder="Contraseña"
        placeholderTextColor="#999"
        value={password}
        onChangeText={setPassword}
        secureTextEntry
      />

      <TouchableOpacity style={styles.button} onPress={handleLogin} disabled={cargando}>
        {cargando ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>Ingresar</Text>}
      </TouchableOpacity>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', paddingHorizontal: 24, backgroundColor: '#fff' },
  title: { fontSize: 28, fontWeight: 'bold', textAlign: 'center', marginBottom: 8, color: '#1D3D47' },
  subtitle: { fontSize: 16, textAlign: 'center', marginBottom: 32, color: '#666' },
  input: {
    borderWidth: 1,
    borderColor: '#ccc',
    borderRadius: 8,
    paddingHorizontal: 16,
    paddingVertical: 12,
    marginBottom: 16,
    fontSize: 16,
  },
  button: {
    backgroundColor: '#1D3D47',
    borderRadius: 8,
    paddingVertical: 14,
    alignItems: 'center',
    marginTop: 8,
  },
  buttonText: { color: '#fff', fontSize: 16, fontWeight: '600' },
});
