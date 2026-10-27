-- 066_dms_test_seed.sql
-- Test seed for DMS: 3 fully populated folders (compraventa, alquiler_temporada,
-- alquiler_turistico) with correct party roles, and field_vault keys that match
-- the exact placeholder names used in template files.
-- Safe to re-run (ON CONFLICT DO NOTHING / DO UPDATE).

DO $$
DECLARE
  v_org  UUID := '9d6cb56d-3f21-4f7b-80ea-797a7c2c62cf';

  -- Folder IDs
  f_cv   UUID := 'd0000000-0000-0000-0000-000000000001'; -- compraventa
  f_at   UUID := 'd0000000-0000-0000-0000-000000000002'; -- alquiler_temporada
  f_tu   UUID := 'd0000000-0000-0000-0000-000000000003'; -- alquiler_turistico

  -- Party IDs — compraventa
  p_cv_buyer   UUID := 'd1000000-0000-0000-0000-000000000001';
  p_cv_seller  UUID := 'd1000000-0000-0000-0000-000000000002';
  p_cv_agent   UUID := 'd1000000-0000-0000-0000-000000000003';

  -- Party IDs — alquiler_temporada
  p_at_landlord UUID := 'd2000000-0000-0000-0000-000000000001';
  p_at_tenant   UUID := 'd2000000-0000-0000-0000-000000000002';
  p_at_agent    UUID := 'd2000000-0000-0000-0000-000000000003';

  -- Party IDs — alquiler_turistico
  p_tu_landlord UUID := 'd3000000-0000-0000-0000-000000000001';
  p_tu_guest    UUID := 'd3000000-0000-0000-0000-000000000002';
  p_tu_agent    UUID := 'd3000000-0000-0000-0000-000000000003';

BEGIN

-- ═══════════════════════════════════════════════════════════════════════════
-- 1. COMPRAVENTA — Calle Marineta 7, 3ºA, Palma (Cala Mayor)
--    Comprador: James & Emily Worthington (británicos)
--    Vendedor:  Bartolomé Coll Ferrer
--    Precio: 520.000 € | Arras: 26.000 €
-- ═══════════════════════════════════════════════════════════════════════════

INSERT INTO public.real_estate_deal_folders
  (id, org_id, operation_type, folder_status, language, field_vault)
VALUES (
  f_cv, v_org, 'compraventa', 'active', 'es',
  '{
    "deal.folder_reference":           "EXP-CV-2026-001",
    "deal.operation_type":             "Compraventa",
    "deal.price":                      "520.000 €",
    "deal.asking_price":               "540.000 €",
    "deal.offer_price":                "510.000 €",
    "deal.deposit_amount":             "26.000 €",
    "deal.signing_deadline":           "15/09/2026",
    "deal.visit_date":                 "25/05/2026",
    "deal.visit_notes":                "Visita con agente y ambas partes",
    "deal.signing_date":               "15/09/2026",
    "deal.signing_place":              "Notaría Garau & Asociados, Calle Unión 3, Palma",
    "deal.notary_name":                "Ilmo. Sr. Joan Garau Ferrer",
    "deal.notary_address":             "Calle Unión 3, 07001 Palma de Mallorca",
    "deal.arras_date":                 "30/06/2026",
    "deal.deposit_deadline":           "15 días naturales",
    "deal.deposit_payment_method":     "Transferencia bancaria",
    "deal.price_remaining":            "494.000 €",
    "deal.payment_method":             "Transferencia bancaria SWIFT",
    "deal.reservation_days":           "14",
    "deal.financing_condition":        "Sujeto a financiación hipotecaria",
    "deal.financing_type":             "Hipoteca bancaria",
    "deal.mortgage_amount":            "260.000 €",
    "deal.possession_agreement":       "En el momento de la firma ante notario",
    "deal.doc_review_condition":       "Sujeto a revisión documental satisfactoria",
    "deal.commission_pct":             "3",
    "deal.commission_payer":           "Vendedor",
    "deal.exclusivity":                "Sí",
    "deal.exclusivity_months":         "6",
    "deal.exclusivity_notice_days":    "30",
    "deal.offer_validity_days":        "15",
    "deal.origin_contract_type":       "Contrato de arras penitenciales",
    "deal.origin_contract_date":       "30/06/2026",
    "buyer.id_type":                   "Pasaporte",
    "buyer.id_expiry":                 "01/03/2030",
    "buyer.tax_id":                    "X1234567A (James) / X7654321B (Emily)",
    "buyer.tax_country":               "Reino Unido",
    "buyer.birth_date":                "15/03/1975 (James) / 22/07/1978 (Emily)",
    "buyer.professional_activity":     "Director financiero (James) / Médica (Emily)",
    "buyer.cash_amount":               "270.000 €",
    "buyer.estimated_wealth":          "1.200.000 €",
    "buyer.income_range":              "150.000 - 250.000 €/año",
    "buyer.funds_documents":           "Extractos bancarios Barclays y carta de capacidad hipotecaria CaixaBank",
    "buyer.is_company":                "No",
    "buyer.is_pep":                    "No",
    "buyer.mortgage_bank":             "CaixaBank",
    "buyer.funds_origin":              "Ahorros propios y préstamo hipotecario",
    "seller.id_type":                  "DNI",
    "seller.tax_id":                   "43112345T",
    "seller.birth_date":               "08/11/1962",
    "property.address":                "Calle Marineta 7, 3ºA",
    "property.municipality":           "Palma de Mallorca",
    "property.postal_code":            "07014",
    "property.province":               "Illes Balears",
    "property.cadastral_reference":    "0456789PM5205A0001",
    "property.registry_reference":     "Tomo 3412, Libro 278, Folio 45, Finca 12345",
    "property.energy_certificate":     "Certificado energético vigente hasta 31/12/2031, nº CE-2024-0567",
    "property.energy_rating":          "C",
    "property.habitation_certificate": "Cédula de habitabilidad nº CH-2024-0567, válida hasta 31/12/2031",
    "property.description":            "Piso de 3 habitaciones con vistas al mar en Cala Mayor, completamente reformado en 2023",
    "property.rooms":                  "3",
    "property.registered_area":        "112 m²",
    "property.cadastral_area":         "115 m²",
    "property.registry_office":        "Registro de la Propiedad nº 1 de Palma",
    "property.title_origin":           "Compraventa escritura pública de 12/05/2010",
    "property.occupation_status":      "Desocupado",
    "property.delivery_condition":     "Libre de ocupantes y cargas",
    "property.ibi_status":             "Al corriente de pago",
    "property.charges":                "Ninguna carga pendiente",
    "property.mortgage_pending":       "0 €",
    "property.community_debt_certificate": "Certificado de deuda cero expedido el 10/06/2026",
    "property.nota_simple_date":       "10/06/2026",
    "property.habitation_cert_expiry": "31/12/2031",
    "property.nrua_number":            "NRUA-PMA-2024-0045",
    "organization.legal_name":         "Anclora Private Estates S.L.",
    "organization.trade_name":         "Anclora",
    "organization.tax_id":             "B57234901",
    "organization.roaiib_number":      "AICAT-2890",
    "organization.address":            "Paseo Marítimo 27, 07014 Palma de Mallorca",
    "organization.phone":              "+34 971 000 111",
    "organization.email":              "info@anclora.es",
    "agent.license":                   "API-IB-2019-0234",
    "nda.duration_years":              "2",
    "nda.penalty_amount":              "15.000 €",
    "delivery.datetime":               "15/09/2026 a las 11:00 horas",
    "delivery.observations":           "Entrega de llaves en notaría tras firma de escrituras. Inmueble libre de personas y enseres.",
    "document.custom_body":            "Contrato de arras penitenciales conforme al artículo 1454 del Código Civil.",
    "sof.bank_name":                   "Barclays Bank UK PLC",
    "sof.bank_account_last4":          "4421",
    "sof.business_activity":           "Director financiero empresa FTSE 100",
    "sof.other_description":           "Ahorros acumulados durante 15 años de actividad profesional"
  }'::jsonb
)
ON CONFLICT (id) DO UPDATE SET field_vault = EXCLUDED.field_vault, updated_at = now();

-- Parties — compraventa (buyer = primary)
INSERT INTO public.deal_folder_parties
  (id, folder_id, org_id, party_role, full_name, is_primary, signing_order,
   email, phone, address, nationality, dni_nie_passport)
VALUES
  (p_cv_buyer,  f_cv, v_org, 'buyer',  'James Edward Worthington y Emily Claire Worthington',
   true,  1, 'james.worthington@gmail.com', '+44 7700 900 123',
   '14 Cheltenham Road, London SW11 4PL, United Kingdom', 'Británica', 'PA123456 / PB789012'),
  (p_cv_seller, f_cv, v_org, 'seller', 'Bartolomé Coll Ferrer',
   false, 2, 'bartolome.coll@gmail.com', '+34 971 234 567',
   'Calle Marineta 7, 3ºA, 07014 Palma', 'Española', '43112345T'),
  (p_cv_agent,  f_cv, v_org, 'agent',  'Carlos Mendoza Ruiz',
   false, 3, 'c.mendoza@anclora.es', '+34 971 456 789',
   'Paseo Marítimo 27, 07014 Palma', 'Española', '78900123K')
ON CONFLICT (id) DO UPDATE SET
  party_role = EXCLUDED.party_role,
  full_name  = EXCLUDED.full_name,
  is_primary = EXCLUDED.is_primary,
  signing_order = EXCLUDED.signing_order,
  email = EXCLUDED.email,
  phone = EXCLUDED.phone,
  address = EXCLUDED.address,
  nationality = EXCLUDED.nationality,
  dni_nie_passport = EXCLUDED.dni_nie_passport;

UPDATE public.real_estate_deal_folders
SET primary_party_id = p_cv_buyer WHERE id = f_cv;


-- ═══════════════════════════════════════════════════════════════════════════
-- 2. ALQUILER TEMPORADA — Camí de s'Ermita 4, Port d'Andratx
--    Arrendador: Margalida Puig Roca
--    Arrendatario: Marco & Chiara Bertolucci (italianos)
--    Renta: 2.200 €/mes | 6 meses | 01/07/2026 – 31/12/2026
-- ═══════════════════════════════════════════════════════════════════════════

INSERT INTO public.real_estate_deal_folders
  (id, org_id, operation_type, folder_status, language, field_vault)
VALUES (
  f_at, v_org, 'alquiler_temporada', 'active', 'es',
  '{
    "deal.folder_reference":           "EXP-AT-2026-001",
    "deal.operation_type":             "Arrendamiento de temporada",
    "deal.price":                      "13.200 €",
    "deal.deposit_amount":             "4.400 €",
    "deal.signing_deadline":           "20/06/2026",
    "deal.signing_date":               "20/06/2026",
    "deal.signing_place":              "Oficinas Anclora, Paseo Marítimo 27, Palma",
    "tenancy.start_date":              "01/07/2026",
    "tenancy.end_date":                "31/12/2026",
    "tenancy.duration_months":         "6",
    "tenancy.duration_days":           "184",
    "tenancy.rent_amount":             "2.200 €",
    "tenancy.rent_period":             "Mensual",
    "tenancy.payment_day":             "1",
    "tenancy.payment_method":          "Transferencia bancaria SEPA",
    "tenancy.rent_update_index":       "IPC",
    "tenancy.deposit_amount":          "4.400 €",
    "tenancy.deposit_months":          "2",
    "tenancy.deposit_payment_method":  "Transferencia bancaria",
    "tenancy.deposit_received_date":   "20/06/2026",
    "tenancy.deposit_registered":      "No (temporada)",
    "tenancy.temporality_cause":       "Viaje de trabajo y turismo de larga estancia",
    "tenancy.cause_documents":         "Contrato de trabajo temporal en España / pasaportes",
    "tenancy.ibi_party":               "Arrendador",
    "tenancy.community_charges_party": "Arrendador",
    "tenancy.additional_guarantee":    "Sin garantía adicional",
    "tenancy.contract_reference":      "ARR-AT-2026-001",
    "tenancy.contract_date":           "20/06/2026",
    "landlord.id_type":                "DNI",
    "landlord.tax_id":                 "41234567M",
    "landlord.birth_date":             "14/06/1971",
    "tenant.id_type":                  "Pasaporte",
    "tenant.tax_id":                   "YA8901234 (Marco) / YB5678901 (Chiara)",
    "tenant.birth_date":               "03/04/1985 (Marco) / 17/11/1987 (Chiara)",
    "tenant.permanent_address":        "Via Montenapoleone 12, 20121 Milán, Italia",
    "property.address":                "Camí de s''Ermita 4",
    "property.municipality":           "Port d''Andratx",
    "property.postal_code":            "07157",
    "property.province":               "Illes Balears",
    "property.cadastral_reference":    "07003A012003490000AE",
    "property.registry_reference":     "Registro de la Propiedad de Andratx, Finca 4821",
    "property.energy_certificate":     "Certificado energético clase D, válido hasta 30/06/2029",
    "property.energy_rating":          "D",
    "property.habitation_certificate": "Cédula de habitabilidad vigente hasta 30/06/2029",
    "property.description":            "Villa de 4 habitaciones con piscina privada y vistas al puerto, jardín de 800 m²",
    "property.rooms":                  "4",
    "property.registered_area":        "195 m²",
    "property.occupation_status":      "Desocupado entre arrendamientos",
    "property.delivery_condition":     "Amueblada y equipada, lista para habitar",
    "property.ibi_status":             "Al corriente",
    "property.nrua_number":            "No aplica (temporada)",
    "organization.legal_name":         "Anclora Private Estates S.L.",
    "organization.trade_name":         "Anclora",
    "organization.tax_id":             "B57234901",
    "organization.roaiib_number":      "AICAT-2890",
    "organization.address":            "Paseo Marítimo 27, 07014 Palma de Mallorca",
    "organization.phone":              "+34 971 000 111",
    "organization.email":              "info@anclora.es",
    "agent.license":                   "API-IB-2019-0234",
    "nda.duration_years":              "2",
    "nda.penalty_amount":              "10.000 €",
    "delivery.datetime":               "01/07/2026 a las 16:00 horas",
    "delivery.observations":           "Entrega de llaves en el inmueble. Lectura de contadores de luz y agua.",
    "document.custom_body":            "Contrato de arrendamiento de temporada según artículo 3.2 de la LAU.",
    "supply.electricity_company":      "Endesa",
    "supply.electricity_contract":     "ES0031405566953001DF",
    "supply.electricity_reading":      "18.432 kWh",
    "supply.water_company":            "EMAYA",
    "supply.water_contract":           "AGU-2024-004512",
    "supply.water_reading":            "1.245 m³",
    "supply.gas_company":              "Sin suministro de gas (bombonas butano)",
    "supply.gas_contract":             "N/A",
    "supply.gas_reading":              "N/A",
    "keys.main_door_qty":              "2",
    "keys.main_door_notes":            "Llave Mul-T-Lock con apertura antipalanca",
    "keys.mailbox_qty":                "1",
    "keys.mailbox_notes":              "Buzón metálico nº 4",
    "keys.garage_qty":                 "1",
    "keys.garage_notes":               "Mando Came BX-708",
    "keys.remote_qty":                 "2",
    "keys.remote_notes":               "Mando portero automático Fermax",
    "keys.card_qty":                   "0",
    "keys.card_notes":                 "N/A",
    "keys.other_qty":                  "1",
    "keys.other_notes":                "Llave trastero planta baja"
  }'::jsonb
)
ON CONFLICT (id) DO UPDATE SET field_vault = EXCLUDED.field_vault, updated_at = now();

-- Parties — alquiler temporada (tenant = primary client; correct roles)
INSERT INTO public.deal_folder_parties
  (id, folder_id, org_id, party_role, full_name, is_primary, signing_order,
   email, phone, address, nationality, dni_nie_passport)
VALUES
  (p_at_landlord, f_at, v_org, 'landlord', 'Margalida Puig Roca',
   false, 2, 'm.puig.roca@hotmail.com', '+34 971 671 234',
   'Camí de s''Ermita 4, 07157 Port d''Andratx', 'Española', '41234567M'),
  (p_at_tenant,   f_at, v_org, 'tenant',   'Marco Antonio Bertolucci y Chiara Valentina Bertolucci',
   true,  1, 'm.bertolucci@gmail.com', '+39 02 7600 1234',
   'Via Montenapoleone 12, 20121 Milán, Italia', 'Italiana', 'YA8901234 / YB5678901'),
  (p_at_agent,    f_at, v_org, 'agent',    'Carlos Mendoza Ruiz',
   false, 3, 'c.mendoza@anclora.es', '+34 971 456 789',
   'Paseo Marítimo 27, 07014 Palma', 'Española', '78900123K')
ON CONFLICT (id) DO UPDATE SET
  party_role = EXCLUDED.party_role,
  full_name  = EXCLUDED.full_name,
  is_primary = EXCLUDED.is_primary,
  signing_order = EXCLUDED.signing_order,
  email = EXCLUDED.email,
  phone = EXCLUDED.phone,
  address = EXCLUDED.address,
  nationality = EXCLUDED.nationality,
  dni_nie_passport = EXCLUDED.dni_nie_passport;

UPDATE public.real_estate_deal_folders
SET primary_party_id = p_at_tenant WHERE id = f_at;


-- ═══════════════════════════════════════════════════════════════════════════
-- 3. ALQUILER TURÍSTICO — Avda. de la Playa 12, 2ºB, Palmanova
--    Propietarios: Thomas & Ingrid Weber (alemanes)
--    Huésped: François Dubois (francés)
--    14 noches julio 2026 | 4.900 € total | ETV activa
-- ═══════════════════════════════════════════════════════════════════════════

INSERT INTO public.real_estate_deal_folders
  (id, org_id, operation_type, folder_status, language, field_vault)
VALUES (
  f_tu, v_org, 'alquiler_turistico', 'active', 'es',
  '{
    "deal.folder_reference":           "EXP-TU-2026-001",
    "deal.operation_type":             "Alquiler turístico",
    "deal.price":                      "4.900 €",
    "deal.deposit_amount":             "600 €",
    "deal.signing_deadline":           "01/07/2026",
    "deal.signing_date":               "01/07/2026",
    "booking.checkin_date":            "01/07/2026",
    "booking.checkout_date":           "15/07/2026",
    "booking.checkin_time":            "16:00",
    "booking.checkout_time":           "11:00",
    "booking.nights":                  "14",
    "booking.adults":                  "4",
    "booking.guest_count":             "4",
    "booking.minors":                  "0",
    "booking.total_price":             "4.900 €",
    "booking.security_deposit":        "600 €",
    "booking.tourist_tax":             "1,10 €/persona/noche (61,60 € total)",
    "booking.prepayment":              "50 % al confirmar reserva",
    "booking.cancellation_policy":     "Sin devolución si se cancela con menos de 14 días de antelación",
    "booking.free_cancellation_date":  "17/06/2026",
    "booking.pets_allowed":            "No",
    "booking.smoking_allowed":         "No (prohibido en interior)",
    "landlord.id_type":                "Pasaporte",
    "landlord.tax_id":                 "X9876543C (NIE España)",
    "landlord.birth_date":             "22/09/1968 (Thomas) / 05/03/1972 (Ingrid)",
    "guest.id_type":                   "Pasaporte",
    "guest.birth_date":                "29/01/1980",
    "guest.tax_id":                    "07AB12345",
    "property.address":                "Avda. de la Playa 12, 2ºB",
    "property.municipality":           "Palmanova",
    "property.postal_code":            "07181",
    "property.province":               "Illes Balears",
    "property.cadastral_reference":    "07015A001003720000MK",
    "property.registry_reference":     "Registro de la Propiedad de Calvià, Finca 7243",
    "property.energy_certificate":     "Certificado energético clase C, válido hasta 30/06/2029",
    "property.energy_rating":          "C",
    "property.habitation_certificate": "Cédula de habitabilidad ETV nº ETV-2022-0789, vigente",
    "property.description":            "Apartamento de 2 habitaciones con terraza y vistas al mar, 50 m de la playa",
    "property.rooms":                  "2",
    "property.registered_area":        "85 m²",
    "property.capacity":               "4",
    "property.max_capacity":           "4",
    "property.etv_license":            "ETV-2022-0789",
    "property.nrua_number":            "NRUA-CAL-2022-0789",
    "property.habitation_cert_expiry": "30/06/2029",
    "property.occupation_status":      "Uso turístico activo",
    "property.delivery_condition":     "Amueblado y equipado según inventario adjunto",
    "property.ibi_status":             "Al corriente",
    "organization.legal_name":         "Anclora Private Estates S.L.",
    "organization.trade_name":         "Anclora",
    "organization.tax_id":             "B57234901",
    "organization.roaiib_number":      "AICAT-2890",
    "organization.address":            "Paseo Marítimo 27, 07014 Palma de Mallorca",
    "organization.phone":              "+34 971 000 111",
    "organization.email":              "info@anclora.es",
    "agent.license":                   "API-IB-2019-0234",
    "nda.duration_years":              "1",
    "nda.penalty_amount":              "4.900 €",
    "delivery.datetime":               "01/07/2026 a las 16:00 horas",
    "delivery.observations":           "Check-in con entrega de llaves mediante caja de seguridad código 4512.",
    "document.custom_body":            "Contrato de cesión de uso turístico según Ley 8/2012 de Turismo de las Illes Balears.",
    "keys.main_door_qty":              "2",
    "keys.main_door_notes":            "Llave Yale + caja de seguridad código 4512",
    "keys.mailbox_qty":                "1",
    "keys.mailbox_notes":              "Buzón 2B portal derecha",
    "keys.garage_qty":                 "0",
    "keys.garage_notes":               "N/A",
    "keys.remote_qty":                 "1",
    "keys.remote_notes":               "Mando piscina comunitaria",
    "keys.card_qty":                   "2",
    "keys.card_notes":                 "Tarjetas acceso piscina y zona spa",
    "keys.other_qty":                  "0",
    "keys.other_notes":                "N/A",
    "supply.electricity_company":      "Endesa",
    "supply.electricity_contract":     "ES0031000889274001KZ",
    "supply.electricity_reading":      "9.876 kWh",
    "supply.water_company":            "EMAYA",
    "supply.water_contract":           "AGU-2024-007891",
    "supply.water_reading":            "876 m³",
    "supply.gas_company":              "Sin suministro de gas",
    "supply.gas_contract":             "N/A",
    "supply.gas_reading":              "N/A",
    "inventory.salon_estado":          "Bueno",
    "inventory.salon_obs":             "Sofá Chester 3 plazas, TV Samsung 55'', mesa comedor 6 pax",
    "inventory.cocina_estado":         "Excelente",
    "inventory.cocina_obs":            "Cocina americana equipada: nevera, lavavajillas, microondas, cafetera Nespresso",
    "inventory.dorm1_estado":          "Bueno",
    "inventory.dorm1_obs":             "Cama doble 160x200, armario empotrado, AC split",
    "inventory.dorm2_estado":          "Bueno",
    "inventory.dorm2_obs":             "Dos camas individuales 90x200, armario",
    "inventory.bano1_estado":          "Excelente",
    "inventory.bano1_obs":             "Ducha italiana, inodoro suspendido, toallero eléctrico",
    "inventory.terraza_estado":        "Bueno",
    "inventory.terraza_obs":           "Mesa y 4 sillas exterior, parasol, hamacas",
    "inventory.entrada_estado":        "Bueno",
    "inventory.entrada_obs":           "Perchero, espejo, zapatero",
    "inventory.luz_lectura":           "9.876 kWh",
    "inventory.agua_lectura":          "876 m³",
    "inventory.gas_lectura":           "N/A",
    "inventory.internet_estado":       "Operativo — Movistar Fibra 600 Mbps (clave: palmanova2026)",
    "inventory.llaves_principal":      "2 juegos entregados",
    "inventory.llaves_buzon":          "1 llave entregada",
    "inventory.mandos_garaje":         "N/A",
    "inventory.tarjetas_acceso":       "2 tarjetas piscina entregadas",
    "inventory.mobiliario_detalle":    "Según inventario fotográfico firmado en fecha de entrega",
    "inventory.observaciones_generales": "Apartamento en perfecto estado. Se entregan instrucciones de electrodomésticos en 4 idiomas."
  }'::jsonb
)
ON CONFLICT (id) DO UPDATE SET field_vault = EXCLUDED.field_vault, updated_at = now();

-- Parties — alquiler turístico (guest = primary; correct roles)
INSERT INTO public.deal_folder_parties
  (id, folder_id, org_id, party_role, full_name, is_primary, signing_order,
   email, phone, address, nationality, dni_nie_passport)
VALUES
  (p_tu_landlord, f_tu, v_org, 'landlord', 'Thomas Heinrich Weber e Ingrid Maria Weber',
   false, 2, 't.weber@gmx.de', '+49 89 1234 5678',
   'Schillerstraße 45, 80336 Múnich, Alemania', 'Alemana', 'C01234567 / C09876543'),
  (p_tu_guest,    f_tu, v_org, 'guest',    'François Jean-Pierre Dubois',
   true,  1, 'f.dubois@orange.fr', '+33 6 12 34 56 78',
   '12 Rue de la Paix, 75002 París, Francia', 'Francesa', '07AB12345'),
  (p_tu_agent,    f_tu, v_org, 'agent',    'Carlos Mendoza Ruiz',
   false, 3, 'c.mendoza@anclora.es', '+34 971 456 789',
   'Paseo Marítimo 27, 07014 Palma', 'Española', '78900123K')
ON CONFLICT (id) DO UPDATE SET
  party_role = EXCLUDED.party_role,
  full_name  = EXCLUDED.full_name,
  is_primary = EXCLUDED.is_primary,
  signing_order = EXCLUDED.signing_order,
  email = EXCLUDED.email,
  phone = EXCLUDED.phone,
  address = EXCLUDED.address,
  nationality = EXCLUDED.nationality,
  dni_nie_passport = EXCLUDED.dni_nie_passport;

UPDATE public.real_estate_deal_folders
SET primary_party_id = p_tu_guest WHERE id = f_tu;

END $$;
