"""
Integration tests for ProspectionService — CSL Editability Contract.
Feature: ANCLORA-CSL-001
"""

import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4
from decimal import Decimal

from backend.models.prospection import PropertyUpdate, PropertySourceSystem
from backend.services.prospection_service import ProspectionService

@pytest.fixture
def service():
    return ProspectionService()

@pytest.fixture
def org_id():
    return str(uuid4())

@pytest.fixture
def property_id():
    return str(uuid4())

@pytest.mark.asyncio
async def test_update_property_manual_origin_allows_all(service, org_id, property_id):
    """Properties with 'manual' origin should allow all updates."""
    mock_existing = {
        "id": property_id,
        "org_id": org_id,
        "source_system": "manual",
        "source": "direct"
    }
    
    update_data = PropertyUpdate(
        title="New Title",
        source="mls", # Attempt to change source
        price=Decimal("1000000")
    )

    with patch.object(service, "get_property", return_value=mock_existing), \
         patch("backend.services.prospection_service.neon_service") as mock_neon:
        
        mock_neon.client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value.data = [mock_existing]
        
        await service.update_property(org_id, property_id, update_data)
        
        # Verify that 'source' WAS included in the update call
        call_args = mock_neon.client.table.return_value.update.call_args[0][0]
        assert "title" in call_args
        assert "source" in call_args
        assert call_args["source"] == "mls"

@pytest.mark.asyncio
async def test_update_property_widget_origin_protects_trace(service, org_id, property_id):
    """Properties with 'widget' origin should protect trace fields."""
    mock_existing = {
        "id": property_id,
        "org_id": org_id,
        "source_system": "widget",
        "source": "idealista"
    }
    
    update_data = PropertyUpdate(
        title="Enhanced Title",
        source="fotocasa" # Attempt to change source (should be protected)
    )

    with patch.object(service, "get_property", return_value=mock_existing), \
         patch("backend.services.prospection_service.neon_service") as mock_neon:
        
        mock_neon.client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value.data = [mock_existing]
        
        await service.update_property(org_id, property_id, update_data)
        
        call_args = mock_neon.client.table.return_value.update.call_args[0][0]
        assert "title" in call_args
        assert "source" not in call_args # protected

@pytest.mark.asyncio
async def test_update_property_pbm_origin_protects_trace_and_scoring(service, org_id, property_id):
    """Properties with 'pbm' origin should protect trace and scoring fields."""
    mock_existing = {
        "id": property_id,
        "org_id": org_id,
        "source_system": "pbm",
        "high_ticket_score": 85.0
    }
    
    # We use a dict to simulate fields not in PropertyUpdate if needed, 
    # but for this test we check if they are stripped IF provided.
    # Note: PropertyUpdate doesn't even have high_ticket_score, but the service strips it anyway for safety.
    
    update_data = PropertyUpdate(
        notes="Important notes",
        source_system=PropertySourceSystem.MANUAL # Attempt to change origin
    )

    with patch.object(service, "get_property", return_value=mock_existing), \
         patch("backend.services.prospection_service.neon_service") as mock_neon:
        
        mock_neon.client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value.data = [mock_existing]
        
        await service.update_property(org_id, property_id, update_data)
        
        call_args = mock_neon.client.table.return_value.update.call_args[0][0]
        assert "notes" in call_args
        assert "source_system" not in call_args # protected

@pytest.mark.asyncio
async def test_update_property_decimals_conversion(service, org_id, property_id):
    """Decimals should be converted to floats for Neon."""
    mock_existing = {"id": property_id, "org_id": org_id, "source_system": "manual"}
    update_data = PropertyUpdate(useful_area_m2=Decimal("123.45"))

    with patch.object(service, "get_property", return_value=mock_existing), \
         patch("backend.services.prospection_service.neon_service") as mock_neon:
        
        mock_neon.client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value.data = [mock_existing]
        
        await service.update_property(org_id, property_id, update_data)
        
        call_args = mock_neon.client.table.return_value.update.call_args[0][0]
        assert isinstance(call_args["useful_area_m2"], float)
        assert call_args["useful_area_m2"] == 123.45
