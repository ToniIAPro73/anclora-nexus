import pytest
from pydantic import ValidationError
from sdd.features.intelligence.skills.lead_intake import LeadInput
from backend.agents.nodes.all_nodes import result_handler_node
from unittest.mock import AsyncMock, patch

def test_lead_input_validation():
    print("RUNNING: test_lead_input_validation")
    # Valid input
    valid_data = {
        "name": "John Doe",
        "email": "john@example.com",
        "source_system": "cta_web",
        "source_channel": "website",
        "ingestion_mode": "realtime"
    }
    lead = LeadInput(**valid_data)
    assert lead.source_system == "cta_web"
    
    # Invalid system
    invalid_data = valid_data.copy()
    invalid_data["source_system"] = "invalid_system"
    with pytest.raises(ValidationError):
        LeadInput(**invalid_data)

    # Invalid channel
    invalid_data = valid_data.copy()
    invalid_data["source_channel"] = "invalid_channel"
    with pytest.raises(ValidationError):
        LeadInput(**invalid_data)

@pytest.mark.asyncio
async def test_result_handler_origin_mapping():
    mock_db = AsyncMock()
    mock_db.fixed_org_id = "00000000-0000-0000-0000-000000000000"
    mock_db.insert_lead.return_value = {"id": "new-lead-uuid"}
    
    state = {
        "skill_output": {
            "ai_summary": "Summary",
            "ai_priority": 3,
            "priority_score": 0.5,
            "next_action": "email_48h",
            "copy_email": "Draft",
            "copy_whatsapp": "Draft",
            "processed_at": "2024-01-01T00:00:00",
            "task_due_date": "2024-01-03T00:00:00"
        },
        "selected_skill": "lead_intake",
        "input_data": {
            "name": "Jane Doe",
            "source": "manual-linkedin", # Legacy source
        },
        "org_id": "org-uuid"
    }
    
    with patch("backend.services.neon_service.neon_service", mock_db):
        await result_handler_node(state)
        
        # Verify insert_lead call
        args, kwargs = mock_db.insert_lead.call_args
        lead_data = args[0]
        
        # Check mapping logic
        assert lead_data["source"] == "manual-linkedin"
        assert lead_data["source_system"] == "manual" # Fallback
        assert lead_data["source_channel"] == "linkedin" # Fallback from legacy
        assert lead_data["ingestion_mode"] == "manual"
        assert "captured_at" in lead_data

@pytest.mark.asyncio
async def test_result_handler_direct_origin():
    mock_db = AsyncMock()
    mock_db.fixed_org_id = "00000000-0000-0000-0000-000000000000"
    mock_db.insert_lead.return_value = {"id": "new-lead-uuid"}
    
    state = {
        "skill_output": {
            "ai_summary": "Summary",
            "ai_priority": 3,
            "priority_score": 0.5,
            "next_action": "email_48h",
            "copy_email": "Draft",
            "copy_whatsapp": "Draft",
            "processed_at": "2024-01-01T00:00:00",
            "task_due_date": "2024-01-03T00:00:00"
        },
        "selected_skill": "lead_intake",
        "input_data": {
            "name": "Direct Lead",
            "source_system": "referral",
            "source_channel": "phone",
            "ingestion_mode": "batch"
        }
    }
    
    with patch("backend.services.neon_service.neon_service", mock_db):
        await result_handler_node(state)
        
        args, kwargs = mock_db.insert_lead.call_args
        lead_data = args[0]
        
        assert lead_data["source_system"] == "referral"
        assert lead_data["source_channel"] == "phone"
        assert lead_data["ingestion_mode"] == "batch"
