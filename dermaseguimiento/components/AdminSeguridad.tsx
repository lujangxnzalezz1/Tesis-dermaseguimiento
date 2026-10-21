import { useEffect, useState } from 'react';
import { ActivityIndicator, Text } from 'react-native';
import { api, fechaCorta, mensaje } from '../lib/api';
import { Aviso, Boton, Campo, Casilla, COLOR, Confirmar, Subtitulo, Tarjeta } from './ui';

const RUTA = '/admin/seguridad/politica-contrasenas';

/** Sección de administración: política de contraseñas (se monta dentro de app/admin.tsx).
 *  El servidor valida los valores (longitud 8 a 64, vigencia 0 a 730 días) y audita cada cambio. */
export default function AdminSeguridad() {
  const [datos, setDatos] = useState<any>(null);
  const [longitud, setLongitud] = useState('');
  const [dias, setDias] = useState('');
  const [comunes, setComunes] = useState('');
  const [reglas, setReglas] = useState({ requiere_mayuscula: true, requiere_minuscula: true, requiere_numero: true, requiere_especial: true });
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [guardando, setGuardando] = useState(false);
  const [confirmarRestablecer, setConfirmarRestablecer] = useState(false);

  const cargar = (d: any) => {
    setDatos(d);
    setLongitud(String(d.longitud_minima));
    setDias(String(d.max_dias_vigencia));
    setComunes((d.comunes_adicionales ?? []).join('\n'));
    setReglas({ requiere_mayuscula: d.requiere_mayuscula, requiere_minuscula: d.requiere_minuscula, requiere_numero: d.requiere_numero, requiere_especial: d.requiere_especial });
  };

  useEffect(() => { api(RUTA).then((r) => (r.ok ? cargar(r.data) : setError(mensaje(r)))); }, []);

  const guardar = async () => {
    setError(null); setOk(null);
    const l = Number(longitud), d = Number(dias);
    if (!Number.isInteger(l) || l < 8 || l > 64) return setError('La longitud mínima debe ser un número entero entre 8 y 64.');
    if (!Number.isInteger(d) || d < 0 || d > 730) return setError('La vigencia debe ser un número de días entre 0 (no vence) y 730.');
    setGuardando(true);
    const r = await api(RUTA, {
      method: 'PUT',
      json: { longitud_minima: l, max_dias_vigencia: d, ...reglas, comunes_adicionales: comunes.split('\n').map((x) => x.trim()).filter(Boolean) },
    });
    setGuardando(false);
    if (!r.ok) return setError(mensaje(r));
    cargar(r.data);
    setOk('Política guardada. Se exige en el próximo cambio de contraseña de cada usuario.');
  };

  const restablecer = async () => {
    setConfirmarRestablecer(false);
    const r = await api(RUTA, { method: 'DELETE' });
    if (!r.ok) return setError(mensaje(r));
    cargar(r.data);
    setOk('Se restablecieron los valores de la configuración del servidor.');
  };

  if (!datos) return error ? <Aviso tipo="error" texto={error} /> : <ActivityIndicator color={COLOR.primario} />;

  const marcar = (clave: keyof typeof reglas) => (v: boolean) => setReglas({ ...reglas, [clave]: v });
  return (
    <Tarjeta>
      <Subtitulo>Política de contraseñas</Subtitulo>
      <Text style={{ color: COLOR.textoSuave, marginBottom: 8 }}>
        {datos.personalizada ? `Personalizada (última modificación: ${fechaCorta(datos.actualizado_en)}).` : 'Se usan los valores de la configuración del servidor.'}
      </Text>
      {error && <Aviso tipo="error" texto={error} />}
      {ok && <Aviso tipo="ok" texto={ok} />}
      <Campo etiqueta="Longitud mínima (8 a 64)" value={longitud} onChangeText={setLongitud} keyboardType="number-pad" maxLength={2} />
      <Casilla marcada={reglas.requiere_mayuscula} onCambio={marcar('requiere_mayuscula')}><Text>Exigir una letra mayúscula</Text></Casilla>
      <Casilla marcada={reglas.requiere_minuscula} onCambio={marcar('requiere_minuscula')}><Text>Exigir una letra minúscula</Text></Casilla>
      <Casilla marcada={reglas.requiere_numero} onCambio={marcar('requiere_numero')}><Text>Exigir un número</Text></Casilla>
      <Casilla marcada={reglas.requiere_especial} onCambio={marcar('requiere_especial')}><Text>Exigir un carácter especial</Text></Casilla>
      <Campo etiqueta="Vigencia de la contraseña en días (0 = no vence)" value={dias} onChangeText={setDias} keyboardType="number-pad" maxLength={3}
        ayuda="Al vencer, el usuario solo puede cambiar su contraseña o cerrar sesión hasta elegir una nueva." />
      <Campo etiqueta="Contraseñas prohibidas adicionales (una por línea)" value={comunes} onChangeText={setComunes} multiline
        ayuda="Se suman a la lista incorporada de contraseñas comunes, secuencias y repeticiones." />
      <Boton texto="Guardar política" icono="save-outline" onPress={guardar} cargando={guardando} />
      {datos.personalizada && (
        <Boton texto="Volver a los valores del servidor" icono="refresh-outline" variante="secundario" estilo={{ marginTop: 8 }}
          onPress={() => setConfirmarRestablecer(true)} />
      )}
      <Confirmar visible={confirmarRestablecer} titulo="Restablecer la política"
        mensaje="Se borrarán los valores guardados y se usarán los de la configuración del servidor." textoConfirmar="Restablecer"
        onConfirmar={restablecer} onCancelar={() => setConfirmarRestablecer(false)} />
    </Tarjeta>
  );
}
