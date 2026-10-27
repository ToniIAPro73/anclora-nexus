import json
from datetime import datetime, timedelta
from typing import Dict, Any
from backend.services.llm_service import LLMService
from backend.services.neon_service import NeonService

async def run_lead_intake(data: Dict[str, Any], llm: LLMService, db: NeonService) -> Dict[str, Any]:
    """
    Skill for processing new real estate leads.
    1. Summarize and prioritize with LLM.
    2. Generate luxury-toned initial contact drafts.
    3. Persist to Neon.
    4. Create follow-up tasks.
    """
    
    # 1. Classification and Summary (GPT-4o-mini via LLMService.summarize/analyze)
    # We use a structured prompt to get both priority and summary
    analysis_prompt = f"""
    Analyze this luxury real estate lead:
    {json.dumps(data, ensure_ascii=False)}
    
    Provide a JSON response with:
    - "summary": A 3-line luxury summary.
    - "priority": An integer 1-5 (5 is highest).
    - "score": A float 0.0-1.0 based on budget, urgency, and fit.
    """
    
    analysis_raw = await llm.analyze(analysis_prompt)
    try:
        # Simple extraction if LLM doesn't return pure JSON
        if "```json" in analysis_raw:
            analysis_raw = analysis_raw.split("```json")[1].split("```")[0].strip()
        analysis = json.loads(analysis_raw)
    except:
        # Fallback if parsing fails
        analysis = {
            "summary": "Nuevo interesado en propiedad. Ver detalles en el formulario.",
            "priority": 3,
            "score": 0.5
        }

    # 2. Generar Luxury Copy (Claude 3.5 Sonnet via LLMService.generate_copy)
    copy_prompt = f"""
    Genera drafts de contacto de lujo para este lead:
    {json.dumps(data, ensure_ascii=False)}
    
    Incluye:
    - "email": Tono sofisticado, discreto, personalizado. Firma: Toni Amengual, Anclora Private Estates. Máximo 150 palabras.
    - "whatsapp": Breve, cercano pero profesional. Máximo 2-3 líneas.
    """
    copy_raw = await llm.generate_copy(copy_prompt)
    try:
        if "```json" in copy_raw:
            copy_raw = copy_raw.split("```json")[1].split("```")[0].strip()
        copies = json.loads(copy_raw)
    except:
        copies = {
            "email": "Estimado/a cliente, gracias por su interés...",
            "whatsapp": "Hola, soy Toni de Anclora. He recibido su consulta..."
        }

    # 3. Define next action and due date
    priority = analysis.get("priority", 3)
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

    # 4. Preparation for return (persistence will be handled by result_handler_node)
    result = {
        "ai_summary": analysis.get("summary"),
        "ai_priority": priority,
        "priority_score": analysis.get("score"),
        "next_action": next_action,
        "copy_email": copies.get("email"),
        "copy_whatsapp": copies.get("whatsapp"),
        "processed_at": datetime.utcnow().isoformat(),
        "task_due_date": due_date.isoformat()
    }

    return result
