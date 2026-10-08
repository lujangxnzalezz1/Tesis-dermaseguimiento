import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { Text } from 'react-native';
import { Aviso, Boton, Campo, Pantalla, ReglasPassword, Subtitulo, Tarjeta, Titulo, FUENTE } from '../components/ui';
import { api, cerrarSesion, mensaje } from '../lib/api';
import { usePoliticaPassword } from '../lib/politica';

export default function CuentaScreen() {
  const [perfil, setPerfil] = useState<any>(null);
  const [actual, setActual] = useState('');
  const [nueva, setNueva] = useState('');
  const [confirmar, setConfirmar] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);
  const { reglas, cumple } = usePoliticaPassword(nueva);

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
  };

  return (
    <Pantalla>
      <Titulo>Mi cuenta</Titulo>
      {perfil && <Tarjeta><Text style={{ fontFamily: FUENTE.textoFuerte }}>{perfil.nombre}</Text><Text>{perfil.email}</Text><Text>Perfil: {perfil.rol}</Text></Tarjeta>}
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
    </Pantalla>
  );
}
