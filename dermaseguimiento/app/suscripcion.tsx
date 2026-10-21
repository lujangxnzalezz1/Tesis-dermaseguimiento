import * as WebBrowser from 'expo-web-browser';
import { useCallback, useState } from 'react';
import { ActivityIndicator, Text, View } from 'react-native';
import { router, useFocusEffect } from 'expo-router';
import { Aviso, Boton, Campo, COLOR, Confirmar, Pantalla, Subtitulo, Tarjeta, Titulo, FUENTE } from '../components/ui';
import { api, fechaCorta, formatoMonto, mensaje } from '../lib/api';
import { descargarComprobante as descargarPdf } from '../lib/comprobantes';
import { ESTADO_PAGO, EVENTO_HISTORIAL, precioPlan } from '../lib/planes';

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
  const [cotizacion, setCotizacion] = useState<any>(null);
  const [cancelando, setCancelando] = useState(false);
  const [historial, setHistorial] = useState<any[]>([]);
  const [documento, setDocumento] = useState('');
  const [telefono, setTelefono] = useState('');

  const cargar = useCallback(async () => {
    const [s, p, pg, n, h] = await Promise.all([
      api('/suscripcion'), api('/planes', { auth: false }), api('/pagos?tamano=10'), api('/notificaciones'), api('/suscripcion/historial'),
    ]);
    if (s.ok) setSusc(s.data); else setError(mensaje(s));
    if (p.ok) setPlanes(p.data.planes);
    if (pg.ok) setPagos(pg.data.items);
    if (h.ok) setHistorial(h.data.slice(0, 10));
    if (n.ok) {
      setNotifs(n.data.items.slice(0, 5));
      n.data.items.filter((x: any) => !x.leida).forEach((x: any) => api(`/notificaciones/${x.id}/leida`, { method: 'POST' }));
    }
  }, []);

  useFocusEffect(useCallback(() => { cargar(); }, [cargar]));

  const esperarResultado = async (pagoId: number) => {
    for (let i = 0; i < 90; i++) { // hasta 3 minutos para completar el pago
      const r = await api(`/pagos/${pagoId}`);
      if (r.ok && r.data.estado !== 'pendiente') return r.data.estado as string;
      await new Promise((res) => setTimeout(res, 2000));
    }
    return 'pendiente';
  };

  /** Antes de ir a la pasarela se muestra el importe exacto y el crédito por el tiempo no usado. */
  const elegir = async (plan: any) => {
    setError(null); setInfo(null); setOcupado(plan.codigo);
    const r = await api(`/suscripcion/cotizacion?plan_codigo=${encodeURIComponent(plan.codigo)}`);
    setOcupado(null);
    if (!r.ok) return setError(mensaje(r));
    if (r.data.accion === 'ninguna') return setInfo('Ya estás en ese plan. No hace falta ningún cambio.');
    setCotizacion(r.data); setElegido(plan);
  };

  const textoConfirmacion = (): string => {
    if (!elegido || !cotizacion) return '';
    if (cotizacion.accion === 'programar') {
      return `Vas a pasar al plan «${elegido.nombre}» cuando termine tu período actual. Hasta entonces conservás tus funciones. No se cobra nada ahora y no se hacen reembolsos por bajas de plan.`;
    }
    const m = cotizacion.moneda;
    const lineas = [`Plan: ${elegido.nombre}`, `Precio: ${formatoMonto(cotizacion.precio, m)}`];
    if (Number(cotizacion.credito) > 0) lineas.push(`Crédito por el tiempo no usado de tu plan actual: − ${formatoMonto(cotizacion.credito, m)}`);
    lineas.push(`Total a pagar: ${formatoMonto(cotizacion.monto, m)} (incluye IVA 10 %: ${formatoMonto(cotizacion.iva_incluido, m)})`);
    lineas.push(Number(cotizacion.monto) > 0 ? 'Al continuar te llevamos a la pasarela de pago.' : 'El crédito cubre todo el importe: el cambio se aplica sin pagar.');
    return lineas.join('\n');
  };

  const contratar = async () => {
    const plan = elegido; setElegido(null); setCotizacion(null); setError(null); setInfo(null);
    setOcupado(plan.codigo);
    const datos: Record<string, string> = { plan_codigo: plan.codigo };
    if (documento.trim()) datos.documento = documento.trim();
    if (telefono.trim()) datos.telefono = telefono.trim();
    const r = await api('/suscripcion/checkout', { method: 'POST', json: datos });
    if (!r.ok) { setOcupado(null); return setError(mensaje(r)); }
    if (r.data.accion !== 'pago') { setOcupado(null); setInfo(r.data.mensaje); return cargar(); }
    await WebBrowser.openBrowserAsync(r.data.url_pago); // pasarela de pago
    const estado = await esperarResultado(r.data.pago_id);
    setOcupado(null);
    if (estado === 'aprobado') setInfo('¡Pago aprobado! Tu suscripción ya está activa y el comprobante quedó registrado.');
    else if (estado === 'rechazado') setError('El pago fue rechazado. No se te cobró nada; podés intentar con otro medio de pago.');
    else if (estado === 'cancelado') setError('Cancelaste el pago. No se realizó ningún cobro.');
    else if (estado === 'vencido') setError('El plazo para pagar venció. No se realizó ningún cobro; podés iniciar el pago de nuevo.');
    else setInfo('Tu pago sigue pendiente. Cuando la pasarela lo confirme se actualizará esta pantalla.');
    cargar();
  };

  const cancelar = async (motivo: string) => {
    setCancelando(false); setError(null); setInfo(null);
    const r = await api('/suscripcion/cancelar', { method: 'POST', json: { motivo, confirmar: true } });
    if (!r.ok) return setError(mensaje(r));
    setInfo(r.data.mensaje); cargar();
  };

  const descargarComprobante = async (id: number, numero: string) => {
    setError(null);
    const problema = await descargarPdf(id, numero);
    if (problema) setError(problema);
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
          <Text style={{ fontSize: 18, fontFamily: FUENTE.titulo, color: COLOR.primario }}>{susc.plan.nombre}</Text>
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
      <Boton texto="Comparar planes" icono="git-compare-outline" variante="texto" onPress={() => router.push('/planes')} estilo={{ alignSelf: 'flex-start', paddingHorizontal: 0 }} />
      {planes.map((p) => (
        <Tarjeta key={p.codigo} color={p.codigo === actual ? '#E8F5E9' : COLOR.suave}>
          <Text style={{ fontSize: 17, fontFamily: FUENTE.titulo, color: COLOR.primario }}>{p.nombre}</Text>
          <Text style={{ fontSize: 16 }}>{precioPlan(p)}</Text>
          {p.funcionalidades.map((f: string) => <Text key={f}>• {f}</Text>)}
          {p.limites.map((f: string) => <Text key={f} style={{ color: COLOR.textoSuave }}>– {f}</Text>)}
          <Text style={{ color: COLOR.textoSuave, marginTop: 6, fontSize: 12 }}>{p.condiciones}</Text>
          <Boton texto={p.codigo === actual ? (p.periodicidad === 'gratuito' ? 'Plan actual' : 'Renovar este plan') : 'Elegir este plan'}
            icono={p.codigo === actual ? 'refresh' : 'checkmark-circle-outline'} estilo={{ marginTop: 10 }}
            deshabilitado={p.codigo === actual && p.periodicidad === 'gratuito'} cargando={ocupado === p.codigo} onPress={() => elegir(p)} />
        </Tarjeta>
      ))}
      <Tarjeta color={COLOR.suave}>
        <Text style={{ fontFamily: FUENTE.textoFuerte, color: COLOR.texto, marginBottom: 8 }}>Datos para el recibo (opcional)</Text>
        <Campo etiqueta="RUC o CI" value={documento} onChangeText={setDocumento} maxLength={20} keyboardType="numbers-and-punctuation" placeholder="Ej.: 1234567-8" />
        <Campo etiqueta="Teléfono" value={telefono} onChangeText={setTelefono} maxLength={25} keyboardType="phone-pad" placeholder="Ej.: 0981 123456" />
      </Tarjeta>
      {puedeCancelar && <Boton texto="Cancelar mi suscripción" icono="close-circle-outline" variante="peligro" onPress={() => setCancelando(true)} />}

      <Subtitulo>Mis pagos y comprobantes</Subtitulo>
      {pagos.length === 0 && <Text style={{ color: COLOR.textoSuave }}>Todavía no tenés pagos.</Text>}
      {pagos.map((p) => (
        <View key={p.id} style={{ paddingVertical: 8, borderBottomWidth: 1, borderColor: '#eee' }}>
          <Text style={{ fontFamily: FUENTE.textoFuerte }}>{fechaCorta(p.fecha)} — {p.plan}</Text>
          <Text>{formatoMonto(p.monto, p.moneda)} · {ESTADO_PAGO[p.estado] ?? p.estado}{p.comprobante_numero ? ` · Comprobante ${p.comprobante_numero}` : ''}</Text>
          {p.comprobante_id && (
            <Boton texto="Descargar comprobante (PDF)" icono="download-outline" variante="texto" onPress={() => descargarComprobante(p.comprobante_id, p.comprobante_numero)} />
          )}
        </View>
      ))}

      <Subtitulo>Historial de la suscripción</Subtitulo>
      {historial.length === 0 && <Text style={{ color: COLOR.textoSuave }}>Todavía no hay movimientos.</Text>}
      {historial.map((h, i) => (
        <View key={`${h.fecha}-${i}`} style={{ paddingVertical: 6, borderBottomWidth: 1, borderColor: '#eee' }}>
          <Text style={{ fontFamily: FUENTE.textoFuerte }}>{fechaCorta(h.fecha)} — {EVENTO_HISTORIAL[h.evento] ?? h.evento}</Text>
          {(h.plan_anterior || h.plan_nuevo) && (
            <Text>{h.plan_anterior && h.plan_nuevo && h.plan_anterior !== h.plan_nuevo ? `${h.plan_anterior} → ${h.plan_nuevo}` : (h.plan_nuevo ?? h.plan_anterior)}</Text>
          )}
          {h.detalle && <Text style={{ color: COLOR.textoSuave, fontSize: 13 }}>{h.detalle}</Text>}
        </View>
      ))}

      <Confirmar visible={!!elegido && !!cotizacion} titulo={cotizacion?.accion === 'programar' ? 'Confirmar cambio de plan' : 'Confirmar el pago'}
        mensaje={textoConfirmacion()}
        textoConfirmar={cotizacion?.accion === 'programar' ? 'Programar el cambio' : Number(cotizacion?.monto) > 0 ? 'Ir a pagar' : 'Aplicar el cambio'}
        onConfirmar={contratar} onCancelar={() => { setElegido(null); setCotizacion(null); }} />
      <Confirmar visible={cancelando} peligro pedirMotivo motivoObligatorio titulo="¿Cancelar la suscripción?"
        mensaje="Vas a conservar las funciones Premium hasta la fecha de vencimiento. No se hacen reembolsos proporcionales."
        textoConfirmar="Sí, cancelar" onConfirmar={cancelar} onCancelar={() => setCancelando(false)} />
    </Pantalla>
  );
}
