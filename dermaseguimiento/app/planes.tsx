import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { ActivityIndicator, ScrollView, Text, View } from 'react-native';
import { Aviso, Boton, COLOR, FUENTE, Pantalla, Subtitulo, Tarjeta, Titulo } from '../components/ui';
import { api, mensaje } from '../lib/api';
import { obtenerToken } from '../lib/auth';
import { PERIODICIDAD, Plan, precioPlan } from '../lib/planes';

/** Catálogo PÚBLICO de planes (no requiere iniciar sesión). Los datos salen de GET /planes, la misma
 *  tabla con la que el servidor aplica las reglas, así que lo que se muestra no puede contradecirlas. */
export default function PlanesScreen() {
  const [planes, setPlanes] = useState<Plan[] | null>(null);
  const [diasPrueba, setDiasPrueba] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const conSesion = !!obtenerToken();

  useEffect(() => {
    api('/planes', { auth: false }).then((r) => {
      if (r.ok) { setPlanes(r.data.planes); setDiasPrueba(r.data.dias_de_prueba ?? 0); } else setError(mensaje(r));
    });
  }, []);

  const contratar = () => (conSesion ? router.push('/suscripcion') : router.push('/registro'));

  if (!planes && !error) return <Pantalla><ActivityIndicator size="large" color={COLOR.primario} /></Pantalla>;

  return (
    <Pantalla>
      <Titulo>Planes</Titulo>
      {error && <Aviso tipo="error" texto={error} />}
      {diasPrueba > 0 && !conSesion && (
        <Aviso tipo="info" texto={`Al crear tu cuenta tenés ${diasPrueba} días de prueba con todas las funciones Premium, sin cargar ningún medio de pago.`} />
      )}

      {(planes ?? []).map((p) => (
        <Tarjeta key={p.codigo} color={p.incluye_procesamiento ? COLOR.tarjeta : COLOR.suave}>
          <Text style={{ fontSize: 20, fontFamily: FUENTE.titulo, color: COLOR.primario }}>{p.nombre}</Text>
          <Text style={{ fontSize: 17, fontFamily: FUENTE.textoFuerte, color: COLOR.texto, marginTop: 2 }}>{precioPlan(p)}</Text>
          <Text style={{ color: COLOR.textoSuave, fontFamily: FUENTE.texto, marginBottom: 6 }}>Periodicidad: {PERIODICIDAD[p.periodicidad] ?? p.periodicidad}</Text>
          <Text style={{ fontFamily: FUENTE.textoFuerte, color: COLOR.texto, marginTop: 4 }}>Incluye</Text>
          {p.funcionalidades.map((f) => <Text key={f} style={{ fontFamily: FUENTE.texto, color: COLOR.texto }}>• {f}</Text>)}
          {p.limites.length > 0 && <Text style={{ fontFamily: FUENTE.textoFuerte, color: COLOR.texto, marginTop: 6 }}>Límites</Text>}
          {p.limites.map((f) => <Text key={f} style={{ fontFamily: FUENTE.texto, color: COLOR.textoSuave }}>– {f}</Text>)}
          <Text style={{ fontFamily: FUENTE.textoFuerte, color: COLOR.texto, marginTop: 6 }}>Condiciones</Text>
          <Text style={{ color: COLOR.textoSuave, fontSize: 13, fontFamily: FUENTE.texto }}>{p.condiciones}</Text>
          {p.periodicidad !== 'gratuito' && (
            <Boton texto="Contratar" icono="card-outline" estilo={{ marginTop: 12 }} onPress={contratar} />
          )}
        </Tarjeta>
      ))}

      {planes && planes.length > 0 && <Comparacion planes={planes} />}

      {!conSesion && (
        <View style={{ marginTop: 12 }}>
          <Boton texto="Crear mi cuenta" icono="person-add-outline" onPress={() => router.push('/registro')} />
          <Boton texto="Ya tengo cuenta: ingresar" variante="texto" onPress={() => router.replace('/')} estilo={{ marginTop: 4 }} />
        </View>
      )}
      {conSesion && <Boton texto="Ir a mi suscripción" icono="card-outline" variante="secundario" onPress={() => router.push('/suscripcion')} estilo={{ marginTop: 12 }} />}
    </Pantalla>
  );
}

const ANCHO_ETIQUETA = 150;
const ANCHO_COLUMNA = 150;

/** Tabla comparativa Gratuito / Mensual / Anual. Se desplaza de costado en pantallas angostas. */
function Comparacion({ planes }: { planes: Plan[] }) {
  const filas: { etiqueta: string; valor: (p: Plan) => string }[] = [
    { etiqueta: 'Precio', valor: (p) => precioPlan(p) },
    { etiqueta: 'Periodicidad', valor: (p) => PERIODICIDAD[p.periodicidad] ?? p.periodicidad },
    { etiqueta: 'Procesamiento de imágenes, informes y reportes', valor: (p) => (p.incluye_procesamiento ? 'Sí' : 'No') },
    { etiqueta: 'Pacientes y fichas clínicas', valor: () => 'Sí' },
    { etiqueta: 'Límites', valor: (p) => (p.limites.length ? p.limites.join('; ') : 'Sin límites') },
  ];
  const celda = { padding: 10, borderBottomWidth: 1, borderColor: COLOR.borde } as const;
  return (
    <>
      <Subtitulo>Comparación de planes</Subtitulo>
      <ScrollView horizontal showsHorizontalScrollIndicator>
        <View style={{ backgroundColor: COLOR.tarjeta, borderRadius: 18, overflow: 'hidden' }} accessibilityLabel="Tabla comparativa de planes">
          <View style={{ flexDirection: 'row', backgroundColor: COLOR.primario }}>
            <Text style={[celda, { width: ANCHO_ETIQUETA, color: '#fff', fontFamily: FUENTE.textoFuerte }]}> </Text>
            {planes.map((p) => (
              <Text key={p.codigo} style={[celda, { width: ANCHO_COLUMNA, color: '#fff', fontFamily: FUENTE.textoFuerte }]}>{p.nombre}</Text>
            ))}
          </View>
          {filas.map((f) => (
            <View key={f.etiqueta} style={{ flexDirection: 'row' }}>
              <Text style={[celda, { width: ANCHO_ETIQUETA, fontFamily: FUENTE.textoFuerte, color: COLOR.texto }]}>{f.etiqueta}</Text>
              {planes.map((p) => (
                <Text key={p.codigo} style={[celda, { width: ANCHO_COLUMNA, fontFamily: FUENTE.texto, color: COLOR.texto }]}>{f.valor(p)}</Text>
              ))}
            </View>
          ))}
        </View>
      </ScrollView>
    </>
  );
}
