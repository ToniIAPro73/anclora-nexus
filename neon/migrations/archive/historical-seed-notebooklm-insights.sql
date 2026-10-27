-- Seed: Initial NotebookLM territorial insights from vulnerabilidades.md
-- Run once after migration 036 is applied.
-- Date: 2026-03-08

-- Org ID for single-tenant v0
DO $$
DECLARE
  v_org_id UUID := '00000000-0000-0000-0000-000000000001';
  v_notebook_id TEXT := '9f003773-16c5-4fb4-ab37-7b6c230ab4da';
  v_notebook_name TEXT := 'Inteligencia Territorial Suroeste Mallorca 2026';
BEGIN

-- ─── Global territorial insight (all 5 opportunities) ───────────────────────
INSERT INTO notebooklm_insights (
  org_id, notebook_id, notebook_name, query, response, insight_type, zona, metadata
) VALUES (
  v_org_id,
  v_notebook_id,
  v_notebook_name,
  '¿Cuáles son las 5 vulnerabilidades u oportunidades territoriales más críticas para un agente inmobiliario en el Suroeste de Mallorca (Andratx, Calvià, Son Ferrer, Santa Ponça) en 2026?',
  '# Vulnerabilidades y Oportunidades Territoriales — Suroeste Mallorca 2026

[Generado por Anclora Nexus Agent — notebooklm_territorial_brain]
Fecha: 2026-03-08

## Oportunidad #1 — Efecto Halo del Mandarin Oriental Punta Negra ⭐ CRÍTICA
Apertura primavera 2026 del Mandarin Oriental (Nobu + Dani García). Valorización esperada: +15-25% en radio 0-2 km. Precio actual infravalorado: €5.000-6.500/m² (vs. comparables Bendinat/Portals >€7.000/m²). Señal: scraper Idealista detecta propiedades en Punta Negra/Costa d''en Blanes con precios infravalorados, DOM <90 días.

## Oportunidad #2 — Enforcement STR → Vendedores Forzados
+19,1% inspecciones verano 2025. 4.400 anuncios retirados enero 2025. Propietarios sin licencia STR = vendedores motivados. Zonas: Calvià, Andratx. Responder <15 min desde alerta.

## Oportunidad #3 — Divergencias Microzonales + DOM >180d
Costa d''en Blanes: +22,2% interanual. Portals Nous/Bendinat: -3,3% (divergencia 25pp). Son Ferrer: mercado estancado. Señal: DOM > 180 días en Idealista por subzona.

## Oportunidad #4 — Hub Superyates + Demanda UHNWI
Superyacht New Build Hub 2026: 20 nuevos amarres 30-60m. Suizos: €5-15M+. DOM waterfront <15 días. Zonas: Puerto Portals, Bendinat, Puerto Andratx.

## Oportunidad #5 — FSBO + Cambio Generacional
Propietarios 50-75 años sin acceso compradores internacionales. Alemanes: 42% demanda, €2-8M. Zonas: Paguera, Santa Ponça, Andratx. Señal: FSBO Fotocasa + cambios catastrales (herencias) + bajadas precio >5% en <90 días.',
  'territorial',
  'general',
  '{"urgencia": "CRITICA", "oportunidades_count": 5, "fuentes": 7, "source_file": "public/docs/vulnerabilidades.md"}'::jsonb
);

-- ─── Per-zone insight: Punta Negra / Costa d'en Blanes ───────────────────────
INSERT INTO notebooklm_insights (
  org_id, notebook_id, notebook_name, query, response, insight_type, zona, metadata
) VALUES (
  v_org_id,
  v_notebook_id,
  v_notebook_name,
  'Oportunidad Mandarin Oriental Halo Effect — Punta Negra y Costa d''en Blanes',
  'CRÍTICA: Apertura primavera 2026 del Mandarin Oriental provoca +15-25% valorización en 18-24 meses. Precio actual infravalorado: €5.000-6.500/m² vs €7.000/m² en comparables. Ejecutar prospección intensiva Q1 2026. Argumento: "El Mandarin Oriental abre en 3 meses — es el momento de vender antes del spike de precios."',
  'territorial',
  'punta_negra',
  '{"urgencia": "NOW", "valorización_esperada": "15-25%", "precio_actual_m2": "5000-6500", "accion": "prospección intensiva Q1 2026"}'::jsonb
);

-- ─── Per-zone insight: Calvià / Andratx (STR enforcement) ────────────────────
INSERT INTO notebooklm_insights (
  org_id, notebook_id, notebook_name, query, response, insight_type, zona, metadata
) VALUES (
  v_org_id,
  v_notebook_id,
  v_notebook_name,
  'Señales STR enforcement y vendedores forzados — Calvià y Andratx',
  'Enforcement STR → Vendedores Forzados. +19,1% inspecciones verano 2025. 4.400 anuncios retirados enero 2025. Propietarios que pierden licencias STR necesitan vender por liquidez. Responder en <15 min desde alerta. Argumento: "Venda antes de que la regulación siga endureciéndose."',
  'territorial',
  'calvia',
  '{"urgencia": "NOW", "inspecciones_incremento": "19.1%", "anuncios_retirados": 4400, "señal": "STR enforcement"}'::jsonb
);

-- ─── Per-zone insight: Son Ferrer (stagnant market) ─────────────────────────
INSERT INTO notebooklm_insights (
  org_id, notebook_id, notebook_name, query, response, insight_type, zona, metadata
) VALUES (
  v_org_id,
  v_notebook_id,
  v_notebook_name,
  'Divergencias microzonales y propiedades estancadas — Son Ferrer y Costa d''en Blanes',
  'Divergencias Microzonales + DOM >180d. Costa d''en Blanes: +22,2% interanual. Portals Nous/Bendinat: -3,3% (divergencia 25pp en zonas vecinas). Son Ferrer: mercado estancado = oportunidad. Señal: DOM > 180 días = vendedor frustrado. Ofrecer CMA gratuito como entrada a captación.',
  'territorial',
  'son_ferrer',
  '{"urgencia": "Q2 2026", "costa_den_blanes_yoy": "+22.2%", "portals_yoy": "-3.3%", "señal": "DOM > 180 días"}'::jsonb
);

-- ─── Per-zone insight: Paguera / Santa Ponça (FSBO) ─────────────────────────
INSERT INTO notebooklm_insights (
  org_id, notebook_id, notebook_name, query, response, insight_type, zona, metadata
) VALUES (
  v_org_id,
  v_notebook_id,
  v_notebook_name,
  'FSBO y cambio generacional — Paguera, Santa Ponça, Andratx',
  'FSBO + Cambio Generacional. Propietarios 50-75 años sin acceso a compradores internacionales. Alemanes 42% demanda, €2-8M. Señal: anuncios FSBO Fotocasa + cambios catastrales (herencias) + bajadas precio >5% en <90 días. Argumento: "Mi red eXp Global tiene compradores alemanes buscando exactamente propiedades como la suya — y no están en Idealista."',
  'territorial',
  'paguera',
  '{"urgencia": "ongoing", "buyer_nationality": "alemanes 42%", "buyer_budget": "2-8M EUR", "señal": "FSBO + herencias"}'::jsonb
);

END $$;
