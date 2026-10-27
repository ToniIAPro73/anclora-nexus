import json
from datetime import datetime, timedelta
from typing import Dict, Any, List
from backend.services.llm_service import LLMService
from backend.services.neon_service import NeonService

async def run_recap_weekly(data: Dict[str, Any], llm: LLMService, db: NeonService) -> Dict[str, Any]:
    """
    Skill for generating a weekly luxury executive summary.
    1. Collect data from the last 7 days (leads, prospection executions, properties).
    2. Analyze metrics and highlights.
    3. Generate luxury summary with Claude 3.5 Sonnet.
    4. Register metrics and summary.
    """
    
    # 1. Collect Data
    days = data.get("days", 7)
    leads = await db.get_recent_leads(days=days)
    executions = await db.get_recent_executions(days=days)
    properties = await db.get_recent_properties_updates(days=days)
    
    # 2. Calculate Basic Metrics
    new_leads_count = len(leads)
    prospection_runs = len([e for e in executions if e.get("skill_id") == "prospection_weekly" or e.get("input", {}).get("skill") == "prospection_weekly"])
    total_executions = len(executions)
    
    # Find high priority lead highlight
    high_priority_lead = None
    if leads:
        sorted_leads = sorted(leads, key=lambda x: x.get("priority_score") or 0.0, reverse=True)
        high_priority_lead = sorted_leads[0]
        
    # 3. LLM Analysis and Summary (Claude 3.5 Sonnet)
    context = {
        "period_days": days,
        "metrics": {
            "new_leads": new_leads_count,
            "prospection_executions": prospection_runs,
            "total_agent_activities": total_executions,
            "properties_updated": len(properties)
        },
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
    
    recap_raw = await llm.generate_copy(prompt)
    try:
        if "```json" in recap_raw:
            recap_raw = recap_raw.split("```json")[1].split("```")[0].strip()
        recap_data = json.loads(recap_raw)
    except:
        recap_data = {
            "luxury_summary": recap_raw if len(recap_raw) > 50 else "Resumen semanal de Anclora Nexus: Actividad estable en la zona suroeste.",
            "metrics": context["metrics"],
            "top_action": "Contactar a los leads de mayor prioridad identificados esta semana."
        }
        
    # 4. Final Result
    result = {
        "week_start": (datetime.utcnow() - timedelta(days=days)).date().isoformat(),
        "week_end": datetime.utcnow().date().isoformat(),
        "metrics": recap_data.get("metrics", context["metrics"]),
        "luxury_summary": recap_data.get("luxury_summary"),
        "top_action": recap_data.get("top_action"),
        "processed_at": datetime.utcnow().isoformat()
    }
    
    return result
