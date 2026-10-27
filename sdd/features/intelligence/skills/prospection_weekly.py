"""
Prospection Weekly Skill — Refactored (v1.0.0)
Weekly property prospection and lead matching using strategic AI routing.
"""

import json
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, ValidationError

from backend.services.llm_service import LLMService


# --- Versioning ---
__version__ = "1.0.0"

# --- Structured Logging ---
def log_event(level: str, event_type: str, details: Dict[str, Any]) -> None:
    """Helper for structured JSON logging."""
    log_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "level": level,
        "event_type": event_type,
        "skill": "prospection_weekly",
        "version": __version__,
        "details": details
    }
    print(json.dumps(log_data, ensure_ascii=False))

# --- Schemas ---
class ProspectionInput(BaseModel):
    """Input parameters for prospection."""
    priority_min: int = Field(3, ge=1, le=5)
    org_id: Optional[str] = None

class PropertyMatch(BaseModel):
    """Schema for a single lead-property match."""
    lead_id: str
    property_id: str
    score: float = Field(..., ge=0.0, le=1.0)
    reason: str

class MatchingsResponse(BaseModel):
    """Schema for LLM matching response."""
    matchings: List[PropertyMatch]

class ProspectionOutput(BaseModel):
    """Final output schema for prospection."""
    leads_processed: int
    properties_analyzed: int
    matches_found: int
    matchings: List[PropertyMatch]
    luxury_summary: str
    processed_at: str

# --- Internal Helpers ---
async def _call_llm_with_retry(func, *args, attempts: int = 3, **kwargs) -> Any:
    """Retry logic for LLM calls with exponential backoff."""
    last_error = None
    for i in range(attempts):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_error = e
            wait_time = (2 ** i) * 0.5
            log_event("WARNING", "llm_retry", {"attempt": i + 1, "error": str(e)})
            await asyncio.sleep(wait_time)
    raise last_error

# --- Core Skill ---
async def run_prospection_weekly(data: Dict[str, Any], llm: LLMService, db: Any) -> Dict[str, Any]:
    """
    Skill for weekly property prospection and lead matching.

    1. Fetches high-priority leads and available properties from Neon.
    2. Uses GPT-4o-mini to find logical matches between leads and properties.
    3. Generates a luxury executive summary of the prospection with Claude 3.5 Sonnet.
    4. Validates all inputs and outputs with Pydantic.

    Args:
        data: Execution parameters (e.g., priority_min).
        llm: Injected LLM service.
        db: Injected database service.

    Returns:
        A dictionary matching ProspectionOutput schema.
    """
    start_time = datetime.utcnow()
    log_event("INFO", "skill_started", {"data": data})

    try:
        # 1. Input Validation
        params = ProspectionInput(**data)

        # 2. Fetch Context
        leads = await db.get_active_leads(priority_min=params.priority_min)
        properties = await db.get_available_properties()

        if not leads:
            log_event("INFO", "prospection_skipped", {"reason": "no_leads"})
            return {"status": "skipped", "reason": "No active leads found with required priority."}
        
        if not properties:
            log_event("INFO", "prospection_skipped", {"reason": "no_properties"})
            return {"status": "skipped", "reason": "No available properties found for matching."}

        # 3. Property Matching (GPT-4o-mini)
        matching_prompt = f"""
        Eres un experto inmobiliario de lujo en Mallorca.
        Tu tarea es cruzar estos LEADS con estas PROPIEDADES disponibles.
        
        LEADS:
        {json.dumps([{ 'id': l['id'], 'name': l['name'], 'interest': l['property_interest'], 'budget': l['budget_range']} for l in leads], ensure_ascii=False)}
        
        PROPIEDADES:
        {json.dumps([{ 'id': p['id'], 'address': p['address'], 'price': p['price'], 'type': p['property_type']} for p in properties], ensure_ascii=False)}
        
        Para cada LEAD, encuentra la mejor propiedad coincidente (si hay alguna razonable).
        
        Responde UNICAMENTE con un JSON:
        {{
          "matchings": [
            {{
              "lead_id": "uuid",
              "property_id": "uuid",
              "score": 0.0-1.0,
              "reason": "breve explicación de por qué encaja"
            }}
          ]
        }}
        """
        
        matching_raw = await _call_llm_with_retry(llm.analyze, matching_prompt)
        
        # Robust JSON Parsing
        matchings: List[PropertyMatch] = []
        try:
            if "```json" in matching_raw:
                matching_raw = matching_raw.split("```json")[1].split("```")[0].strip()
            matching_data = json.loads(matching_raw)
            validated_matchings = MatchingsResponse(**matching_data)
            matchings = validated_matchings.matchings
        except (ValueError, json.JSONDecodeError, ValidationError) as e:
            log_event("WARNING", "matching_parsing_failed", {"error": str(e), "raw": matching_raw[:200]})
            # Continue with empty matchings if parsing fails

        # 4. Luxury Summary (Claude 3.5 Sonnet)
        summary_prompt = f"""
        Genera un resumen ejecutivo de prospección semanal con tono de lujo.
        Hemos cruzado {len(leads)} leads de alta prioridad con {len(properties)} propiedades.
        Se han encontrado {len(matchings)} coincidencias estratégicas.
        
        DETALLES DE MATCHING:
        {json.dumps([m.model_dump() for m in matchings], ensure_ascii=False)}
        
        El resumen debe ser sofisticado, motivador y breve. Enfócate en las oportunidades detectadas en Andratx, Calvià y Son Ferrer.
        """
        
        summary = await _call_llm_with_retry(llm.generate_copy, summary_prompt)

        # 5. Result Construction
        result = ProspectionOutput(
            leads_processed=len(leads),
            properties_analyzed=len(properties),
            matches_found=len(matchings),
            matchings=matchings,
            luxury_summary=summary,
            processed_at=datetime.utcnow().isoformat()
        )

        log_event("INFO", "skill_completed", {
            "matches": result.matches_found,
            "duration_ms": (datetime.utcnow() - start_time).total_seconds() * 1000
        })

        return result.model_dump()

    except Exception as e:
        log_event("CRITICAL", "skill_failed", {"error": str(e)})
        raise
