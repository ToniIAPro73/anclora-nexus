"""
Recap Weekly Skill — Refactored (v1.0.0)
Generates a weekly luxury executive summary for business performance monitoring.
"""

import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
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
        "skill": "recap_weekly",
        "version": __version__,
        "details": details
    }
    print(json.dumps(log_data, ensure_ascii=False))

# --- Schemas ---
class RecapInput(BaseModel):
    """Input parameters for the weekly recap."""
    days: int = Field(7, ge=1, le=30, description="Number of days to look back")
    org_id: Optional[str] = None

class RecapLLMResponse(BaseModel):
    """Schema for the LLM generated summary data."""
    luxury_summary: str
    metrics: Dict[str, Any]
    top_action: str

class RecapOutput(BaseModel):
    """Final output schema for the weekly recap."""
    week_start: str
    week_end: str
    metrics: Dict[str, Any]
    luxury_summary: str
    top_action: str
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
async def run_recap_weekly(data: Dict[str, Any], llm: LLMService, db: Any) -> Dict[str, Any]:
    """
    Skill for generating a weekly luxury executive summary.
    
    1. Collects data from the last X days (leads, prospection executions, properties).
    2. Calculates key performance indicators (KPIs).
    3. Analyzes highlights and generates a luxury summary using Claude 3.5 Sonnet.
    4. Handles errors gracefully with fallback defaults.

    Args:
        data: Execution parameters (e.g., lookback days).
        llm: Injected LLM service.
        db: Injected database service.

    Returns:
        A dictionary matching RecapOutput schema.
    """
    start_time = datetime.utcnow()
    log_event("INFO", "skill_started", {"data": data})

    try:
        # 1. Input Validation
        params = RecapInput(**data)
        
        # 2. Collect Data
        log_event("DEBUG", "data_collection_started", {"days": params.days})
        try:
            results = await asyncio.gather(
                db.get_recent_leads(days=params.days),
                db.get_recent_executions(days=params.days),
                db.get_recent_properties_updates(days=params.days)
            )
            leads, executions, properties = results
        except Exception as e:
            log_event("ERROR", "data_collection_failed", {"error": str(e)})
            # Default empty lists for graceful degradation
            leads, executions, properties = [], [], []

        # 3. Calculate Metrics
        new_leads_count = len(leads)
        prospection_runs = len([e for e in executions if e.get("skill_id") == "prospection_weekly" or e.get("input", {}).get("skill") == "prospection_weekly"])
        total_executions = len(executions)
        
        high_priority_lead = None
        if leads:
            # Sort by priority score (desc) to find highlight
            sorted_leads = sorted(leads, key=lambda x: x.get("priority_score") or 0.0, reverse=True)
            high_priority_lead = sorted_leads[0]
            
        metrics = {
            "new_leads": new_leads_count,
            "prospection_executions": prospection_runs,
            "total_agent_activities": total_executions,
            "properties_updated": len(properties)
        }

        # 4. LLM Analysis and Summary (Claude 3.5 Sonnet)
        context = {
            "period_days": params.days,
            "metrics": metrics,
            "highlights": {
                "top_lead": {
                    "name": high_priority_lead.get("name") if high_priority_lead else "None",
                    "priority": high_priority_lead.get("ai_priority") if high_priority_lead else "N/A",
                    "summary": high_priority_lead.get("ai_summary") if high_priority_lead else "No hay leads nuevos de alta relevancia."
                }
            }
        }
        
        prompt = f"""
        Eres el Agente de Estrategia de Anclora Private Estates. Tu misión es generar un RECAP SEMANAL EJECUTIVO para Toni Amengual.
        
        DATOS DE LA SEMANA:
        {json.dumps(context, indent=2, ensure_ascii=False)}
        
        INSTRUCCIONES:
        1. Usa un TONO LUXURY: sofisticado, discreto, analítico y motivador. (Mallorca SW: Andratx, Calvià, Son Ferrer).
        2. Estructura:
           - KPIs: Resumen de actividad (leads, prospección).
           - Highlights: El lead o evento más importante.
           - Acción Recomendada: Qué debería priorizar Toni la próxima semana.
        3. Formato: Devuelve un JSON con:
           - "luxury_summary": Texto completo formateado para email/widget.
           - "metrics": Diccionario de KPIs clave.
           - "top_action": Una sola acción estratégica.
        """
        
        recap_raw = await _call_llm_with_retry(llm.generate_copy, prompt)
        
        # Robust JSON Parsing with Fallback
        try:
            if "```json" in recap_raw:
                recap_raw = recap_raw.split("```json")[1].split("```")[0].strip()
            recap_data_dict = json.loads(recap_raw)
            recap_data = RecapLLMResponse(**recap_data_dict)
        except (ValueError, json.JSONDecodeError, ValidationError) as e:
            log_event("WARNING", "recap_parsing_failed", {"error": str(e)})
            recap_data = RecapLLMResponse(
                luxury_summary=recap_raw if len(recap_raw) > 50 else "Resumen semanal de Anclora Nexus: Actividad estable en la zona suroeste. Los sistemas de prospección y gestión de leads operan con normalidad.",
                metrics=metrics,
                top_action="Continuar con el seguimiento personalizado de los leads captados recientemente."
            )

        # 5. Final Result
        result = RecapOutput(
            week_start=(datetime.utcnow() - timedelta(days=params.days)).date().isoformat(),
            week_end=datetime.utcnow().date().isoformat(),
            metrics=recap_data.metrics,
            luxury_summary=recap_data.luxury_summary,
            top_action=recap_data.top_action,
            processed_at=datetime.utcnow().isoformat()
        )

        log_event("INFO", "skill_completed", {
            "new_leads": result.metrics.get("new_leads"),
            "duration_ms": (datetime.utcnow() - start_time).total_seconds() * 1000
        })
        
        return result.model_dump()

    except Exception as e:
        log_event("CRITICAL", "skill_failed", {"error": str(e)})
        raise
