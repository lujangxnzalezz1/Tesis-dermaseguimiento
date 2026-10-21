import { router } from 'expo-router';
import { useState } from 'react';
import { Text } from 'react-native';
import { MSG_FALTA_CAPTCHA, useCaptcha } from '../components/Captcha';
import { Aviso, Boton, Campo, Pantalla, PieLegal, Titulo, COLOR } from '../components/ui';
import { api, mensaje } from '../lib/api';
import { EMAIL_RE } from '../lib/politica';

export default function RecuperarScreen() {
  const [email, setEmail] = useState('');
  const [cargando, setCargando] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const captcha = useCaptcha();

  const enviar = async () => {
    setError(null);
    if (!EMAIL_RE.test(email.trim())) return setError('Escribí un correo electrónico válido.');
    if (captcha.falta) return setError(MSG_FALTA_CAPTCHA);
    setCargando(true);
    const r = await api('/recuperar-contrasena', { method: 'POST', json: { email: email.trim(), captcha_token: captcha.token }, auth: false });
    setCargando(false);
    captcha.reiniciar();
    if (!r.ok) return setError(mensaje(r));
    setMsg(r.data.mensaje);
  };

  return (
    <Pantalla>
      <Titulo>Recuperar contraseña</Titulo>
      <Text style={{ color: COLOR.textoSuave, marginBottom: 16 }}>
        Te enviamos por correo un enlace de un solo uso, válido por pocos minutos, para elegir una contraseña nueva.
      </Text>
      {error && <Aviso tipo="error" texto={error} />}
      {msg && <Aviso tipo="ok" texto={msg} />}
      <Campo etiqueta="Correo electrónico" value={email} onChangeText={setEmail} autoCapitalize="none" keyboardType="email-address" maxLength={120} />
      {captcha.widget}
      <Boton texto="Enviarme el enlace" icono="mail-outline" onPress={enviar} cargando={cargando} />
      <Boton texto="Ya tengo el código del correo" icono="key-outline" variante="secundario" estilo={{ marginTop: 12 }} onPress={() => router.push('/restablecer')} />
      <PieLegal alAbrir={() => router.push('/privacidad')} />
    </Pantalla>
  );
}
