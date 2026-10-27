# Cutover runtime — Anclora Nexus

**Rama:** `development`
**Estado del código:** preparado localmente y pendiente de validación del usuario.
**Runtime objetivo:** Vercel, Neon PostgreSQL/Neon Data API, Anclora Identity y Vercel Blob.

## Implementado en este cambio

- El frontend y backend usan Neon Data API para operaciones de aplicación.
- La autenticación y las sesiones de usuario usan Anclora Identity.
- Los documentos y avatares usan Vercel Blob.
- Se retiraron los clientes, rutas y credenciales de proveedores anteriores del runtime.
- Se actualizaron las políticas de Neon para utilizar los claims de identidad compatibles con Neon.
- Los scripts de operación de datos ahora se conectan a Neon.

## Validación y límites

- `cd backend && ../.venv/bin/python -m pytest -q`: **964 passed, 1 skipped**. The skipped FinOps QA mutates Neon data and now requires explicit opt-in with `NEON_FINOPS_LIVE_TESTS=1`.
- Backend Python compilation: `python3 -m compileall -q backend` passed.
- Frontend checks passed: `npm run lint`, `npm test -w frontend` (19 tests), `npm run typecheck -w frontend`, `npm run build`, and `npm run ops:guesthub-pilot:check-env`.
- DMS route tests use an in-memory Blob stub; they do not require production Blob credentials.
- No remote database migration was applied and no deployment was performed in this validation pass.
- Historical documents and SQL retain Supabase references where they describe the old architecture. They are archived evidence, not runtime configuration; the active migration guide is `neon/migrations/README.md`.

## Siguiente validación

- Revisar el flujo de Identity y las operaciones de datos/archivos con la cuenta QA persistente.
- Aplicar las migraciones Neon conforme al proceso gobernado y verificar sus políticas.
- Validar el build y el deployment de Vercel; mantener cambios sin commit hasta la validación de Toni.
