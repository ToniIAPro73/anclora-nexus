# Checklist de validación — persistencia de revisión de solicitudes de acceso (2026-10-29)

> Este fichero se sobrescribe en cada entrega. El historial queda en Git.

**Repositorio:** anclora-nexus  
**Rama:** development  
**SHA local:** a071e64 (pendiente de publicación)  
**Validación de Toni en development:** pendiente; Toni indicó que no puede acceder a la URL localhost.  
**Autorización de promoción:** Toni escribió `PROMOTE=FULL`; la promoción requiere el SHA exacto revisado en Preview.  
**Servicios:** migración 004 aplicada y verificada en Neon Production; no se ha desplegado el código de aplicación.

## 1. Qué cambia

- Las decisiones de aprobación/rechazo y su auditoría se persisten atómicamente en Neon mediante RPC acotadas.
- El backend usa las RPC para leer auditoría, revisar solicitudes, iniciar reintentos y finalizar la provisión de Anclora Identity.
- El permiso directo de `service_role` para actualizar/borrar `access_requests` y leer/escribir `audit_log` sigue denegado.
- El estado transitorio aceptado por el contrato de base de datos es `pending`.

## 2. Ya comprobado por el agente

| Comprobación | Comando o método | Resultado |
| --- | --- | --- |
| Pruebas enfocadas del servicio de revisión | `/tmp/anclora-nexus-review-qa312/bin/python -m pytest backend/tests/test_access_request_review_service.py -q` | PASS; 23 pruebas |
| Tipos del frontend | `npm run typecheck` en `frontend/` | PASS |
| Integridad del diff | `git diff --check` | PASS |
| SQL de migración | Rama Neon temporal y pruebas de RPC | PASS; funciones, auditoría y permisos verificados |
| Migración en Neon Production | Neon MCP; proyecto `misty-truth-72362527`, rama `br-noisy-grass-bao7yidm` | PASS; RPC disponibles, ACL directas siguen denegadas |
| Identidad activa en Nexus Production | Menú de sesión de Nexus | `qa.nexus@anclora.local` |
| Solicitudes QA | Neon Production y Nexus Production | Data Lab y GuestHub siguen `pending`; no se han aprobado |

## 3. Validación pendiente

| Prueba | Motivo concreto |
| --- | --- |
| Flujo completo en Preview con la base Production y la identidad QA | Requiere publicar `development` para generar la Preview; todavía no existe un SHA de Preview revisable. |
| Aprobar ambas solicitudes QA y comprobar provisión en Identity | El código actualizado aún no está desplegado; el Nexus Production actual sigue mostrando errores de acceso a `audit_log`. No se deben aprobar con el backend antiguo. |
| Login en Data Lab y GuestHub con la identidad provisionada | Depende de completar el flujo anterior. |

## 4. Checklist de release

| # | Dónde | Pasos | Resultado esperado | Estado |
| --- | --- | --- | --- | --- |
| 1 | Preview de Nexus | Revisar el SHA exacto en Preview con `qa.nexus@anclora.local` y la organización aislada | Auditoría visible; decisiones idempotentes y persistidas; acceso QA limitado a los productos solicitados | Pendiente |
| 2 | Promote workflow | Despachar una vez con `target=full` y el SHA exacto que Toni haya revisado en Preview | Flujo ordenado `development -> staging -> production -> main`; sin divergencias ni force-push | Pendiente |
| 3 | Nexus Production | Reabrir las solicitudes QA usando el reviewer dedicado | Sin errores de permisos; provisionado y auditable | Pendiente |
| 4 | Data Lab y GuestHub Production | Completar login Identity con la identidad QA autorizada | Login de ambos productos confirmado | Pendiente |

## 5. Decisión de Toni

- [ ] Toni validó el flujo en development/Preview.
- [x] Toni autorizó la promoción con `PROMOTE=FULL`.
- [ ] Toni revisó y confirmó el SHA exacto de Preview.
- [ ] Promote full-chain despachado.
- [ ] Login QA verificado en Data Lab y GuestHub.
