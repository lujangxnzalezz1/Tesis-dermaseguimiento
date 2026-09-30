import { Alert, Platform } from 'react-native';

/** Alert.alert con botones no funciona en la versión web: estas funciones usan el diálogo del navegador en web. */
export function avisar(titulo: string, mensaje: string, alAceptar?: () => void) {
  if (Platform.OS === 'web') {
    window.alert(`${titulo}\n\n${mensaje}`);
    alAceptar?.();
    return;
  }
  Alert.alert(titulo, mensaje, [{ text: 'Aceptar', onPress: alAceptar }]);
}

export function elegirOrigenFoto(alElegir: (origen: 'galeria' | 'camara') => void) {
  if (Platform.OS === 'web') {
    alElegir('galeria'); // en el navegador se abre el selector de archivos
    return;
  }
  Alert.alert('Seleccionar imagen', '¿De dónde querés obtener la foto?', [
    { text: 'Cancelar', style: 'cancel' },
    { text: 'Galería', onPress: () => alElegir('galeria') },
    { text: 'Cámara', onPress: () => alElegir('camara') },
  ]);
}
