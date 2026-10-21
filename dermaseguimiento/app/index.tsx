import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { Ionicons } from '@expo/vector-icons';
import { Text, View } from 'react-native';
import { MSG_FALTA_CAPTCHA, useCaptcha } from '../components/Captcha';
import { Aviso, Boton, Campo, COLOR, FUENTE, Pantalla, PieLegal, Tarjeta } from '../components/ui';
import { api, mensaje } from '../lib/api';
import { guardarToken, obtenerToken } from '../lib/auth';
import { EMAIL_RE } from '../lib/politica';

export default function LoginScreen() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sinConfirmar, setSinConfirmar] = useState(false);
  const [info, setInfo] = useState<string | null>(null);
  const [reenviando, setReenviando] = useState(false);
  const captcha = useCaptcha();

  // Con una sesión guardada no hace falta volver a ingresar.
  useEffect(() => {
    if (obtenerToken()) router.replace('/pacientes');
  }, []);

  const ingresar = async () => {
    setError(null);
    setInfo(null);
    setSinConfirmar(false);
    if (!EMAIL_RE.test(email.trim())) return setError('Escribí un correo electrónico válido, por ejemplo nombre@dominio.com.');
    if (!password) return setError('Escribí tu contraseña para continuar.');
    if (captcha.falta) return setError(MSG_FALTA_CAPTCHA);
    setCargando(true);
    const body = new URLSearchParams({ username: email.trim(), password });
    if (captcha.token) body.append('captcha_token', captcha.token);
    const r = await api('/login', { method: 'POST', form: body, auth: false });
    setCargando(false);
    captcha.reiniciar(); // el token del CAPTCHA es de un solo uso
    if (!r.ok) {
      setSinConfirmar(r.status === 403 && mensaje(r).includes('confirmaste tu correo'));
      return setError(mensaje(r, 'No pudimos iniciar tu sesión. Intentá de nuevo.'));
    }
    await guardarToken(r.data.access_token);
    const siguiente = r.data.password_vencida ? '/cuenta' : '/pacientes';
    // Si cambió la política de privacidad, primero hay que leerla y aceptarla
    if (r.data.politica_pendiente) router.replace({ pathname: '/privacidad', params: { aceptar: '1', siguiente } });
    else router.replace(siguiente);
  };

  const reenviar = async () => {
    if (captcha.falta) return setError(MSG_FALTA_CAPTCHA);
    setReenviando(true);
    const r = await api('/reenviar-verificacion', { method: 'POST', json: { email: email.trim(), captcha_token: captcha.token }, auth: false });
    setReenviando(false);
    captcha.reiniciar();
    if (!r.ok) return setError(mensaje(r));
    setError(null);
    setSinConfirmar(false);
    setInfo(r.data.mensaje);
  };

  return (
    <Pantalla>
      <View style={{ position: 'absolute', top: -120, right: -110, width: 320, height: 320, borderRadius: 160, backgroundColor: COLOR.suave }} />
      <View style={{ position: 'absolute', top: 110, right: 30, width: 64, height: 64, borderRadius: 32, borderWidth: 2, borderColor: COLOR.dorado }} />
      <View style={{ height: 36 }} />
      <View style={{ width: 64, height: 64, borderRadius: 22, backgroundColor: COLOR.primario, alignItems: 'center', justifyContent: 'center', marginBottom: 18 }}>
        <Ionicons name="happy-outline" size={34} color={COLOR.fondo} />
      </View>
      <Text style={{ fontFamily: FUENTE.titulo, fontSize: 32, lineHeight: 37, color: COLOR.texto, letterSpacing: -0.5 }}>Seguimiento de la piel,{'\n'}consulta a consulta</Text>
      <Text style={{ fontFamily: FUENTE.texto, fontSize: 15, lineHeight: 22, color: COLOR.textoSuave, marginTop: 8, marginBottom: 22 }}>
        Compará fotos de tus pacientes alineadas automáticamente y entregá informes claros.
      </Text>
      {error && <Aviso tipo="error" texto={error} />}
      {info && <Aviso tipo="ok" texto={info} />}
      {sinConfirmar && (
        <Boton texto="Reenviar correo de confirmación" icono="mail-outline" variante="secundario" cargando={reenviando} onPress={reenviar} estilo={{ marginBottom: 12 }} />
      )}
      <Tarjeta estilo={{ padding: 22, borderRadius: 28 }}>
        <Campo etiqueta="Correo electrónico" value={email} onChangeText={setEmail} autoCapitalize="none" keyboardType="email-address" autoComplete="email" maxLength={120} placeholder="nombre@consultorio.com" />
        <Campo etiqueta="Contraseña" value={password} onChangeText={setPassword} secureTextEntry autoComplete="password" maxLength={128} onSubmitEditing={ingresar} returnKeyType="go" />
        <Boton texto="¿Olvidaste tu contraseña?" variante="texto" onPress={() => router.push('/recuperar')} estilo={{ alignSelf: 'flex-end', paddingHorizontal: 0, marginTop: -6, marginBottom: 4 }} />
        {captcha.widget}
        <Boton texto="Ingresar" onPress={ingresar} cargando={cargando} />
      </Tarjeta>
      <View style={{ alignItems: 'center', gap: 4, marginTop: 18 }}>
        <View style={{ flexDirection: 'row', alignItems: 'center' }}>
          <Text style={{ fontFamily: FUENTE.texto, color: COLOR.textoSuave, fontSize: 14 }}>¿Primera vez?</Text>
          <Boton texto="Creá tu cuenta" variante="texto" onPress={() => router.push('/registro')} estilo={{ paddingHorizontal: 6 }} />
        </View>
      </View>
      <PieLegal alAbrir={() => router.push('/privacidad')} />
    </Pantalla>
  );
}
