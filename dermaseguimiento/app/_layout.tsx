import { COLOR, FUENTE } from '../components/ui';
import { Figtree_400Regular, Figtree_500Medium, Figtree_600SemiBold } from '@expo-google-fonts/figtree';
import { Outfit_600SemiBold, Outfit_700Bold } from '@expo-google-fonts/outfit';
import { useFonts } from 'expo-font';
import { Stack } from 'expo-router';
import { useEffect, useState } from 'react';
import { ActivityIndicator, View } from 'react-native';
import { cargarToken } from '../lib/auth';
import { iniciarPush } from '../lib/push';

export default function RootLayout() {
  const [listo, setListo] = useState(false);
  const [fuentes] = useFonts({ Outfit_600SemiBold, Outfit_700Bold, Figtree_400Regular, Figtree_500Medium, Figtree_600SemiBold });

  useEffect(() => {
    // Recupera la sesión guardada antes de mostrar cualquier pantalla. Si el servidor la considera
    // vencida, la primera llamada devolverá 401 y la app volverá sola al inicio de sesión.
    cargarToken().then(() => setListo(true));
    iniciarPush();
  }, []);

  if (!listo || !fuentes) {
    return (
      <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: COLOR.fondo }}>
        <ActivityIndicator size="large" color="#1D3D47" />
      </View>
    );
  }

  return (
    <Stack screenOptions={{
      headerTintColor: COLOR.primario, headerBackTitle: 'Volver', headerShadowVisible: false,
      headerStyle: { backgroundColor: COLOR.fondo }, contentStyle: { backgroundColor: COLOR.fondo },
      headerTitleStyle: { fontFamily: FUENTE.titulo, fontSize: 18, color: COLOR.texto }, headerTitleAlign: 'center',
    }}>
      <Stack.Screen name="index" options={{ title: 'Ingresar', headerShown: false }} />
      <Stack.Screen name="registro" options={{ title: 'Crear cuenta' }} />
      <Stack.Screen name="recuperar" options={{ title: 'Recuperar contraseña' }} />
      <Stack.Screen name="restablecer" options={{ title: 'Nueva contraseña' }} />
      <Stack.Screen name="privacidad" options={{ title: 'Política de privacidad' }} />
      <Stack.Screen name="pacientes" options={{ title: 'Pacientes', headerBackVisible: false }} />
      <Stack.Screen name="procesamiento" options={{ title: 'Nuevo seguimiento' }} />
      <Stack.Screen name="captura" options={{ title: 'Tomar foto con guía' }} />
      <Stack.Screen name="historial" options={{ title: 'Historial' }} />
      <Stack.Screen name="suscripcion" options={{ title: 'Suscripción' }} />
      <Stack.Screen name="cuenta" options={{ title: 'Mi cuenta' }} />
      <Stack.Screen name="sus" options={{ title: 'Encuesta de usabilidad' }} />
      <Stack.Screen name="admin" options={{ title: 'Administración' }} />
    </Stack>
  );
}
