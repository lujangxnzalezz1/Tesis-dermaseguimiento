import { COLOR, FUENTE } from '../components/ui';
import { Figtree_400Regular, Figtree_500Medium, Figtree_600SemiBold } from '@expo-google-fonts/figtree';
import { Outfit_600SemiBold, Outfit_700Bold } from '@expo-google-fonts/outfit';
import { useFonts } from 'expo-font';
import { router, Stack, useRootNavigationState, useSegments } from 'expo-router';
import { useEffect, useState } from 'react';
import { ActivityIndicator, View } from 'react-native';
import { rolDeSesion } from '../lib/api';
import { cargarToken, obtenerToken } from '../lib/auth';
import { iniciarPush } from '../lib/push';

// Pantallas que se pueden ver sin sesión. Todas las demás exigen sesión y «admin» exige el rol admin.
// Es solo para la navegación: el servidor verifica sesión y permisos en cada operación.
const RUTAS_PUBLICAS = new Set(['index', 'registro', 'recuperar', 'restablecer', 'privacidad', 'planes']);
const RUTAS_SOLO_ADMIN = new Set(['admin']);

export default function RootLayout() {
  const [listo, setListo] = useState(false);
  const [fuentes] = useFonts({ Outfit_600SemiBold, Outfit_700Bold, Figtree_400Regular, Figtree_500Medium, Figtree_600SemiBold });
  const segmentos = useSegments();
  const navegacion = useRootNavigationState();

  useEffect(() => {
    // Recupera la sesión guardada antes de mostrar cualquier pantalla. Si el servidor la considera
    // vencida, la primera llamada devolverá 401 y la app volverá sola al inicio de sesión.
    cargarToken().then(() => setListo(true));
    iniciarPush();
  }, []);

  // Guardia de rutas: sin sesión, solo las públicas; la administración, solo para el rol admin.
  useEffect(() => {
    if (!listo || !navegacion?.key) return;
    const ruta = (segmentos[0] as string | undefined) ?? 'index';
    if (!RUTAS_PUBLICAS.has(ruta) && !obtenerToken()) router.replace('/');
    else if (RUTAS_SOLO_ADMIN.has(ruta) && rolDeSesion() !== 'admin') router.replace('/pacientes');
  }, [listo, navegacion?.key, segmentos]);

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
      <Stack.Screen name="planes" options={{ title: 'Planes' }} />
      <Stack.Screen name="admin-planes" options={{ title: 'Planes (administración)' }} />
    </Stack>
  );
}
