import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { Text } from 'react-native';
import { Aviso, Boton, Campo, Casilla, COLOR, Pantalla, ReglasPassword, Subtitulo, Tarjeta, Titulo, FUENTE } from '../components/ui';
import { api, cerrarSesion, mensaje } from '../lib/api';
import { borrarToken } from '../lib/auth';
import { avisar } from '../lib/dialogo';
import { usePoliticaPassword } from '../lib/politica';
import { desvincularUsuarioPush } from '../lib/push';

export default function CuentaScreen() {
  const [perfil, setPerfil] = useState<any>(null);
  const [actual, setActual] = useState('');
  const [nueva, setNueva] = useState('');
  const [confirmar, setConfirmar] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);
  const { reglas, cumple } = usePoliticaPassword(nueva);
  // Baja de la cuenta (retiro del consentimiento)
  const [bajaAbierta, setBajaAbierta] = useState(false);
  const [bajaPassword, setBajaPassword] = useState('');
  const [bajaMotivo, setBajaMotivo] = useState('');
  const [bajaEntiendo, setBajaEntiendo] = useState(false);
  const [bajaError, setBajaError] = useState<string | null>(null);
  const [bajaCargando, setBajaCargando] = useState(false);

  useEffect(() => { api('/perfil').then((r) => r.ok && setPerfil(r.data)); }, []);

  const cambiar = async () => {
    setError(null); setOk(null);
    if (!actual) return setError('Escribí tu contraseña actual.');
    if (!cumple) return setError('La contraseña nueva todavía no cumple todos los requisitos de la lista.');
    if (nueva !== confirmar) return setError('Las contraseñas nuevas no coinciden.');
    setCargando(true);
    const r = await api('/cambiar-contrasena', { method: 'POST', json: { password_actual: actual, password: nueva, confirmar_password: confirmar } });
    setCargando(false);
    if (!r.ok) return setError(mensaje(r));
    setOk(r.data.mensaje); setActual(''); setNueva(''); setConfirmar('');
    if (perfil?.password_vencida) {
      setPerfil({ ...perfil, password_vencida: false });
      router.replace('/pacientes'); // ya puede seguir usando el sistema
    }
  };

  const darDeBaja = async () => {
    setBajaError(null);
    if (!bajaPassword) return setBajaError('Escribí tu contraseña para confirmar que sos vos.');
    if (!bajaEntiendo) return setBajaError('Marcá la casilla para confirmar que entendés que no se puede deshacer.');
    setBajaCargando(true);
    const r = await api('/cuenta/eliminar', { method: 'POST', json: { password: bajaPassword, confirmar: true, motivo: bajaMotivo.trim() || null } });
    setBajaCargando(false);
    if (!r.ok) return setBajaError(mensaje(r));
    // Las sesiones ya se revocaron en el servidor: solo queda limpiar el dispositivo
    desvincularUsuarioPush();
    await borrarToken();
    avisar('Cuenta dada de baja', r.data.mensaje, () => router.replace('/'));
  };

  return (
    <Pantalla>
      <Titulo>Mi cuenta</Titulo>
      {perfil && <Tarjeta><Text style={{ fontFamily: FUENTE.textoFuerte }}>{perfil.nombre}</Text><Text>{perfil.email}</Text><Text>Perfil: {perfil.rol}</Text></Tarjeta>}
      {perfil?.password_vencida && (
        <Aviso tipo="aviso" texto="Tu contraseña venció. Elegí una nueva para seguir usando el sistema." />
      )}
      <Subtitulo>Cambiar contraseña</Subtitulo>
      {error && <Aviso tipo="error" texto={error} />}
      {ok && <Aviso tipo="ok" texto={ok} />}
      <Campo etiqueta="Contraseña actual" value={actual} onChangeText={setActual} secureTextEntry maxLength={128} />
      <Campo etiqueta="Contraseña nueva" value={nueva} onChangeText={setNueva} secureTextEntry maxLength={128} />
      <ReglasPassword reglas={reglas} />
      <Campo etiqueta="Repetí la contraseña nueva" value={confirmar} onChangeText={setConfirmar} secureTextEntry maxLength={128} />
      <Boton texto="Guardar contraseña" icono="save-outline" onPress={cambiar} cargando={cargando} />
      <Subtitulo>Más</Subtitulo>
      <Boton texto="Encuesta de usabilidad (SUS)" icono="clipboard-outline" variante="secundario" onPress={() => router.push('/sus')} />
      <Boton texto="Política de privacidad" icono="shield-checkmark-outline" variante="secundario" estilo={{ marginTop: 8 }} onPress={() => router.push('/privacidad')} />
      <Boton texto="Cerrar sesión" icono="log-out-outline" variante="peligro" estilo={{ marginTop: 16 }} onPress={cerrarSesion} />

      <Subtitulo>Retirar mi consentimiento y dar de baja la cuenta</Subtitulo>
      <Text style={{ color: COLOR.textoSuave, lineHeight: 20, marginBottom: 8 }}>
        Tu cuenta se desactiva, tus datos personales (nombre y correo) se anonimizan y se cierran todas tus sesiones.
        Por obligación legal se conservan la bitácora de auditoría y los pagos y comprobantes; las fichas de tus
        pacientes quedan desactivadas y se anonimizan al vencer el plazo de conservación. No se puede deshacer.
      </Text>
      {!bajaAbierta ? (
        <Boton texto="Dar de baja mi cuenta" icono="trash-outline" variante="secundario" onPress={() => setBajaAbierta(true)} />
      ) : (
        <Tarjeta>
          {bajaError && <Aviso tipo="error" texto={bajaError} />}
          <Campo etiqueta="Tu contraseña" value={bajaPassword} onChangeText={setBajaPassword} secureTextEntry maxLength={128} />
          <Campo etiqueta="Motivo (opcional)" value={bajaMotivo} onChangeText={setBajaMotivo} maxLength={300} />
          <Casilla marcada={bajaEntiendo} onCambio={setBajaEntiendo}>
            <Text>Entiendo que mi cuenta se da de baja definitivamente y que esta acción no se puede deshacer.</Text>
          </Casilla>
          <Boton texto="Dar de baja definitivamente" icono="trash-outline" variante="peligro" cargando={bajaCargando} onPress={darDeBaja} />
          <Boton texto="Cancelar" variante="secundario" estilo={{ marginTop: 8 }}
            onPress={() => { setBajaAbierta(false); setBajaPassword(''); setBajaEntiendo(false); setBajaError(null); }} />
        </Tarjeta>
      )}
    </Pantalla>
  );
}
