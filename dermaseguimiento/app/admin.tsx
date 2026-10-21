import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Text, TouchableOpacity, View } from 'react-native';
import { Aviso, Boton, Campo, Casilla, COLOR, Confirmar, Pantalla, Subtitulo, Tarjeta, Titulo, FUENTE } from '../components/ui';
import { api, fechaCorta, formatoMonto, mensaje } from '../lib/api';
import { CampoFecha, hoyTexto } from '../components/CampoFecha';

type Seccion = 'usuarios' | 'suscripciones' | 'comprobantes' | 'pacientes' | 'auditoria' | 'correo';
const SECCIONES: { id: Seccion; texto: string }[] = [
  { id: 'usuarios', texto: 'Usuarios' }, { id: 'suscripciones', texto: 'Suscripciones' },
  { id: 'comprobantes', texto: 'Comprobantes' }, { id: 'pacientes', texto: 'Pacientes dados de baja' },
  { id: 'auditoria', texto: 'Auditoría' }, { id: 'correo', texto: 'Correo' },
];
const TAM = 20;

/** Paginación común a los listados: «Página X de Y» con anterior y siguiente. */
function Paginador({ pagina, total, tamano = TAM, onIr }: { pagina: number; total: number; tamano?: number; onIr: (p: number) => void }) {
  const paginas = Math.max(1, Math.ceil(total / tamano));
  if (total <= tamano) return <Text style={{ color: COLOR.textoSuave, marginVertical: 8 }}>{total} {total === 1 ? 'resultado' : 'resultados'}</Text>;
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, marginVertical: 8 }}>
      <Boton texto="Anterior" icono="chevron-back" variante="secundario" deshabilitado={pagina <= 1} onPress={() => onIr(pagina - 1)} estilo={{ flex: 1 }} />
      <Text style={{ color: COLOR.textoSuave, fontFamily: FUENTE.texto }} accessibilityLiveRegion="polite">Página {pagina} de {paginas} · {total}</Text>
      <Boton texto="Siguiente" icono="chevron-forward" variante="secundario" deshabilitado={pagina >= paginas} onPress={() => onIr(pagina + 1)} estilo={{ flex: 1 }} />
    </View>
  );
}

export default function AdminScreen() {
  const [seccion, setSeccion] = useState<Seccion>('usuarios');
  const [prohibido, setProhibido] = useState(false);

  useEffect(() => { api('/perfil').then((r) => r.ok && r.data.rol !== 'admin' && setProhibido(true)); }, []);

  if (prohibido) return <Pantalla><Aviso tipo="error" texto="Esta sección es solo para administradores." /></Pantalla>;

  return (
    <Pantalla>
      <Titulo>Administración</Titulo>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 10 }}>
        {SECCIONES.map((s) => (
          <TouchableOpacity key={s.id} accessibilityRole="button" accessibilityLabel={s.texto} onPress={() => setSeccion(s.id)}
            style={{ paddingVertical: 10, paddingHorizontal: 14, borderRadius: 20, borderWidth: 1, borderColor: COLOR.primario, backgroundColor: seccion === s.id ? COLOR.primario : '#fff' }}>
            <Text style={{ color: seccion === s.id ? '#fff' : COLOR.primario, fontFamily: FUENTE.textoFuerte }}>{s.texto}</Text>
          </TouchableOpacity>
        ))}
      </View>
      {/* PUNTO DE MONTAJE (integración): acá van <AdminSeguridad /> y el enlace a la pantalla de planes
          (router.push('/admin-planes')), que se desarrollan por separado. No agregar otra cosa en este lugar. */}
      {seccion === 'usuarios' && <Usuarios />}
      {seccion === 'suscripciones' && <Suscripciones />}
      {seccion === 'comprobantes' && <Comprobantes />}
      {seccion === 'pacientes' && <PacientesBaja />}
      {seccion === 'auditoria' && <Auditoria />}
      {seccion === 'correo' && <><Correo /><PlantillasCorreo /></>}
    </Pantalla>
  );
}

function Usuarios() {
  const [q, setQ] = useState('');
  const [items, setItems] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [pagina, setPagina] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [accion, setAccion] = useState<{ u: any; tipo: 'inactivar' | 'reactivar' } | null>(null);

  const cargar = useCallback(async (p = 1) => {
    setError(null);
    const r = await api(`/admin/usuarios?pagina=${p}&tamano=${TAM}${q.trim() ? `&q=${encodeURIComponent(q.trim())}` : ''}`);
    if (!r.ok) return setError(mensaje(r));
    setItems(r.data.items); setTotal(r.data.total); setPagina(p);
  }, [q]);
  useEffect(() => { cargar(1); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const ejecutar = async (motivo: string) => {
    const { u, tipo } = accion!; setAccion(null);
    const r = await api(`/admin/usuarios/${u.id}/${tipo}`, { method: 'POST', json: { motivo: motivo || null, confirmar: true } });
    if (!r.ok) return setError(mensaje(r));
    setInfo(r.data.mensaje); cargar(pagina);
  };

  return (
    <>
      {error && <Aviso tipo="error" texto={error} />}
      {info && <Aviso tipo="ok" texto={info} />}
      <Campo etiqueta="Buscar usuario" value={q} onChangeText={setQ} onSubmitEditing={() => cargar(1)} maxLength={80} />
      <Boton texto="Buscar" icono="search" onPress={() => cargar(1)} />
      <Paginador pagina={pagina} total={total} onIr={cargar} />
      {items.map((u) => (
        <Tarjeta key={u.id} color={u.activo ? COLOR.suave : '#FDECEA'}>
          <Text style={{ fontFamily: FUENTE.textoFuerte }}>{u.nombre} · {u.rol}</Text>
          <Text>{u.email}</Text>
          <Text style={{ color: COLOR.textoSuave }}>Alta: {fechaCorta(u.fecha_creacion)} · Último acceso: {fechaCorta(u.ultimo_acceso)}</Text>
          {!u.activo && <Text style={{ color: COLOR.error }}>Inactivo desde {fechaCorta(u.fecha_inactivacion)}{u.motivo_inactivacion ? ` — ${u.motivo_inactivacion}` : ''}</Text>}
          {u.fecha_reactivacion && u.activo && <Text style={{ color: COLOR.textoSuave }}>Reactivado: {fechaCorta(u.fecha_reactivacion)}</Text>}
          {u.activo
            ? <Boton texto="Inactivar" icono="ban-outline" variante="peligro" estilo={{ marginTop: 8 }} onPress={() => setAccion({ u, tipo: 'inactivar' })} />
            : <Boton texto="Reactivar" icono="checkmark-circle-outline" estilo={{ marginTop: 8 }} onPress={() => setAccion({ u, tipo: 'reactivar' })} />}
        </Tarjeta>
      ))}
      {items.length > 0 && <Paginador pagina={pagina} total={total} onIr={cargar} />}
      <Confirmar visible={!!accion} peligro={accion?.tipo === 'inactivar'} pedirMotivo motivoObligatorio={accion?.tipo === 'inactivar'}
        titulo={accion?.tipo === 'inactivar' ? '¿Inactivar usuario?' : '¿Reactivar usuario?'}
        mensaje={accion?.tipo === 'inactivar' ? `${accion?.u.email} no podrá iniciar sesión y se cerrarán sus sesiones abiertas.` : `${accion?.u.email} podrá volver a ingresar.`}
        textoConfirmar={accion?.tipo === 'inactivar' ? 'Sí, inactivar' : 'Sí, reactivar'} onConfirmar={ejecutar} onCancelar={() => setAccion(null)} />
    </>
  );
}

function Suscripciones() {
  const [cat, setCat] = useState('');
  const [q, setQ] = useState('');
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const cargar = useCallback(async (c: string, p = 1, texto = '') => {
    setError(null);
    const r = await api(`/admin/suscripciones?pagina=${p}&tamano=${TAM}${c ? `&categoria=${c}` : ''}${texto.trim() ? `&q=${encodeURIComponent(texto.trim())}` : ''}`);
    if (r.ok) setData(r.data); else setError(mensaje(r));
  }, []);
  useEffect(() => { cargar(cat, 1, q); }, [cat, cargar]); // eslint-disable-line react-hooks/exhaustive-deps

  const CATS: [string, string][] = [['', 'Todas'], ['activa', 'Activas'], ['proxima_a_vencer', 'Por vencer'], ['vencida', 'Vencidas'], ['cancelada', 'Canceladas'], ['pendiente_pago', 'Pend. de pago']];
  return (
    <>
      {error && <Aviso tipo="error" texto={error} />}
      {data && <Text style={{ marginBottom: 8, color: COLOR.textoSuave }}>
        Activas {data.resumen.activa} · Por vencer {data.resumen.proxima_a_vencer} · Vencidas {data.resumen.vencida} · Canceladas {data.resumen.cancelada} · Pendientes {data.resumen.pendiente_pago}
      </Text>}
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 8 }}>
        {CATS.map(([id, t]) => (
          <TouchableOpacity key={id} onPress={() => setCat(id)} accessibilityRole="button" accessibilityLabel={t}
            style={{ paddingVertical: 6, paddingHorizontal: 12, borderRadius: 16, borderWidth: 1, borderColor: COLOR.primario, backgroundColor: cat === id ? COLOR.primario : '#fff' }}>
            <Text style={{ color: cat === id ? '#fff' : COLOR.primario }}>{t}</Text>
          </TouchableOpacity>
        ))}
      </View>
      <Campo etiqueta="Buscar por nombre o correo" value={q} onChangeText={setQ} onSubmitEditing={() => cargar(cat, 1, q)} autoCapitalize="none" maxLength={80} />
      {!data && !error && <ActivityIndicator color={COLOR.primario} />}
      {data && <Paginador pagina={data.pagina} total={data.total} onIr={(p) => cargar(cat, p, q)} />}
      {data?.items.map((s: any) => (
        <Tarjeta key={s.suscripcion_id}>
          <Text style={{ fontFamily: FUENTE.textoFuerte }}>{s.usuario} — {s.plan}</Text>
          <Text>{s.email}</Text>
          <Text>Estado: {s.categoria.replace(/_/g, ' ')}{s.es_prueba ? ' (prueba)' : ''}</Text>
          <Text>Vence: {s.fecha_vencimiento ? `${fechaCorta(s.fecha_vencimiento)} (${s.dias_restantes} días)` : 'sin vencimiento'}</Text>
        </Tarjeta>
      ))}
      {data && data.items.length === 0 && <Text style={{ color: COLOR.textoSuave }}>No hay suscripciones en esta categoría.</Text>}
      {data && data.items.length > 0 && <Paginador pagina={data.pagina} total={data.total} onIr={(p) => cargar(cat, p, q)} />}
    </>
  );
}

function Auditoria() {
  const [modulo, setModulo] = useState('');
  const [resultado, setResultado] = useState('');
  const [usuario, setUsuario] = useState('');
  const [desde, setDesde] = useState('');
  const [hasta, setHasta] = useState('');
  const [items, setItems] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [pagina, setPagina] = useState(1);
  const [error, setError] = useState<string | null>(null);

  const cargar = useCallback(async (p: number) => {
    setError(null);
    if (desde && hasta && desde > hasta) return setError('La fecha «desde» no puede ser posterior a «hasta».');
    const qs = `pagina=${p}&tamano=${TAM}${modulo ? `&modulo=${encodeURIComponent(modulo)}` : ''}${resultado ? `&resultado=${resultado}` : ''}`
      + `${usuario ? `&usuario=${encodeURIComponent(usuario)}` : ''}${desde ? `&desde=${desde}` : ''}${hasta ? `&hasta=${hasta}` : ''}`;
    const r = await api(`/admin/auditoria?${qs}`);
    if (!r.ok) return setError(mensaje(r));
    setItems(r.data.items);
    setTotal(r.data.total); setPagina(p);
  }, [modulo, resultado, usuario, desde, hasta]);
  useEffect(() => { cargar(1); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <>
      {error && <Aviso tipo="error" texto={error} />}
      <Campo etiqueta="Usuario (correo)" value={usuario} onChangeText={setUsuario} autoCapitalize="none" maxLength={80} />
      <Campo etiqueta="Módulo (auth, pacientes, seguimientos, pagos…)" value={modulo} onChangeText={setModulo} autoCapitalize="none" maxLength={40} />
      <View style={{ flexDirection: 'row', gap: 6, marginBottom: 8 }}>
        {[['', 'Todos'], ['exito', 'Éxito'], ['fallo', 'Fallo']].map(([id, t]) => (
          <TouchableOpacity key={id} onPress={() => setResultado(id)} accessibilityRole="button" accessibilityLabel={t}
            style={{ flex: 1, padding: 8, borderRadius: 8, borderWidth: 1, borderColor: COLOR.primario, alignItems: 'center', backgroundColor: resultado === id ? COLOR.primario : '#fff' }}>
            <Text style={{ color: resultado === id ? '#fff' : COLOR.primario }}>{t}</Text>
          </TouchableOpacity>
        ))}
      </View>
      <CampoFecha etiqueta="Desde (opcional)" valor={desde} onCambio={setDesde} maximo={hasta || hoyTexto()} />
      <CampoFecha etiqueta="Hasta (opcional)" valor={hasta} onCambio={setHasta} minimo={desde || undefined} maximo={hoyTexto()} />
      <Boton texto="Aplicar filtros" icono="filter-outline" onPress={() => cargar(1)} />
      <Text style={{ marginTop: 8, color: COLOR.textoSuave }}>Registros de solo lectura</Text>
      <Paginador pagina={pagina} total={total} onIr={cargar} />
      {items.map((a) => (
        <View key={a.id} style={{ paddingVertical: 8, borderBottomWidth: 1, borderColor: '#eee' }}>
          <Text style={{ fontFamily: FUENTE.textoFuerte, color: a.resultado === 'fallo' ? COLOR.error : COLOR.primario }}>{a.modulo} · {a.accion} · {a.resultado}</Text>
          <Text style={{ fontSize: 12 }}>{fechaCorta(a.fecha)} · {a.usuario ?? 'sin usuario'} · {a.ip ?? '—'}</Text>
          {a.detalle ? <Text style={{ fontSize: 12, color: COLOR.textoSuave }}>{a.detalle}</Text> : null}
        </View>
      ))}
      {items.length > 0 && <Paginador pagina={pagina} total={total} onIr={cargar} />}
    </>
  );
}

function Correo() {
  const [c, setC] = useState<any>(null);
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [guardando, setGuardando] = useState(false);

  useEffect(() => { api('/admin/config-correo').then((r) => (r.ok ? setC(r.data) : setError(mensaje(r)))); }, []);
  if (!c) return error ? <Aviso tipo="error" texto={error} /> : <ActivityIndicator color={COLOR.primario} />;
  const set = (k: string) => (v: string) => setC((x: any) => ({ ...x, [k]: v }));

  const guardar = async () => {
    setError(null); setInfo(null);
    const puerto = parseInt(String(c.puerto), 10);
    if (!Number.isInteger(puerto) || puerto < 1 || puerto > 65535) return setError('El puerto debe ser un número entre 1 y 65535.');
    if (!['none', 'starttls', 'ssl'].includes(c.seguridad)) return setError('El cifrado debe ser none, starttls o ssl.');
    setGuardando(true);
    const r = await api('/admin/config-correo', {
      method: 'PUT',
      json: { habilitado: !!c.habilitado, host: c.host, puerto, seguridad: c.seguridad, usuario: c.usuario, password: password || null,
        remitente_email: c.remitente_email, remitente_nombre: c.remitente_nombre, timeout_segundos: parseInt(String(c.timeout), 10) || 10 },
    });
    setGuardando(false);
    if (!r.ok) return setError(mensaje(r));
    setC({ ...r.data, timeout: r.data.timeout }); setPassword(''); setInfo('Configuración guardada. La contraseña se almacena cifrada y no se vuelve a mostrar.');
  };

  const probar = async () => {
    setError(null); setInfo(null);
    const r = await api('/admin/config-correo/probar', { method: 'POST' });
    if (r.ok) setInfo(r.data.mensaje); else setError(mensaje(r));
  };

  return (
    <>
      <Subtitulo>Servidor de correo (SMTP)</Subtitulo>
      {error && <Aviso tipo="error" texto={error} />}
      {info && <Aviso tipo="ok" texto={info} />}
      <Casilla marcada={!!c.habilitado} onCambio={(v) => setC((x: any) => ({ ...x, habilitado: v }))}><Text>Servicio de correo habilitado</Text></Casilla>
      <Campo etiqueta="Servidor" value={c.host} onChangeText={set('host')} autoCapitalize="none" maxLength={200} />
      <Campo etiqueta="Puerto" value={String(c.puerto)} onChangeText={set('puerto')} keyboardType="numeric" maxLength={5} />
      <Campo etiqueta="Cifrado (none, starttls o ssl)" value={c.seguridad} onChangeText={set('seguridad')} autoCapitalize="none" maxLength={10} />
      <Campo etiqueta="Usuario" value={c.usuario} onChangeText={set('usuario')} autoCapitalize="none" maxLength={200} />
      <Campo etiqueta="Contraseña" value={password} onChangeText={setPassword} secureTextEntry maxLength={300}
        ayuda={c.password_configurada ? 'Ya hay una contraseña guardada (cifrada). Dejalo vacío para conservarla.' : 'Todavía no hay contraseña guardada.'} />
      <Campo etiqueta="Correo remitente" value={c.remitente_email} onChangeText={set('remitente_email')} autoCapitalize="none" maxLength={200} />
      <Campo etiqueta="Nombre del remitente" value={c.remitente_nombre} onChangeText={set('remitente_nombre')} maxLength={100} />
      <Campo etiqueta="Tiempo de espera (segundos)" value={String(c.timeout)} onChangeText={set('timeout')} keyboardType="numeric" maxLength={3} />
      <Boton texto="Guardar configuración" icono="save-outline" onPress={guardar} cargando={guardando} />
      <Boton texto="Probar conexión" icono="flash-outline" variante="secundario" estilo={{ marginTop: 8 }} onPress={probar} />
    </>
  );
}

function Comprobantes() {
  const [q, setQ] = useState('');
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [anular, setAnular] = useState<any>(null);

  const cargar = useCallback(async (p = 1) => {
    setError(null);
    const r = await api(`/admin/comprobantes?pagina=${p}&tamano=${TAM}${q.trim() ? `&q=${encodeURIComponent(q.trim())}` : ''}`);
    if (r.ok) setData(r.data); else setError(mensaje(r));
  }, [q]);
  useEffect(() => { cargar(1); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const confirmarAnulacion = async (motivo: string) => {
    const c = anular; setAnular(null); setInfo(null);
    const r = await api(`/admin/comprobantes/${c.id}/anular`, { method: 'POST', json: { motivo, confirmar: true } });
    if (!r.ok) return setError(mensaje(r));
    setInfo(r.data.mensaje); cargar(data?.pagina ?? 1);
  };

  return (
    <>
      {error && <Aviso tipo="error" texto={error} />}
      {info && <Aviso tipo="ok" texto={info} />}
      <Text style={{ color: COLOR.textoSuave, marginBottom: 8 }}>Los recibos no se editan: si tienen un error se anulan (queda constancia del motivo) y se emite otro.</Text>
      <Campo etiqueta="Buscar por número, nombre o correo" value={q} onChangeText={setQ} onSubmitEditing={() => cargar(1)} autoCapitalize="none" maxLength={80} />
      <Boton texto="Buscar" icono="search" onPress={() => cargar(1)} />
      {!data && !error && <ActivityIndicator color={COLOR.primario} />}
      {data && <Paginador pagina={data.pagina} total={data.total} onIr={cargar} />}
      {data?.items.map((c: any) => (
        <Tarjeta key={c.id} color={c.estado === 'anulado' ? '#FDECEA' : COLOR.tarjeta}>
          <Text style={{ fontFamily: FUENTE.textoFuerte }}>{c.numero} · {formatoMonto(c.monto, c.moneda)}</Text>
          <Text>{c.pagador_nombre} · {c.pagador_email}</Text>
          <Text style={{ color: COLOR.textoSuave }}>{c.concepto} · {fechaCorta(c.fecha_emision)}</Text>
          {c.estado === 'anulado'
            ? <Text style={{ color: COLOR.error }}>Anulado el {fechaCorta(c.anulado_en)}{c.motivo_anulacion ? ` — ${c.motivo_anulacion}` : ''}</Text>
            : <Boton texto="Anular comprobante" icono="close-circle-outline" variante="peligro" estilo={{ marginTop: 8 }} onPress={() => setAnular(c)} />}
        </Tarjeta>
      ))}
      {data && data.items.length === 0 && <Text style={{ color: COLOR.textoSuave }}>No hay comprobantes con esos datos.</Text>}
      <Confirmar visible={!!anular} peligro pedirMotivo motivoObligatorio titulo="¿Anular el comprobante?"
        mensaje={`El comprobante ${anular?.numero ?? ''} quedará anulado de forma permanente. Esta acción no se puede deshacer.`}
        textoConfirmar="Sí, anular" onConfirmar={confirmarAnulacion} onCancelar={() => setAnular(null)} />
    </>
  );
}

function PacientesBaja() {
  const [q, setQ] = useState('');
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [reactivar, setReactivar] = useState<any>(null);

  const cargar = useCallback(async (p = 1) => {
    setError(null);
    const r = await api(`/admin/pacientes-baja?pagina=${p}&tamano=${TAM}${q.trim() ? `&q=${encodeURIComponent(q.trim())}` : ''}`);
    if (r.ok) setData(r.data); else setError(mensaje(r));
  }, [q]);
  useEffect(() => { cargar(1); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const confirmar = async (motivo: string) => {
    const p = reactivar; setReactivar(null); setInfo(null);
    const r = await api(`/admin/pacientes/${p.id}/reactivar`, { method: 'POST', json: { confirmar: true, motivo: motivo || null } });
    if (!r.ok) return setError(mensaje(r));
    setInfo(r.data.mensaje); cargar(1);
  };

  return (
    <>
      {error && <Aviso tipo="error" texto={error} />}
      {info && <Aviso tipo="ok" texto={info} />}
      <Text style={{ color: COLOR.textoSuave, marginBottom: 8 }}>Pacientes que su dermatólogo dio de baja. Al reactivarlos vuelven a su lista con todo el historial.</Text>
      <Campo etiqueta="Buscar por cédula, nombre o apellido" value={q} onChangeText={setQ} onSubmitEditing={() => cargar(1)} maxLength={80} />
      <Boton texto="Buscar" icono="search" onPress={() => cargar(1)} />
      {!data && !error && <ActivityIndicator color={COLOR.primario} />}
      {data && <Paginador pagina={data.pagina} total={data.total} onIr={cargar} />}
      {data?.items.map((p: any) => (
        <Tarjeta key={p.id} color="#FDECEA">
          <Text style={{ fontFamily: FUENTE.textoFuerte }}>{p.nombre} {p.apellido} · CI {p.cedula}</Text>
          <Text>Dermatólogo: {p.dermatologo}</Text>
          <Text style={{ color: COLOR.textoSuave }}>Baja: {fechaCorta(p.eliminado_en)}{p.motivo_eliminacion ? ` — ${p.motivo_eliminacion}` : ''}</Text>
          <Boton texto="Reactivar" icono="refresh-outline" estilo={{ marginTop: 8 }} onPress={() => setReactivar(p)} />
        </Tarjeta>
      ))}
      {data && data.items.length === 0 && <Text style={{ color: COLOR.textoSuave }}>No hay pacientes dados de baja.</Text>}
      <Confirmar visible={!!reactivar} pedirMotivo titulo="¿Reactivar al paciente?"
        mensaje={`${reactivar?.nombre ?? ''} ${reactivar?.apellido ?? ''} volverá a la lista de ${reactivar?.dermatologo ?? 'su dermatólogo'}.`}
        textoConfirmar="Sí, reactivar" onConfirmar={confirmar} onCancelar={() => setReactivar(null)} />
    </>
  );
}

const NOMBRES_PLANTILLA: Record<string, string> = {
  restablecer_password: 'Recuperación de contraseña', verificar_email: 'Verificación de correo',
  aviso_vencimiento: 'Aviso de vencimiento', suscripcion_vencida: 'Suscripción vencida', pago_aprobado: 'Pago aprobado',
};

/** Textos de los correos que envía el sistema. Las variables ($nombre, $enlace…) se reemplazan al enviar. */
function PlantillasCorreo() {
  const [items, setItems] = useState<any[] | null>(null);
  const [abierta, setAbierta] = useState<string | null>(null);
  const [borrador, setBorrador] = useState<{ asunto: string; cuerpo: string }>({ asunto: '', cuerpo: '' });
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [guardando, setGuardando] = useState(false);

  const cargar = useCallback(async () => {
    const r = await api('/admin/plantillas-correo');
    if (r.ok) setItems(r.data); else setError(mensaje(r));
  }, []);
  useEffect(() => { cargar(); }, [cargar]);

  const abrir = (p: any) => { setAbierta(p.codigo); setBorrador({ asunto: p.asunto, cuerpo: p.cuerpo }); setError(null); setInfo(null); };
  const variables = (t: string) => Array.from(new Set(t.match(/\$\w+/g) ?? []));

  const guardar = async () => {
    setError(null); setInfo(null);
    if (borrador.asunto.trim().length < 3) return setError('El asunto debe tener al menos 3 caracteres.');
    if (borrador.cuerpo.trim().length < 10) return setError('El texto del correo debe tener al menos 10 caracteres.');
    const original = items?.find((p) => p.codigo === abierta);
    const faltan = variables(original?.cuerpo ?? '').filter((v) => !borrador.cuerpo.includes(v));
    if (faltan.length) return setError(`El texto debe conservar las variables ${faltan.join(', ')}: se reemplazan por los datos reales al enviar.`);
    setGuardando(true);
    const r = await api(`/admin/plantillas-correo/${abierta}`, { method: 'PUT', json: { asunto: borrador.asunto.trim(), cuerpo: borrador.cuerpo } });
    setGuardando(false);
    if (!r.ok) return setError(mensaje(r));
    setInfo(r.data.mensaje); setAbierta(null); cargar();
  };

  return (
    <>
      <Subtitulo>Plantillas de correo</Subtitulo>
      {error && <Aviso tipo="error" texto={error} />}
      {info && <Aviso tipo="ok" texto={info} />}
      {!items && !error && <ActivityIndicator color={COLOR.primario} />}
      {items?.map((p) => (
        <Tarjeta key={p.codigo}>
          <Text style={{ fontFamily: FUENTE.textoFuerte }}>{NOMBRES_PLANTILLA[p.codigo] ?? p.codigo.replace(/_/g, ' ')}{p.personalizada ? ' (personalizada)' : ''}</Text>
          {abierta === p.codigo ? (
            <>
              <Campo etiqueta="Asunto" value={borrador.asunto} onChangeText={(v) => setBorrador((b) => ({ ...b, asunto: v }))} maxLength={200} />
              <Campo etiqueta="Texto del correo" value={borrador.cuerpo} onChangeText={(v) => setBorrador((b) => ({ ...b, cuerpo: v }))} multiline maxLength={5000}
                ayuda={variables(p.cuerpo).length ? `Variables disponibles: ${variables(p.cuerpo).join(', ')}` : undefined} />
              <Boton texto="Guardar plantilla" icono="save-outline" onPress={guardar} cargando={guardando} />
              <Boton texto="Cancelar" icono="close" variante="secundario" estilo={{ marginTop: 8 }} onPress={() => setAbierta(null)} />
            </>
          ) : (
            <>
              <Text style={{ color: COLOR.textoSuave }} numberOfLines={1}>{p.asunto}</Text>
              <Boton texto="Editar" icono="create-outline" variante="texto" onPress={() => abrir(p)} estilo={{ alignSelf: 'flex-start' }} />
            </>
          )}
        </Tarjeta>
      ))}
    </>
  );
}
