import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Alert, Text } from 'react-native';
import { Aviso, Boton, Campo, Pantalla, ReglasPassword, Titulo } from '../components/ui';
import { api, mensaje } from '../lib/api';
import { usePoliticaPassword } from '../lib/politica';

export default function RestablecerScreen() {
  // Si se abre desde el enlace del correo, el token llega en la dirección (dermaseguimiento://restablecer?token=...)
  const { token: tokenUrl } = useLocalSearchParams<{ token?: string }>();
  const [token, setToken] = useState(tokenUrl ?? '');
  const [password, setPassword] = useState('');
  const [confirmar, setConfirmar] = useState('');
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { reglas, cumple } = usePoliticaPassword(password);

  const enviar = async () => {
    setError(null);
    if (token.trim().length < 20) return setError('Pegá el código completo que llegó en el enlace del correo.');
    if (!cumple) return setError('La contraseña todavía no cumple todos los requisitos de la lista.');
    if (password !== confirmar) return setError('Las contraseñas no coinciden. Escribilas de nuevo.');
    setCargando(true);
    const r = await api('/restablecer-contrasena', { method: 'POST', auth: false, json: { token: token.trim(), password, confirmar_password: confirmar } });
    setCargando(false);
    if (!r.ok) return setError(mensaje(r));
    Alert.alert('Listo', r.data.mensaje, [{ text: 'Ir a ingresar', onPress: () => router.replace('/') }]);
  };

  return (
    <Pantalla>
      <Titulo>Elegí tu nueva contraseña</Titulo>
      {error && <Aviso tipo="error" texto={error} />}
      <Campo etiqueta="Código del enlace" value={token} onChangeText={setToken} autoCapitalize="none" autoCorrect={false}
        ayuda="Si abriste el enlace desde el correo se completa solo. Si no, copiá lo que va después de «token=»." />
      <Campo etiqueta="Nueva contraseña" value={password} onChangeText={setPassword} secureTextEntry maxLength={128} />
      <ReglasPassword reglas={reglas} />
      <Campo etiqueta="Repetí la nueva contraseña" value={confirmar} onChangeText={setConfirmar} secureTextEntry maxLength={128} />
      <Boton texto="Guardar contraseña" icono="save-outline" onPress={enviar} cargando={cargando} />
      <Text style={{ color: '#666', marginTop: 12, fontSize: 12 }}>El enlace se puede usar una sola vez y vence a los pocos minutos.</Text>
    </Pantalla>
  );
}
