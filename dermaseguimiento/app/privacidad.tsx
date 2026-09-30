import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Text } from 'react-native';
import { Aviso, Pantalla, Subtitulo, Titulo } from '../components/ui';
import { api, mensaje } from '../lib/api';

export default function PrivacidadScreen() {
  const [politica, setPolitica] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api('/politica-privacidad', { auth: false }).then((r) => (r.ok ? setPolitica(r.data) : setError(mensaje(r))));
  }, []);

  return (
    <Pantalla>
      {error && <Aviso tipo="error" texto={error} />}
      {!politica && !error && <ActivityIndicator size="large" color="#1D3D47" />}
      {politica && (
        <>
          <Titulo>{politica.titulo}</Titulo>
          <Text style={{ color: '#666', marginBottom: 12 }}>Versión {politica.version}</Text>
          {politica.secciones.map((s: any) => (
            <React.Fragment key={s.titulo}>
              <Subtitulo>{s.titulo}</Subtitulo>
              <Text style={{ lineHeight: 21, color: '#222' }}>{s.texto}</Text>
            </React.Fragment>
          ))}
        </>
      )}
    </Pantalla>
  );
}
