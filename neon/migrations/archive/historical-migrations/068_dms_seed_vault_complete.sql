-- 068_dms_seed_vault_complete.sql
-- Merges every remaining template placeholder key into the 3 test folder vaults.
-- Uses jsonb || so existing values are preserved (user-provided values win).
-- Run after 066 and 067.

DO $$
DECLARE
  f_cv UUID := 'd0000000-0000-0000-0000-000000000001'; -- compraventa
  f_at UUID := 'd0000000-0000-0000-0000-000000000002'; -- alquiler_temporada
  f_tu UUID := 'd0000000-0000-0000-0000-000000000003'; -- alquiler_turistico

BEGIN

-- ── COMPRAVENTA ──────────────────────────────────────────────────────────────
UPDATE public.real_estate_deal_folders
SET
  field_vault = field_vault || '{
    "deal.price_total":                      "520.000 €",
    "deal.deposit_proposed":                 "26.000 €",
    "deal.minimum_price":                    "490.000 €",
    "deal.post_exclusivity_protection_months": "3",
    "deal.exclusivity_renewal":              "No",
    "deal.mandate_duration_months":          "6",
    "deal.mandate_auto_renewal":             "No",
    "deal.direct_sale_protection":           "Sí",
    "property.registry_record":              "Tomo 3412, Libro 278, Folio 45, Finca 12345",
    "property.registry_office":              "Registro de la Propiedad nº 1 de Palma",
    "property.ite_certificate":              "ITE no requerida (edificio < 20 años de antigüedad)",
    "property.nota_simple_date":             "10/06/2026",
    "property.charges":                      "Ninguna carga pendiente",
    "property.mortgage_pending":             "0 €",
    "property.community_debt_certificate":   "Certificado de deuda cero expedido el 10/06/2026",
    "buyer.company_tax_id":                  "N/A",
    "buyer.company_name":                    "N/A",
    "buyer.company_cif":                     "N/A",
    "sof.inheritance_date":                  "N/A",
    "sof.inheritance_notary":                "N/A",
    "sof.mortgage_amount":                   "260.000 €",
    "sof.mortgage_bank":                     "CaixaBank",
    "sof.pep_details":                       "No aplica — el cliente no es persona expuesta políticamente"
  }'::jsonb,
  updated_at = now()
WHERE id = f_cv;


-- ── ALQUILER TEMPORADA ───────────────────────────────────────────────────────
UPDATE public.real_estate_deal_folders
SET
  field_vault = field_vault || '{
    "deal.price_total":                      "13.200 €",
    "deal.deposit_proposed":                 "4.400 €",
    "deal.minimum_price":                    "2.000 €/mes",
    "tenancy.duration_years":                "0,5 años (6 meses)",
    "tenancy.deposit_official_ref":          "No aplica — arrendamiento de temporada",
    "property.registry_record":              "Registro de la Propiedad de Andratx, Finca 4821",
    "property.registry_office":              "Registro de la Propiedad de Andratx",
    "property.ite_certificate":              "ITE favorable emitida el 15/03/2023",
    "property.nota_simple_date":             "05/06/2026",
    "property.charges":                      "Ninguna carga pendiente",
    "property.mortgage_pending":             "0 €",
    "property.community_debt_certificate":   "Certificado de deuda cero expedido el 05/06/2026",
    "property.title_origin":                 "Compraventa escritura pública de 22/07/2008",
    "property.registered_area":              "195 m²",
    "property.rooms":                        "4",
    "sof.inheritance_date":                  "N/A",
    "sof.inheritance_notary":                "N/A",
    "sof.mortgage_amount":                   "N/A",
    "sof.mortgage_bank":                     "N/A",
    "sof.pep_details":                       "No aplica",
    "tenant.company_cif":                    "N/A",
    "tenant.company_name":                   "N/A",
    "tenant.is_company":                     "No"
  }'::jsonb,
  updated_at = now()
WHERE id = f_at;


-- ── ALQUILER TURÍSTICO ───────────────────────────────────────────────────────
UPDATE public.real_estate_deal_folders
SET
  field_vault = field_vault || '{
    "deal.price_total":                      "4.900 €",
    "deal.deposit_proposed":                 "600 €",
    "tenancy.rent_amount":                   "4.900 € total",
    "tenancy.start_date":                    "01/07/2026",
    "tenancy.end_date":                      "15/07/2026",
    "tenancy.duration_days":                 "14",
    "tenancy.deposit_amount":                "600 €",
    "tenancy.deposit_months":                "—",
    "tenancy.deposit_official_ref":          "No aplica — cesión uso turístico",
    "tenancy.deposit_received_date":         "01/07/2026",
    "tenancy.deposit_registered":            "No aplica",
    "tenancy.payment_method":                "Tarjeta o transferencia",
    "tenancy.payment_day":                   "Al confirmar reserva",
    "tenancy.duration_years":                "Estancia puntual (14 noches)",
    "tenancy.temporality_cause":             "Turismo y descanso vacacional",
    "tenancy.cause_documents":               "Pasaporte y confirmación de reserva",
    "tenancy.contract_reference":            "TURIST-2026-001",
    "tenancy.contract_date":                 "01/07/2026",
    "tenancy.ibi_party":                     "Propietario",
    "tenancy.community_charges_party":       "Propietario",
    "tenancy.additional_guarantee":          "Sin garantía adicional",
    "tenancy.rent_period":                   "Pago único al confirmar reserva",
    "tenancy.rent_update_index":             "No aplica",
    "property.registry_record":              "Registro de la Propiedad de Calvià, Finca 7243",
    "property.registry_office":              "Registro de la Propiedad de Calvià",
    "property.ite_certificate":              "ITE favorable emitida el 10/01/2024",
    "property.nota_simple_date":             "01/06/2026",
    "property.charges":                      "Ninguna carga pendiente",
    "property.mortgage_pending":             "0 €",
    "property.community_debt_certificate":   "Certificado de deuda cero expedido el 01/06/2026",
    "property.title_origin":                 "Compraventa escritura pública de 18/04/2018",
    "property.registered_area":              "85 m²",
    "property.rooms":                        "2",
    "property.description":                  "Apartamento de 2 habitaciones con terraza y vistas al mar, 50 m de la playa",
    "sof.inheritance_date":                  "N/A",
    "sof.inheritance_notary":                "N/A",
    "sof.mortgage_amount":                   "N/A",
    "sof.mortgage_bank":                     "N/A",
    "sof.pep_details":                       "No aplica"
  }'::jsonb,
  updated_at = now()
WHERE id = f_tu;

END $$;
