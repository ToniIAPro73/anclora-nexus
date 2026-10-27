import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

from backend.models.prospection import (
    PropertyCreate,
    PropertySourceSystem,
    PropertySourcePortal,
)
from backend.services.prospection_service import ProspectionService

ORG_A = str(uuid4())

class MockNeonQuery:
    def __init__(self, data: list):
        self._data = data

    def table(self, name: str): return self
    def select(self, *args, **kwargs): return self
    def insert(self, record: dict):
        self._data = [record]
        return self
    def update(self, data: dict):
        if self._data: self._data[0].update(data)
        return self
    def eq(self, *args): return self
    def neq(self, *args): return self
    def gte(self, *args): return self
    def order(self, *args, **kwargs): return self
    def range(self, *args, **kwargs): return self
    def execute(self):
        result = MagicMock()
        result.data = self._data
        result.count = len(self._data)
        return result

@pytest.mark.asyncio
async def test_create_property_with_origin():
    service = ProspectionService()
    prop_data = PropertyCreate(
        source="idealista",
        title="Test Villa",
        price=Decimal("1000000"),
        source_system=PropertySourceSystem.WIDGET,
        source_portal=PropertySourcePortal.IDEALISTA
    )

    mock_query = MockNeonQuery([])
    with patch("backend.services.prospection_service.neon_service") as mock_sb:
        mock_sb.client.table.return_value = mock_query
        result = await service.create_property(ORG_A, prop_data)

    assert result["source_system"] == "widget"
    assert result["source_portal"] == "idealista"
    assert result["org_id"] == ORG_A

@pytest.mark.asyncio
async def test_create_property_default_origin():
    service = ProspectionService()
    prop_data = PropertyCreate(
        source="idealista",
        title="Test Villa",
        price=Decimal("1000000")
        # source_system defaults to manual
    )

    mock_query = MockNeonQuery([])
    with patch("backend.services.prospection_service.neon_service") as mock_sb:
        mock_sb.client.table.return_value = mock_query
        result = await service.create_property(ORG_A, prop_data)

    assert result["source_system"] == "manual"
    assert result.get("source_portal") is None

@pytest.mark.asyncio
async def test_property_organization_isolation():
    service = ProspectionService()
    ORG_B = str(uuid4())
    
    prop_data = PropertyCreate(
        source="idealista",
        title="Org A Property",
        price=Decimal("1000000")
    )

    mock_query = MockNeonQuery([])
    with patch("backend.services.prospection_service.neon_service") as mock_sb:
        mock_sb.client.table.return_value = mock_query
        # Create in ORG_A
        await service.create_property(ORG_A, prop_data)
        
        # Verify query for ORG_B returns nothing (mock behavior)
        # Note: In a real integration test we would check the .eq("org_id", ...) call
        # but for this unit mock test, we verify the service passes the correct org_id.
        
        with patch.object(mock_query, "eq", wraps=mock_query.eq) as mock_eq:
            await service.list_properties(ORG_B)
            mock_eq.assert_any_call("org_id", ORG_B)

@pytest.mark.asyncio
async def test_normalize_portal_validation():
    # Test normalization logic in model
    prop_data = PropertyCreate(
        source="idealista",
        title="Test Villa",
        price=Decimal("1000000"),
        source_portal="IDEALISTA " # Mixed case and space
    )
    assert prop_data.source_portal == PropertySourcePortal.IDEALISTA

    prop_data_other = PropertyCreate(
        source="idealista",
        title="Test Villa",
        price=Decimal("1000000"),
        source_portal="unknown-portal"
    )
    assert prop_data_other.source_portal == PropertySourcePortal.OTHER
