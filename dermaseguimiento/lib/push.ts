import Constants, { ExecutionEnvironment } from 'expo-constants';
import { Platform } from 'react-native';

// Notificaciones push con OneSignal. El SDK es nativo: no existe en la versión web ni en Expo Go,
// así que ahí todas estas funciones no hacen nada y la app sigue funcionando igual.
// Para probarlas hace falta un development build (npx expo run:android / run:ios).
const APP_ID: string | undefined = Constants.expoConfig?.extra?.oneSignalAppId;

const disponible =
  Platform.OS !== 'web' && Constants.executionEnvironment !== ExecutionEnvironment.StoreClient && !!APP_ID;

// Se carga recién al usarlo para que importar este archivo no falle donde el módulo nativo no está.
function sdk() {
  return disponible ? require('react-native-onesignal').OneSignal : null;
}

let iniciado = false;

/** Inicializa OneSignal una sola vez, al arrancar la app. */
export function iniciarPush() {
  const OneSignal = sdk();
  if (!OneSignal || iniciado) return;
  OneSignal.initialize(APP_ID);
  iniciado = true;
}

/**
 * Asocia el dispositivo al usuario del backend (su id) para poder enviarle push desde el servidor
 * con `include_aliases: { external_id: [...] }`. También pide el permiso de notificaciones
 * (Android 13+ e iOS lo piden la primera vez; después el sistema recuerda la respuesta).
 */
export function vincularUsuarioPush(usuarioId: number | string) {
  const OneSignal = sdk();
  if (!OneSignal) return;
  iniciarPush();
  OneSignal.login(String(usuarioId));
  OneSignal.Notifications.requestPermission(false);
}

/** Desasocia el dispositivo al cerrar sesión, para que no le lleguen avisos de otra cuenta. */
export function desvincularUsuarioPush() {
  const OneSignal = sdk();
  if (!OneSignal || !iniciado) return;
  OneSignal.logout();
}
