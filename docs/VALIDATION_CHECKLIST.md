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
