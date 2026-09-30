import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { Text, View } from 'react-native';
import { Aviso, Boton, Campo, Pantalla, Titulo } from '../components/ui';
import { api, mensaje } from '../lib/api';
import { guardarToken, obtenerToken } from '../lib/auth';
import { EMAIL_RE } from '../lib/politica';

export default function LoginScreen() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Con una sesión guardada no hace falta volver a ingresar.
  useEffect(() => {
    if (obtenerToken()) router.replace('/pacientes');
  }, []);

  const ingresar = async () => {
    setError(null);
    if (!EMAIL_RE.test(email.trim())) return setError('Escribí un correo electrónico válido, por ejemplo nombre@dominio.com.');
    if (!password) return setError('Escribí tu contraseña para continuar.');
    setCargando(true);
    const body = new URLSearchParams({ username: email.trim(), password });
    const r = await api('/login', { method: 'POST', form: body, auth: false });
    setCargando(false);
    if (!r.ok) return setError(mensaje(r, 'No pudimos iniciar tu sesión. Intentá de nuevo.'));
    await guardarToken(r.data.access_token);
    router.replace(r.data.password_vencida ? '/cuenta' : '/pacientes');
  };

  return (
    <Pantalla>
      <View style={{ height: 40 }} />
      <Titulo>DermaSeguimiento</Titulo>
      <Text style={{ color: '#666', marginBottom: 24 }}>Iniciá sesión para continuar</Text>
      {error && <Aviso tipo="error" texto={error} />}
      <Campo etiqueta="Correo electrónico" value={email} onChangeText={setEmail} autoCapitalize="none" keyboardType="email-address" autoComplete="email" maxLength={120} />
      <Campo etiqueta="Contraseña" value={password} onChangeText={setPassword} secureTextEntry autoComplete="password" maxLength={128} onSubmitEditing={ingresar} returnKeyType="go" />
      <Boton texto="Ingresar" icono="log-in-outline" onPress={ingresar} cargando={cargando} />
      <View style={{ height: 8 }} />
      <Boton texto="Crear cuenta" icono="person-add-outline" variante="secundario" onPress={() => router.push('/registro')} />
      <Boton texto="Olvidé mi contraseña" icono="key-outline" variante="texto" onPress={() => router.push('/recuperar')} />
      <Boton texto="Política de privacidad" icono="shield-checkmark-outline" variante="texto" onPress={() => router.push('/privacidad')} />
    </Pantalla>
  );
}
