# Checklist de validación — tests de solicitudes de acceso alineados con la persistencia atómica (2026-10-30)

> Se sobrescribe en cada entrega; el historial queda en Git.

**Repositorio:** anclora-nexus
**Rama:** development
**Datos:** no se usaron ni modificaron datos de aplicación.

## 1. Qué cambia
- El commit `0dcba9f` (29 oct) pasó la decisión de solicitudes de acceso a funciones RPC atómicas (`nexus_review_access_request`, `nexus_log_access_request_audit_event`, `nexus_list_access_request_audit_events`) y actualizó solo parte de los tests; el CI del job "Backend pytest" quedó rojo (9 tests).
- Se actualizan los tests desfasados, sin tocar código de producto: `test_access_request_audit_service` (mock con `prepare_access_request_audit_event` y RPC), `test_access_request_decision_lifecycle` (mock de Identity), `test_access_request_sla` (lectura de auditoría por RPC con el `MockNeonClient` compartido) y los tres `approve_request` de `test_identity_provisioning` (cliente RPC y servicio de auditoría simulados).
- La cobertura de escenarios se mantiene (alertas a 24 h/72 h, deduplicación, email fallido, atención de provisioning, casos A/B y fail-closed de Identity).

## 2. Ya comprobado por el agente
| Comprobación | Resultado |
| --- | --- |
| Reproducidos los 9 fallos con Python 3.12 y las dependencias del CI | — |
| `pytest` completo del backend tras el arreglo | 979 PASS, 1 skipped |
| `git diff --check` | PASS |

## 3. NOT_RUN
Tests de frontend y `Validate Nexus`: ya estaban en verde y no se tocan.

## 4. Para Toni
Comprobar que el CI de `development` queda en verde. Bloqueante: no.
