-- ============================================================
-- 005_seed.sql — Anclora Nexus v0 Complete Seed
-- Realistic dataset for luxury real estate in SW Mallorca
-- ============================================================

-- 1. Organization
INSERT INTO organizations (id, name, slug)
VALUES ('9d6cb56d-3f21-4f7b-80ea-797a7c2c62cf', 'Anclora Private Estates', 'anclora-private-estates')
ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name;

DO $$
DECLARE
    v_org  UUID := '9d6cb56d-3f21-4f7b-80ea-797a7c2c62cf';
    -- Agent IDs
    a_lead UUID := 'a0000000-0000-0000-0000-000000000001';
    a_pros UUID := 'a0000000-0000-0000-0000-000000000002';
    a_recap UUID := 'a0000000-0000-0000-0000-000000000003';
    -- Lead IDs (b prefix)
    l01 UUID := 'b0000000-0000-0000-0000-000000000001';
    l02 UUID := 'b0000000-0000-0000-0000-000000000002';
    l03 UUID := 'b0000000-0000-0000-0000-000000000003';
    l04 UUID := 'b0000000-0000-0000-0000-000000000004';
    l05 UUID := 'b0000000-0000-0000-0000-000000000005';
    l06 UUID := 'b0000000-0000-0000-0000-000000000006';
    l07 UUID := 'b0000000-0000-0000-0000-000000000007';
    l08 UUID := 'b0000000-0000-0000-0000-000000000008';
    l09 UUID := 'b0000000-0000-0000-0000-000000000009';
    l10 UUID := 'b0000000-0000-0000-0000-000000000010';
    l11 UUID := 'b0000000-0000-0000-0000-000000000011';
    l12 UUID := 'b0000000-0000-0000-0000-000000000012';
    l13 UUID := 'b0000000-0000-0000-0000-000000000013';
    l14 UUID := 'b0000000-0000-0000-0000-000000000014';
    l15 UUID := 'b0000000-0000-0000-0000-000000000015';
    l16 UUID := 'b0000000-0000-0000-0000-000000000016';
    l17 UUID := 'b0000000-0000-0000-0000-000000000017';
    l18 UUID := 'b0000000-0000-0000-0000-000000000018';
    -- Property IDs (c prefix)
    p01 UUID := 'c0000000-0000-0000-0000-000000000001';
    p02 UUID := 'c0000000-0000-0000-0000-000000000002';
    p03 UUID := 'c0000000-0000-0000-0000-000000000003';
    p04 UUID := 'c0000000-0000-0000-0000-000000000004';
    p05 UUID := 'c0000000-0000-0000-0000-000000000005';
    p06 UUID := 'c0000000-0000-0000-0000-000000000006';
    p07 UUID := 'c0000000-0000-0000-0000-000000000007';
    p08 UUID := 'c0000000-0000-0000-0000-000000000008';
    p09 UUID := 'c0000000-0000-0000-0000-000000000009';
    p10 UUID := 'c0000000-0000-0000-0000-000000000010';
    p11 UUID := 'c0000000-0000-0000-0000-000000000011';
    p12 UUID := 'c0000000-0000-0000-0000-000000000012';
    p13 UUID := 'c0000000-0000-0000-0000-000000000013';
    p14 UUID := 'c0000000-0000-0000-0000-000000000014';
    p15 UUID := 'c0000000-0000-0000-0000-000000000015';
BEGIN

-- ============================================================
-- 2. Agents
-- ============================================================
INSERT INTO agents (id, org_id, name, description, skill_name, status) VALUES
  (a_lead,  v_org, 'Lead Intake Agent',   'Cualifica y prioriza leads entrantes',   'lead_intake',        'active'),
  (a_pros,  v_org, 'Prospection Agent',   'Búsqueda semanal de propiedades',        'prospection_weekly', 'active'),
  (a_recap, v_org, 'Weekly Recap Agent',  'Resumen ejecutivo semanal',              'recap_weekly',       'active')
ON CONFLICT (org_id, skill_name) DO NOTHING;

-- ============================================================
-- 3. Constitutional Limits
-- ============================================================
INSERT INTO constitutional_limits (org_id, limit_type, limit_value, description) VALUES
  (v_org, 'max_daily_leads',        50,     'Límite diario de leads procesados'),
  (v_org, 'max_llm_tokens_per_day', 100000, 'Límite diario de tokens LLM')
ON CONFLICT (org_id, limit_type) DO UPDATE SET limit_value = EXCLUDED.limit_value;

-- ============================================================
-- 4. Properties (15) — Luxury SW Mallorca
-- ============================================================
INSERT INTO properties (id, org_id, address, city, postal_code, latitude, longitude, property_type, price, surface_m2, bedrooms, bathrooms, features, status, owner_contact, catastro_ref, ai_valuation, ai_valuation_confidence, prospection_score, notes, created_at) VALUES
(p01, v_org, 'Calle Isaac Peral 12',          'Port d''Andratx',   '07157', 39.54520000, 2.38250000, 'villa',     4950000,  520, 5, 4, '{"sea_view":true,"pool":true,"garden":true,"garage":true,"smart_home":true}',               'listed',       '{"name":"María Esteva","phone":"+34 671 234 001","email":"m.esteva@gmail.com"}',          'AND-2024-00147', 5100000, 0.88, 0.92, '{"notes":"Primera línea con acceso directo al puerto"}',        NOW() - INTERVAL '45 days'),
(p02, v_org, 'Camí de Son Vic Vell 8',        'Calvià',            '07184', 39.56210000, 2.50730000, 'finca',     7800000,  1200, 7, 6, '{"sea_view":false,"pool":true,"garden":true,"garage":true,"vineyard":true,"olive_grove":true}', 'prospect',   '{"name":"Tomeu Barceló","phone":"+34 629 112 345"}',                                     'CAL-2024-00231', 7500000, 0.82, 0.85, '{"notes":"Finca histórica con viñedo propio, 15.000m² parcela"}', NOW() - INTERVAL '30 days'),
(p03, v_org, 'Avda. de la Playa 3, Ático',    'Santa Ponsa',       '07180', 39.51210000, 2.47890000, 'penthouse', 2850000,  280, 4, 3, '{"sea_view":true,"pool":true,"terrace":true,"concierge":true}',                            'listed',       '{"name":"Sandra Reus","phone":"+34 654 887 223","email":"s.reus@outlook.es"}',            'STP-2024-00089', 2900000, 0.91, 0.78, '{"notes":"Ático dúplex con terraza panorámica 120m²"}',         NOW() - INTERVAL '22 days'),
(p04, v_org, 'Carrer des Coll Baix 15',       'Andratx',           '07150', 39.57430000, 2.42110000, 'villa',     3200000,  420, 4, 3, '{"sea_view":true,"pool":true,"garden":true,"garage":true}',                                'contacted',    '{"name":"Pere Jaume","phone":"+34 600 445 678"}',                                        'AND-2024-00198', 3350000, 0.85, 0.88, '{"notes":"Villa moderna con vistas al valle de Andratx"}',      NOW() - INTERVAL '18 days'),
(p05, v_org, 'Urb. Son Ferrer, Calle Luna 7', 'Son Ferrer',        '07181', 39.50870000, 2.49230000, 'villa',     1450000,  310, 4, 3, '{"sea_view":false,"pool":true,"garden":true,"garage":true}',                               'listed',       '{"name":"Catalina Munar","phone":"+34 666 332 198","email":"cmunar@hotmail.com"}',        'CAL-2024-00412', 1500000, 0.90, 0.72, '{"notes":"Villa familiar reformada 2024, parcela 800m²"}',      NOW() - INTERVAL '15 days'),
(p06, v_org, 'Paseo del Mar 22',              'Camp de Mar',       '07160', 39.53650000, 2.41870000, 'villa',     6200000,  650, 6, 5, '{"sea_view":true,"pool":true,"spa":true,"gym":true,"smart_home":true,"elevator":true}',    'under_offer',  '{"name":"Alejandro Font","phone":"+34 690 221 445","email":"a.font@bufete-font.es"}',     'AND-2024-00076', 6500000, 0.87, 0.95, '{"notes":"Propiedad exclusiva frente al mar, acceso privado a cala"}', NOW() - INTERVAL '60 days'),
(p07, v_org, 'Carrer Bendinat 45',            'Bendinat',          '07181', 39.53890000, 2.53210000, 'villa',     5500000,  580, 5, 5, '{"sea_view":true,"pool":true,"garden":true,"garage":true,"cinema":true}',                  'listed',       '{"name":"Miquel Tous","phone":"+34 618 776 543"}',                                       'CAL-2024-00155', 5700000, 0.86, 0.90, '{"notes":"Villa de lujo en urbanización cerrada con seguridad 24h"}', NOW() - INTERVAL '35 days'),
(p08, v_org, 'Cala Vinyes, Camí del Far 3',   'Cala Vinyes',       '07181', 39.49870000, 2.47650000, 'villa',     2100000,  350, 4, 3, '{"sea_view":true,"pool":true,"garden":true}',                                             'prospect',     '{"name":"Joana Vidal","phone":"+34 652 443 897"}',                                       'CAL-2024-00367', 2200000, 0.83, 0.76, '{"notes":"A 200m de la playa, necesita actualización cocina"}', NOW() - INTERVAL '10 days'),
(p09, v_org, 'Sol de Mallorca, Calle Orión 9','Sol de Mallorca',   '07181', 39.50120000, 2.48910000, 'villa',     3800000,  480, 5, 4, '{"sea_view":true,"pool":true,"garden":true,"garage":true,"bbq":true}',                     'contacted',    '{"name":"Antònia Serra","phone":"+34 637 556 012","email":"a.serra@yahoo.es"}',           'CAL-2024-00298', 3900000, 0.89, 0.84, '{"notes":"Vistas despejadas hasta Cabrera, diseño Minotti"}',   NOW() - INTERVAL '25 days'),
(p10, v_org, 'Puerto Portals, Marina 18',     'Portals Nous',      '07181', 39.52560000, 2.54780000, 'apartment', 1850000,  185, 3, 2, '{"sea_view":true,"pool":false,"concierge":true,"parking":true}',                           'listed',       '{"name":"Inmobiliaria Portals SL","phone":"+34 971 676 543"}',                           'CAL-2024-00511', 1900000, 0.92, 0.70, '{"notes":"Frente al puerto deportivo, alquiler turístico vigente"}', NOW() - INTERVAL '40 days'),
(p11, v_org, 'Carrer de la Tramuntana 6',     'Port d''Andratx',   '07157', 39.54330000, 2.38890000, 'apartment', 1250000,  145, 3, 2, '{"sea_view":true,"pool":true,"terrace":true}',                                            'prospect',     '{"name":"Rafael Colom","phone":"+34 625 998 112"}',                                      'AND-2024-00256', 1300000, 0.87, 0.68, '{"notes":"Complejo residencial premium, plaza garaje incluida"}', NOW() - INTERVAL '8 days'),
(p12, v_org, 'Finca Es Capdellà km3',         'Es Capdellà',       '07196', 39.55780000, 2.46320000, 'finca',     9500000,  1800, 8, 7, '{"sea_view":false,"pool":true,"garden":true,"garage":true,"helipad":true,"guest_house":true}', 'prospect',  '{"name":"Herencia Familia Bestard","phone":"+34 971 234 567"}',                           'CAL-2024-00044', 9200000, 0.78, 0.93, '{"notes":"Gran finca señorial con licencia agroturismo, 80.000m² terreno"}', NOW() - INTERVAL '5 days'),
(p13, v_org, 'Costa de la Calma, C/ Cipres 4','Costa de la Calma', '07181', 39.50450000, 2.46780000, 'villa',     1750000,  290, 4, 3, '{"sea_view":false,"pool":true,"garden":true,"garage":true}',                               'sold',         '{"name":"Francisca Palmer","phone":"+34 649 213 876"}',                                  'CAL-2024-00389', 1800000, 0.93, 0.65, '{"notes":"Vendida en febrero 2026 a cliente alemán"}',          NOW() - INTERVAL '90 days'),
(p14, v_org, 'Sa Mola, Parcela 23',           'Andratx',           '07150', 39.56890000, 2.40120000, 'land',      1100000,  2500, 0, 0, '{"sea_view":true,"building_permit":true}',                                                 'listed',       '{"name":"Joan Alemany","phone":"+34 661 554 332","email":"j.alemany@gmail.com"}',         'AND-2024-00301', 1150000, 0.84, 0.80, '{"notes":"Parcela con licencia y proyecto aprobado para villa 400m²"}', NOW() - INTERVAL '12 days'),
(p15, v_org, 'Cala Llamp, Camí des Moll 1',   'Port d''Andratx',   '07157', 39.54010000, 2.37560000, 'villa',    12500000,  850, 6, 6, '{"sea_view":true,"pool":true,"spa":true,"gym":true,"smart_home":true,"elevator":true,"dock":true}', 'listed', '{"name":"Bufete Garau & Asociados","phone":"+34 971 678 901","email":"info@garau-law.es"}', 'AND-2024-00012', 13000000, 0.80, 0.97, '{"notes":"Mansión icónica en Cala Llamp, acceso privado al mar, embarcadero propio"}', NOW() - INTERVAL '55 days')
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- 5. Leads (18) — International high-net-worth buyers
-- ============================================================
INSERT INTO leads (id, org_id, name, email, phone, source, property_interest, budget_range, urgency, ai_summary, ai_priority, priority_score, next_action, status, last_contact_at, processed_at, created_at) VALUES
(l01, v_org, 'Klaus & Ingrid Schmidt',   'k.schmidt@schmidt-holding.de',     '+49 172 345 6789',  'referral',  'Villa con vistas al mar en Port d''Andratx',         '4M-6M EUR',   'high',      'Matrimonio alemán, empresarios industriales jubilados. Buscan residencia principal. Flexibles en precio si la ubicación es premium. Referidos por cliente anterior (Weber).', 5, 0.95, 'Agendar visita a p01 y p06',              'qualified',    NOW() - INTERVAL '2 days',  NOW() - INTERVAL '5 days',  NOW() - INTERVAL '7 days'),
(l02, v_org, 'James Hamilton',           'james@hamiltonpartners.co.uk',     '+44 7700 900 123',  'linkedin',  'Propiedad de inversión con licencia turística',      '1.5M-3M EUR', 'medium',    'Inversor británico, fondo inmobiliario boutique. Interesado en rentabilidad. Busca propiedades con licencia de alquiler turístico vigente.',                                  4, 0.82, 'Enviar dossier p03 y p10',                'contacted',    NOW() - INTERVAL '4 days',  NOW() - INTERVAL '6 days',  NOW() - INTERVAL '8 days'),
(l03, v_org, 'Astrid Lindström',         'astrid.lindstrom@telia.se',        '+46 70 234 5678',   'web',       'Finca rústica con terreno amplio',                   '5M-10M EUR',  'immediate', 'Empresaria sueca del sector tech. Busca finca para proyecto de bienestar y retiro premium. Dispuesta a invertir en reforma integral. Alta urgencia: quiere decidir en marzo.', 5, 0.98, 'Visita urgente p02 y p12',                'negotiating',  NOW() - INTERVAL '1 day',   NOW() - INTERVAL '3 days',  NOW() - INTERVAL '5 days'),
(l04, v_org, 'Pierre & Colette Dubois',  'p.dubois@dubois-patrimoine.fr',    '+33 6 12 34 56 78', 'exp',       'Penthouse o ático de lujo',                          '2M-4M EUR',   'medium',    'Pareja francesa, directivos sector financiero. Segunda residencia. Prefieren urbanizaciones con servicios (conserje, seguridad). Viajan frecuente a Palma.',                  4, 0.80, 'Proponer p03 y p07',                      'contacted',    NOW() - INTERVAL '3 days',  NOW() - INTERVAL '5 days',  NOW() - INTERVAL '6 days'),
(l05, v_org, 'Markus Weber',             'mweber@weber-ag.ch',              '+41 79 345 67 89',  'referral',  'Villa moderna con domótica',                         '3M-5M EUR',   'high',      'Empresario suizo, sector farmacéutico. Cliente recurrente — compró propiedad en Son Vida en 2023. Ahora busca segunda villa en la costa suroeste para su familia.',           5, 0.93, 'Agendar visita p04, p07, p09',            'qualified',    NOW() - INTERVAL '1 day',   NOW() - INTERVAL '3 days',  NOW() - INTERVAL '4 days'),
(l06, v_org, 'Erik & Mette Johansson',   'erik.johansson@outlook.com',       '+45 30 12 34 56',   'web',       'Villa familiar con jardín grande',                   '1M-2M EUR',   'low',       'Familia danesa, padre directivo IT. Buscan casa familiar para mudanza permanente. Hijos en edad escolar — interesados en zona cerca de colegios internacionales.',             3, 0.58, 'Enviar listado p05 y p08',                'new',          NULL,                       NOW() - INTERVAL '2 days',  NOW() - INTERVAL '2 days'),
(l07, v_org, 'Victoria Robertson',       'victoria@robertson-estates.co.uk', '+44 7911 123 456',  'linkedin',  'Propiedades exclusivas >5M para clientes UHNW',     '5M-15M EUR',  'high',      'Agente de compras británica que representa a clientes ultra-high-net-worth. Busca propiedades off-market en primera línea. Relación B2B potencial muy valiosa.',               5, 0.96, 'Meeting presencial + tour p06, p15, p12', 'qualified',    NOW() - INTERVAL '1 day',   NOW() - INTERVAL '2 days',  NOW() - INTERVAL '3 days'),
(l08, v_org, 'Hans-Peter Bauer',         'hp.bauer@t-online.de',            '+49 151 234 5678',  'cold',      'Apartamento en Port d''Andratx',                     '1M-1.5M EUR', 'low',       'Jubilado alemán, presupuesto ajustado para la zona. Busca apartamento pequeño como pied-à-terre. Posibilidad limitada pero recurrente en recomendaciones.',                   2, 0.35, 'Enviar opciones p11',                     'contacted',    NOW() - INTERVAL '10 days', NOW() - INTERVAL '12 days', NOW() - INTERVAL '14 days'),
(l09, v_org, 'Sergei & Natalia Volkov',  'svolkov@proton.me',               '+7 916 234 5678',   'web',       'Mansión con embarcadero privado',                    '10M+ EUR',    'immediate', 'Pareja rusa con residencia fiscal en Dubái. Buscan propiedad trophy en Cala Llamp o similar. Pago cash. Requiere due diligence de compliance adicional.',                     4, 0.75, 'Verificar compliance + presentar p15',    'new',          NULL,                       NOW() - INTERVAL '1 day',   NOW() - INTERVAL '1 day'),
(l10, v_org, 'Thomas & Anna Fischer',    'fischer.thomas@gmx.de',           '+49 176 987 6543',  'referral',  'Villa con piscina, zona Calvià',                     '2M-3.5M EUR', 'medium',    'Matrimonio alemán, sector automoción (BMW ejecutivo). Buscan segunda residencia con buena conexión al aeropuerto. Referidos por Schmidt (l01).',                               4, 0.78, 'Agendar visita p09 y p05',                'contacted',    NOW() - INTERVAL '5 days',  NOW() - INTERVAL '7 days',  NOW() - INTERVAL '9 days'),
(l11, v_org, 'Sophie Clarke',            'sophie.c@claridges-advisory.com',  '+44 7456 789 012',  'exp',       'Proyecto de inversión hotelera boutique',            '8M-12M EUR',  'medium',    'Consultora hotelera británica. Representa grupo inversor interesado en convertir finca histórica en hotel boutique de lujo. Proyecto a largo plazo pero alto valor.',          4, 0.84, 'Presentar p02 y p12 como oportunidad',    'contacted',    NOW() - INTERVAL '6 days',  NOW() - INTERVAL '8 days',  NOW() - INTERVAL '10 days'),
(l12, v_org, 'Lars Eriksen',             'lars@eriksen-kapital.no',          '+47 912 34 567',    'linkedin',  'Parcela para construir villa a medida',              '2M-4M EUR',   'high',      'Empresario noruego, sector energías renovables. Quiere construir villa sostenible con certificación passivhaus. Busca parcela con vistas y licencia.',                        4, 0.81, 'Mostrar p14 + contactar arquitecto local','qualified',    NOW() - INTERVAL '3 days',  NOW() - INTERVAL '4 days',  NOW() - INTERVAL '5 days'),
(l13, v_org, 'Michael & Sarah Thompson', 'michael@thompsonventures.com',     '+1 212 555 0147',   'web',       'Villa con helipuerto o cercana',                     '6M-10M EUR',  'medium',    'Pareja estadounidense, venture capital NYC. Pasan 3 meses/año en Europa. Buscan propiedad exclusiva con máxima privacidad. Interesados en domótica y seguridad avanzada.',     4, 0.79, 'Proponer p06 y p12',                      'new',          NULL,                       NOW() - INTERVAL '3 days',  NOW() - INTERVAL '3 days'),
(l14, v_org, 'Friedrich Meier',          'f.meier@ubs.com',                  '+41 44 234 56 78',  'cold',      'Cartera de inversión inmobiliaria',                  '3M-8M EUR',   'low',       'Banker suizo UBS, gestiona patrimonio de varios clientes HNW. Busca oportunidades de inversión con rentabilidad >4% anual. Relación institucional interesante.',               3, 0.62, 'Preparar informe ROI propiedades',         'contacted',    NOW() - INTERVAL '15 days', NOW() - INTERVAL '18 days', NOW() - INTERVAL '20 days'),
(l15, v_org, 'Isabella Rossi',           'isabella@rossi-design.it',         '+39 335 678 9012',  'web',       'Propiedad con carácter para reformar',               '1.5M-2.5M EUR','medium',   'Diseñadora de interiores italiana. Busca proyecto personal — propiedad con potencial de reforma donde aplicar su visión. Presupuesto moderado pero gran potencial de PR.',     3, 0.60, 'Enviar p08 como oportunidad de reforma',  'new',          NULL,                       NOW() - INTERVAL '4 days',  NOW() - INTERVAL '4 days'),
(l16, v_org, 'Henrik Andersen',          'h.andersen@maersk.dk',             '+45 20 98 76 54',   'referral',  'Villa o finca premium con privacidad',               '4M-7M EUR',   'high',      'Ejecutivo danés, naviera Maersk. Busca retiro premium. Referido por Johansson (l06). Presupuesto sólido. Muy interesado en zona Andratx/Camp de Mar.',                        5, 0.91, 'Tour privado p04, p06, p09',              'qualified',    NOW() - INTERVAL '2 days',  NOW() - INTERVAL '3 days',  NOW() - INTERVAL '4 days'),
(l17, v_org, 'Yuki & Ken Tanaka',        'yuki.tanaka@softbank.jp',          '+81 90 1234 5678',  'exp',       'Propiedad icónica como inversión de prestigio',      '10M+ EUR',    'low',       'Matrimonio japonés, sector tech (SoftBank). Compra aspiracional, no urgente. Buscan propiedad emblemática en el Mediterráneo. Mallorca compite con Côte d''Azur y Cerdeña.',  3, 0.55, 'Enviar brochure p15 y comparativa mercado','new',          NULL,                       NOW() - INTERVAL '7 days',  NOW() - INTERVAL '7 days'),
(l18, v_org, 'Martin & Lisa Wagner',     'martin.wagner@bmw.de',             '+49 89 123 4567',   'web',       'Villa moderna cerca de golf',                        '2M-3M EUR',   'medium',    'Ejecutivos alemanes BMW Múnich. Buscan residencia vacacional con acceso a campo de golf. Interesados en Santa Ponsa y alrededores. Viajan con frecuencia.',                   3, 0.65, 'Proponer p05 y p09',                      'contacted',    NOW() - INTERVAL '8 days',  NOW() - INTERVAL '10 days', NOW() - INTERVAL '12 days')
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- 6. Tasks (26) — Mix of follow_up, prospection, dossier, admin
-- ============================================================
INSERT INTO tasks (org_id, title, description, type, status, due_date, related_lead_id, related_property_id, ai_generated, agent_id, created_at, completed_at) VALUES
-- Follow-up tasks (active)
(v_org, 'Agendar visita Schmidt — Port d''Andratx',         'Coordinar visita presencial a p01 y p06 con Klaus & Ingrid Schmidt. Confirmar disponibilidad propietarios.', 'follow_up', 'pending', NOW() + INTERVAL '2 days',  l01, p01,  true,  a_lead, NOW() - INTERVAL '2 days', NULL),
(v_org, 'Enviar dossier propiedades a Hamilton',             'Preparar y enviar PDF con fichas de p03 y p10 incluyendo análisis ROI y proyección alquiler turístico.',     'follow_up', 'pending', NOW() + INTERVAL '1 day',   l02, p03,  true,  a_lead, NOW() - INTERVAL '3 days', NULL),
(v_org, 'Visita urgente Lindström — fincas',                 'Tour privado fincas p02 y p12 para Astrid Lindström. Contactar propietarios para acceso inmediato.',        'follow_up', 'pending', NOW(),                      l03, p02,  false, NULL,   NOW() - INTERVAL '1 day',  NULL),
(v_org, 'Preparar comparativa para Dubois',                  'Crear documento comparativo entre p03 (Santa Ponsa) y p07 (Bendinat) adaptado al perfil del cliente.',      'follow_up', 'pending', NOW() + INTERVAL '3 days',  l04, p03,  true,  a_lead, NOW() - INTERVAL '2 days', NULL),
(v_org, 'Segunda visita Weber — villa shortlist',            'Organizar segunda ronda de visitas para Markus Weber: p04, p07, p09. Incluir almuerzo en Port d''Andratx.', 'follow_up', 'pending', NOW() + INTERVAL '1 day',   l05, p04,  false, NULL,   NOW() - INTERVAL '1 day',  NULL),
(v_org, 'Meeting presencial con Robertson',                  'Reunión B2B con Victoria Robertson en Hotel Gran Meliá. Presentar portfolio off-market y condiciones.',     'follow_up', 'pending', NOW() + INTERVAL '2 days',  l07, p15,  false, NULL,   NOW() - INTERVAL '1 day',  NULL),
(v_org, 'Tour privado Andersen — zona Andratx',              'Organizar tour exclusivo para Henrik Andersen: p04, p06, p09. Conductor privado + almuerzo Oliu.',          'follow_up', 'pending', NOW() + INTERVAL '3 days',  l16, p06,  true,  a_lead, NOW() - INTERVAL '2 days', NULL),
(v_org, 'Llamar a Fischer para seguimiento',                 'Follow-up telefónico con Thomas Fischer sobre las propiedades enviadas. Confirmar si quiere agendar visita.','follow_up', 'pending', NOW() + INTERVAL '4 days',  l10, NULL, true,  a_lead, NOW() - INTERVAL '3 days', NULL),
(v_org, 'Verificación compliance Volkov',                    'Ejecutar proceso KYC/AML para Sergei Volkov antes de presentar propiedades. Contactar departamento legal.',  'follow_up', 'pending', NOW() + INTERVAL '5 days',  l09, NULL, false, NULL,   NOW() - INTERVAL '1 day',  NULL),

-- Prospection tasks
(v_org, 'Escaneo semanal propiedades off-market',            'Ejecutar búsqueda semanal en portales y contactos para detectar nuevas oportunidades en SW Mallorca.',       'prospection', 'pending', NOW() + INTERVAL '4 days', NULL, NULL, true,  a_pros, NOW() - INTERVAL '1 day',  NULL),
(v_org, 'Contactar propietario parcela Sa Mola',             'Negociar precio de p14 con Joan Alemany. Objetivo: cerrar bajo 1M EUR para cliente Eriksen.',               'prospection', 'pending', NOW() + INTERVAL '2 days', l12, p14,  false, NULL,   NOW() - INTERVAL '2 days', NULL),
(v_org, 'Investigar finca Es Capdellà — herencia',           'Contactar Familia Bestard para conocer condiciones de venta de p12. Verificar estado legal herencia.',      'prospection', 'pending', NOW() + INTERVAL '3 days', NULL, p12,  true,  a_pros, NOW() - INTERVAL '3 days', NULL),
(v_org, 'Prospección nuevas captaciones Camp de Mar',        'Identificar propiedades potenciales en Camp de Mar no listadas. Recorrer zona y hablar con vecinos.',        'prospection', 'pending', NOW() + INTERVAL '7 days', NULL, NULL, false, NULL,   NOW() - INTERVAL '1 day',  NULL),

-- Dossier tasks
(v_org, 'Generar dossier premium villa Cala Llamp',          'Crear PDF profesional para p15: fotografía drone, planos, análisis mercado comparativo, proyección valor.',  'dossier', 'pending', NOW() + INTERVAL '5 days', NULL, p15, true,  a_pros, NOW() - INTERVAL '4 days', NULL),
(v_org, 'Actualizar ficha p07 Bendinat con nuevas fotos',    'El propietario de p07 ha renovado la piscina. Coordinar sesión fotográfica profesional y actualizar dossier.','dossier', 'pending', NOW() + INTERVAL '6 days', NULL, p07, false, NULL,   NOW() - INTERVAL '2 days', NULL),
(v_org, 'Preparar informe ROI para Friedrich Meier',         'Crear análisis de rentabilidad de portfolio (p03, p05, p10) para UBS: yield, crecimiento capital, gastos.',  'dossier', 'pending', NOW() + INTERVAL '4 days', l14, NULL, true,  a_lead, NOW() - INTERVAL '5 days', NULL),

-- Admin tasks
(v_org, 'Renovar licencia CRM inmobiliario',                 'Renovar suscripción anual de la plataforma CRM. Verificar factura y actualizar datos fiscales.',             'admin', 'pending', NOW() + INTERVAL '10 days', NULL, NULL, false, NULL,   NOW() - INTERVAL '5 days', NULL),
(v_org, 'Actualizar web con nuevas propiedades',             'Subir fichas de p08, p11 y p14 al sitio web de Anclora. Incluir traducciones EN/DE.',                       'admin', 'pending', NOW() + INTERVAL '3 days',  NULL, NULL, false, NULL,   NOW() - INTERVAL '2 days', NULL),
(v_org, 'Preparar agenda semanal de visitas',                'Consolidar todas las visitas confirmadas de la semana y enviar itinerario al conductor.',                    'admin', 'pending', NOW() + INTERVAL '1 day',   NULL, NULL, false, NULL,   NOW(),                      NULL),

-- Completed tasks
(v_org, 'Primera llamada de cualificación — Lindström',      'Llamada inicial para entender necesidades de Astrid Lindström. Resultado: perfil UHNW confirmado.',          'follow_up',   'done', NOW() - INTERVAL '3 days', l03, NULL, true,  a_lead, NOW() - INTERVAL '5 days', NOW() - INTERVAL '3 days'),
(v_org, 'Enviar brochure general a Tanaka',                  'Enviar presentación general de Anclora + ficha p15 traducida al inglés para Yuki Tanaka.',                  'follow_up',   'done', NOW() - INTERVAL '5 days', l17, p15,  true,  a_lead, NOW() - INTERVAL '7 days', NOW() - INTERVAL '5 days'),
(v_org, 'Visita p13 con comprador alemán — Costa de la Calma','Acompañar al comprador alemán a visitar p13. Resultado: oferta aceptada, propiedad vendida.',              'follow_up',   'done', NOW() - INTERVAL '30 days',NULL, p13,  false, NULL,   NOW() - INTERVAL '35 days',NOW() - INTERVAL '30 days'),
(v_org, 'Generar resumen semanal Feb W1',                    'Resumen ejecutivo automático de la primera semana de febrero 2026.',                                        'admin',       'done', NOW() - INTERVAL '7 days', NULL, NULL, true,  a_recap,NOW() - INTERVAL '8 days', NOW() - INTERVAL '7 days'),
(v_org, 'Ejecutar prospección semanal Feb W1',               'Escaneo automático de nuevas propiedades en el mercado del suroeste de Mallorca.',                          'prospection', 'done', NOW() - INTERVAL '7 days', NULL, NULL, true,  a_pros, NOW() - INTERVAL '8 days', NOW() - INTERVAL '7 days'),
(v_org, 'Enviar opciones iniciales a Bauer',                 'Enviar ficha de p11 a Hans-Peter Bauer como única opción dentro de su presupuesto.',                        'follow_up',   'done', NOW() - INTERVAL '10 days',l08, p11,  true,  a_lead, NOW() - INTERVAL '12 days',NOW() - INTERVAL '10 days'),
(v_org, 'Verificar catastro parcela Sa Mola',                'Confirmar referencia catastral y verificar que la licencia de construcción de p14 sigue vigente.',           'prospection', 'done', NOW() - INTERVAL '8 days', NULL, p14,  false, NULL,   NOW() - INTERVAL '10 days',NOW() - INTERVAL '8 days')
ON CONFLICT DO NOTHING;

END $$;
