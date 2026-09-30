# Guía para probar los cambios

Rama: `mejoras-tutora` (nada está commiteado todavía; revisá con `git status` / `git diff`).
Respaldo de tu base anterior: `~/Desktop/Tesis_respaldos/dermaseguimiento_antes_de_migrar.sql`

## 0. Levantar todo

```bash
cd backend && source venv/bin/activate
pytest                      # 133 pruebas automáticas, todas deben pasar
uvicorn main:app --reload   # API en http://localhost:8000  (docs en /docs)
```

En otra terminal:

```bash
cd dermaseguimiento
cp .env.example .env        # solo la primera vez
npx expo start              # tecla "i" = simulador iOS
```

Usuario administrador: el que está en `backend/.env` (`ADMIN_EMAIL` / `ADMIN_PASSWORD`).
Tus dos usuarios de antes siguen funcionando con sus contraseñas actuales (la política nueva solo aplica a contraseñas nuevas).

## 1. Recorrido manual sugerido (app)

| # | Qué probar | Resultado esperado |
|---|---|---|
| 1 | Crear cuenta con contraseña débil (`abc`) | La lista de requisitos marca lo que falta y no deja enviar |
| 2 | Crear cuenta sin marcar la política | Error claro; la casilla viene desmarcada |
| 3 | Login con contraseña incorrecta 5 veces | Mensaje genérico y luego bloqueo temporal de 15 min |
| 4 | Cerrar la app y volver a abrirla | Sigue logueada (token en SecureStore) |
| 5 | «Cerrar sesión» y usar el botón atrás | Vuelve al login; el token viejo ya no sirve (se invalida en el servidor) |
| 6 | Dejar la sesión 30 min sin usar | La primera acción muestra «sesión cerrada por inactividad» |
| 7 | «Olvidé mi contraseña» | Sin SMTP el enlace aparece **en la consola del servidor** (log `correo`); pegá el código en «Ya tengo el código» |
| 8 | Usar el mismo enlace dos veces | La segunda vez dice que venció/ya se usó |
| 9 | Registrar paciente sin marcar consentimiento | No deja registrar |
| 10 | Tus pacientes viejos | Aparecen con «Sin consentimiento»: usá «Registrar consentimiento» antes de procesar |
| 11 | Búsqueda + «Cargar más» | Filtra por cédula/nombre y pagina de a 10 |
| 12 | «Dar de baja» | Pide motivo (obligatorio); el paciente desaparece de la lista pero sigue en la base |
| 13 | Procesar seguimiento con dos fotos reales de un rostro | Funciona durante el período de prueba; muestra el tiempo de procesamiento |
| 14 | Procesar con un PDF/archivo renombrado a .jpg, o una foto >10 MB | Mensaje claro, no se guarda nada |
| 15 | Suscripción → «Elegir Premium mensual» | Abre la página de la pasarela de pruebas; «Pagar» aprueba, «Simular tarjeta rechazada» rechaza |
| 16 | Tras aprobar | Estado «Activa», aparece el pago y su comprobante `REC-000001` |
| 17 | Mejorar de mensual a anual | El importe descuenta el tiempo no usado (crédito proporcional) |
| 18 | Cancelar suscripción | Pide motivo y confirmación; conserva el acceso hasta el vencimiento |
| 19 | Entrar con el administrador → Administración | Usuarios (inactivar/reactivar), Suscripciones, Auditoría, Correo |
| 20 | Inactivar a un usuario con sesión abierta | Su próxima acción lo devuelve al login; ya no puede ingresar |

## 2. Cosas que puedo probar por vos con curl / SQL

- Vencer una suscripción a mano: `UPDATE suscripciones SET fecha_vencimiento = now() - interval '1 day' WHERE usuario_id = X;`
  → se bloquea el procesamiento (402) pero se puede seguir consultando pacientes.
- Avisos: `UPDATE suscripciones SET fecha_vencimiento = now() + interval '2 days' WHERE usuario_id = X;` y abrir la pantalla Suscripción.
- Auditoría inmutable: `UPDATE auditoria SET detalle='x';` → PostgreSQL responde con error (disparador).

## 3. Limitaciones conocidas / pendientes

Ver el resumen al final de la conversación. Lo principal: la pasarela real (Pagopar/Bancard) requiere credenciales sandbox;
no se descarga el PDF del comprobante desde la app (sí desde la API: `GET /comprobantes/{id}/pdf`);
los pacientes no tienen acceso de solo lectura (RF-06); faltan SSIM, YOLOv8 y análisis periorbital (RF-13 a 16).
