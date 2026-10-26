# Checklist de validación — migración de runtime de base de datos a Neon

**Repositorio:** anclora-nexus
**Rama:** development
**Fecha:** 2026-10-26
**Alcance:** preparar el enrutamiento PostgreSQL de Nexus a Neon. Supabase Auth y Storage permanecen; Anclora Identity no forma parte de este cambio.
**Despliegue y entorno de producción:** no modificados.

## Cambios incluidos

- Añade firma de JWT ES256 para Neon Data API en backend y frontend, y rutas de intercambio de token/JWKS.
- Enruta las consultas de base de datos por Neon cuando se selecciona el proveedor, manteniendo Supabase para Auth y Storage.
- Añade migraciones de roles, grants y RLS para la rama aislada de revisión de Neon.
- Restringe los campos devueltos por el perfil público.

## Validación realizada

| Comprobación | Resultado |
| --- | --- |
| TypeScript `npm run typecheck` | PASS |
| ESLint de archivos modificados | PASS |
| Suite frontend `npm test -w frontend` | PASS — 17 pruebas |
| `npm run lint` | PASS |
| `npm run build` | PASS |
| Unittests focalizados `backend.tests.test_neon_tokens` | PASS — 3 pruebas |
| `git diff --check` | PASS |
| Suite Python completa `python -m pytest` | NOT RUN — pytest no está instalado en el entorno virtual del repo |

## Estado de Neon y límites de la validación

- La migración de roles/grants/RLS se aplicó solo a la rama temporal `nexus-neon-cutover-security-review-20261026`; la rama productiva `main` no fue alterada.
- Las comprobaciones de esquema y políticas fueron de solo lectura; no se modificaron registros de aplicación.
- No se cambió la configuración de producción ni se desplegó este código.
- La verificación funcional en Preview sigue pendiente: requiere desplegar y configurar las variables de Preview, enlazar la URL JWKS pública, restringir CORS y probar con la identidad dedicada de QA, incluidos RLS, lecturas/escrituras permitidas, aislamiento entre organizaciones, Auth, Storage y polling.

## Revisión de Toni

- [ ] Revisado en `development`
- [ ] Preview validado con la identidad dedicada de QA
- [ ] Autorizar promoción (si procede)
