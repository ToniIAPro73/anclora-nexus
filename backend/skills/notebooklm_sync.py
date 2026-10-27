"""
NotebookLM Sync Skill

This skill is executed by Claude Code (not the production backend) to:
1. Process territorial intelligence from the NotebookLM RAG notebook
2. Synthesize it using the LLM
3. Store structured insights in Neon for the API to serve

Why this architecture: NotebookLM MCP uses browser session (Google auth)
and is NOT callable from the production FastAPI backend. Claude Code acts
as the bridge: MCP → NotebookLM → LLM synthesis → Neon.

Trigger: Manual by Claude Code or scheduled via cron (weekly, same time as
prospection_weekly and recap_weekly — Sunday ~19:00 CET).

Usage (from Claude Code session):
    from backend.skills.notebooklm_sync import run_notebooklm_sync
    result = await run_notebooklm_sync(data, llm, db)
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict

from backend.services.llm_service import LLMService
from backend.services.org_context_service import resolve_legacy_org_id
from backend.services.neon_service import NeonService
from backend.services.notebooklm_service import save_insight

TERRITORIAL_ZONES = [
    "andratx", "calvia", "son_ferrer", "santa_ponca",
    "paguera", "portals_nous", "bendinat", "costa_den_blanes"
]


async def run_notebooklm_sync(
    data: Dict[str, Any],
    llm: LLMService,
    db: NeonService,
) -> Dict[str, Any]:
    """
    Sync territorial intelligence from NotebookLM to Neon.

    NOTE: This skill expects that Claude Code has already queried NotebookLM
    via MCP and passed the raw response in `data['notebooklm_response']`.
    This skill then uses the LLM to structure and classify the response,
    and saves it to Neon.

    Args:
        data: Dict containing:
            - notebooklm_response (str): Raw response from NotebookLM query
            - query (str): The query that was asked
            - insight_type (str): Type of insight (territorial, cma, etc.)
            - zona (str, optional): Geographic zone
            - org_id (str, optional): Override org_id
        llm: LLMService instance
        db: NeonService instance

    Returns:
        Dict with sync results
    """
    raw_response = data.get("notebooklm_response", "")
    query = data.get("query", "Inteligencia territorial Suroeste Mallorca")
    insight_type = data.get("insight_type", "territorial")
    zona = data.get("zona")
    org_id = resolve_legacy_org_id(data.get("org_id"), "notebooklm_sync")
    source_mode = data.get("source_mode", "manual")
    source_ref = data.get("source_ref")

    if not raw_response:
        return {
            "status": "skipped",
            "reason": "No notebooklm_response provided. "
                      "Query NotebookLM via MCP first and pass the response in data.",
        }

    # Use LLM to extract structured summary for storage
    structuring_prompt = f"""
Eres un experto en inteligencia inmobiliaria del Suroeste de Mallorca.

Se te proporciona una respuesta de NotebookLM sobre inteligencia territorial.
Tu tarea es extraer y estructurar la información más relevante para un agente
inmobiliario de lujo en formato JSON.

CONSULTA ORIGINAL: {query}

RESPUESTA NOTEBOOKLM:
{raw_response[:4000]}

Extrae la información clave en el siguiente formato JSON:
{{
  "resumen": "2-3 frases del hallazgo principal",
  "oportunidades": ["oportunidad 1", "oportunidad 2", ...],
  "zonas_calientes": ["zona 1", "zona 2", ...],
  "senales_deteccion": ["señal 1", "señal 2", ...],
  "acciones_recomendadas": ["acción 1", "acción 2", ...],
  "urgencia": "alta|media|baja",
  "fuentes_citadas": ["fuente 1", "fuente 2", ...]
}}

Responde ÚNICAMENTE con el JSON válido.
"""

    structured_raw = await llm.analyze(structuring_prompt)

    # Parse structured output
    structured = {}
    try:
        if "```json" in structured_raw:
            structured_raw = structured_raw.split("```json")[1].split("```")[0].strip()
        elif "```" in structured_raw:
            structured_raw = structured_raw.split("```")[1].split("```")[0].strip()
        structured = json.loads(structured_raw)
    except Exception as e:
        print(f"[notebooklm_sync] Warning: Could not parse structured output: {e}")
        structured = {"resumen": raw_response[:500]}

    # Save to Neon
    try:
        saved = await save_insight(
            db=db,
            org_id=org_id,
            query=query,
            response=raw_response,
            insight_type=insight_type,
            zona=zona or "general",
            metadata={
                "structured": structured,
                "synced_at": datetime.now(timezone.utc).isoformat(),
                "source": "notebooklm_territorial_2026",
                "source_mode": source_mode,
                "source_ref": source_ref,
            },
        )
        insight_id = saved.get("id", "unknown")
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "raw_response_length": len(raw_response),
        }

    result_summary = structured.get("resumen", raw_response[:200])
    urgencia = structured.get("urgencia", "media")

    return {
        "status": "success",
        "insight_id": insight_id,
        "insight_type": insight_type,
        "zona": zona or "general",
        "urgencia": urgencia,
        "resumen": result_summary,
        "oportunidades_detectadas": len(structured.get("oportunidades", [])),
        "zonas_calientes": structured.get("zonas_calientes", []),
        "acciones_recomendadas": structured.get("acciones_recomendadas", []),
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "output_tag": (
            f"[Generado por Anclora Nexus Agent — notebooklm_sync] "
            f"Fecha: {datetime.now(timezone.utc).isoformat()}"
        ),
    }
