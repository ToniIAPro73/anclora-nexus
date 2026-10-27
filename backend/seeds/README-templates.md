# Anclora Nexus — Biblioteca de Plantillas DMS

## Estructura

```
backend/seeds/
├── document_templates_seed.sql   ← Seed SQL principal (ejecutar en Neon)
├── README-templates.md           ← Este archivo
└── templates/
    └── es/                       ← 14 plantillas en español
        ├── tpl-arras-penitenciales.es.md
        ├── tpl-contrato-compraventa.es.md
        ├── tpl-oferta-compra.es.md
        ├── tpl-contrato-reserva-senal.es.md
        ├── tpl-nota-encargo.es.md
        ├── tpl-contrato-temporada.es.md
        ├── tpl-contrato-arrendamiento.es.md
        ├── tpl-contrato-alquiler-turistico.es.md
        ├── tpl-recibo-fianza.es.md
        ├── tpl-acta-entrega-llaves.es.md
        ├── tpl-mandato-exclusiva.es.md
        ├── tpl-kyc-identificacion-cliente.es.md
        ├── tpl-acuerdo-confidencialidad.es.md
        └── tpl-generico.es.md
```

## Pasos de integración

1. **Subir los `.md`** al storage privado de Nexus en la ruta `templates/es/`
2. **Ejecutar el seed SQL** en Neon:

   ```sql
   \i backend/seeds/document_templates_seed.sql
   ```

3. **Estado inicial:** todos los registros quedan en `legal_review_status = 'pending'`
4. **No publicar** ninguna plantilla sin revisión jurídica humana + validación de Advisor AI
5. **Publicar** via Biblioteca de plantillas en Nexus → botón "Publicar" → cambia estado a `published`
6. El DMS filtra automáticamente por `status = published + operation_type + jurisdiction + language`

## Variables de autocompletado

Todas las plantillas usan `{{ variable }}` resueltas automáticamente desde el expediente:

| Prefijo                   | Fuente CRM                           |
| ------------------------- | ------------------------------------ |
| `buyer.*`                 | `leads` (rol comprador)              |
| `seller.*`                | `nexus_sellers`                      |
| `tenant.*` / `landlord.*` | `leads` / `nexus_sellers` (alquiler) |
| `guest.*`                 | `leads` (ETV)                        |
| `property.*`              | `properties`                         |
| `deal.*`                  | `realestatedealfolders`              |
| `agent.*`                 | `profiles` (agente responsable)      |
| `organization.*`          | `organizations`                      |
| `tenancy.*`               | `dealfolderparties` + overrides      |
| `booking.*`               | overrides ETV                        |

## Legislación de referencia

- Código Civil (art. 1454 — arras penitenciales)
- LAU (Ley 29/1994 y modificaciones 2023)
- Ley de Vivienda 12/2023
- Ley de Turismo de les Illes Balears
- Ley 3/2024 ROAIIB (agentes inmobiliarios Baleares)
- RD 933/2021 (registro de viajeros)
- RGPD (KYC y tratamiento de datos)
