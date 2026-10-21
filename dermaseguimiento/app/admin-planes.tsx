import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Text, View } from 'react-native';
import { Aviso, Boton, Campo, Casilla, COLOR, Confirmar, FUENTE, Pantalla, Tarjeta, Titulo } from '../components/ui';
import { api, mensaje } from '../lib/api';
import { PERIODICIDAD, Plan, precioPlan } from '../lib/planes';

/** Administración de planes: precio, estado, funcionalidades, límites y condiciones (solo administradores). */
export default function AdminPlanesScreen() {
  const [planes, setPlanes] = useState<Plan[] | null>(null);
  const [prohibido, setProhibido] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [editando, setEditando] = useState<string | null>(null);

  const cargar = useCallback(async () => {
    const r = await api('/admin/planes');
    if (r.status === 403) return setProhibido(true);
    if (r.ok) setPlanes(r.data.planes); else setError(mensaje(r));
  }, []);
  useEffect(() => { cargar(); }, [cargar]);

  if (prohibido) return <Pantalla><Aviso tipo="error" texto="Esta sección es solo para administradores." /></Pantalla>;
  if (!planes && !error) return <Pantalla><ActivityIndicator size="large" color={COLOR.primario} /></Pantalla>;

  return (
    <Pantalla>
      <Titulo>Planes</Titulo>
      <Text style={{ color: COLOR.textoSuave, fontFamily: FUENTE.texto, marginBottom: 6 }}>
        Lo que guardes acá es lo que ve el público en la página de planes y lo que se cobra en los pagos nuevos. Los pagos ya iniciados conservan su importe.
      </Text>
      {error && <Aviso tipo="error" texto={error} />}
      {info && <Aviso tipo="ok" texto={info} />}
      {(planes ?? []).map((p) => editando === p.codigo ? (
        <EditorPlan key={p.codigo} plan={p} onCancelar={() => setEditando(null)}
          onGuardado={(m) => { setEditando(null); setError(null); setInfo(m); cargar(); }} />
      ) : (
        <Tarjeta key={p.codigo} color={p.activo ? COLOR.tarjeta : COLOR.arena}>
          <Text style={{ fontSize: 18, fontFamily: FUENTE.titulo, color: COLOR.primario }}>{p.nombre}{p.activo ? '' : ' (inactivo)'}</Text>
          <Text style={{ fontFamily: FUENTE.textoFuerte }}>{precioPlan(p)} · {PERIODICIDAD[p.periodicidad] ?? p.periodicidad}</Text>
          {p.funcionalidades.map((f) => <Text key={f}>• {f}</Text>)}
          {p.limites.map((f) => <Text key={f} style={{ color: COLOR.textoSuave }}>– {f}</Text>)}
          <Text style={{ color: COLOR.textoSuave, fontSize: 12, marginTop: 6 }}>{p.condiciones}</Text>
          <Boton texto="Editar" icono="create-outline" variante="secundario" estilo={{ marginTop: 10 }} onPress={() => { setInfo(null); setEditando(p.codigo); }} />
        </Tarjeta>
      ))}
    </Pantalla>
  );
}

const aLineas = (lista: string[]) => lista.join('\n');
const deLineas = (texto: string) => texto.split('\n').map((l) => l.trim()).filter(Boolean);

function EditorPlan({ plan, onGuardado, onCancelar }: { plan: Plan; onGuardado: (mensaje: string) => void; onCancelar: () => void }) {
  const gratuito = plan.periodicidad === 'gratuito';
  const [precio, setPrecio] = useState(String(Math.round(Number(plan.precio))));
  const [activo, setActivo] = useState(!!plan.activo);
  const [funcionalidades, setFuncionalidades] = useState(aLineas(plan.funcionalidades));
  const [limites, setLimites] = useState(aLineas(plan.limites));
  const [condiciones, setCondiciones] = useState(plan.condiciones);
  const [error, setError] = useState<string | null>(null);
  const [guardando, setGuardando] = useState(false);
  const [confirmando, setConfirmando] = useState(false);

  const precioValido = /^\d{1,8}$/.test(precio.trim()) && (gratuito ? Number(precio) === 0 : Number(precio) > 0);
  const errorPrecio = precioValido ? null : gratuito ? 'El plan gratuito no tiene precio.' : 'Ingresá un precio mayor que cero, sin puntos ni decimales.';
  const faltanFunciones = deLineas(funcionalidades).length === 0;

  const guardar = async () => {
    setConfirmando(false); setError(null); setGuardando(true);
    const datos: Record<string, unknown> = {
      activo, funcionalidades: deLineas(funcionalidades), limites: deLineas(limites), condiciones: condiciones.trim(),
    };
    if (!gratuito) datos.precio = Number(precio);
    const r = await api(`/admin/planes/${plan.codigo}`, { method: 'PATCH', json: datos });
    setGuardando(false);
    if (!r.ok) return setError(mensaje(r));
    onGuardado(r.data.mensaje);
  };

  return (
    <Tarjeta>
      <Text style={{ fontSize: 18, fontFamily: FUENTE.titulo, color: COLOR.primario, marginBottom: 8 }}>Editar «{plan.nombre}»</Text>
      {error && <Aviso tipo="error" texto={error} />}
      {!gratuito && (
        <Campo etiqueta={`Precio en ${plan.moneda === 'PYG' ? 'guaraníes' : plan.moneda} (IVA incluido)`} value={precio} onChangeText={setPrecio}
          keyboardType="number-pad" maxLength={8} error={errorPrecio} />
      )}
      <Campo etiqueta="Funcionalidades (una por línea)" value={funcionalidades} onChangeText={setFuncionalidades} multiline
        error={faltanFunciones ? 'Agregá al menos una funcionalidad.' : null} style={{ minHeight: 110, textAlignVertical: 'top' }} />
      <Campo etiqueta="Límites (uno por línea, opcional)" value={limites} onChangeText={setLimites} multiline style={{ minHeight: 70, textAlignVertical: 'top' }} />
      <Campo etiqueta="Condiciones" value={condiciones} onChangeText={setCondiciones} multiline maxLength={1000}
        error={condiciones.trim() ? null : 'Las condiciones no pueden quedar vacías.'} style={{ minHeight: 80, textAlignVertical: 'top' }} />
      {!gratuito && <Casilla marcada={activo} onCambio={setActivo}><Text style={{ fontFamily: FUENTE.texto, color: COLOR.texto }}>Plan activo (se ofrece al público)</Text></Casilla>}
      <View style={{ marginTop: 10 }}>
        <Boton texto="Guardar cambios" icono="save-outline" cargando={guardando}
          deshabilitado={(!gratuito && !precioValido) || faltanFunciones || !condiciones.trim()} onPress={() => setConfirmando(true)} />
        <Boton texto="Cancelar" variante="secundario" icono="close" estilo={{ marginTop: 8 }} onPress={onCancelar} />
      </View>
      <Confirmar visible={confirmando} titulo="¿Guardar los cambios del plan?"
        mensaje={`Los cambios se ven enseguida en la página pública de planes${!gratuito && Number(precio) !== Math.round(Number(plan.precio)) ? ' y el nuevo precio se cobra en los pagos que se inicien desde ahora' : ''}${!activo && plan.activo ? '. Al desactivarlo deja de ofrecerse; las suscripciones vigentes no cambian' : ''}.`}
        textoConfirmar="Guardar" onConfirmar={guardar} onCancelar={() => setConfirmando(false)} />
    </Tarjeta>
  );
}
