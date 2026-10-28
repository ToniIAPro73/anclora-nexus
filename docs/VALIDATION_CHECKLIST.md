# Checklist de validación — recepción y revisión QA GuestHub/Data Lab (2026-10-28)

> Este fichero se sobrescribe en cada entrega. El historial queda en Git.

**Repositorio:** anclora-nexus
**Rama:** development
**Validación en development:** Toni validó este cambio.
**Datos:** no se enviaron solicitudes ni se modificaron solicitudes/membresías de usuarios.

## 1. Qué cambia

- Añade endpoints de ingreso QA independientes para GuestHub y Data Lab, con credenciales y marcadores de producto separados.
- Las solicitudes quedan limitadas por la organización Nexus QA; el aprovisionamiento solo pide rol `qa` para solicitudes marcadas por el servidor.
- No se registran secretos ni detalles de excepciones en respuestas o logs.

## 2. Ya comprobado por el agente

| Comprobación | Comando o método | Resultado |
| --- | --- | --- |
| Pruebas focalizadas | `.venv/bin/pytest -q backend/tests/test_syncxml_pilot_routes.py backend/tests/test_identity_provisioning.py` | PASS; 36 pruebas |
| Integridad | `git diff --check` | PASS |
| Organización y revisora QA | Neon solo lectura: `Nexus Production QA`, scope `isolated-auth-qa`, una membresía activa y cero solicitudes | PASS |
| Fallos Render | Eventos/logs solo lectura para ambos intentos recientes | Diagnóstico: falta `NEON_DATA_API_URL` |

## 3. Pruebas no ejecutadas (NOT_RUN)

| Prueba | Motivo concreto |
| --- | --- |
| Ingreso y aprobación real en Nexus | Endpoint QA no está desplegado ni dispone de secretos QA configurados. |
| Revisión visual de Nexus con solicitud QA | No se creó solicitud; se requiere deployment con este cambio. |

## 4. Checklist para validar en la aplicación

| # | Dónde | Pasos | Resultado esperado | Cuenta o configuración | Bloqueante |
| --- | --- | --- | --- | --- | --- |
| 1 | Nexus Preview | Filtrar por producto y scope QA; revisar una solicitud enviada desde cada app | Solo la revisora QA puede aprobar y el evento queda auditado | `qa.nexus@anclora.local` | Sí |

### Casos negativos y de borde

- Credencial QA ausente o inválida: no se persiste ninguna solicitud.
- Una solicitud de un org distinto no se puede consultar ni aprobar.
- Los endpoints ordinarios no aceptan que el cliente marque el scope QA.

## 5. Riesgos y limitaciones

- Los dos últimos deployments de Render fallaron en arranque por `NEON_DATA_API_URL` ausente; el servicio live sigue en una revisión anterior.
- El servicio Render disponible está ligado a `production`; no se cambió configuración ni se redeplegó.
- No se hicieron solicitudes ni aprobaciones reales.

## 6. Decisión de Toni

- [x] Cambios revisados y validados en development.
- [ ] Todos los puntos bloqueantes del flujo desplegado pasan.
- [ ] Se promociona: escribir `PROMOTE=FULL`.
