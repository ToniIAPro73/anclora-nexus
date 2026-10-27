import json
from datetime import datetime
from typing import Dict, Any, List
from backend.services.llm_service import LLMService
from backend.services.org_context_service import resolve_legacy_org_id
from backend.services.neon_service import NeonService
from backend.services.sellers_service import create_seller
from backend.models.sellers import NexusSellerCreate, ZonaEnum, FuenteEnum

async def run_prospection_weekly(data: Dict[str, Any], llm: LLMService, db: NeonService) -> Dict[str, Any]:
    """
    Skill for weekly property prospection and lead matching.
    1. Fetch high-priority leads.
    2. Fetch available properties.
    3. Match lead-property with LLM (GPT-4o-mini).
    4. Generate luxury weekly summary (Claude 3.5 Sonnet).
    5. Register matching.
    """
    
    # 1. Fetch context
    org_id = resolve_legacy_org_id(data.get("org_id"), "prospection_weekly")
    priority_min = data.get("priority_min", 3)
    leads = await db.get_active_leads(org_id=org_id, priority_min=priority_min)
    properties = await db.get_available_properties(org_id=org_id)
    
    if not leads:
        return {"status": "skipped", "reason": "No active leads found with required priority."}
    
    if not properties:
        return {"status": "skipped", "reason": "No available properties found for matching."}

    # 2. Property Matching (GPT-4o-mini)
    # We'll do a batch analysis to find the best property for each lead
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
    
    matching_raw = await llm.analyze(matching_prompt)
    matchings = []
    try:
        if "```json" in matching_raw:
            matching_raw = matching_raw.split("```json")[1].split("```")[0].strip()
        matching_data = json.loads(matching_raw)
        matchings = matching_data.get("matchings", [])
    except Exception as e:
        print(f"Error parsing matching response: {e}")
        # Fallback empty matchings

    # 3. Luxury Summary (Claude 3.5 Sonnet)
    summary_prompt = f"""
    Genera un resumen ejecutivo de prospección semanal con tono de lujo.
    Hemos cruzado {len(leads)} leads de alta prioridad con {len(properties)} propiedades.
    Se han encontrado {len(matchings)} coincidencias estratégicas.
    
    DETALLES DE MATCHING:
    {json.dumps(matchings, ensure_ascii=False)}
    
    El resumen debe ser sofisticado, motivador y breve. Enfócate en las oportunidades detectadas en Andratx, Calvià y Son Ferrer.
    """
    
    summary = await llm.generate_copy(summary_prompt)

    # 4. Detect potential FSBOs / stagnant properties → write to nexus_sellers
    sellers_created = 0
    for prop in properties:
        # Heuristic: properties without an assigned agent or with long DOM
        # are candidates for seller prospecting
        prop_type = prop.get("property_type", "")
        address = prop.get("address", "")
        price = prop.get("price")

        # Only prospect luxury properties (>€500K) in target zones
        if price and price >= 500000:
            zona_raw = prop.get("zone", prop.get("zona", "otra")).lower().replace(" ", "_").replace("-", "_")
            # Map to valid ZonaEnum value
            zona_map = {
                "andratx": "andratx", "calvià": "calvia", "calvia": "calvia",
                "son_ferrer": "son_ferrer", "santa_ponça": "santa_ponca",
                "santa_ponca": "santa_ponca", "paguera": "paguera",
                "portals_nous": "portals_nous", "bendinat": "bendinat",
                "punta_negra": "punta_negra", "costa_den_blanes": "costa_den_blanes",
                "port_adriano": "port_adriano", "palma": "palma",
            }
            zona_value = zona_map.get(zona_raw, "otra")

            try:
                seller_data = NexusSellerCreate(
                    anuncio_url=prop.get("url", prop.get("listing_url")),
                    direccion=address,
                    zona=ZonaEnum(zona_value),
                    fuente=FuenteEnum.prospection_match,
                    precio_publicado=float(price),
                    tipo_propiedad=prop_type,
                    dias_en_mercado=prop.get("days_on_market"),
                    datos_extraidos={
                        "property_id": str(prop.get("id", "")),
                        "match_context": "detected_by_prospection_weekly",
                    },
                    prioridad=4 if price >= 2000000 else 3,
                )
                await create_seller(db=db, org_id=org_id, data=seller_data)
                sellers_created += 1
            except Exception as e:
                print(f"[prospection_weekly] Warning: Could not create seller for property {prop.get('id')}: {e}")

    # 5. Prepare results
    result = {
        "leads_processed": len(leads),
        "properties_analyzed": len(properties),
        "matches_found": len(matchings),
        "matchings": matchings,
        "luxury_summary": summary,
        "sellers_detected": sellers_created,
        "processed_at": datetime.utcnow().isoformat()
    }

    return result
