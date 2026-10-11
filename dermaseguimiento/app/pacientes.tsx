import { router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { Ionicons } from '@expo/vector-icons';
import { ActivityIndicator, Text, TextInput, TouchableOpacity, View } from 'react-native';
import { Aviso, Boton, BotonIcono, Campo, Casilla, COLOR, Confirmar, Iniciales, Pantalla, Pildora, Subtitulo, Tarjeta, Titulo, FUENTE } from '../components/ui';
import { api, cerrarSesion, mensaje } from '../lib/api';
import { vincularUsuarioPush } from '../lib/push';
import { CampoFecha, haceAniosTexto, hoyTexto } from '../components/CampoFecha';

type Paciente = {
  id: number; cedula: string; nombre: string; apellido: string; telefono: string | null; tiene_consentimiento: boolean;
};

const TEXTO_CONSENTIMIENTO =
  'El paciente fue informado y autoriza que se registren fotografías clínicas de su rostro y se analice la evolución de su piel ' +
  'únicamente con fines de seguimiento médico. Puede retirar este consentimiento cuando quiera.';

function fechaValida(txt: string): string | null {
  if (!txt) return null;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(txt)) return 'Usá el formato AAAA-MM-DD, por ejemplo 1990-05-24.';
  const d = new Date(txt + 'T00:00:00');
  if (isNaN(d.getTime()) || d.toISOString().slice(0, 10) !== txt) return 'Esa fecha no existe.';
  if (d > new Date()) return 'La fecha de nacimiento no puede ser futura.';
  if (d.getFullYear() < new Date().getFullYear() - 120) return 'La fecha de nacimiento no es válida.';
  return null;
}

export default function PacientesScreen() {
  const [perfil, setPerfil] = useState<any>(null);
  const [susc, setSusc] = useState<any>(null);
  const [noLeidas, setNoLeidas] = useState(0);
  const [avisos, setAvisos] = useState<string[]>([]);

  const [q, setQ] = useState('');
  const [items, setItems] = useState<Paciente[]>([]);
  const [total, setTotal] = useState(0);
  const [pagina, setPagina] = useState(1);
  const [cargando, setCargando] = useState(false);
  const [errorLista, setErrorLista] = useState<string | null>(null);

  const [modo, setModo] = useState<'lista' | 'nuevo'>('lista');
  const [f, setF] = useState({ cedula: '', nombre: '', apellido: '', fecha_nacimiento: '', sexo: '', telefono: '', antecedentes_medicos: '', observaciones: '' });
  const [consiente, setConsiente] = useState(false);
  const [errores, setErrores] = useState<Record<string, string>>({});
  const [errorForm, setErrorForm] = useState<string | null>(null);
  const [guardando, setGuardando] = useState(false);

  const [bajaDe, setBajaDe] = useState<Paciente | null>(null);
  const [consentDe, setConsentDe] = useState<Paciente | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  const cargarLista = useCallback(async (p = 1, texto = q) => {
    setCargando(true);
    setErrorLista(null);
    const r = await api(`/pacientes?pagina=${p}&tamano=10${texto.trim() ? `&q=${encodeURIComponent(texto.trim())}` : ''}`);
    setCargando(false);
    if (!r.ok) return setErrorLista(mensaje(r));
    setItems((prev) => (p === 1 ? r.data.items : [...prev, ...r.data.items]));
    setTotal(r.data.total);
    setPagina(p);
  }, [q]);

  useFocusEffect(
    useCallback(() => {
      (async () => {
        const [pf, sc, nt] = await Promise.all([api('/perfil'), api('/suscripcion'), api('/notificaciones')]);
        if (pf.ok) {
          setPerfil(pf.data);
          vincularUsuarioPush(pf.data.id);
        }
        if (sc.ok) setSusc(sc.data);
        if (nt.ok) {
          setNoLeidas(nt.data.no_leidas);
          setAvisos(nt.data.items.filter((n: any) => !n.leida && (n.tipo === 'vencimiento' || n.tipo === 'vencida')).map((n: any) => n.mensaje).slice(0, 1));
        }
      })();
      cargarLista(1);
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [])
  );

  const abrirNuevo = () => {
    setF((x) => ({ ...x, cedula: /^\d+$/.test(q.trim()) ? q.trim() : x.cedula }));
    setErrores({}); setErrorForm(null); setConsiente(false); setModo('nuevo');
  };

  const validar = () => {
    const e: Record<string, string> = {};
    const ced = f.cedula.replace(/[.\s]/g, '');
    if (!/^\d{4,10}$/.test(ced)) e.cedula = 'La cédula debe tener solo números (entre 4 y 10 dígitos).';
    if (!f.nombre.trim()) e.nombre = 'El nombre es obligatorio.';
    if (!f.apellido.trim()) e.apellido = 'El apellido es obligatorio.';
    if (/[<>]/.test(f.nombre + f.apellido + f.antecedentes_medicos + f.observaciones)) e.nombre = 'No se pueden usar los caracteres < o >.';
    if (f.telefono && !/^\+?[0-9][0-9 \-]{5,18}$/.test(f.telefono.trim())) e.telefono = 'Usá solo números, espacios o guiones (ej.: 0981 123456).';
    const fe = fechaValida(f.fecha_nacimiento.trim());
    if (fe) e.fecha_nacimiento = fe;
    if (f.antecedentes_medicos.length > 2000 || f.observaciones.length > 2000) e.observaciones = 'El texto es demasiado largo (máximo 2000 caracteres).';
    return e;
  };

  const registrar = async () => {
    setErrorForm(null);
    const e = validar();
    setErrores(e);
    if (Object.keys(e).length) return setErrorForm('Revisá los campos marcados en rojo.');
    if (!consiente) return setErrorForm('Necesitás el consentimiento informado del paciente: leelo con él y marcá la casilla.');
    setGuardando(true);
    const r = await api('/pacientes', {
      method: 'POST',
      json: {
        cedula: f.cedula, nombre: f.nombre, apellido: f.apellido, fecha_nacimiento: f.fecha_nacimiento.trim() || null,
        sexo: f.sexo || null, telefono: f.telefono.trim() || null, antecedentes_medicos: f.antecedentes_medicos || null,
        observaciones: f.observaciones || null, consentimiento: { acepta: true },
      },
    });
    setGuardando(false);
    if (!r.ok) return setErrorForm(mensaje(r));
    setInfo('Paciente registrado correctamente.');
    setF({ cedula: '', nombre: '', apellido: '', fecha_nacimiento: '', sexo: '', telefono: '', antecedentes_medicos: '', observaciones: '' });
    setModo('lista');
    setQ(r.data.cedula);
    cargarLista(1, r.data.cedula);
  };

  const darDeBaja = async (motivo: string) => {
    const p = bajaDe!; setBajaDe(null);
    const r = await api(`/pacientes/${p.id}`, { method: 'DELETE', json: { motivo, confirmar: true } });
    setInfo(r.ok ? r.data.mensaje : null);
    if (!r.ok) setErrorLista(mensaje(r)); else cargarLista(1);
  };

  const darConsentimiento = async () => {
    const p = consentDe!; setConsentDe(null);
    const r = await api(`/pacientes/${p.id}/consentimiento`, { method: 'POST' });
    if (!r.ok) setErrorLista(mensaje(r)); else { setInfo('Consentimiento registrado.'); cargarLista(1); }
  };

  const set = (k: keyof typeof f) => (v: string) => setF((x) => ({ ...x, [k]: v }));
  const vencida = susc && !susc.funciones_avanzadas;

  return (
    <Pantalla>
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
        <View style={{ flex: 1 }}>
          <Text style={{ fontFamily: FUENTE.texto, fontSize: 14, color: COLOR.textoSuave }}>Hola,</Text>
          <Text style={{ fontFamily: FUENTE.titulo, fontSize: 26, color: COLOR.texto, letterSpacing: -0.3 }} numberOfLines={1}>{perfil?.nombre ?? ' '}</Text>
        </View>
        <BotonIcono icono="card-outline" etiqueta={noLeidas ? `Suscripción, ${noLeidas} avisos` : 'Suscripción'} marca={noLeidas > 0} onPress={() => router.push('/suscripcion')} />
        <BotonIcono icono="person-circle-outline" etiqueta="Mi cuenta" onPress={() => router.push('/cuenta')} />
        {perfil?.rol === 'admin' && <BotonIcono icono="settings-outline" etiqueta="Administración" onPress={() => router.push('/admin')} />}
        <BotonIcono icono="log-out-outline" etiqueta="Cerrar sesión" onPress={cerrarSesion} />
      </View>
      {susc?.dias_restantes != null && susc.estado !== 'vencida' && susc.plan.periodicidad !== 'gratuito' && (
        <Text style={{ color: COLOR.textoSuave, marginBottom: 4 }}>
          {susc.es_prueba ? 'Período de prueba' : `Plan ${susc.plan.nombre}`}: vence el {new Date(susc.fecha_vencimiento + 'Z').toLocaleDateString('es-PY')} ({susc.dias_restantes} días)
        </Text>
      )}
      {avisos.map((a) => <Aviso key={a} tipo="aviso" texto={a} />)}
      {vencida && <Aviso tipo="aviso" texto="Tu plan no incluye el procesamiento de imágenes. Podés seguir consultando a tus pacientes; para procesar fotos, renová o elegí un plan Premium." />}
      {info && <Aviso tipo="ok" texto={info} />}

      {modo === 'lista' ? (
        <>
          <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginTop: 4 }}>
            <Titulo>Pacientes</Titulo>
            <Boton texto="Nuevo" icono="person-add-outline" onPress={abrirNuevo} estilo={{ minHeight: 44, paddingVertical: 10, marginBottom: 8 }} />
          </View>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, backgroundColor: COLOR.tarjeta, borderRadius: 18, paddingLeft: 16, paddingRight: 6, marginBottom: 8 }}>
            <Ionicons name="search" size={20} color={COLOR.textoSuave} />
            <TextInput value={q} onChangeText={setQ} onSubmitEditing={() => cargarLista(1)} returnKeyType="search" maxLength={80}
              placeholder="Buscar por nombre, apellido o cédula" placeholderTextColor="#8A968F" accessibilityLabel="Buscar por cédula, nombre o apellido"
              style={{ flex: 1, paddingVertical: 15, fontSize: 15, fontFamily: FUENTE.texto, color: COLOR.texto }} />
            <Boton texto="Buscar" variante="texto" onPress={() => cargarLista(1)} cargando={cargando && pagina === 1} />
          </View>
          {errorLista && <Aviso tipo="error" texto={errorLista} />}
          {!cargando && !errorLista && items.length === 0 && (
            <Tarjeta><Text>No encontramos pacientes con esos datos. Podés registrarlo con «Paciente nuevo».</Text></Tarjeta>
          )}
          {items.map((p) => (
            <Tarjeta key={p.id} estilo={{ padding: 14 }}>
              <TouchableOpacity accessibilityRole="button" accessibilityLabel={`Ver historial de ${p.nombre} ${p.apellido}`}
                onPress={() => router.push({ pathname: '/historial', params: { pacienteId: String(p.id), nombre: p.nombre, apellido: p.apellido } })}
                style={{ flexDirection: 'row', alignItems: 'center', gap: 14 }}>
                <Iniciales nombre={p.nombre} apellido={p.apellido} />
                <View style={{ flex: 1, gap: 4, minWidth: 0 }}>
                  <Text style={{ fontSize: 16, fontFamily: FUENTE.textoFuerte, color: COLOR.texto }}>{p.nombre} {p.apellido}</Text>
                  <Text style={{ fontSize: 13, fontFamily: FUENTE.texto, color: COLOR.textoSuave }}>CI {p.cedula}{p.telefono ? ` · ${p.telefono}` : ''}</Text>
                  {p.tiene_consentimiento
                    ? <Pildora texto="Consentimiento vigente" icono="checkmark" />
                    : <Pildora texto="Sin consentimiento" icono="alert" fondo="#F8EBDD" color={COLOR.aviso} />}
                </View>
              </TouchableOpacity>
              <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 12 }}>
                {p.tiene_consentimiento ? (
                  <Boton texto="Nuevo seguimiento" icono="camera-outline" estilo={{ flexGrow: 1, minHeight: 46, paddingVertical: 10 }}
                    onPress={() => router.push({ pathname: '/procesamiento', params: { pacienteId: String(p.id), nombre: p.nombre, apellido: p.apellido } })} />
                ) : (
                  <Boton texto="Registrar consentimiento" icono="document-text-outline" estilo={{ flexGrow: 1, minHeight: 46, paddingVertical: 10 }} onPress={() => setConsentDe(p)} />
                )}
                <Boton texto="Historial" icono="time-outline" variante="secundario" estilo={{ flexGrow: 1, minHeight: 46, paddingVertical: 10 }}
                  onPress={() => router.push({ pathname: '/historial', params: { pacienteId: String(p.id), nombre: p.nombre, apellido: p.apellido } })} />
                <BotonIcono icono="trash-outline" etiqueta={`Dar de baja a ${p.nombre} ${p.apellido}`} onPress={() => setBajaDe(p)} />
              </View>
            </Tarjeta>
          ))}
          {cargando && pagina > 1 && <ActivityIndicator color={COLOR.primario} />}
          {items.length < total && (
            <Boton texto={`Cargar más (${items.length} de ${total})`} icono="chevron-down" variante="secundario" onPress={() => cargarLista(pagina + 1)} />
          )}
        </>
      ) : (
        <>
          <Titulo>Paciente nuevo</Titulo>
          {errorForm && <Aviso tipo="error" texto={errorForm} />}
          <Campo etiqueta="Cédula" value={f.cedula} onChangeText={set('cedula')} keyboardType="numeric" error={errores.cedula} maxLength={12} />
          <Campo etiqueta="Nombre" value={f.nombre} onChangeText={set('nombre')} error={errores.nombre} maxLength={80} />
          <Campo etiqueta="Apellido" value={f.apellido} onChangeText={set('apellido')} error={errores.apellido} maxLength={80} />
          <CampoFecha etiqueta="Fecha de nacimiento (opcional)" valor={f.fecha_nacimiento} onCambio={set('fecha_nacimiento')}
            error={errores.fecha_nacimiento} minimo={haceAniosTexto(120)} maximo={hoyTexto()} />
          <Text style={{ fontSize: 14, color: COLOR.textoSuave, marginBottom: 6 }}>Sexo (opcional)</Text>
          <View style={{ flexDirection: 'row', gap: 8, marginBottom: 12 }}>
            {[['F', 'Femenino'], ['M', 'Masculino'], ['O', 'Otro']].map(([v, t]) => (
              <TouchableOpacity key={v} onPress={() => set('sexo')(f.sexo === v ? '' : v)} accessibilityRole="button" accessibilityLabel={t}
                style={{ flex: 1, padding: 10, borderRadius: 8, borderWidth: 1, borderColor: COLOR.primario, alignItems: 'center', backgroundColor: f.sexo === v ? COLOR.primario : '#fff' }}>
                <Text style={{ color: f.sexo === v ? '#fff' : COLOR.primario }}>{t}</Text>
              </TouchableOpacity>
            ))}
          </View>
          <Campo etiqueta="Teléfono (opcional)" value={f.telefono} onChangeText={set('telefono')} keyboardType="phone-pad" error={errores.telefono} maxLength={20} />
          <Campo etiqueta="Antecedentes médicos (opcional)" value={f.antecedentes_medicos} onChangeText={set('antecedentes_medicos')} multiline maxLength={2000} />
          <Campo etiqueta="Observaciones (opcional)" value={f.observaciones} onChangeText={set('observaciones')} multiline maxLength={2000} error={errores.observaciones} />
          <Subtitulo>Consentimiento informado</Subtitulo>
          <Casilla marcada={consiente} onCambio={setConsiente}><Text>{TEXTO_CONSENTIMIENTO}</Text></Casilla>
          <Text style={{ color: COLOR.primario, textDecorationLine: 'underline', marginBottom: 12 }} onPress={() => router.push('/privacidad')}>Ver la Política de Privacidad</Text>
          <Boton texto="Registrar paciente" icono="save-outline" onPress={registrar} cargando={guardando} />
          <Boton texto="Cancelar" icono="close" variante="secundario" estilo={{ marginTop: 8 }} onPress={() => setModo('lista')} />
        </>
      )}

      <Confirmar visible={!!bajaDe} peligro pedirMotivo motivoObligatorio titulo="¿Dar de baja al paciente?"
        mensaje={`${bajaDe?.nombre ?? ''} ${bajaDe?.apellido ?? ''} dejará de aparecer en tus listas. Su historial se conserva y no se borra.`}
        textoConfirmar="Sí, dar de baja" onConfirmar={darDeBaja} onCancelar={() => setBajaDe(null)} />
      <Confirmar visible={!!consentDe} titulo="Registrar consentimiento" mensaje={TEXTO_CONSENTIMIENTO + ' ¿El paciente lo aceptó?'}
        textoConfirmar="Sí, lo aceptó" onConfirmar={darConsentimiento} onCancelar={() => setConsentDe(null)} />
    </Pantalla>
  );
}
