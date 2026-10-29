# Checklist de validación — diagnóstico de errores de Identity (2026-10-29)

**Repositorio:** anclora-nexus  
**Rama:** development  
**SHA:** se registra en el commit actualizado.  
**Validación de Toni en development:** confirmada en esta conversación.  
**Promoción:** autorizada por Toni mediante `PROMOTE=FULL`.

## Cambio

- IdentityProvisioningError conserva operación, código HTTP y cuerpo de respuesta saneado.
- El error detallado queda en `provisioning_error`; el evento de auditoría firmado conserva campos estructurados `http_status` y `response`.
- El log del backend incluye código HTTP y respuesta saneada, sin email del solicitante.
- Se limitan los cuerpos a 2.048 caracteres y se redactan credenciales, tokens, cookies, sesiones y direcciones de email.
- No cambia el esquema de Neon ni el flujo de aprobación o asignación de acceso.

## Comprobaciones

| Comprobación | Resultado |
| --- | --- |
| `python3 -m py_compile` en los dos servicios modificados | PASS |
| `git diff --check` | PASS |
| Pruebas automatizadas | No ejecutadas en esta tarea |
| Validación de Toni en el entorno `development` | Confirmada |

## Publicación

1. Commit y push a `origin/development` autorizados por Toni.
2. Ejecutar una sola vez el workflow `promote.yml` con `target=full` y el SHA exacto de `development`.
3. El workflow conserva sus comprobaciones de estado y divergencia; no realizar despliegues directos.
