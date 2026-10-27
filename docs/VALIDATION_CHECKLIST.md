# Checklist de validación — Supabase Storage a Vercel Blob (2026-10-27)

**Repositorio:** anclora-nexus
**Rama:** development
**Alcance:** preparar Blob privado para DMS y avatares, manteniendo Supabase Auth y la base de datos sin cambios.
**Render:** se conserva el único servicio existente en `production`; sus variables y tráfico no se modificaron.

## Cambios incluidos

- Añade una fachada server-side de almacenamiento que conserva Supabase como proveedor por defecto y permite activar Blob mediante `NEXUS_STORAGE_PROVIDER`.
- Enruta las operaciones DMS existentes por la fachada y añade subida autenticada y lectura controlada de avatares.
- Añade un copiador idempotente con inventario `--dry-run`, selección de buckets, verificación SHA-256 y sin borrar objetos de origen.
- Actualiza el perfil web para cargar avatares mediante el backend.
- Añade especificación, plan, tareas y runbook para el corte gradual.

## Estado de datos

- Copia verificada a Blob privado: 15 objetos `dms` y 2 `avatars`; 17 objetos, 2.286.402 bytes.
- La descarga y la copia de cada objeto coinciden por SHA-256. Los objetos originales de Supabase permanecen intactos.
- Neon contiene 198 referencias a rutas de `dms-templates` sin objetos coincidentes en Supabase. No se inventaron ni copiaron archivos para esas referencias; deben revisarse antes de validar descargas de plantillas.
- `NEXUS_STORAGE_PROVIDER` sigue en `supabase` por defecto. No se cambió el servicio Render de producción.

## Validación realizada

| Comprobación | Resultado |
| --- | --- |
| `python -m compileall` en rutas, fachada y script de migración | PASS |
| Pruebas backend focalizadas de DMS y migración | PASS — 50 pruebas |
| `npm run frontend:lint` | PASS |
| `npm run frontend:build` | PASS |
| Inventario y copia de objetos | PASS — 17 objetos verificados |
| Escaneo de patrones de secretos en archivos preparados | PASS; sin credenciales detectadas |

## Pendiente de revisión de Toni

| # | Dónde | Validación | Resultado esperado | Bloqueante |
| --- | --- | --- | --- | --- |
| 1 | `development` | Revisar fachada, rutas DMS/perfil, lista de 17 objetos y referencias de plantilla pendientes | Proveedor Supabase sigue por defecto y no aparecen secretos | Sí |
| 2 | QA local y Vercel Preview | Con el entorno local production-backed y `qa.nexus@anclora.local`, probar DMS upload/download/version/firma y visualización de avatar; validar Preview del frontend. Render no tiene servicio Preview separado | Flujos autorizados funcionan contra Blob privado; Auth y base de datos permanecen sin cambios | Sí, antes del corte |
| 3 | Render Production | Solo tras revisar el cambio y autorizar el corte: configurar `BLOB_READ_WRITE_TOKEN`, desplegar el backend revisado y después activar `NEXUS_STORAGE_PROVIDER=vercel_blob` | API y archivos funcionan con Blob; Supabase conserva los originales para rollback | Sí |

## Decisión de Toni

- [ ] Validado en development
- [ ] Validado en QA local / Preview disponible
- [ ] Autorizar corte de producción
- [ ] No se promociona. Motivo: ______________________
