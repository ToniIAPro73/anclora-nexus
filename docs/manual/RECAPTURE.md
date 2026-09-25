# Recaptura del manual de usuario — Anclora Nexus

Documento operativo generado el 2026-09-25 (CHG-0014). Fuente de verdad: `docs/manual/screenshots.manifest.json`.

## Estado actual

| CURRENT | STALE | PLACEHOLDER | STATIC |
| ---: | ---: | ---: | ---: |
| 0 | 0 | 17 | 0 |

- **CURRENT**: la UI capturada sigue vigente; solo se actualizó el branding.
- **STALE**: la UI cambió después de la captura; pendiente de recaptura real (no se parchea).
- **PLACEHOLDER**: imagen de relleno o ausente; pendiente de captura real.
- **STATIC**: asset de marca del documento; no se captura.

## Reglas QA-safe

- Solo la identidad QA persistente definida en `.anclora/PRODUCTION_RUNTIME.md`; nunca la cuenta personal ni cuentas operativas.
- El ejecutor **no siembra, no crea y no borra datos**: navega y fotografía. Reutiliza los datos QA existentes (`QA_REUSE=true`).
- Las pantallas `assisted` las prepara el operador dentro de la cuenta QA; cualquier acción con escritura se hace solo sobre datos QA.
- Trabajo y commits en `development` (el script se niega a ejecutarse en otra rama).

## Requisitos

1. Dependencias raíz (`npm ci`, incluye Playwright) y `pip install python-docx` para el conversor DOCX.
2. Variables en `frontend/.env.local` (no versionado): `MANUAL_QA_PASSWORD`, ninguna adicional. Opcional `MANUAL_APP_URL` (por defecto `http://localhost:3000`).
3. Datos QA necesarios: Datos sintéticos de la cuenta QA de Nexus (leads, propiedades, tareas). Nunca capturar datos de clientes reales.

## Identidades QA por rol

| Rol | Identidad | Variables | Acceso |
| --- | --- | --- | --- |
| `qa` | qa.nexus@anclora.local | `MANUAL_QA_EMAIL` / `MANUAL_QA_PASSWORD` | inicio de sesión manual en el navegador abierto |

## Ejecución (en el Mac)

```bash
# 1. Arrancar la app en una terminal
cd frontend && npm run dev   # backend según frontend/.env.local

# 2. En otra terminal, desde la raíz del repo
bash scripts/manual/recapture-manual.sh              # todas las capturas pendientes
bash scripts/manual/recapture-manual.sh --auto-only  # solo las automáticas
bash scripts/manual/recapture-manual.sh --only a.png,b.png
node scripts/manual/recapture-manual.mjs --list      # ver el inventario
```

El script comprueba rama, fichero de entorno y que la app responde; captura en `public/docs/manual-usuario/assets/screenshots/`, deja un registro en `tmp/manual-recapture-log.json` y regenera el documento con:

```bash
python3 scripts/convert-manual-to-docx.py --lang es && python3 scripts/convert-manual-to-docx.py --lang en
```

Documentos que se regeneran: `public/docs/manual-usuario/MANUAL_USUARIO_ANCLORA_NEXUS.docx`, `public/docs/manual-usuario/MANUAL_USUARIO_ANCLORA_NEXUS_EN.docx`.

Tras revisar capturas y documento: actualiza `status` a `CURRENT` en el manifiesto para las pantallas recapturadas, registra el cambio en el changelog del manual si existe y haz commit en `development`.

## Pantallas

| Archivo | Estado | Modo | Rol | Ruta inicial | Qué capturar |
| --- | --- | --- | --- | --- | --- |
| `01-dashboard.png` | PLACEHOLDER | assisted | qa | / | Pantalla «3.1 Dashboard»; la imagen actual es un marcador de posición. |
| `02-leads.png` | PLACEHOLDER | assisted | qa | / | Pantalla «3.2 Leads»; la imagen actual es un marcador de posición. |
| `03-properties.png` | PLACEHOLDER | assisted | qa | / | Pantalla «3.3 Properties»; la imagen actual es un marcador de posición. |
| `04-tasks.png` | PLACEHOLDER | assisted | qa | / | Pantalla «3.4 Tasks»; la imagen actual es un marcador de posición. |
| `05-team.png` | PLACEHOLDER | assisted | qa | / | Pantalla «3.5 Team»; la imagen actual es un marcador de posición. |
| `06-prospection-unified.png` | PLACEHOLDER | assisted | qa | / | Pantalla «4.2 Prospection operativa»; la imagen actual es un marcador de posición. |
| `07-sellers.png` | PLACEHOLDER | assisted | qa | / | Pantalla «4.3 Seller Pipeline»; la imagen actual es un marcador de posición. |
| `08-opportunity-ranking.png` | PLACEHOLDER | assisted | qa | / | Pantalla «4.4 Opportunity Ranking»; la imagen actual es un marcador de posición. |
| `09-intelligence.png` | PLACEHOLDER | assisted | qa | / | Pantalla «4.5 Intelligence»; la imagen actual es un marcador de posición. |
| `10-statefox-bridge.png` | PLACEHOLDER | assisted | qa | / | Pantalla «StateFox Bridge»; la imagen actual es un marcador de posición. |
| `11-ingestion.png` | PLACEHOLDER | assisted | qa | / | Pantalla «5.1 Ingestion»; la imagen actual es un marcador de posición. |
| `12-data-quality.png` | PLACEHOLDER | assisted | qa | / | Pantalla «5.2 Data Quality»; la imagen actual es un marcador de posición. |
| `13-feed-orchestrator.png` | PLACEHOLDER | assisted | qa | / | Pantalla «5.3 Feed Orchestrator»; la imagen actual es un marcador de posición. |
| `14-automation-alerting.png` | PLACEHOLDER | assisted | qa | / | Pantalla «5.4 Automation & Alerting»; la imagen actual es un marcador de posición. |
| `15-command-center.png` | PLACEHOLDER | assisted | qa | / | Pantalla «5.5 Command Center»; la imagen actual es un marcador de posición. |
| `16-deal-margin-simulator.png` | PLACEHOLDER | assisted | qa | / | Pantalla «5.6 Deal Margin Simulator»; la imagen actual es un marcador de posición. |
| `17-source-observatory.png` | PLACEHOLDER | assisted | qa | / | Pantalla «5.7 Source Observatory»; la imagen actual es un marcador de posición. |
