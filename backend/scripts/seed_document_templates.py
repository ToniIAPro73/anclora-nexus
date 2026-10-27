#!/usr/bin/env python3
"""
Seed the document template catalogue for all organizations.

Creates one draft template per canonical document type. All templates are
seeded in 'draft' status — a legal professional must review canonical texts
and publish each one before use.

Usage:
    python3 backend/scripts/seed_document_templates.py \
        --org-id <uuid> [--dry-run]

Environment:
    NEON_DATA_API_URL, NEON_JWT_PRIVATE_KEY, NEON_JWT_KEY_ID, NEXUS_DOCUMENT_ENCRYPTION_KEY
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from uuid import uuid4

TEMPLATE_CATALOGUE = [
    {
        "name": "Contrato de Arras Penitenciales",
        "template_document_type": "arras_penitenciales",
        "description": "Contrato de arras penitenciales conforme al artículo 1454 del Código Civil español.",
        "jurisdiction": "España",
        "language": "es",
        "fields": [
            {"field_key": "seller_name", "label": "Nombre del vendedor", "field_type": "text", "required": True},
            {"field_key": "seller_dni", "label": "DNI/NIE del vendedor", "field_type": "text", "required": True},
            {"field_key": "buyer_name", "label": "Nombre del comprador", "field_type": "text", "required": True},
            {"field_key": "buyer_dni", "label": "DNI/NIE del comprador", "field_type": "text", "required": True},
            {"field_key": "property_address", "label": "Dirección del inmueble", "field_type": "text", "required": True},
            {"field_key": "cadastral_reference", "label": "Referencia catastral", "field_type": "text", "required": False},
            {"field_key": "arras_amount", "label": "Importe de arras (EUR)", "field_type": "amount", "required": True},
            {"field_key": "sale_price", "label": "Precio de compraventa total (EUR)", "field_type": "amount", "required": True},
            {"field_key": "deadline_date", "label": "Fecha límite para escritura", "field_type": "date", "required": True},
            {"field_key": "notary_name", "label": "Notaría designada", "field_type": "text", "required": False},
        ],
    },
    {
        "name": "Contrato de Compraventa de Inmueble",
        "template_document_type": "contrato_compraventa",
        "description": "Contrato privado de compraventa de inmueble. Complementario a la escritura pública notarial.",
        "jurisdiction": "España",
        "language": "es",
        "fields": [
            {"field_key": "seller_name", "label": "Nombre del vendedor", "field_type": "text", "required": True},
            {"field_key": "seller_dni", "label": "DNI/NIE del vendedor", "field_type": "text", "required": True},
            {"field_key": "buyer_name", "label": "Nombre del comprador", "field_type": "text", "required": True},
            {"field_key": "buyer_dni", "label": "DNI/NIE del comprador", "field_type": "text", "required": True},
            {"field_key": "property_address", "label": "Dirección del inmueble", "field_type": "text", "required": True},
            {"field_key": "cadastral_reference", "label": "Referencia catastral", "field_type": "text", "required": True},
            {"field_key": "sale_price", "label": "Precio de compraventa (EUR)", "field_type": "amount", "required": True},
            {"field_key": "payment_method", "label": "Forma de pago", "field_type": "text", "required": True},
            {"field_key": "possession_date", "label": "Fecha de entrega de llaves", "field_type": "date", "required": True},
            {"field_key": "charges", "label": "Cargas y gravámenes", "field_type": "text", "required": True},
            {"field_key": "tax_assignment", "label": "Asignación de impuestos (ITP/AJD)", "field_type": "text", "required": True},
            {"field_key": "notary_name", "label": "Notaría designada", "field_type": "text", "required": True},
        ],
    },
    {
        "name": "Contrato de Alquiler de Temporada",
        "template_document_type": "contrato_temporada",
        "description": "Contrato de arrendamiento de temporada conforme a la LAU (Art. 3.2). No es vivienda habitual.",
        "jurisdiction": "España",
        "language": "es",
        "fields": [
            {"field_key": "landlord_name", "label": "Nombre del arrendador", "field_type": "text", "required": True},
            {"field_key": "landlord_dni", "label": "DNI/NIE del arrendador", "field_type": "text", "required": True},
            {"field_key": "tenant_name", "label": "Nombre del arrendatario", "field_type": "text", "required": True},
            {"field_key": "tenant_dni", "label": "DNI/NIE del arrendatario", "field_type": "text", "required": True},
            {"field_key": "property_address", "label": "Dirección del inmueble", "field_type": "text", "required": True},
            {"field_key": "monthly_rent", "label": "Renta mensual (EUR)", "field_type": "amount", "required": True},
            {"field_key": "deposit_amount", "label": "Fianza (EUR)", "field_type": "amount", "required": True},
            {"field_key": "start_date", "label": "Fecha de inicio", "field_type": "date", "required": True},
            {"field_key": "end_date", "label": "Fecha de fin", "field_type": "date", "required": True},
            {"field_key": "utilities_included", "label": "Suministros incluidos", "field_type": "boolean", "required": True, "default_value": "false"},
            {"field_key": "rescission_notice_days", "label": "Preaviso rescisión (días)", "field_type": "number", "required": True, "default_value": "15"},
        ],
    },
    {
        "name": "Contrato de Alquiler Turístico / ETV",
        "template_document_type": "contrato_alquiler_turistico",
        "description": "Contrato de estancia turística conforme a normativa DRIAT/ETV de las Illes Balears.",
        "jurisdiction": "España",
        "language": "es",
        "fields": [
            {"field_key": "owner_name", "label": "Nombre del propietario", "field_type": "text", "required": True},
            {"field_key": "owner_dni", "label": "DNI/NIE del propietario", "field_type": "text", "required": True},
            {"field_key": "guest_name", "label": "Nombre del huésped", "field_type": "text", "required": True},
            {"field_key": "property_address", "label": "Dirección de la vivienda", "field_type": "text", "required": True},
            {"field_key": "license_number", "label": "Número de licencia ETV/DRIAT", "field_type": "text", "required": True},
            {"field_key": "max_guests", "label": "Capacidad máxima (personas)", "field_type": "number", "required": True},
            {"field_key": "nightly_price", "label": "Precio por noche (EUR)", "field_type": "amount", "required": True},
            {"field_key": "check_in_date", "label": "Fecha de entrada", "field_type": "date", "required": True},
            {"field_key": "check_out_date", "label": "Fecha de salida", "field_type": "date", "required": True},
            {"field_key": "tourist_tax", "label": "Impost turístic (EUR/noche)", "field_type": "amount", "required": True},
            {"field_key": "deposit_amount", "label": "Fianza (EUR)", "field_type": "amount", "required": True},
            {"field_key": "cancellation_policy", "label": "Política de cancelación", "field_type": "text", "required": True},
            {"field_key": "cleaning_fee", "label": "Importe de limpieza (EUR)", "field_type": "amount", "required": False},
        ],
    },
    {
        "name": "Mandato de Exclusiva",
        "template_document_type": "mandato_exclusiva",
        "description": "Mandato de encargo de venta en exclusiva a la agencia inmobiliaria.",
        "jurisdiction": "España",
        "language": "es",
        "fields": [
            {"field_key": "owner_name", "label": "Nombre del propietario", "field_type": "text", "required": True},
            {"field_key": "owner_dni", "label": "DNI/NIE del propietario", "field_type": "text", "required": True},
            {"field_key": "property_address", "label": "Dirección del inmueble", "field_type": "text", "required": True},
            {"field_key": "listing_price", "label": "Precio de salida (EUR)", "field_type": "amount", "required": True},
            {"field_key": "agency_fee_percent", "label": "Honorarios de agencia (%)", "field_type": "number", "required": True},
            {"field_key": "exclusivity_end_date", "label": "Fecha de fin de exclusiva", "field_type": "date", "required": True},
            {"field_key": "agency_name", "label": "Nombre de la agencia", "field_type": "text", "required": True},
        ],
    },
    {
        "name": "Oferta de Compra",
        "template_document_type": "oferta_compra",
        "description": "Carta de oferta de compra de inmueble. No vinculante hasta aceptación formal.",
        "jurisdiction": "España",
        "language": "es",
        "fields": [
            {"field_key": "buyer_name", "label": "Nombre del comprador", "field_type": "text", "required": True},
            {"field_key": "property_address", "label": "Dirección del inmueble ofertado", "field_type": "text", "required": True},
            {"field_key": "offer_price", "label": "Precio ofertado (EUR)", "field_type": "amount", "required": True},
            {"field_key": "offer_expiry_date", "label": "Fecha de expiración de la oferta", "field_type": "date", "required": True},
            {"field_key": "conditions", "label": "Condiciones suspensivas", "field_type": "text", "required": False},
        ],
    },
    {
        "name": "Ficha KYC Cliente",
        "template_document_type": "kyc_cliente",
        "description": "Ficha de conocimiento del cliente (Know Your Customer) para prevención de blanqueo de capitales.",
        "jurisdiction": "España",
        "language": "es",
        "fields": [
            {"field_key": "client_name", "label": "Nombre completo del cliente", "field_type": "text", "required": True},
            {"field_key": "client_dni", "label": "DNI/NIE/Pasaporte", "field_type": "text", "required": True},
            {"field_key": "client_nationality", "label": "Nacionalidad", "field_type": "text", "required": True},
            {"field_key": "client_address", "label": "Domicilio habitual", "field_type": "text", "required": True},
            {"field_key": "client_occupation", "label": "Ocupación / actividad profesional", "field_type": "text", "required": True},
            {"field_key": "origin_of_funds", "label": "Origen de los fondos", "field_type": "text", "required": True},
            {"field_key": "politically_exposed", "label": "Persona Políticamente Expuesta (PEP)", "field_type": "boolean", "required": True, "default_value": "false"},
            {"field_key": "declaration_date", "label": "Fecha de la declaración", "field_type": "date", "required": True},
        ],
    },
]


def seed(org_id: str, dry_run: bool = False) -> None:
    if dry_run:
        print(f"[DRY RUN] Would seed {len(TEMPLATE_CATALOGUE)} templates for org {org_id}")
        for t in TEMPLATE_CATALOGUE:
            print(f"  • {t['template_document_type']}: {t['name']} ({len(t['fields'])} fields)")
        return

    from backend.services.neon_service import neon_service
    client = neon_service.client

    now = datetime.now(timezone.utc).isoformat()

    for template_def in TEMPLATE_CATALOGUE:
        fields = template_def.pop("fields")
        template_payload = {
            **template_def,
            "org_id": org_id,
            "is_global": False,
            "status": "draft",
            "created_at": now,
            "updated_at": now,
        }

        existing = (
            client.table("document_templates")
            .select("id")
            .eq("org_id", org_id)
            .eq("template_document_type", template_def["template_document_type"])
            .limit(1)
            .execute()
        )
        if existing.data:
            print(f"  SKIP (exists): {template_def['template_document_type']}")
            template_def["fields"] = fields
            continue

        tmpl_response = client.table("document_templates").insert(template_payload).execute()
        tmpl = tmpl_response.data[0]
        tmpl_id = tmpl["id"]

        # Create version 1 (no binary — canonical text must be uploaded via API)
        version_payload = {
            "template_id": tmpl_id,
            "org_id": org_id,
            "version_number": 1,
            "storage_path": "",
            "sha256_hash": "",
            "encryption_iv": "",
            "encryption_auth_tag": "",
            "canonical_text": None,
            "change_summary": "Versión inicial (pendiente de texto canónico)",
            "immutable": False,
        }
        ver_response = client.table("document_template_versions").insert(version_payload).execute()
        version_id = ver_response.data[0]["id"]

        # Create field definitions
        for field in fields:
            client.table("document_template_fields").insert({
                "template_version_id": version_id,
                "org_id": org_id,
                **field,
            }).execute()

        print(f"  CREATED: {template_def['template_document_type']} — {len(fields)} fields — id={tmpl_id}")
        template_def["fields"] = fields

    print(f"\nSeed complete for org {org_id}.")
    print("Next step: upload canonical text for each template via POST /api/dms/templates/{id}/versions")
    print("Then review with legal counsel and publish via PATCH /api/dms/templates/{id}/publish")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed document templates")
    parser.add_argument("--org-id", required=True, help="Organization UUID")
    parser.add_argument("--dry-run", action="store_true", help="Print plan without making changes")
    args = parser.parse_args()

    seed(args.org_id, dry_run=args.dry_run)
