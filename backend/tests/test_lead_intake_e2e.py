import asyncio
import json
import os
import pytest
from uuid import uuid4
from backend.agents.graph import agent_executor
from backend.agents.state import AgentState

# Live E2E: executes the real agent graph against a reachable Neon
# instance (requires NEXUS_RUN_LIVE_E2E=1 and valid credentials in .env).
@pytest.mark.skipif(
    os.environ.get("NEXUS_RUN_LIVE_E2E") != "1",
    reason="live E2E requires reachable Neon; set NEXUS_RUN_LIVE_E2E=1 to run",
)
@pytest.mark.asyncio
async def test_lead_intake():
    print("🚀 Starting Lead Intake E2E Test...")

    # Mock lead input
    test_input = {
        "lead_id": str(uuid4()), # In real n8n flow, this would be an actual UUID from Neon
        "name": "Juan Palomo",
        "email": "juan.palomo@mallorca-luxury.com",
        "phone": "+34 600 000 000",
        "property_interest": "Villa in Andratx",
        "budget_range": "3-5M",
        "urgency": "immediate",
        "source": "website_form"
    }

    # Initial state
    initial_state: AgentState = {
        "input_data": test_input,
        "skill_name": "lead_intake",
        "org_id": "00000000-0000-0000-0000-000000000000", # Seed org ID
        "user_id": "system",
        "plan": None,
        "selected_skill": None,
        "limits_ok": False,
        "limit_violation": None,
        "skill_output": None,
        "error": None,
        "audit_logged": False,
        "agent_log_id": None,
        "final_result": None,
        "status": "running"
    }

    print(f"📊 Sending input to agent: {json.dumps(test_input, indent=2)}")

    # Execute graph
    async for output in agent_executor.astream(initial_state):
        for node_name, state_update in output.items():
            print(f"✅ Node [{node_name}] finished.")
            if state_update.get("error"):
                print(f"❌ Error in node {node_name}: {state_update['error']}")

    print("\n🏁 State after execution:")
    # Note: agent_executor.astream returns updates, to get final state we'd usually use ainvoke or collect updates
    # But for a quick test, we check if it finished without unhandled exceptions
    print("Verification complete. Check Neon 'leads', 'tasks', 'audit_log', and 'agent_logs' for results.")

if __name__ == "__main__":
    try:
        asyncio.run(test_lead_intake())
    except Exception as e:
        print(f"🚨 Test failed with exception: {e}")
