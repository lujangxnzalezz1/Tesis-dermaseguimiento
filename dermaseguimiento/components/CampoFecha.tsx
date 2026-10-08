import DateTimePicker, { DateTimePickerEvent } from '@react-native-community/datetimepicker';
import { Ionicons } from '@expo/vector-icons';
import React, { useState } from 'react';
import { Platform, Text, TouchableOpacity, View } from 'react-native';
import { COLOR, FUENTE } from './ui';

/** Fecha en formato AAAA-MM-DD sin corrimientos por zona horaria. */
function aTexto(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function aFecha(t: string): Date | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(t)) return null;
  const [a, m, d] = t.split('-').map(Number);
  return new Date(a, m - 1, d);
}

function legible(t: string): string {
  const d = aFecha(t);
  return d ? d.toLocaleDateString('es-PY', { day: '2-digit', month: '2-digit', year: 'numeric' }) : '';
}

/** Campo de fecha con calendario: en web usa el selector del navegador (calendario en la Mac, rueda en
 *  el iPhone); en la app nativa, el selector del sistema. El valor siempre es AAAA-MM-DD (lo que espera la API). */
export function CampoFecha({
  etiqueta, valor, onCambio, error, minimo, maximo,
}: {
  etiqueta: string; valor: string; onCambio: (v: string) => void; error?: string | null; minimo?: string; maximo?: string;
}) {
  const [abierto, setAbierto] = useState(false);
  const borde = { borderWidth: 1, borderColor: error ? COLOR.error : '#ccc', borderRadius: 8 };

  return (
    <View style={{ marginBottom: 12 }}>
      <Text style={{ fontSize: 14, color: COLOR.textoSuave, marginBottom: 6 }}>{etiqueta}</Text>
      {Platform.OS === 'web' ? (
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
          {React.createElement('input', {
            type: 'date',
            value: valor,
            min: minimo,
            max: maximo,
            'aria-label': etiqueta,
            onChange: (e: any) => onCambio(e.target.value),
            style: {
              flex: 1, fontSize: 16, padding: '11px 14px', borderRadius: 8, fontFamily: 'inherit',
              border: `1px solid ${error ? COLOR.error : '#ccc'}`, color: COLOR.texto, backgroundColor: '#fff', minHeight: 46,
            },
          } as any)}
          {valor ? (
            <TouchableOpacity accessibilityRole="button" accessibilityLabel={`Borrar ${etiqueta}`} onPress={() => onCambio('')}>
              <Ionicons name="close-circle" size={24} color="#999" />
            </TouchableOpacity>
          ) : null}
        </View>
      ) : (
        <>
          <TouchableOpacity accessibilityRole="button" accessibilityLabel={etiqueta} onPress={() => setAbierto(true)}
            style={[borde, { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 14, paddingVertical: 12 }]}>
            <Text style={{ fontSize: 16, color: valor ? '#222' : '#999' }}>{valor ? legible(valor) : 'Elegir fecha'}</Text>
            <View style={{ flexDirection: 'row', gap: 10 }}>
              {valor ? <Ionicons name="close-circle" size={22} color="#999" onPress={() => onCambio('')} /> : null}
              <Ionicons name="calendar-outline" size={22} color={COLOR.primario} />
            </View>
          </TouchableOpacity>
          {abierto && (
            <DateTimePicker
              value={aFecha(valor) ?? aFecha(maximo ?? '') ?? new Date()}
              mode="date"
              display={Platform.OS === 'ios' ? 'inline' : 'default'}
              minimumDate={minimo ? aFecha(minimo) ?? undefined : undefined}
              maximumDate={maximo ? aFecha(maximo) ?? undefined : undefined}
              locale="es-PY"
              onChange={(e: DateTimePickerEvent, d?: Date) => {
                if (Platform.OS !== 'ios' || e.type !== 'set') setAbierto(false);
                if (e.type === 'set' && d) onCambio(aTexto(d));
              }}
            />
          )}
          {abierto && Platform.OS === 'ios' && (
            <TouchableOpacity onPress={() => setAbierto(false)} style={{ alignSelf: 'flex-end', padding: 8 }}>
              <Text style={{ color: COLOR.primario, fontFamily: FUENTE.textoFuerte }}>Listo</Text>
            </TouchableOpacity>
          )}
        </>
      )}
      {error ? <Text style={{ fontSize: 13, color: COLOR.error, marginTop: 4 }}>{error}</Text> : null}
    </View>
  );
}

export function hoyTexto(): string {
  return aTexto(new Date());
}

export function haceAniosTexto(anios: number): string {
  const d = new Date();
  d.setFullYear(d.getFullYear() - anios);
  return aTexto(d);
}
