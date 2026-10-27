import json
from datetime import datetime
from typing import Dict, Any, List
from backend.agents.state import AgentState

async def process_input_node(state: AgentState) -> AgentState:
    print("--- PROCESS INPUT ---")
    return state

async def planner_node(state: AgentState) -> AgentState:
    print("--- PLANNER ---")
    # In v0, we assume the skill_name is passed in the input or inferred
    # For now, let's look at the input_data
    if state.get("skill_name") == "lead_intake" or state["input_data"].get("skill") == "lead_intake":
        state["selected_skill"] = "lead_intake"
        state["plan"] = "Execute lead intake processing"
    elif state.get("skill_name") == "prospection_weekly" or state["input_data"].get("skill") == "prospection_weekly":
        state["selected_skill"] = "prospection_weekly"
        state["plan"] = "Execute weekly property prospection and matching"
    elif state.get("skill_name") == "recap_weekly" or state["input_data"].get("skill") == "recap_weekly":
        state["selected_skill"] = "recap_weekly"
        state["plan"] = "Generate weekly executive recap"
    return state

async def limit_check_node(state: AgentState) -> AgentState:
    print("--- LIMIT CHECK ---")
    from backend.services.neon_service import neon_service

    org_id = state.get("org_id", neon_service.fixed_org_id)
    limits = await neon_service.get_constitutional_limits(org_id)

    state["limits_ok"] = True

    # 1. Check max_daily_leads
    if "max_daily_leads" in limits:
        daily_leads = await neon_service.count_daily_leads(org_id)
        if daily_leads >= limits["max_daily_leads"]:
            state["limits_ok"] = False
            state["status"] = "blocked"
            state["limit_violation"] = "max_daily_leads"
            state["error"] = f"Constitutional limit reached: max_daily_leads ({limits['max_daily_leads']})"
            print(f"LIMIT BLOCKED: {state['error']}")

    # 2. Check max_llm_tokens_per_day
    if state["limits_ok"] and "max_llm_tokens_per_day" in limits:
        daily_tokens = await neon_service.get_daily_token_usage(org_id)
        if daily_tokens >= limits["max_llm_tokens_per_day"]:
            state["limits_ok"] = False
            state["status"] = "blocked"
            state["limit_violation"] = "max_llm_tokens_per_day"
            state["error"] = f"Constitutional limit reached: max_llm_tokens_per_day ({limits['max_llm_tokens_per_day']})"
            print(f"LIMIT BLOCKED: {state['error']}")

    if not state["limits_ok"]:
        # Log rejection to audit_log
        await neon_service.insert_audit_log({
            "org_id": org_id,
            "actor_type": "system",
            "actor_id": "constitutional_validator",
            "action": "limit_check.rejected",
            "resource_type": "constitutional_limit",
            "details": {"reason": state["error"]}
        })

    return state

async def executor_node(state: AgentState) -> AgentState:
    print("--- EXECUTOR ---")
    from sdd.features.intelligence.skills.lead_intake import run_lead_intake
    from backend.services.llm_service import llm_service
    from backend.services.neon_service import neon_service

    if state["selected_skill"] == "lead_intake":
        from sdd.features.intelligence.skills.lead_intake import run_lead_intake
        try:
            output = await run_lead_intake(state["input_data"], llm_service, neon_service)
            state["skill_output"] = output
        except Exception as e:
            state["error"] = str(e)
            state["status"] = "error"
    elif state["selected_skill"] == "prospection_weekly":
        from sdd.features.intelligence.skills.prospection_weekly import run_prospection_weekly
        try:
            output = await run_prospection_weekly(state["input_data"], llm_service, neon_service)
            state["skill_output"] = output
        except Exception as e:
            state["error"] = str(e)
            state["status"] = "error"
    elif state["selected_skill"] == "recap_weekly":
        from sdd.features.intelligence.skills.recap_weekly import run_recap_weekly
        try:
            output = await run_recap_weekly(state["input_data"], llm_service, neon_service)
            state["skill_output"] = output
        except Exception as e:
            state["error"] = str(e)
            state["status"] = "error"

    return state

async def result_handler_node(state: AgentState) -> AgentState:
    print("--- RESULT HANDLER ---")
    from backend.services.neon_service import neon_service

    if state.get("skill_output") and state["selected_skill"] == "lead_intake":
        output = state["skill_output"]
        org_id = state.get("org_id", state["input_data"].get("org_id", neon_service.fixed_org_id))
        assignee_user_id = None
        assignee_role = None
        assignee_reason = None

        # 1. Update or Insert Lead
        lead_id = state["input_data"].get("lead_id")
        lead_data = {
            "ai_summary": output["ai_summary"],
            "ai_priority": output["ai_priority"],
            "priority_score": output["priority_score"],
            "next_action": output["next_action"],
            "copy_email": output["copy_email"],
            "copy_whatsapp": output["copy_whatsapp"],
            "processed_at": output["processed_at"],
            "status": "new"
        }

        if lead_id:
            await neon_service.update_lead(lead_id, lead_data)
        else:
            assignee = await neon_service.pick_lead_assignee(org_id)
            assignee_user_id = assignee.get("user_id")
            assignee_role = assignee.get("role")
            assignee_reason = assignee.get("reason")

            # Insert new lead with input data + AI output
            input_data = state["input_data"]

            # Origin Mapping & Legacy Compatibility (ANCLORA-LSO-001)
            source_legacy = input_data.get("source", "manual")
            source_system = input_data.get("source_system")
            source_channel = input_data.get("source_channel")

            # Minimal legacy fallback if new fields are missing
            if not source_system:
                if "web" in source_legacy.lower():
                    source_system = "cta_web"
                else:
                    source_system = "manual"

            if not source_channel:
                if "linkedin" in source_legacy.lower():
                    source_channel = "linkedin"
                elif "web" in source_legacy.lower():
                    source_channel = "website"
                else:
                    source_channel = "other"

            incoming_notes = input_data.get("notes")
            normalized_notes = incoming_notes if isinstance(incoming_notes, dict) else {}
            if input_data.get("message"):
                normalized_notes["message"] = input_data.get("message")

            full_lead_data = {
                "org_id": org_id,
                "name": input_data.get("name", "Unknown"),
                "email": input_data.get("email"),
                "phone": input_data.get("phone"),
                "assigned_user_id": assignee_user_id,
                "source": source_legacy,
                "source_system": source_system,
                "source_channel": source_channel,
                "source_campaign": input_data.get("source_campaign"),
                "source_detail": input_data.get("source_detail"),
                "source_url": input_data.get("source_url"),
                "source_referrer": input_data.get("source_referrer"),
                "source_event_id": input_data.get("source_event_id"),
                "ingestion_mode": input_data.get("ingestion_mode", "manual"),
                "captured_at": datetime.utcnow().isoformat(),
                "property_interest": input_data.get("property_interest"),
                "budget_range": input_data.get("budget"), # Map budget -> budget_range
                "notes": normalized_notes,
                **lead_data
            }
            new_lead = await neon_service.insert_lead(full_lead_data)
            lead_id = new_lead.get("id")
            if not lead_id:
                raise ValueError("Lead intake persistence completed without returning a lead id")

            if assignee_user_id:
                lead_notes = new_lead.get("notes") if isinstance(new_lead.get("notes"), dict) else {}
                lead_notes["routing"] = {
                    "assigned_user_id": assignee_user_id,
                    "assigned_role": assignee_role,
                    "reason": assignee_reason,
                    "assigned_at": datetime.utcnow().isoformat(),
                }
                await neon_service.update_lead(lead_id, {"notes": lead_notes})
            
        # 2. Create Task
        assignment_hint = (
            f" Asignado a {assignee_role or 'n/a'} ({assignee_user_id})."
            if assignee_user_id
            else ""
        )
        await neon_service.insert_task({
            "org_id": org_id,
            "title": f"Follow-up: {state['input_data'].get('name')}",
            "description": f"Prioridad {output['ai_priority']}/5. Acción: {output['next_action']}. Resumen: {output['ai_summary']}.{assignment_hint}",
            "type": "follow_up",
            "related_lead_id": lead_id,
            "assigned_user_id": assignee_user_id,
            "due_date": output["task_due_date"],
            "ai_generated": True
        })

        source_system = (state["input_data"].get("source_system") or "").lower()
        if source_system == "cta_web":
            await neon_service.insert_task({
                "org_id": org_id,
                "title": f"Aviso contacto web: {state['input_data'].get('name')}",
                "description": (
                    f"Nuevo lead de origen web-cta. "
                    f"Routing: {assignee_reason or 'unassigned'}."
                    f"{assignment_hint}"
                ),
                "type": "admin",
                "related_lead_id": lead_id,
                "assigned_user_id": assignee_user_id,
                "due_date": datetime.utcnow().isoformat(),
                "ai_generated": True
            })
        
        state["final_result"] = {
            **output,
            "lead_id": lead_id,
            "assigned_user_id": assignee_user_id,
            "assigned_role": assignee_role,
            "assignment_reason": assignee_reason,
        }
    elif state.get("skill_output") and state["selected_skill"] == "prospection_weekly":
        output = state["skill_output"]
        org_id = state.get("org_id", state["input_data"].get("org_id"))

        if output.get("status") == "skipped":
            state["final_result"] = output
            return state

        # 1. Update Property Matchings
        for match in output.get("matchings", []):
            await neon_service.update_property_matching(match["property_id"], {
                "prospection_score": match["score"],
                "notes": {"matching_reason": match["reason"]}
            })

        # 2. Create Weekly Recap entry
        await neon_service.insert_weekly_recap({
            "org_id": org_id,
            "week_start": datetime.utcnow().date().isoformat(), # Simplified
            "week_end": datetime.utcnow().date().isoformat(),
            "metrics": {
                "leads_processed": output["leads_processed"],
                "properties_analyzed": output["properties_analyzed"],
                "matches_found": output["matches_found"]
            },
            "insights": output["luxury_summary"]
        })

        # 3. Insert into agent_executions
        await neon_service.insert_agent_execution({
            "org_id": org_id,
            "skill_id": state.get("agent_id"), # Assuming agent_id is in state
            "status": "COMPLETED",
            "input": state["input_data"],
            "output": output,
            "reasoning": f"Prospection completed: {output['matches_found']} matches found.",
            "execution_time_ms": 0, # Placeholder
            "completed_at": datetime.utcnow().isoformat()
        })

        state["final_result"] = output
    elif state.get("skill_output") and state["selected_skill"] == "recap_weekly":
        output = state["skill_output"]
        org_id = state.get("org_id", state["input_data"].get("org_id"))

        # 1. Insert Weekly Recap
        await neon_service.insert_weekly_recap({
            "org_id": org_id,
            "week_start": output["week_start"],
            "week_end": output["week_end"],
            "metrics": output["metrics"],
            "insights": output["luxury_summary"],
            "top_actions": {"action": output["top_action"]}
        })

        # 2. Insert into agent_executions
        await neon_service.insert_agent_execution({
            "org_id": org_id,
            "skill_id": state.get("agent_id"),
            "status": "COMPLETED",
            "input": state["input_data"],
            "output": output,
            "reasoning": f"Weekly recap generated for {output['week_start']} to {output['week_end']}.",
            "execution_time_ms": 0,
            "completed_at": datetime.utcnow().isoformat()
        })

        state["final_result"] = output
    return state

async def audit_logger_node(state: AgentState) -> AgentState:
    print("--- AUDIT LOGGER ---")
    from backend.services.neon_service import neon_service

    org_id = state.get("org_id", state["input_data"].get("org_id", neon_service.fixed_org_id))

    # Audit Log Entry (Constitutional Compliance Título X)
    audit_data = {
        "org_id": org_id,
        "actor_type": "agent",
        "actor_id": f"nexus-agent-{state['selected_skill']}",
        "action": f"{state['selected_skill']}.executed",
        "resource_type": "lead" if state['selected_skill'] == "lead_intake" else "agent_execution",
        "resource_id": str(state["input_data"].get("lead_id", state.get("agent_id", "unknown"))),
        "details": {
            "input": state["input_data"],
            "output": state.get("skill_output"),
            "status": state.get("status", "success")
        }
    }
    await neon_service.insert_audit_log(audit_data)

    # Agent Execution Log
    agent_log_data = {
        "org_id": org_id,
        "agent_name": f"Nexus {state['selected_skill'].capitalize()} Agent",
        "skill_name": state["selected_skill"],
        "input": state["input_data"],
        "output": state.get("skill_output"),
        "llm_model": state.get("skill_output", {}).get("llm_model", "runtime-default"),
        "tokens_used": state.get("skill_output", {}).get("tokens_used", 0),
        "status": "success" if not state.get("error") else "error"
    }
    await neon_service.insert_agent_log(agent_log_data)

    state["audit_logged"] = True
    return state

async def finalize_node(state: AgentState) -> AgentState:
    print("--- FINALIZE ---")
    if state.get("status") not in {"error", "blocked"}:
        state["status"] = "success"
    return state
