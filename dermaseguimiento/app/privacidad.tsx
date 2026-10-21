import { router, useLocalSearchParams } from 'expo-router';
import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Text } from 'react-native';
import { Aviso, Boton, Casilla, Pantalla, Subtitulo, Tarjeta, Titulo, COLOR } from '../components/ui';
import { api, cerrarSesion, mensaje } from '../lib/api';
import { obtenerToken } from '../lib/auth';

export default function PrivacidadScreen() {
  // Con ?aceptar=1 (al ingresar, si hay una versión nueva de la política) se pide aceptarla para seguir
  const { aceptar, siguiente } = useLocalSearchParams<{ aceptar?: string; siguiente?: string }>();
  const pedirAceptacion = aceptar === '1' && !!obtenerToken();
  const [politica, setPolitica] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [acepta, setAcepta] = useState(false); // desmarcada por defecto
  const [guardando, setGuardando] = useState(false);

  useEffect(() => {
    api('/politica-privacidad', { auth: false }).then((r) => (r.ok ? setPolitica(r.data) : setError(mensaje(r))));
  }, []);

  const confirmar = async () => {
    setError(null);
    if (!acepta) return setError('Para seguir usando DermaSeguimiento marcá la casilla de aceptación.');
    setGuardando(true);
    const r = await api('/aceptar-politica', { method: 'POST', json: { version: politica.version, acepta } });
    setGuardando(false);
    if (!r.ok) return setError(mensaje(r));
    router.replace(siguiente === '/cuenta' ? '/cuenta' : '/pacientes');
  };

  return (
    <Pantalla>
      {error && <Aviso tipo="error" texto={error} />}
      {!politica && !error && <ActivityIndicator size="large" color="#1D3D47" />}
      {politica && (
        <>
          {pedirAceptacion && (
            <Aviso tipo="info" texto={`Actualizamos la Política de Privacidad (versión ${politica.version}). Leela y aceptala para seguir usando el sistema.`} />
          )}
          <Titulo>{politica.titulo}</Titulo>
          <Text style={{ color: COLOR.textoSuave, marginBottom: 12 }}>Versión {politica.version}</Text>
          {politica.secciones.map((s: any) => (
            <React.Fragment key={s.titulo}>
              <Subtitulo>{s.titulo}</Subtitulo>
              <Text style={{ lineHeight: 21, color: COLOR.texto }}>{s.texto}</Text>
            </React.Fragment>
          ))}
          {pedirAceptacion && (
            <Tarjeta estilo={{ marginTop: 16 }}>
              <Casilla marcada={acepta} onCambio={setAcepta}>
                <Text>Leí y acepto que DermaSeguimiento trate mis datos de profesional para el uso del sistema, según esta Política de Privacidad.</Text>
              </Casilla>
              <Boton texto="Aceptar y continuar" icono="checkmark" onPress={confirmar} cargando={guardando} />
              <Boton texto="No acepto: cerrar sesión" variante="secundario" icono="log-out-outline" estilo={{ marginTop: 8 }} onPress={cerrarSesion} />
            </Tarjeta>
          )}
        </>
      )}
    </Pantalla>
  );
}
