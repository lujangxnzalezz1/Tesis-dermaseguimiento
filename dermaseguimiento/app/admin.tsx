import { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Text, TouchableOpacity, View } from 'react-native';
import { Aviso, Boton, Campo, Casilla, COLOR, Confirmar, Pantalla, Subtitulo, Tarjeta, Titulo, FUENTE } from '../components/ui';
import { api, fechaCorta, mensaje } from '../lib/api';

type Seccion = 'usuarios' | 'suscripciones' | 'auditoria' | 'correo';
const SECCIONES: { id: Seccion; texto: string }[] = [
  { id: 'usuarios', texto: 'Usuarios' }, { id: 'suscripciones', texto: 'Suscripciones' },
  { id: 'auditoria', texto: 'Auditoría' }, { id: 'correo', texto: 'Correo' },
];

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
      {seccion === 'usuarios' && <Usuarios />}
      {seccion === 'suscripciones' && <Suscripciones />}
      {seccion === 'auditoria' && <Auditoria />}
      {seccion === 'correo' && <Correo />}
    </Pantalla>
  );
}

function Usuarios() {
  const [q, setQ] = useState('');
  const [items, setItems] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [accion, setAccion] = useState<{ u: any; tipo: 'inactivar' | 'reactivar' } | null>(null);

  const cargar = useCallback(async () => {
    setError(null);
    const r = await api(`/admin/usuarios?tamano=50${q.trim() ? `&q=${encodeURIComponent(q.trim())}` : ''}`);
    if (r.ok) setItems(r.data.items); else setError(mensaje(r));
  }, [q]);
  useEffect(() => { cargar(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const ejecutar = async (motivo: string) => {
    const { u, tipo } = accion!; setAccion(null);
    const r = await api(`/admin/usuarios/${u.id}/${tipo}`, { method: 'POST', json: { motivo: motivo || null, confirmar: true } });
    if (!r.ok) return setError(mensaje(r));
    setInfo(r.data.mensaje); cargar();
  };

  return (
    <>
      {error && <Aviso tipo="error" texto={error} />}
      {info && <Aviso tipo="ok" texto={info} />}
      <Campo etiqueta="Buscar usuario" value={q} onChangeText={setQ} onSubmitEditing={cargar} maxLength={80} />
      <Boton texto="Buscar" icono="search" onPress={cargar} />
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
      <Confirmar visible={!!accion} peligro={accion?.tipo === 'inactivar'} pedirMotivo motivoObligatorio={accion?.tipo === 'inactivar'}
        titulo={accion?.tipo === 'inactivar' ? '¿Inactivar usuario?' : '¿Reactivar usuario?'}
        mensaje={accion?.tipo === 'inactivar' ? `${accion?.u.email} no podrá iniciar sesión y se cerrarán sus sesiones abiertas.` : `${accion?.u.email} podrá volver a ingresar.`}
        textoConfirmar={accion?.tipo === 'inactivar' ? 'Sí, inactivar' : 'Sí, reactivar'} onConfirmar={ejecutar} onCancelar={() => setAccion(null)} />
    </>
  );
}

function Suscripciones() {
  const [cat, setCat] = useState('');
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const cargar = useCallback(async (c: string) => {
    const r = await api(`/admin/suscripciones?tamano=100${c ? `&categoria=${c}` : ''}`);
    if (r.ok) setData(r.data); else setError(mensaje(r));
  }, []);
  useEffect(() => { cargar(cat); }, [cat, cargar]);

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
      {!data && <ActivityIndicator color={COLOR.primario} />}
      {data?.items.map((s: any) => (
        <Tarjeta key={s.suscripcion_id}>
          <Text style={{ fontFamily: FUENTE.textoFuerte }}>{s.usuario} — {s.plan}</Text>
          <Text>{s.email}</Text>
          <Text>Estado: {s.categoria.replace(/_/g, ' ')}{s.es_prueba ? ' (prueba)' : ''}</Text>
          <Text>Vence: {s.fecha_vencimiento ? `${fechaCorta(s.fecha_vencimiento)} (${s.dias_restantes} días)` : 'sin vencimiento'}</Text>
        </Tarjeta>
      ))}
      {data && data.items.length === 0 && <Text style={{ color: COLOR.textoSuave }}>No hay suscripciones en esta categoría.</Text>}
    </>
  );
}

function Auditoria() {
  const [modulo, setModulo] = useState('');
  const [resultado, setResultado] = useState('');
  const [usuario, setUsuario] = useState('');
  const [items, setItems] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [pagina, setPagina] = useState(1);
  const [error, setError] = useState<string | null>(null);

  const cargar = useCallback(async (p: number) => {
    setError(null);
    const qs = `pagina=${p}&tamano=20${modulo ? `&modulo=${encodeURIComponent(modulo)}` : ''}${resultado ? `&resultado=${resultado}` : ''}${usuario ? `&usuario=${encodeURIComponent(usuario)}` : ''}`;
    const r = await api(`/admin/auditoria?${qs}`);
    if (!r.ok) return setError(mensaje(r));
    setItems((prev) => (p === 1 ? r.data.items : [...prev, ...r.data.items]));
    setTotal(r.data.total); setPagina(p);
  }, [modulo, resultado, usuario]);
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
      <Boton texto="Aplicar filtros" icono="filter-outline" onPress={() => cargar(1)} />
      <Text style={{ marginVertical: 8, color: COLOR.textoSuave }}>{total} registros (solo lectura)</Text>
      {items.map((a) => (
        <View key={a.id} style={{ paddingVertical: 8, borderBottomWidth: 1, borderColor: '#eee' }}>
          <Text style={{ fontFamily: FUENTE.textoFuerte, color: a.resultado === 'fallo' ? COLOR.error : COLOR.primario }}>{a.modulo} · {a.accion} · {a.resultado}</Text>
          <Text style={{ fontSize: 12 }}>{fechaCorta(a.fecha)} · {a.usuario ?? 'sin usuario'} · {a.ip ?? '—'}</Text>
          {a.detalle ? <Text style={{ fontSize: 12, color: COLOR.textoSuave }}>{a.detalle}</Text> : null}
        </View>
      ))}
      {items.length < total && <Boton texto="Cargar más" icono="chevron-down" variante="secundario" onPress={() => cargar(pagina + 1)} />}
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
