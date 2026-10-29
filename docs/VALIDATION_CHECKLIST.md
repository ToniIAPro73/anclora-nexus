# Checklist de validación — intake QA y reenvío de invitaciones (2026-10-29)

**Repositorio:** anclora-nexus  
**Rama:** development  
**Validación de Toni en development:** confirmada en esta conversación.  
**Promoción:** autorizada por Toni mediante `PROMOTE=FULL`; pendiente del Preview revisado y su SHA exacto.

## Cambio

- Data Lab y otros productores de intake pueden enviar `company_name`; Nexus lo normaliza al campo canónico `company` de `access_requests` antes de persistir.
- GuestHub conserva su campo `company` actual y los valores explícitos de `company` tienen prioridad.
- Los reintentos de solicitudes aprobadas con invitación pendiente reutilizan el endpoint de Identity para reenviar el correo y rotar el token.
- Se registran eventos de auditoría de éxito o fallo.
- Nexus muestra “Reenviar invitación” cuando el aprovisionamiento ya está en estado `invite_ready`.
- Las respuestas de Identity se mantienen saneadas y no incluyen tokens.

## Comprobaciones de intake

| Comprobación | Resultado |
| --- | --- |
| Backend `test_syncxml_pilot_routes.py` | PASS; 27 pruebas |
| Mapeo `company_name` → `company` sin escribir en Production | PASS; cliente Neon simulado |
| `git diff --check` | PASS |

## GuestHub producción: error 500 posterior al insert

- Diagnóstico: `service_role` solo tiene `SELECT` e `INSERT` en `access_requests`; el handler intentaba actualizar la fila después de insertarla.
- Los intentos `419d8117-df36-471f-a65d-b3a75c1e5106` y `d7431a55-ea12-4e3d-a4cb-ee94b07ec0df` sí existen con estado `pending`; ninguno tiene tarea `syncxml_pilot_review` asociada.
- El rol de producción no tiene grants sobre `tasks`; la creación de tareas queda best-effort. Los registros de solicitud se guardan en `access_requests`, que es lo que consulta la bandeja de solicitudes.
- Corrección local: insertar el estado y metadatos ya calculados; los reintentos devuelven la fila existente sin duplicarla.
- Aprobación automática de GuestHub configurada explícitamente como `false` en Render Production.

| Comprobación | Resultado |
| --- | --- |
| `backend/tests/test_syncxml_pilot_tasks.py` | PASS; 17 pruebas |
| Persistencia sin UPDATE y reparación idempotente de tarea | PASS; pruebas con Neon simulado |
| `git diff --check` | PASS |

Toni validó esta corrección en development y autorizó commit y push.

## Comprobaciones de reenvío de invitaciones

| Comprobación | Resultado |
| --- | --- |
| Pruebas de reenvío de Identity y retry de Nexus | PASS; 2 pruebas |
| TypeScript del frontend | PASS |
| ESLint de los tres archivos frontend modificados | PASS |
| `git diff --check` | PASS |

No se modificó el esquema de Neon. El reenvío efectivo requiere publicar Nexus e Identity.

## Publicación

1. [x] Cambios validados en development por Toni.
2. [x] Commit y push a `origin/development` autorizados.
3. [ ] Preview revisado por Toni y SHA exacto confirmado.
4. [ ] Ejecutar una sola vez `promote.yml` con `target=full` y el SHA exacto revisado.
5. [ ] Verificar que el workflow termina y reintentar Data Lab/GuestHub en vivo.
