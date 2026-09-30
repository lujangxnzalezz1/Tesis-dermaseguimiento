import * as WebBrowser from 'expo-web-browser';
import { useCallback, useState } from 'react';
import { ActivityIndicator, Text, View } from 'react-native';
import { useFocusEffect } from 'expo-router';
import { Aviso, Boton, COLOR, Confirmar, Pantalla, Subtitulo, Tarjeta, Titulo } from '../components/ui';
import { api, fechaCorta, mensaje } from '../lib/api';

const ETIQUETA_ESTADO: Record<string, string> = {
  prueba: 'Período de prueba', activa: 'Activa', vencida: 'Vencida', cancelada: 'Cancelada (activa hasta el vencimiento)', pendiente_pago: 'Pendiente de pago',
};

export default function SuscripcionScreen() {
  const [susc, setSusc] = useState<any>(null);
  const [planes, setPlanes] = useState<any[]>([]);
  const [pagos, setPagos] = useState<any[]>([]);
  const [notifs, setNotifs] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState<string | null>(null);
  const [elegido, setElegido] = useState<any>(null);
  const [cancelando, setCancelando] = useState(false);

  const cargar = useCallback(async () => {
    const [s, p, pg, n] = await Promise.all([api('/suscripcion'), api('/planes', { auth: false }), api('/pagos?tamano=10'), api('/notificaciones')]);
    if (s.ok) setSusc(s.data); else setError(mensaje(s));
    if (p.ok) setPlanes(p.data.planes);
    if (pg.ok) setPagos(pg.data.items);
    if (n.ok) {
      setNotifs(n.data.items.slice(0, 5));
      n.data.items.filter((x: any) => !x.leida).forEach((x: any) => api(`/notificaciones/${x.id}/leida`, { method: 'POST' }));
    }
  }, []);

  useFocusEffect(useCallback(() => { cargar(); }, [cargar]));

  const esperarResultado = async (pagoId: number) => {
    for (let i = 0; i < 15; i++) {
      const r = await api(`/pagos/${pagoId}`);
      if (r.ok && r.data.estado !== 'pendiente') return r.data.estado as string;
      await new Promise((res) => setTimeout(res, 2000));
    }
    return 'pendiente';
  };

  const contratar = async () => {
    const plan = elegido; setElegido(null); setError(null); setInfo(null);
    setOcupado(plan.codigo);
    const r = await api('/suscripcion/checkout', { method: 'POST', json: { plan_codigo: plan.codigo } });
    if (!r.ok) { setOcupado(null); return setError(mensaje(r)); }
    if (r.data.accion !== 'pago') { setOcupado(null); setInfo(r.data.mensaje); return cargar(); }
    await WebBrowser.openBrowserAsync(r.data.url_pago); // pasarela de pago
    const estado = await esperarResultado(r.data.pago_id);
    setOcupado(null);
    if (estado === 'aprobado') setInfo('¡Pago aprobado! Tu suscripción ya está activa y el comprobante quedó registrado.');
    else if (estado === 'rechazado') setError('El pago fue rechazado. No se te cobró nada; podés intentar con otro medio de pago.');
    else if (estado === 'cancelado') setError('Cancelaste el pago. No se realizó ningún cobro.');
    else setInfo('Tu pago sigue pendiente. Cuando la pasarela lo confirme se actualizará esta pantalla.');
    cargar();
  };

  const cancelar = async (motivo: string) => {
    setCancelando(false); setError(null); setInfo(null);
    const r = await api('/suscripcion/cancelar', { method: 'POST', json: { motivo, confirmar: true } });
    if (!r.ok) return setError(mensaje(r));
    setInfo(r.data.mensaje); cargar();
  };

  if (!susc && !error) return <Pantalla><ActivityIndicator size="large" color={COLOR.primario} /></Pantalla>;

  const actual = susc?.plan?.codigo;
  const puedeCancelar = susc && susc.plan.periodicidad !== 'gratuito' && ['prueba', 'activa'].includes(susc.estado) && !susc.es_prueba;

  return (
    <Pantalla>
      <Titulo>Suscripción</Titulo>
      {error && <Aviso tipo="error" texto={error} />}
      {info && <Aviso tipo="ok" texto={info} />}
      {susc && (
        <Tarjeta>
          <Text style={{ fontSize: 18, fontWeight: '700', color: COLOR.primario }}>{susc.plan.nombre}</Text>
          <Text>Estado: {ETIQUETA_ESTADO[susc.estado] ?? susc.estado}</Text>
          {susc.fecha_vencimiento && <Text>Vence: {fechaCorta(susc.fecha_vencimiento)} ({susc.dias_restantes} días)</Text>}
          <Text>Procesamiento de imágenes: {susc.funciones_avanzadas ? 'incluido' : 'no disponible'}</Text>
          {susc.plan_siguiente && <Text>Próximo plan: {susc.plan_siguiente.nombre} (al terminar el período pagado)</Text>}
          {susc.pago_pendiente && <Aviso tipo="aviso" texto="Tenés un pago pendiente de confirmación." />}
          {susc.estado === 'vencida' && <Aviso tipo="aviso" texto="Tu suscripción venció: el procesamiento de imágenes está bloqueado. Renovala abajo." />}
        </Tarjeta>
      )}

      {notifs.length > 0 && (<><Subtitulo>Avisos</Subtitulo>{notifs.map((n) => <Aviso key={n.id} tipo="info" texto={`${fechaCorta(n.fecha)} — ${n.mensaje}`} />)}</>)}

      <Subtitulo>Planes disponibles</Subtitulo>
      {planes.map((p) => (
        <Tarjeta key={p.codigo} color={p.codigo === actual ? '#E8F5E9' : COLOR.suave}>
          <Text style={{ fontSize: 17, fontWeight: '700', color: COLOR.primario }}>{p.nombre}</Text>
          <Text style={{ fontSize: 16 }}>{p.periodicidad === 'gratuito' ? 'Gratis' : `${p.precio} ${p.moneda} / ${p.periodicidad === 'mensual' ? 'mes' : 'año'}`}</Text>
          {p.funcionalidades.map((f: string) => <Text key={f}>• {f}</Text>)}
          {p.limites.map((f: string) => <Text key={f} style={{ color: '#666' }}>– {f}</Text>)}
          <Text style={{ color: '#666', marginTop: 6, fontSize: 12 }}>{p.condiciones}</Text>
          <Boton texto={p.codigo === actual ? (p.periodicidad === 'gratuito' ? 'Plan actual' : 'Renovar este plan') : 'Elegir este plan'}
            icono={p.codigo === actual ? 'refresh' : 'checkmark-circle-outline'} estilo={{ marginTop: 10 }}
            deshabilitado={p.codigo === actual && p.periodicidad === 'gratuito'} cargando={ocupado === p.codigo} onPress={() => setElegido(p)} />
        </Tarjeta>
      ))}
      {puedeCancelar && <Boton texto="Cancelar mi suscripción" icono="close-circle-outline" variante="peligro" onPress={() => setCancelando(true)} />}

      <Subtitulo>Mis pagos y comprobantes</Subtitulo>
      {pagos.length === 0 && <Text style={{ color: '#666' }}>Todavía no tenés pagos.</Text>}
      {pagos.map((p) => (
        <View key={p.id} style={{ paddingVertical: 8, borderBottomWidth: 1, borderColor: '#eee' }}>
          <Text style={{ fontWeight: '600' }}>{fechaCorta(p.fecha)} — {p.plan}</Text>
          <Text>{p.monto} {p.moneda} · {p.estado}{p.comprobante_numero ? ` · Comprobante ${p.comprobante_numero}` : ''}</Text>
        </View>
      ))}

      <Confirmar visible={!!elegido} titulo="Confirmar cambio de plan"
        mensaje={elegido ? `Vas a elegir «${elegido.nombre}»${elegido.periodicidad === 'gratuito' ? '. Se aplicará cuando termine tu período pagado.' : `. Si corresponde pagar, te llevamos a la pasarela de pago. El importe exacto (con crédito por el tiempo no usado, si aplica) se muestra allí.`}` : ''}
        textoConfirmar="Continuar" onConfirmar={contratar} onCancelar={() => setElegido(null)} />
      <Confirmar visible={cancelando} peligro pedirMotivo motivoObligatorio titulo="¿Cancelar la suscripción?"
        mensaje="Vas a conservar las funciones Premium hasta la fecha de vencimiento. No se hacen reembolsos proporcionales."
        textoConfirmar="Sí, cancelar" onConfirmar={cancelar} onCancelar={() => setCancelando(false)} />
    </Pantalla>
  );
}
