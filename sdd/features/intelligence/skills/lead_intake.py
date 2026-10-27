"""
Lead Intake Skill — Refactored (v1.0.0)
Processes incoming real estate leads with LLM analysis and lux-toned response drafting.
"""

import json
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Literal

from backend.services.llm_service import LLMService

from pydantic import BaseModel, Field, EmailStr, ValidationError

# --- Versioning ---
__version__ = "1.1.0"

# --- Structured Logging ---
def log_event(level: str, event_type: str, details: Dict[str, Any]) -> None:
    """Helper for structured JSON logging."""
    log_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "level": level,
        "event_type": event_type,
        "skill": "lead_intake",
        "version": __version__,
        "details": details
    }
    print(json.dumps(log_data, ensure_ascii=False))

# --- Schemas ---
class LeadInput(BaseModel):
    """Input schema for lead intake."""
    name: str = Field(..., description="Full name of the lead")
    email: Optional[EmailStr] = Field(None, description="Email address")
    phone: Optional[str] = Field(None, description="Contact phone")
    property_interest: Optional[str] = Field(None, description="Specific property or area of interest")
    budget: Optional[str] = Field(None, description="Budget range (e.g., '1M-2M')")
    
    # Origin Tracking (ANCLORA-LSO-001)
    source: str = Field("manual", description="Legacy source field")
    source_system: Literal['manual', 'cta_web', 'import', 'referral', 'partner', 'social'] = Field("manual")
    source_channel: Literal['website', 'linkedin', 'instagram', 'facebook', 'email', 'phone', 'other'] = Field("other")
    source_campaign: Optional[str] = None
    source_detail: Optional[str] = None
    source_url: Optional[str] = None
    source_referrer: Optional[str] = None
    source_event_id: Optional[str] = None
    ingestion_mode: Literal['realtime', 'batch', 'manual'] = Field("manual")
    
    org_id: Optional[str] = Field(None, description="Organization ID for multi-tenancy")

class AnalysisResult(BaseModel):
    """Internal analysis schema."""
    summary: str
    priority: int = Field(..., ge=1, le=5)
    score: float = Field(..., ge=0.0, le=1.0)

class CopyResult(BaseModel):
    """Internal copy generation schema."""
    email: str
    whatsapp: str

class LeadOutput(BaseModel):
    """Final output schema for lead intake."""
    ai_summary: str
    ai_priority: int
    priority_score: float
    next_action: str
    copy_email: str
    copy_whatsapp: str
    processed_at: str
    task_due_date: str

# --- Internal Helpers ---
async def _call_llm_with_retry(func, *args, attempts: int = 3, **kwargs) -> Any:
    """Retry logic for LLM calls with exponential backoff."""
    last_error = None
    for i in range(attempts):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_error = e
            wait_time = (2 ** i) * 0.5  # 0.5, 1, 2 seconds
            log_event("WARNING", "llm_retry", {"attempt": i + 1, "error": str(e), "wait_time": wait_time})
            await asyncio.sleep(wait_time)
    
    log_event("ERROR", "llm_exhausted", {"attempts": attempts, "final_error": str(last_error)})
    raise last_error

# --- Core Skill ---
async def run_lead_intake(data: Dict[str, Any], llm: LLMService, db: Any) -> Dict[str, Any]:
    """
    Skill for processing new real estate leads.
    
    1. Validates input data with Pydantic.
    2. Summarizes and prioritizes lead with GPT-4o-mini.
    3. Generates luxury-toned drafts with Claude 3.5 Sonnet.
    4. Calculates next actions and due dates.
    5. Returns validated structured results.

    Args:
        data: Raw lead dictionary.
        llm: Injected LLM service.
        db: Injected database service.

    Returns:
        A dictionary matching LeadOutput schema.

    Raises:
        ValidationError: If input or output schemas fail.
        Exception: For general processing failures.
    """
    start_time = datetime.utcnow()
    log_event("INFO", "skill_started", {"input_summary": data.get("name")})

    try:
        # 1. Input Validation
        try:
            validated_input = LeadInput(**data)
        except ValidationError as e:
            log_event("ERROR", "input_validation_failed", {"errors": e.errors()})
            raise

        # 2. Analysis (GPT-4o-mini)
        analysis_prompt = f"""
        Analyze this luxury real estate lead:
        {validated_input.model_dump_json()}
        
        Provide a JSON response with:
        - "summary": A 3-line luxury summary in Spanish.
        - "priority": An integer 1-5 (5 is highest).
        - "score": A float 0.0-1.0 based on budget, urgency, and fit.
        """
        
        analysis_raw = await _call_llm_with_retry(llm.analyze, analysis_prompt)
        
        # Robust JSON Parsing
        try:
            if "```json" in analysis_raw:
                analysis_raw = analysis_raw.split("```json")[1].split("```")[0].strip()
            analysis_dict = json.loads(analysis_raw)
            analysis = AnalysisResult(**analysis_dict)
        except (ValueError, json.JSONDecodeError, ValidationError) as e:
            log_event("WARNING", "analysis_parsing_failed", {"raw": analysis_raw, "error": str(e)})
            analysis = AnalysisResult(
                summary="Lead inmobiliario interesado en Mallorca. Requiere seguimiento.",
                priority=3,
                score=0.5
            )

        # 3. Luxury Copy Generation (Claude 3.5 Sonnet)
        copy_prompt = f"""
        Genera drafts de contacto de lujo para este lead:
        {validated_input.model_dump_json()}
        
        Contexto del análisis: {analysis.summary}
        
        Incluye UNICAMENTE un JSON:
        - "email": Tono sofisticado, discreto, personalizado. Firma: Toni Amengual, Anclora Private Estates. Máximo 150 palabras.
        - "whatsapp": Breve, cercano pero profesional. Máximo 2-3 líneas.
        """
        
        try:
            copy_raw = await _call_llm_with_retry(llm.generate_copy, copy_prompt)
            if "```json" in copy_raw:
                copy_raw = copy_raw.split("```json")[1].split("```")[0].strip()
            copy_dict = json.loads(copy_raw)
            copies = CopyResult(**copy_dict)
        except Exception as e:
            log_event("WARNING", "copy_generation_failed", {"error": str(e)})
            copies = CopyResult(
                email="Estimado/a cliente, gracias por su interés en Anclora Private Estates. Quedo a su disposición para coordinar una llamada.",
                whatsapp="Hola, soy Toni Amengual de Anclora. He recibido su consulta y me encantaría comentarle detalles personalmente."
            )

        # 4. Strategy & Deadlines
        priority = analysis.priority
        if priority >= 4:
            next_action = "call_24h"
            due_days = 1
        elif priority >= 3:
            next_action = "email_48h"
            due_days = 2
        else:
            next_action = "email_weekly"
            due_days = 7
            
        due_date = datetime.utcnow() + timedelta(days=due_days)

        # 5. Output Construction & Validation
        result = LeadOutput(
            ai_summary=analysis.summary,
            ai_priority=priority,
            priority_score=analysis.score,
            next_action=next_action,
            copy_email=copies.email,
            copy_whatsapp=copies.whatsapp,
            processed_at=datetime.utcnow().isoformat(),
            task_due_date=due_date.isoformat()
        )

        log_event("INFO", "skill_completed", {
            "priority": result.ai_priority, 
            "duration_ms": (datetime.utcnow() - start_time).total_seconds() * 1000
        })
        
        return result.model_dump()

    except Exception as e:
        log_event("CRITICAL", "skill_failed", {"error": str(e)})
        # Rethrow important exceptions, or return a graceful error State if the orchestrator expects it
        raise
