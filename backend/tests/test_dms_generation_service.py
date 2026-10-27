"""Unit tests for document_generation_service — pure functions, no I/O."""

import os

os.environ.setdefault("NEXUS_DOCUMENT_ENCRYPTION_KEY", "00" * 32)

from backend.services.document_generation_service import (
    generate_from_template,
    render_template,
)


# ── render_template ────────────────────────────────────────────────────────────

def test_render_template_substitutes_known_keys():
    template = "Comprador: {{buyer_name}}, Precio: {{sale_price}}"
    result = render_template(template, {"buyer_name": "Ana Pérez", "sale_price": "250.000 EUR"})
    assert "Ana Pérez" in result
    assert "250.000 EUR" in result


def test_render_template_leaves_unknown_tokens():
    template = "Campo: {{unknown_key}}"
    result = render_template(template, {})
    assert "{{unknown_key}}" in result


def test_render_template_handles_whitespace_in_token():
    template = "Fecha: {{ closing_date }}"
    result = render_template(template, {"closing_date": "31/12/2026"})
    assert "31/12/2026" in result


def test_render_template_multiple_occurrences():
    template = "{{buyer_name}} firmará con {{buyer_name}} como compradores."
    result = render_template(template, {"buyer_name": "Luis"})
    assert result.count("Luis") == 2


# ── generate_from_template ─────────────────────────────────────────────────────

def test_generate_complete_document_is_marked_complete():
    canonical = "Comprador: {{buyer_name}}. Precio: {{sale_price}}. Notaría: {{notary}}."
    result = generate_from_template(
        canonical,
        {"buyer_name": "Ana", "sale_price": "250.000 EUR", "notary": "Notaría Central"},
    )
    assert result.is_complete
    assert "Ana" in result.rendered_text
    assert not result.unfilled_placeholders


def test_generate_incomplete_document_not_complete():
    canonical = "Comprador: {{buyer_name}}. DNI: {{buyer_dni}}."
    result = generate_from_template(canonical, {"buyer_name": "Ana"})
    assert not result.is_complete
    assert any("buyer_dni" in p for p in result.unfilled_placeholders)


def test_generate_detects_bracket_placeholders():
    canonical = "Comprador: {{buyer_name}}. Dirección: [DIRECCIÓN]."
    result = generate_from_template(canonical, {"buyer_name": "Luis"})
    assert not result.is_complete
    assert any("[DIRECCIÓN]" in p for p in result.unfilled_placeholders)


def test_generate_missing_required_field_blocks_completion():
    canonical = "Precio: {{price}}."
    result = generate_from_template(canonical, {}, required_fields=["price"])
    assert not result.is_complete


def test_generate_applies_defaults():
    canonical = "Idioma: {{language}}."
    result = generate_from_template(canonical, {"language": "es"})
    assert "es" in result.rendered_text
    assert result.is_complete


def test_generate_payload_preserved():
    canonical = "Comprador: {{buyer_name}}."
    values = {"buyer_name": "María", "extra_field": "ignored"}
    result = generate_from_template(canonical, values)
    assert result.generation_payload["buyer_name"] == "María"
    assert result.generation_payload["extra_field"] == "ignored"


def test_generate_tbd_placeholder_detected():
    canonical = "Fecha de entrega: {{delivery_date}} TBD algo."
    result = generate_from_template(canonical, {"delivery_date": "01/01/2027"})
    # "TBD" in the static part should still flag as unfilled
    assert not result.is_complete
