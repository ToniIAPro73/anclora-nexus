<!-- markdownlint-disable MD001 MD013 MD033 MD041 MD060 -->

<div align="center">

<img src="./frontend/public/brand/anclora-nexus.png" alt="Anclora Nexus" width="132" />

# Anclora Nexus

### Sistema interno de coordinación operativa para documentos y contratos

Plataforma centralizada para gestión de carpetas de operaciones, documentos, templates, y workflows de firma en transacciones inmobiliarias.

**Español** · [Català](./README.ca.md) · [English](./README.en.md) · [Deutsch](./README.de.md)

<br />

![Anclora](https://img.shields.io/badge/Anclora-ecosystem-111827)
![Categoría](https://img.shields.io/badge/categoría-Interna-D4AF37)
![Idiomas](https://img.shields.io/badge/idiomas%20producto-4-047857)

</div>

---

> [!IMPORTANT]
> Repositorio interno del ecosistema Anclora. Esta herramienta coordina operaciones críticas con documentos y datos reales de transacciones. No publicar detalles operativos, credenciales, datos de clientes, ni lógica sensible fuera de los canales autorizados.

## Qué es

Nexus es la plataforma operativa central para manejo de documentos y contratos en el ciclo de vida de transacciones inmobiliarias. Coordina carpetas de operaciones, gestiona templates de documentos, genera workflows de firma electrónica (DocuSeal), integra validación de contratos mediante Advisor AI, y proporciona vistas de control para teams internos.

## Categoría en el ecosistema

| Campo | Valor |
|---|---|
| Categoría | Interna |
| Acento de marca | `#D4AF37` |
| Tipografía | Inter |
| Repositorio canónico | `anclora-nexus` |

## Funcionalidades principales

- **Gestión de carpetas de operaciones:** crear, listar y gestionar carpetas vinculadas a deals, propiedades y partes interesadas (leads, sellers, companías, contactos)
- **Ciclo de vida de documentos:** upload/download cifrado, versionado de documentos, revisión legal y gestión de retención conforme a políticas
- **Biblioteca de templates:** templates por familia de documentos, metadata de calidad, generación automática y validación
- **Workflows de firma:** integración con DocuSeal, tracking de envelopes de firma, inmutabilidad de copias firmadas
- **Validación de contratos:** integración con Advisor AI para revisión automática de cláusulas y riesgos legales
- **Coordinación operativa:** indicadores, auditoría de acciones, y vistas consolidadas para teams

## Stack tecnológico

| Área | Tecnología |
|---|---|
| Frontend | Next.js 16, React 19, TypeScript |
| Autenticación | Anclora Identity (OIDC) |
| Base de datos | Neon PostgreSQL Data API |
| Almacenamiento | Vercel Blob (objetos privados) |
| Estilos | Tailwind CSS, Radix UI, shadcn |
| Testing | Vitest + React Testing Library |
| UI Components | Lucide React, Framer Motion |
| Documentos | jsPDF, react-markdown, doc-viewer |

## Arranque local

```bash
cd frontend
npm install
npm run dev
```

El servidor estará disponible en `http://localhost:3000`.

## Idiomas soportados

El producto en producción soporta 4 idiomas: Español (predeterminado), Català, English, Deutsch (`INTERNAL_LOCALES`, `frontend/src/lib/anclora-language-toggle.ts`). Esta documentación se mantiene en los 4 idiomas del producto.

## Documentación y gobernanza

- Especificación de flujos: [`docs/DMS_*.md`](./docs/)
- Contratos de marca y gobernanza: `docs/standards/`
- Bóveda Anclora (fuente de verdad): `contracts/` y `docs/governance/`

## Renombrado SyncXML → GuestHub (2026-08)

El producto **Anclora SyncXML** pasó a llamarse **Anclora GuestHub** (repo `anclora-guesthub`) en 2026-08. Nexus adopta los nombres canónicos `GUESTHUB_*` para variables de entorno con fallback a los legados `SYNCXML_*`. Los identificadores persistidos y de contrato se mantienen como legado sin migración de datos: `product='syncxml'`, `source='syncxml_landing'`, `request_type='syncxml_pilot'`, `task_type='syncxml_pilot_review'`, `origin='anclora-syncxml'`, rutas `/api/syncxml-pilot` y `/api/internal/webhooks/syncxml-pilot` (alias `/api/internal/webhooks/guesthub-pilot` registrado), códigos de error `SYNCXML_PILOT_*` y enums `TargetProduct.SYNCXML`/`IntakeSource.SYNCXML_LANDING`. Detalle operativo en [`docs/GUESTHUB_PILOT_REVIEW_FLOW.md`](./docs/GUESTHUB_PILOT_REVIEW_FLOW.md) y [`docs/ENVIRONMENT_SETUP_GUESTHUB_PILOT.md`](./docs/ENVIRONMENT_SETUP_GUESTHUB_PILOT.md).

---

<div align="center">

### Anclora Group

Uso interno

</div>
