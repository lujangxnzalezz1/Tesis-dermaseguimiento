import { Stack, router } from 'expo-router';
import { useEffect, useState } from 'react';
import { ActivityIndicator, View } from 'react-native';
import { cargarToken } from '../lib/auth';

export default function RootLayout() {
  const [listo, setListo] = useState(false);

  useEffect(() => {
    // Recupera la sesión guardada; si el servidor la considera vencida, la primera llamada devolverá 401
    // y la app volverá al inicio de sesión sola.
    cargarToken().then((t) => {
      setListo(true);
      if (t) setTimeout(() => router.replace('/pacientes'), 0);
    });
  }, []);

  if (!listo) {
    return (
      <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
        <ActivityIndicator size="large" color="#1D3D47" />
      </View>
    );
  }

  return (
    <Stack screenOptions={{ headerTintColor: '#1D3D47', headerBackTitle: 'Volver' }}>
      <Stack.Screen name="index" options={{ title: 'Ingresar', headerShown: false }} />
      <Stack.Screen name="registro" options={{ title: 'Crear cuenta' }} />
      <Stack.Screen name="recuperar" options={{ title: 'Recuperar contraseña' }} />
      <Stack.Screen name="restablecer" options={{ title: 'Nueva contraseña' }} />
      <Stack.Screen name="privacidad" options={{ title: 'Política de privacidad' }} />
      <Stack.Screen name="pacientes" options={{ title: 'Pacientes', headerBackVisible: false }} />
      <Stack.Screen name="procesamiento" options={{ title: 'Nuevo seguimiento' }} />
      <Stack.Screen name="historial" options={{ title: 'Historial' }} />
      <Stack.Screen name="suscripcion" options={{ title: 'Suscripción' }} />
      <Stack.Screen name="cuenta" options={{ title: 'Mi cuenta' }} />
      <Stack.Screen name="sus" options={{ title: 'Encuesta de usabilidad' }} />
      <Stack.Screen name="admin" options={{ title: 'Administración' }} />
    </Stack>
  );
}
