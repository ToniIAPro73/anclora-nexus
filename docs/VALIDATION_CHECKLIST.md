# Checklist de validación — separación de claves Nexus/Neon (2026-10-29)

> Este fichero se sobrescribe en cada entrega. El historial queda en Git.

**Repositorio:** anclora-nexus
**Rama:** development
**Validación en development:** Toni validó el cambio.
**Servicios:** no se modificó configuración de Render, Vercel o Neon.

## 1. Qué cambia

- Render puede firmar JWT de servicio para Neon con `NEON_JWT_PRIVATE_KEY` y `NEON_JWT_KEY_ID` propios.
- El backend verifica los JWT de usuario del frontend con `NEXUS_ACCESS_JWT_PUBLIC_KEY` y `NEXUS_ACCESS_JWT_KEY_ID`, sin necesitar la clave privada de Vercel.
- Se conserva el comportamiento anterior como fallback cuando no se configura la clave pública del frontend.
- El contrato y el plan mantienen las variables portables para la futura migración de Vercel a Cloudflare.

## 2. Ya comprobado por el agente

| Comprobación | Comando o método | Resultado |
| --- | --- | --- |
| Pruebas de JWT y autenticación | `.venv/bin/pytest backend/tests/test_neon_tokens.py backend/tests/test_identity_provisioning.py -q` | PASS; 15 pruebas |
| Pruebas JWKS del frontend | `npm test -- tests/neon-jwks.test.ts tests/anclora-identity.test.ts` | PASS; 7 pruebas |
| Tipos del frontend | `npm run typecheck` | PASS |
| Integridad del diff | `git diff --check` | PASS |

## 3. Pruebas no ejecutadas (NOT_RUN)

| Prueba | Motivo concreto |
| --- | --- |
| Flujo de producción con claves distintas en Render y Vercel | Las variables y el par de claves de producción no se han configurado; la validación de código no incluye la rotación real. |
| Prueba visual de interfaz | El cambio afecta a autenticación backend/JWKS y no modifica interfaz. |

## 4. Checklist de plataforma

| # | Dónde | Pasos | Resultado esperado | Bloqueante |
| --- | --- | --- | --- | --- |
| 1 | Vercel actual / Cloudflare futuro | Añadir el JWK público de Render a `NEON_JWT_ADDITIONAL_PUBLIC_KEYS` | El JWKS publica la clave actual del frontend y la clave pública de Render | Sí |
| 2 | Render | Configurar la URL Data API, el firmante privado de servicio y la clave pública/kid del frontend; guardar sin desplegar | Variables presentes sin reiniciar el backend antiguo | Sí |
| 3 | Release Nexus | Promover el SHA validado; dejar que Render despliegue el código compatible | El backend arranca y acepta tokens del frontend mientras firma sus llamadas de Neon con su clave propia | Sí |

## 5. Riesgos y limitaciones

- El servicio Render está enlazado a la rama `production`; actualizar sus variables con el flujo que dispara deploy antes de desplegar el verificador separado haría que la revisión antigua rechazara los tokens de usuario.
- No se generaron claves ni se cambiaron variables de proveedores en esta entrega.
- Mantener el dominio JWKS estable al migrar el frontend a Cloudflare.

## 6. Decisión de Toni

- [x] Cambios revisados y validados en development.
- [ ] La rotación real con ambos firmantes está verificada.
- [ ] Se promociona: escribir `PROMOTE=FULL`.
