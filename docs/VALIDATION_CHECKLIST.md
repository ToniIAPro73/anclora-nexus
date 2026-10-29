# Checklist de validación — reintento de aprovisionamiento de acceso (2026-10-29)

**Repositorio:** anclora-nexus
**Rama:** development
**SHA local:** se registra al confirmar el commit actualizado.
**Validación de Toni en development:** confirmada en esta conversación.
**Autorización de promoción:** Toni autorizó `PROMOTE=FULL` para este cambio.
**Ámbito QA:** solicitudes de Data Lab y GuestHub de `tonipmi.test@gmail.com`, organización QA aislada.

## 1. Cambio

- Separa la disponibilidad del reintento del correo de la disponibilidad del reintento de aprovisionamiento de Identity.
- Expone desde Nexus el reintento de aprovisionamiento para solicitudes aprobadas que fallaron y no tienen identidad, invitación ni membresía asociada.
- Usa el endpoint autenticado existente `POST /api/access-requests/{id}/provision/retry`; no concede acceso por SQL ni omite la revisión de Nexus.
- Añade textos de estado y acción para español, inglés, alemán y catalán.

## 2. Validación ejecutada

| Comprobación | Resultado |
| --- | --- |
| `git diff --check` | PASS |
| `npm run typecheck` (frontend) | PASS |
| ESLint en los archivos modificados del frontend | PASS |
| `npm run build` (frontend) | PASS |
| Prueba de reintento con provisión fallida y correo enviado | PASS |
| Prueba de solicitud pendiente no reintentable | PASS |
| Suite `test_access_request_decision_lifecycle.py` completa | 1 fallo ambiental preexistente: requiere `IDENTITY_SERVICE_TOKEN`, ausente en el entorno; los otros 4 casos pasaron |
| Visual QA local de la pantalla autenticada | No completada: la configuración local carece de `issuerUrl`, `clientId`, `clientSecret`, `redirectUri` y `sessionSecret` de Identity |

## 3. Estado operativo conocido antes de publicar

- Data Lab y GuestHub siguen sin membresía Identity; los emails recibidos confirman la decisión de Nexus, no el acceso efectivo.
- Los logs de Nexus Production registran fallos genéricos de aprovisionamiento y no exponen el código remoto.
- El intento de diagnóstico SSH a Render fue rechazado por clave pública; la API de Vercel denegó la lectura de configuración del proyecto.
- Este commit no cambia bases de datos ni variables secretas de producción.

## 4. Release

1. Toni validó el cambio en `development`.
2. Commit y push de `development`: autorizados por Toni.
3. Promoción full-chain `development -> staging -> production -> main`: autorizada por Toni mediante `PROMOTE=FULL`; despachar una vez con el SHA exacto de `development` y respetar los gates del workflow.
4. Tras el despliegue, reintentar desde Nexus las solicitudes QA aprobadas y verificar una membresía para cada producto.
5. Iniciar sesión en Data Lab y GuestHub con la identidad QA autorizada; marcar resuelto sólo cuando ambas aplicaciones confirmen acceso.
