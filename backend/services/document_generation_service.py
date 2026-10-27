"""Template variable substitution and generated document lifecycle service."""

import re
from typing import Any

# Patterns that indicate a field is still unfilled
_PLACEHOLDER_PATTERNS = [
    re.compile(r"\[.*?\]"),
    re.compile(r"\{\{[a-zA-Z_][a-zA-Z0-9_]*\}\}"),  # unfilled {{ field_key }} tokens
    re.compile(r"\{[A-Z_]+\}"),                       # {UPPERCASE_VAR} style
    re.compile(r"___+"),
    re.compile(r"<<<.*?>>>"),
    re.compile(r"\bXXXX+\b", re.IGNORECASE),
    re.compile(r"\bPENDIENTE\b", re.IGNORECASE),
    re.compile(r"\bPOR DETERMINAR\b", re.IGNORECASE),
    re.compile(r"\bA COMPLETAR\b", re.IGNORECASE),
    re.compile(r"\bTO BE COMPLETED\b", re.IGNORECASE),
    re.compile(r"\bTBD\b", re.IGNORECASE),
]


def _detect_unfilled_placeholders(text: str) -> list[str]:
    found: list[str] = []
    for pattern in _PLACEHOLDER_PATTERNS:
        found.extend(pattern.findall(text))
    return found


def render_template(canonical_text: str, field_values: dict[str, Any]) -> str:
    """Substitute {{ field_key }} tokens in canonical_text with field_values.

    Template syntax: {{buyer.full_name}}, {{ deal.price }}, etc.
    Dots in keys are supported (namespaced placeholders).
    Unknown tokens are left in place so placeholder detection can catch them.
    """
    def replacer(match: re.Match) -> str:
        key = match.group(1).strip()
        value = field_values.get(key)
        if value is None:
            return match.group(0)   # leave unfilled for detection
        return str(value)

    return re.sub(r"\{\{\s*(\w[\w.]*)\s*\}\}", replacer, canonical_text)


class GenerationResult:
    """Result of a document generation attempt."""

    def __init__(
        self,
        rendered_text: str,
        unfilled_placeholders: list[str],
        generation_payload: dict[str, Any],
    ) -> None:
        self.rendered_text = rendered_text
        self.unfilled_placeholders = unfilled_placeholders
        self.generation_payload = generation_payload

    @property
    def is_complete(self) -> bool:
        return len(self.unfilled_placeholders) == 0


def generate_from_template(
    canonical_text: str,
    field_values: dict[str, Any],
    required_fields: list[str] | None = None,
) -> GenerationResult:
    """Render a document from a template canonical text and field values.

    Returns a GenerationResult. If is_complete is False, the caller must
    decide whether to block or warn.
    """
    missing_required: list[str] = []
    if required_fields:
        missing_required = [k for k in required_fields if k not in field_values]

    rendered = render_template(canonical_text, field_values)
    unfilled = _detect_unfilled_placeholders(rendered)

    # Add missing required fields as synthetic placeholder markers
    for key in missing_required:
        marker = f"{{{{ {key} }}}}"
        if marker not in unfilled:
            unfilled.append(f"[REQUIRED: {key}]")

    return GenerationResult(
        rendered_text=rendered,
        unfilled_placeholders=unfilled,
        generation_payload=field_values,
    )


def fetch_template_required_fields(template_version_id: str, org_id: str) -> list[dict[str, Any]]:
    """Return the list of required field definitions for a template version."""
    from backend.services.neon_service import neon_service  # lazy import
    response = (
        neon_service.client
        .table("document_template_fields")
        .select("field_key,label,field_type,required,default_value,source_path")
        .eq("template_version_id", template_version_id)
        .execute()
    )
    return response.data or []
