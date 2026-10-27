-- 069_dms_seed_vault_final.sql
-- Final vault gap-fill for all 3 test folders.
-- Analysis against every template placeholder vs. vault + party-resolved keys:
--
-- COMPRAVENTA  — adds: keys.*, supply.*, sof.property_sale_date/reference
-- ALQUILER TEMPORADA — adds: property.capacity, deal.origin_contract_*, buyer.*
--   (tenant fallback for generic templates), seller.* (landlord fallback),
--   inventory.* (inventario_estado_inmueble), deal.origin_contract_*
-- ALQUILER TURÍSTICO — adds: deal.origin_contract_*, buyer.* (guest fallback),
--   seller.* (landlord fallback), tenant.* (guest fallback for recibo_fianza &
--   inventario), tenancy.deposit_payment_method
--
-- Run after 066, 067, 068.

DO $$
DECLARE
  f_cv UUID := 'd0000000-0000-0000-0000-000000000001'; -- compraventa
  f_at UUID := 'd0000000-0000-0000-0000-000000000002'; -- alquiler_temporada
  f_tu UUID := 'd0000000-0000-0000-0000-000000000003'; -- alquiler_turistico

BEGIN

-- ── COMPRAVENTA ──────────────────────────────────────────────────────────────
-- Missing: keys.*, supply.* (for acta_entrega_llaves)
--          sof.property_sale_date/reference (for declaracion_origen_fondos)
UPDATE public.real_estate_deal_folders
SET
  field_vault = field_vault || '{
    "keys.main_door_qty":    "2",
    "keys.main_door_notes":  "Llave de seguridad y llave de reserva",
    "keys.mailbox_qty":      "1",
    "keys.mailbox_notes":    "Buzón 3ºA",
    "keys.garage_qty":       "0",
    "keys.garage_notes":     "N/A",
    "keys.remote_qty":       "0",
    "keys.remote_notes":     "N/A",
    "keys.card_qty":         "0",
    "keys.card_notes":       "N/A",
    "keys.other_qty":        "1",
    "keys.other_notes":      "Llave trastero semisótano",
    "supply.electricity_company":  "Endesa",
    "supply.electricity_contract": "ES0031405566953001DF",
    "supply.electricity_reading":  "24.012 kWh",
    "supply.water_company":        "EMAYA",
    "supply.water_contract":       "AGU-2024-001234",
    "supply.water_reading":        "2.108 m³",
    "supply.gas_company":          "Sin suministro de gas",
    "supply.gas_contract":         "N/A",
    "supply.gas_reading":          "N/A",
    "sof.property_sale_date":      "N/A",
    "sof.property_sale_reference": "N/A"
  }'::jsonb,
  updated_at = now()
WHERE id = f_cv;


-- ── ALQUILER TEMPORADA ───────────────────────────────────────────────────────
-- Missing:
--   property.capacity             → contrato_temporada
--   deal.origin_contract_*        → acta_entrega_llaves
--   buyer.* (tenant fallback)     → acta / informacion_privacidad / kyc
--   seller.* (landlord fallback)  → acta_entrega_llaves
--   inventory.*                   → inventario_estado_inmueble
UPDATE public.real_estate_deal_folders
SET
  field_vault = field_vault || '{
    "property.capacity":          "6",
    "deal.origin_contract_type":  "Contrato de arrendamiento de temporada",
    "deal.origin_contract_date":  "20/06/2026",
    "buyer.full_name":            "Marco Antonio Bertolucci y Chiara Valentina Bertolucci",
    "buyer.id_document":          "YA8901234 / YB5678901",
    "buyer.email":                "m.bertolucci@gmail.com",
    "buyer.address":              "Via Montenapoleone 12, 20121 Milán, Italia",
    "buyer.phone":                "+39 02 7600 1234",
    "buyer.nationality":          "Italiana",
    "buyer.id_type":              "Pasaporte",
    "buyer.id_expiry":            "N/A",
    "buyer.tax_id":               "YA8901234 (Marco) / YB5678901 (Chiara)",
    "buyer.tax_country":          "Italia",
    "buyer.birth_date":           "03/04/1985 (Marco) / 17/11/1987 (Chiara)",
    "buyer.is_company":           "No",
    "buyer.is_pep":               "No",
    "buyer.cash_amount":          "N/A",
    "buyer.estimated_wealth":     "N/A",
    "buyer.income_range":         "N/A",
    "buyer.professional_activity":"Consultor de empresas (Marco) / Diseñadora de moda (Chiara)",
    "buyer.funds_origin":         "N/A",
    "buyer.funds_documents":      "N/A",
    "buyer.mortgage_bank":        "N/A",
    "buyer.company_name":         "N/A",
    "buyer.company_tax_id":       "N/A",
    "buyer.company_cif":          "N/A",
    "seller.full_name":           "Margalida Puig Roca",
    "seller.id_document":         "41234567M",
    "seller.email":               "m.puig.roca@hotmail.com",
    "inventory.salon_estado":     "Bueno",
    "inventory.salon_obs":        "Sofá modular 4 plazas, TV 65'', mesa comedor 8 pax, chimenea",
    "inventory.cocina_estado":    "Excelente",
    "inventory.cocina_obs":       "Cocina americana equipada: nevera americana, lavavajillas, horno, microondas, cafetera",
    "inventory.dorm1_estado":     "Bueno",
    "inventory.dorm1_obs":        "Cama doble 180x200, armario empotrado 3 puertas, AC split inverter",
    "inventory.dorm2_estado":     "Bueno",
    "inventory.dorm2_obs":        "Cama doble 160x200, armario empotrado 2 puertas",
    "inventory.bano1_estado":     "Bueno",
    "inventory.bano1_obs":        "Bañera hidromasaje, inodoro suspendido, lavabo doble, toallero eléctrico",
    "inventory.terraza_estado":   "Excelente",
    "inventory.terraza_obs":      "Mesa exterior 8 pax, sillas, hamacas, barbacoa de gas, piscina privada 8x4 m",
    "inventory.entrada_estado":   "Bueno",
    "inventory.entrada_obs":      "Perchero, espejo, zapatero",
    "inventory.luz_lectura":      "18.432 kWh",
    "inventory.agua_lectura":     "1.245 m³",
    "inventory.gas_lectura":      "N/A (bombonas butano)",
    "inventory.internet_estado":  "Operativo — Movistar Fibra 300 Mbps",
    "inventory.llaves_principal": "2 juegos entregados",
    "inventory.llaves_buzon":     "1 llave entregada",
    "inventory.mandos_garaje":    "1 mando Came BX-708",
    "inventory.tarjetas_acceso":  "N/A",
    "inventory.mobiliario_detalle": "Según inventario fotográfico firmado en fecha de entrega",
    "inventory.observaciones_generales": "Villa en excelente estado. Piscina revisada y en servicio. Jardín a cargo del propietario."
  }'::jsonb,
  updated_at = now()
WHERE id = f_at;


-- ── ALQUILER TURÍSTICO ───────────────────────────────────────────────────────
-- Missing:
--   deal.origin_contract_*            → acta_entrega_llaves
--   buyer.* (guest fallback)          → acta / informacion_privacidad / kyc
--   seller.* (landlord fallback)      → acta_entrega_llaves
--   tenant.* (guest fallback)         → recibo_fianza / inventario
--   tenancy.deposit_payment_method    → recibo_fianza
UPDATE public.real_estate_deal_folders
SET
  field_vault = field_vault || '{
    "deal.origin_contract_type":    "Contrato de cesión de uso turístico",
    "deal.origin_contract_date":    "01/07/2026",
    "buyer.full_name":              "François Jean-Pierre Dubois",
    "buyer.id_document":            "07AB12345",
    "buyer.email":                  "f.dubois@orange.fr",
    "buyer.address":                "12 Rue de la Paix, 75002 París, Francia",
    "buyer.phone":                  "+33 6 12 34 56 78",
    "buyer.nationality":            "Francesa",
    "buyer.id_type":                "Pasaporte",
    "buyer.id_expiry":              "N/A",
    "buyer.tax_id":                 "07AB12345",
    "buyer.tax_country":            "Francia",
    "buyer.birth_date":             "29/01/1980",
    "buyer.is_company":             "No",
    "buyer.is_pep":                 "No",
    "buyer.cash_amount":            "N/A",
    "buyer.estimated_wealth":       "N/A",
    "buyer.income_range":           "N/A",
    "buyer.professional_activity":  "N/A",
    "buyer.funds_origin":           "N/A",
    "buyer.funds_documents":        "N/A",
    "buyer.mortgage_bank":          "N/A",
    "buyer.company_name":           "N/A",
    "buyer.company_tax_id":         "N/A",
    "buyer.company_cif":            "N/A",
    "seller.full_name":             "Thomas Heinrich Weber e Ingrid Maria Weber",
    "seller.id_document":           "C01234567 / C09876543",
    "seller.email":                 "t.weber@gmx.de",
    "tenant.full_name":             "François Jean-Pierre Dubois",
    "tenant.id_document":           "07AB12345",
    "tenant.permanent_address":     "12 Rue de la Paix, 75002 París, Francia",
    "tenancy.deposit_payment_method": "Tarjeta de crédito o transferencia bancaria"
  }'::jsonb,
  updated_at = now()
WHERE id = f_tu;

END $$;
