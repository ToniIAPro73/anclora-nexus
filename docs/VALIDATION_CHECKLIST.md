# Checklist de validación — Anclora Identity para Nexus (2026-10-27)

**Repositorio:** anclora-nexus  
**Rama:** development  
**Alcance:** añadir autenticación OIDC de Anclora Identity como piloto gradual; conservar el login Supabase como ruta heredada hasta validar y autorizar el corte. No se modificaron bases de datos ni datos de usuarios.

## Cambios incluidos

- Inicio OIDC con Authorization Code + PKCE, callback validado y cookie de aplicación firmada, `HttpOnly`.
- Control de membresía de `anclora-nexus` en Identity y mapeo de email verificado al perfil y organización Nexus ya existentes.
- Emisión de JWT ES256 de corta duración para el acceso al frontend/backend Neon; el backend conserva compatibilidad temporal con tokens Supabase.
- Bandera explícita desactivada por defecto; la activación requiere que las variables servidor y cliente coincidan.
- Rutas de login y callbacks heredados deshabilitadas cuando se activa el piloto Identity.
- Documentación de configuración Preview y limitaciones conocidas.

## Validación realizada

| Comprobación | Resultado |
| --- | --- |
| `npm run typecheck -w frontend` | PASS |
| `npm exec --workspace frontend vitest -- run tests/anclora-identity.test.ts` | PASS — 2 pruebas |
| `npm run build -w frontend` | PASS |
| `.venv/bin/python -m pytest backend/tests/test_neon_tokens.py -q` | PASS — 4 pruebas |
| `git diff --cached --check` con `core.whitespace=cr-at-eol` | PASS; lockfile mantiene finales CRLF existentes |

## Pendiente de revisión en Preview

| # | Dónde | Validación | Resultado esperado | Bloqueante |
| --- | --- | --- | --- | --- |
| 1 | Vercel Preview + Identity Preview | Configurar variables OIDC, redirección allowlisted, secreto cliente y clave ES256 compartida con el backend/Neon; aprovisionar la cuenta persistente `qa.nexus@anclora.local`, perfil/membresía QA y organización QA dedicada | Login, callback, sesión, rutas protegidas y permisos de la organización QA funcionan; sin acceso a otros tenants | Sí, antes de activar el piloto |
| 2 | Preview | Cerrar sesión de Nexus, volver a iniciar sesión y comprobar que los JWT de API Neon aceptan únicamente el sujeto/organización QA | Flujos autorizados funcionan; sesión de aplicación termina al salir | Sí, antes de retirar Supabase Auth |

## Limitaciones conocidas

- Este primer piloto no implementa federación Google/GitHub, alta de cuenta ni recuperación de contraseña en Identity. No retirar Supabase Auth hasta acordar y validar cómo cubrir estas capacidades.
- La bandera permanece desactivada por defecto; producción no se cambia en este commit.
- No se hizo promoción a staging/production/main.

## Decisión de Toni

- [x] Cambios revisados y validados en development
- [ ] Validado en Preview con identidad y organización QA persistentes
- [ ] Autorizar promoción/corte de producción
