import { router } from 'expo-router';
import { useState } from 'react';
import { Text } from 'react-native';
import { avisar } from '../lib/dialogo';
import { MSG_FALTA_CAPTCHA, useCaptcha } from '../components/Captcha';
import { Aviso, Boton, Campo, Casilla, COLOR, Pantalla, PieLegal, ReglasPassword, Titulo } from '../components/ui';
import { api, mensaje } from '../lib/api';
import { EMAIL_RE, usePoliticaPassword } from '../lib/politica';

export default function RegistroScreen() {
  const [nombre, setNombre] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmar, setConfirmar] = useState('');
  const [acepta, setAcepta] = useState(false); // desmarcada por defecto
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { reglas, cumple } = usePoliticaPassword(password);
  const captcha = useCaptcha();

  const enviar = async () => {
    setError(null);
    if (nombre.trim().length < 2) return setError('Escribí tu nombre completo.');
    if (!EMAIL_RE.test(email.trim())) return setError('Escribí un correo electrónico válido, por ejemplo nombre@dominio.com.');
    if (!cumple) return setError('La contraseña todavía no cumple todos los requisitos de la lista.');
    if (password !== confirmar) return setError('Las contraseñas no coinciden. Escribilas de nuevo.');
    if (!acepta) return setError('Para crear tu cuenta tenés que aceptar la Política de Privacidad.');
    if (captcha.falta) return setError(MSG_FALTA_CAPTCHA);
    setCargando(true);
    const r = await api('/registro', {
      method: 'POST', auth: false,
      json: { nombre: nombre.trim(), email: email.trim(), password, confirmar_password: confirmar, acepta_politica: acepta,
              captcha_token: captcha.token },
    });
    setCargando(false);
    captcha.reiniciar();
    if (!r.ok) return setError(mensaje(r));
    avisar(
      '¡Cuenta creada!',
      r.data.email_verificado
        ? 'Ya podés iniciar sesión. Tenés un período de prueba con todas las funciones.'
        : `Te enviamos un correo a ${email.trim()} para confirmar que es tuyo. Abrí el enlace y después iniciá sesión. ` +
          'Si no lo ves, revisá el correo no deseado.',
      () => router.replace('/'),
    );
  };

  return (
    <Pantalla>
      <Titulo>Crear cuenta</Titulo>
      {error && <Aviso tipo="error" texto={error} />}
      <Campo etiqueta="Nombre completo" value={nombre} onChangeText={setNombre} maxLength={100} autoComplete="name" />
      <Campo etiqueta="Correo electrónico" value={email} onChangeText={setEmail} autoCapitalize="none" keyboardType="email-address" maxLength={120} />
      <Campo etiqueta="Contraseña" value={password} onChangeText={setPassword} secureTextEntry maxLength={128} />
      <ReglasPassword reglas={reglas} />
      <Campo etiqueta="Repetí la contraseña" value={confirmar} onChangeText={setConfirmar} secureTextEntry maxLength={128}
        error={confirmar && confirmar !== password ? 'No coincide con la contraseña.' : null} />
      <Casilla marcada={acepta} onCambio={setAcepta}>
        <Text>
          Acepto que DermaSeguimiento trate mis datos de profesional para gestionar mi cuenta, según la{' '}
          <Text style={{ color: COLOR.primario, textDecorationLine: 'underline' }} onPress={() => router.push('/privacidad')}>Política de Privacidad</Text>.
        </Text>
      </Casilla>
      {captcha.widget}
      <Boton texto="Crear cuenta" icono="person-add-outline" onPress={enviar} cargando={cargando} />
      <PieLegal alAbrir={() => router.push('/privacidad')} />
    </Pantalla>
  );
}
