# Checklist de validación — rotación de firma Neon Data API (2026-10-29)

> Este fichero se sobrescribe en cada entrega. El historial queda en Git.

**Repositorio:** anclora-nexus
**Rama:** development
**Validación en development:** Toni validó el cambio.
**Datos/servicios:** no se generaron claves ni se modificó configuración de Render, Vercel o Neon.

## 1. Qué cambia

- El endpoint `/api/neon-jwks` mantiene la clave pública derivada del firmante actual y permite publicar claves públicas P-256 adicionales durante una rotación.
- La configuración adicional solo admite claves públicas con `kid` único; se rechazan campos privados y material/curvas no admitidos.
- `.env.example` documenta `NEON_JWT_ADDITIONAL_PUBLIC_KEYS` como configuración pública opcional.

## 2. Ya comprobado por el agente

| Comprobación | Comando o método | Resultado |
| --- | --- | --- |
| Pruebas focalizadas | `npm test -- tests/neon-jwks.test.ts tests/anclora-identity.test.ts` | PASS; 7 pruebas |
| Tipos del frontend | `npm run typecheck` | PASS |
| Integridad del diff | `git diff --check` | PASS |

## 3. Pruebas no ejecutadas (NOT_RUN)

| Prueba | Motivo concreto |
| --- | --- |
| Verificación del endpoint publicado y validación real de tokens firmados por Render | La nueva clave y la configuración de proveedores quedan para una fase posterior a esta revisión. |
| Prueba visual de interfaz | El cambio afecta al endpoint JWKS y no modifica interfaz. |

## 4. Checklist para validar en la aplicación

| # | Dónde | Pasos | Resultado esperado | Cuenta o configuración | Bloqueante |
| --- | --- | --- | --- | --- | --- |
| 1 | Desarrollo | Con clave adicional de prueba, consultar `/api/neon-jwks` y comprobar ambos `kid` y ausencia de campos privados | Devuelve las claves públicas configuradas; la clave actual sigue publicada | Claves de prueba no productivas | Sí, antes de configurar la rotación |
| 2 | Configuración de plataforma | Tras aprobar la publicación, configurar el firmante separado de Render y comprobar el flujo de autorización | Neon acepta tokens válidos de ambos firmantes durante la transición | Clave privada solo en Render; JWK público en Nexus | Sí, antes de depender del firmante de Render |

## 5. Riesgos y limitaciones

- La publicación de claves adicionales depende de la configuración `NEON_JWT_ADDITIONAL_PUBLIC_KEYS` en el entorno que sirve `/api/neon-jwks`.
- Este cambio no genera ni distribuye claves privadas, no modifica la clave de Vercel y no cambia Neon/Render/Vercel.
- El JWKS conserva la política actual de caché de cinco minutos; los consumidores pueden retener claves durante la transición.

## 6. Decisión de Toni

- [x] Cambios revisados y validados en development.
- [ ] Validación de la rotación real con ambos firmantes completada.
- [ ] Se promociona: escribir `PROMOTE=FULL`.
