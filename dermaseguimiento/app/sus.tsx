import { router } from 'expo-router';
import { useState } from 'react';
import { Alert, Text, TouchableOpacity, View } from 'react-native';
import { Aviso, Boton, Campo, COLOR, Pantalla, Titulo } from '../components/ui';
import { api, mensaje } from '../lib/api';

const PREGUNTAS = [
  'Creo que me gustaría usar este sistema con frecuencia.',
  'Encontré el sistema innecesariamente complejo.',
  'Pensé que el sistema era fácil de usar.',
  'Creo que necesitaría el apoyo de una persona técnica para poder usar este sistema.',
  'Encontré que las diversas funciones del sistema estaban bien integradas.',
  'Pensé que había demasiada inconsistencia en este sistema.',
  'Imagino que la mayoría de las personas aprendería a usar este sistema muy rápido.',
  'Encontré el sistema muy incómodo de usar.',
  'Me sentí muy seguro/a usando el sistema.',
  'Necesité aprender muchas cosas antes de poder empezar a usar el sistema.',
];

export default function SusScreen() {
  const [resp, setResp] = useState<number[]>(Array(10).fill(0));
  const [comentario, setComentario] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);

  const enviar = async () => {
    setError(null);
    if (resp.some((x) => x === 0)) return setError('Falta responder alguna pregunta. Elegí un valor de 1 a 5 en todas.');
    setCargando(true);
    const r = await api('/sus', { method: 'POST', json: { respuestas: resp, comentario: comentario || null } });
    setCargando(false);
    if (!r.ok) return setError(mensaje(r));
    Alert.alert('¡Gracias!', r.data.mensaje, [{ text: 'Cerrar', onPress: () => router.back() }]);
  };

  return (
    <Pantalla>
      <Titulo>Encuesta de usabilidad</Titulo>
      <Text style={{ color: '#555', marginBottom: 12 }}>1 = Totalmente en desacuerdo · 5 = Totalmente de acuerdo</Text>
      {error && <Aviso tipo="error" texto={error} />}
      {PREGUNTAS.map((p, i) => (
        <View key={i} style={{ marginBottom: 14 }}>
          <Text style={{ marginBottom: 6 }}>{i + 1}. {p}</Text>
          <View style={{ flexDirection: 'row', gap: 6 }}>
            {[1, 2, 3, 4, 5].map((v) => (
              <TouchableOpacity key={v} accessibilityRole="button" accessibilityLabel={`Pregunta ${i + 1}, valor ${v}`}
                onPress={() => setResp((r) => r.map((x, j) => (j === i ? v : x)))}
                style={{ flex: 1, paddingVertical: 10, borderRadius: 8, borderWidth: 1, borderColor: COLOR.primario, alignItems: 'center', backgroundColor: resp[i] === v ? COLOR.primario : '#fff' }}>
                <Text style={{ color: resp[i] === v ? '#fff' : COLOR.primario, fontWeight: '600' }}>{v}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>
      ))}
      <Campo etiqueta="Comentarios (opcional)" value={comentario} onChangeText={setComentario} multiline maxLength={500} />
      <Boton texto="Enviar respuestas" icono="send-outline" onPress={enviar} cargando={cargando} />
    </Pantalla>
  );
}
