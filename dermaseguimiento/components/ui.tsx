import { Ionicons } from '@expo/vector-icons';
import { ComponentProps, ReactNode, useState } from 'react';
import {
  ActivityIndicator,
  Image,
  Modal,
  ScrollView,
  StyleProp,
  StyleSheet,
  Text,
  TextInput,
  TextInputProps,
  TouchableOpacity,
  View,
  ViewStyle,
} from 'react-native';
import { API_URL, obtenerToken } from '../lib/auth';

export const COLOR = { primario: '#1D3D47', fondo: '#fff', suave: '#E6F4FE', error: '#B3261E', ok: '#2E7D32', aviso: '#B26A00' };

type IconName = ComponentProps<typeof Ionicons>['name'];

/** Contenedor con desplazamiento y ancho máximo: se ve bien en celular, tableta y web (diseño adaptable). */
export function Pantalla({ children }: { children: ReactNode }) {
  return (
    <ScrollView contentContainerStyle={estilos.scroll} keyboardShouldPersistTaps="handled">
      <View style={estilos.columna}>{children}</View>
    </ScrollView>
  );
}

/** Botón SIEMPRE con texto; el ícono es un apoyo visual (nunca reemplaza la descripción). */
export function Boton({
  texto, onPress, icono, variante = 'primario', cargando, deshabilitado, estilo,
}: {
  texto: string; onPress: () => void; icono?: IconName; variante?: 'primario' | 'secundario' | 'peligro' | 'texto';
  cargando?: boolean; deshabilitado?: boolean; estilo?: StyleProp<ViewStyle>;
}) {
  const sec = variante === 'secundario';
  const txt = variante === 'texto';
  const fondo = variante === 'peligro' ? COLOR.error : sec || txt ? 'transparent' : COLOR.primario;
  const color = sec || txt ? (variante === 'texto' ? COLOR.primario : COLOR.primario) : '#fff';
  return (
    <TouchableOpacity
      accessibilityRole="button"
      accessibilityLabel={texto}
      onPress={onPress}
      disabled={cargando || deshabilitado}
      style={[estilos.boton, { backgroundColor: fondo, borderWidth: sec ? 1 : 0, borderColor: COLOR.primario, opacity: cargando || deshabilitado ? 0.6 : 1 }, txt && { paddingVertical: 8 }, estilo]}
    >
      {cargando ? (
        <ActivityIndicator color={color} />
      ) : (
        <View style={estilos.filaBoton}>
          {icono && <Ionicons name={icono} size={18} color={color} />}
          <Text style={[estilos.textoBoton, { color }]}>{texto}</Text>
        </View>
      )}
    </TouchableOpacity>
  );
}

export function Campo({ etiqueta, error, ayuda, ...props }: TextInputProps & { etiqueta: string; error?: string | null; ayuda?: string }) {
  return (
    <View style={{ marginBottom: 12 }}>
      <Text style={estilos.etiqueta}>{etiqueta}</Text>
      <TextInput
        placeholderTextColor="#999"
        accessibilityLabel={etiqueta}
        {...props}
        style={[estilos.input, error ? { borderColor: COLOR.error } : null, props.multiline ? { minHeight: 80, textAlignVertical: 'top' } : null]}
      />
      {ayuda && !error ? <Text style={estilos.ayuda}>{ayuda}</Text> : null}
      {error ? <Text style={estilos.error}>{error}</Text> : null}
    </View>
  );
}

export function Casilla({ marcada, onCambio, children }: { marcada: boolean; onCambio: (v: boolean) => void; children: ReactNode }) {
  return (
    <TouchableOpacity
      accessibilityRole="checkbox"
      accessibilityState={{ checked: marcada }}
      onPress={() => onCambio(!marcada)}
      style={{ flexDirection: 'row', gap: 10, alignItems: 'flex-start', marginVertical: 8 }}
    >
      <Ionicons name={marcada ? 'checkbox' : 'square-outline'} size={26} color={COLOR.primario} />
      <View style={{ flex: 1 }}>{children}</View>
    </TouchableOpacity>
  );
}

export function Tarjeta({ children, color = COLOR.suave }: { children: ReactNode; color?: string }) {
  return <View style={[estilos.tarjeta, { backgroundColor: color }]}>{children}</View>;
}

export function Aviso({ tipo, texto }: { tipo: 'error' | 'ok' | 'aviso' | 'info'; texto: string }) {
  const c = { error: '#FDECEA', ok: '#E8F5E9', aviso: '#FFF4E0', info: COLOR.suave }[tipo];
  const i: IconName = { error: 'alert-circle', ok: 'checkmark-circle', aviso: 'warning', info: 'information-circle' }[tipo] as IconName;
  const col = { error: COLOR.error, ok: COLOR.ok, aviso: COLOR.aviso, info: COLOR.primario }[tipo];
  return (
    <View style={[estilos.aviso, { backgroundColor: c }]}>
      <Ionicons name={i} size={20} color={col} />
      <Text style={{ flex: 1, color: '#222' }}>{texto}</Text>
    </View>
  );
}

export const Titulo = ({ children }: { children: ReactNode }) => <Text style={estilos.titulo}>{children}</Text>;
export const Subtitulo = ({ children }: { children: ReactNode }) => <Text style={estilos.subtitulo}>{children}</Text>;

/** Confirmación para acciones críticas, con motivo opcional u obligatorio (punto 29). */
export function Confirmar({
  visible, titulo, mensaje, pedirMotivo, motivoObligatorio, textoConfirmar = 'Confirmar', peligro, onConfirmar, onCancelar,
}: {
  visible: boolean; titulo: string; mensaje: string; pedirMotivo?: boolean; motivoObligatorio?: boolean; textoConfirmar?: string;
  peligro?: boolean; onConfirmar: (motivo: string) => void; onCancelar: () => void;
}) {
  const [motivo, setMotivo] = useState('');
  const invalido = !!motivoObligatorio && motivo.trim().length < 5;
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onCancelar}>
      <View style={estilos.fondoModal}>
        <View style={estilos.modal}>
          <Text style={estilos.subtitulo}>{titulo}</Text>
          <Text style={{ marginBottom: 12, color: '#333' }}>{mensaje}</Text>
          {pedirMotivo && (
            <Campo etiqueta={motivoObligatorio ? 'Motivo (obligatorio, mínimo 5 letras)' : 'Motivo (opcional)'} value={motivo} onChangeText={setMotivo} maxLength={300} />
          )}
          <Boton texto={textoConfirmar} variante={peligro ? 'peligro' : 'primario'} icono="checkmark" deshabilitado={invalido} onPress={() => { const m = motivo; setMotivo(''); onConfirmar(m.trim()); }} />
          <Boton texto="Cancelar" variante="secundario" icono="close" estilo={{ marginTop: 8 }} onPress={() => { setMotivo(''); onCancelar(); }} />
        </View>
      </View>
    </Modal>
  );
}

/** Imagen clínica: el servidor la entrega solo con el token de sesión (no son públicas). */
export function ImagenProtegida({ url, estilo }: { url: string; estilo?: StyleProp<any> }) {
  const token = obtenerToken();
  return <Image source={{ uri: `${API_URL}${url}`, headers: token ? { Authorization: `Bearer ${token}` } : undefined }} style={[estilos.imagen, estilo]} resizeMode="cover" />;
}

const estilos = StyleSheet.create({
  scroll: { flexGrow: 1, backgroundColor: COLOR.fondo, alignItems: 'center' },
  columna: { width: '100%', maxWidth: 640, padding: 20 },
  boton: { borderRadius: 8, paddingVertical: 14, paddingHorizontal: 16, alignItems: 'center', justifyContent: 'center', minHeight: 48 },
  filaBoton: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  textoBoton: { fontSize: 16, fontWeight: '600' },
  etiqueta: { fontSize: 14, color: '#444', marginBottom: 6 },
  input: { borderWidth: 1, borderColor: '#ccc', borderRadius: 8, paddingHorizontal: 14, paddingVertical: 12, fontSize: 16, backgroundColor: '#fff' },
  ayuda: { fontSize: 12, color: '#666', marginTop: 4 },
  error: { fontSize: 13, color: COLOR.error, marginTop: 4 },
  tarjeta: { padding: 16, borderRadius: 8, marginVertical: 8 },
  aviso: { flexDirection: 'row', gap: 10, padding: 12, borderRadius: 8, marginVertical: 6, alignItems: 'center' },
  titulo: { fontSize: 24, fontWeight: 'bold', color: COLOR.primario, marginBottom: 8 },
  subtitulo: { fontSize: 17, fontWeight: '600', color: COLOR.primario, marginBottom: 8, marginTop: 8 },
  fondoModal: { flex: 1, backgroundColor: '#0008', justifyContent: 'center', padding: 20 },
  modal: { backgroundColor: '#fff', borderRadius: 12, padding: 20, width: '100%', maxWidth: 480, alignSelf: 'center' },
  imagen: { width: '100%', height: 220, borderRadius: 8, backgroundColor: '#eee', marginTop: 10 },
});

export function ReglasPassword({ reglas }: { reglas: { texto: string; cumple: boolean }[] }) {
  return (
    <View style={{ marginBottom: 12 }}>
      {reglas.map((r) => (
        <View key={r.texto} style={{ flexDirection: 'row', gap: 6, alignItems: 'center' }}>
          <Ionicons name={r.cumple ? 'checkmark-circle' : 'ellipse-outline'} size={16} color={r.cumple ? COLOR.ok : '#888'} />
          <Text style={{ fontSize: 13, color: r.cumple ? COLOR.ok : '#666' }}>{r.texto}</Text>
        </View>
      ))}
    </View>
  );
}
