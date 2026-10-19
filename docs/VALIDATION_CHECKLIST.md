# Checklist de validación — Backend pytest en verde (2026-10-19)

> Este fichero se sobrescribe en cada entrega. El historial queda en Git.

**Repositorio:** `anclora-nexus`
**Rama y commit:** development (commit del fix de tests)
**Entorno de validación:** GitHub Actions (`Backend pytest`) · runtime local Python 3.12
**Datos:** ninguno; tests con mocks.

## 1. Qué cambia
- `backend/config.py`: se declara `NEXUS_INTERNAL_API_KEY` en `Settings`. El webhook `/api/internal/webhooks/*` lo leía (`internal_webhooks.py:23`) sin que existiera, y lanzaba `AttributeError` cuando `GUESTHUB_WEBHOOK_SECRET` no estaba definido (bug real, no solo de test).
- Tests alineados con el comportamiento ya vigente (commits `19f7e27`, `18ab8fa`): alias `syncxml` normalizado a `guesthub`, landings de Private Estates pueden crear access requests, wrappers legacy usan fuentes `data_lab_app` y `synergi_app`, analítica incluye `guesthub` y `syncxml`.

## 2. Ya comprobado por el agente
| Comprobación | Comando o método | Resultado | SHA |
| --- | --- | --- | --- |
| Reproducción de los 7 fallos del run 39299094006 | `pytest` en `backend/` (Python 3.12, mismas dependencias que CI) | 7 failed antes del cambio | árbol de trabajo |
| Suite backend completa | `python -m pytest` en `backend/` | 960 passed, 1 skipped | árbol de trabajo |

## 3. Pruebas no ejecutadas (NOT_RUN)
| Prueba | Motivo concreto |
| --- | --- |
| Frontend quality gate | No tocado; el job `Validate Nexus` ya estaba en verde |

## 4. Checklist para validar en la aplicación
| # | Dónde | Pasos | Resultado esperado | Cuenta o configuración | Bloqueante |
| --- | --- | --- | --- | --- | --- |
| 1 | GitHub → Actions → CI del commit | Abrir el run | `Backend pytest` en verde | — | Sí |
| 2 | `POST /api/internal/webhooks/dms-retention-sweep` | Llamar con `Authorization: Bearer <NEXUS_INTERNAL_API_KEY>` con `GUESTHUB_WEBHOOK_SECRET` sin definir | 200, no 500 | Variable de entorno del backend | No |

## 5. Riesgos y limitaciones
- Las tres expectativas de tests se cambian a mano según el código vigente; si el comportamiento antiguo (landings bloqueadas) era el deseado, habría que revertir el código, no los tests.

## 6. Decisión de Toni
- [ ] Todos los puntos bloqueantes pasan
- [ ] Se promociona con `PROMOTE=FULL`
- [ ] No se promociona. Motivo: ______________________
