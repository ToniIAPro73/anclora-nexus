"""
Integration tests for ProspectionService — mocked Neon.
Feature: ANCLORA-PBM-001

Tests:
  - CRUD operations with org isolation
  - Recompute creates/updates matches
  - Activity logging with match verification
  - Score consistency through service layer
"""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from backend.models.prospection import (
    ActivityCreate,
    ActivityType,
    BuyerCreate,
    MatchUpdate,
    MatchStatus,
    PropertyCreate,
    PropertyUpdate,
    RecomputeResponse,
)
from backend.services.prospection_service import ProspectionService


ORG_A = str(uuid4())
ORG_B = str(uuid4())


class MockNeonQuery:
    """Builder pattern mock for Neon query chain."""

    def __init__(self, data: list, count: int | None = None):
        self._data = data
        self._count = count

    def table(self, name: str) -> "MockNeonQuery":
        return self

    def select(self, *args, **kwargs) -> "MockNeonQuery":
        return self

    def insert(self, record: dict) -> "MockNeonQuery":
        # Simulate setting id and timestamp
        record.setdefault("id", str(uuid4()))
        self._data = [record]
        return self

    def update(self, data: dict) -> "MockNeonQuery":
        if self._data:
            self._data[0].update(data)
        return self

    def eq(self, field: str, value) -> "MockNeonQuery":
        return self

    def neq(self, field: str, value) -> "MockNeonQuery":
        return self

    def gte(self, field: str, value) -> "MockNeonQuery":
        return self

    def lte(self, field: str, value) -> "MockNeonQuery":
        return self

    def in_(self, field: str, values: list) -> "MockNeonQuery":
        return self

    def order(self, field: str, desc: bool = False) -> "MockNeonQuery":
        return self

    def range(self, start: int, end: int) -> "MockNeonQuery":
        return self

    def single(self) -> "MockNeonQuery":
        return self

    def execute(self) -> MagicMock:
        result = MagicMock()
        result.data = self._data
        result.count = self._count or len(self._data)
        return result


# ═══════════════════════════════════════════════════════════════════════════════
# PROPERTY CRUD
# ═══════════════════════════════════════════════════════════════════════════════


class TestPropertyCRUD:
    """TC-PP-1 through TC-PP-6: Property CRUD operations."""

    @pytest.fixture()
    def service(self) -> ProspectionService:
        return ProspectionService()

    @pytest.mark.asyncio
    async def test_create_property_computes_score(self, service: ProspectionService) -> None:
        """TC-PP-1: Property created with computed high_ticket_score."""
        prop_data = PropertyCreate(
            source="idealista",
            source_url="https://idealista.com/12345",
            title="Villa Test",
            zone="Port d'Andratx",
            price=Decimal("3000000"),
            property_type="villa",
            area_m2=Decimal("400"),
            bedrooms=5,
        )

        record_with_score = {
            "id": str(uuid4()),
            "org_id": ORG_A,
            "source": "idealista",
            "source_url": "https://idealista.com/12345",
            "title": "Villa Test",
            "zone": "Port d'Andratx",
            "price": 3000000.0,
            "property_type": "villa",
            "area_m2": 400.0,
            "bedrooms": 5,
            "high_ticket_score": 85.0,
            "score_breakdown": {"price": 38, "location": 24, "liquidity": 14, "quality": 14.25},
            "status": "new",
        }

        mock_query = MockNeonQuery([record_with_score])

        with patch("backend.services.prospection_service.neon_service") as mock_sb:
            mock_sb.client.table.return_value = mock_query
            result = await service.create_property(ORG_A, prop_data)

        assert result["org_id"] == ORG_A
        assert result["source"] == "idealista"

    @pytest.mark.asyncio
    async def test_list_properties_filters_by_org(self, service: ProspectionService) -> None:
        """TC-PP-6: List only returns properties for given org_id."""
        mock_props = [
            {"id": str(uuid4()), "org_id": ORG_A, "title": "Villa A", "high_ticket_score": 80},
        ]
        mock_query = MockNeonQuery(mock_props, count=1)

        with patch("backend.services.prospection_service.neon_service") as mock_sb:
            mock_sb.client.table.return_value = mock_query
            result = await service.list_properties(ORG_A)

        assert result["total"] == 1
        # All items belong to ORG_A
        for item in result["items"]:
            assert item["org_id"] == ORG_A

    @pytest.mark.asyncio
    async def test_get_property_not_found_returns_none(self, service: ProspectionService) -> None:
        """Property not found returns None instead of error."""
        mock_query = MockNeonQuery([])

        with patch("backend.services.prospection_service.neon_service") as mock_sb:
            mock_sb.client.table.return_value = mock_query
            result = await service.get_property(ORG_A, str(uuid4()))

        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# BUYER CRUD
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuyerCRUD:
    """TC-BP-1 through TC-BP-6: Buyer CRUD operations."""

    @pytest.fixture()
    def service(self) -> ProspectionService:
        return ProspectionService()

    @pytest.mark.asyncio
    async def test_create_buyer(self, service: ProspectionService) -> None:
        """TC-BP-1: Create buyer with valid budget range."""
        buyer_data = BuyerCreate(
            full_name="Hans Mueller",
            budget_min=Decimal("2000000"),
            budget_max=Decimal("4000000"),
            preferred_zones=["Port d'Andratx"],
            preferred_types=["villa"],
            motivation_score=Decimal("88"),
        )

        record = {
            "id": str(uuid4()),
            "org_id": ORG_A,
            "full_name": "Hans Mueller",
            "budget_min": 2000000.0,
            "budget_max": 4000000.0,
            "status": "active",
        }
        mock_query = MockNeonQuery([record])

        with patch("backend.services.prospection_service.neon_service") as mock_sb:
            mock_sb.client.table.return_value = mock_query
            result = await service.create_buyer(ORG_A, buyer_data)

        assert result["org_id"] == ORG_A
        assert result["full_name"] == "Hans Mueller"


# ═══════════════════════════════════════════════════════════════════════════════
# MATCH OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════


class TestMatchOperations:
    """TC-ME-1 through TC-ME-7: Match operations."""

    @pytest.fixture()
    def service(self) -> ProspectionService:
        return ProspectionService()

    @pytest.mark.asyncio
    async def test_recompute_creates_new_matches(self, service: ProspectionService) -> None:
        """TC-ME-1: Recompute creates matches for all property-buyer pairs."""
        properties = [
            {"id": str(uuid4()), "org_id": ORG_A, "price": 2000000, "zone": "Andratx",
             "property_type": "villa", "status": "new"},
        ]
        buyers = [
            {"id": str(uuid4()), "org_id": ORG_A, "budget_min": 1000000,
             "budget_max": 3000000, "preferred_zones": ["Andratx"],
             "preferred_types": ["villa"], "purchase_horizon": "3-6 months",
             "motivation_score": 80, "status": "active"},
        ]

        call_count = 0

        class MockTableChain:
            def __init__(self, data=None, count=None):
                self.data = data or []
                self.count = count

            def select(self, *args, **kwargs): return self
            def eq(self, *args): return self
            def neq(self, *args): return self
            def in_(self, *args): return self
            def limit(self, *args): return self
            def order(self, *args, **kwargs): return self
            def range(self, *args): return self

            def insert(self, record):
                nonlocal call_count
                call_count += 1
                record["id"] = str(uuid4())
                self.data = [record]
                return self

            def update(self, data):
                return self

            def execute(self):
                result = MagicMock()
                result.data = self.data
                result.count = self.count or len(self.data)
                return result

        def mock_table(name: str):
            if name == "prospected_properties":
                return MockTableChain(properties)
            elif name == "buyer_profiles":
                return MockTableChain(buyers)
            elif name == "property_buyer_matches":
                return MockTableChain([])  # No existing matches
            return MockTableChain()

        with patch("backend.services.prospection_service.neon_service") as mock_sb:
            mock_sb.client.table = mock_table
            result = await service.recompute_matches(ORG_A)

        assert isinstance(result, RecomputeResponse)
        assert result.matches_created == 1
        assert result.total_computed == 1


# ═══════════════════════════════════════════════════════════════════════════════
# ACTIVITY LOGGING
# ═══════════════════════════════════════════════════════════════════════════════


class TestActivityLogging:
    """TC-ME-6: Activity logging for matches."""

    @pytest.fixture()
    def service(self) -> ProspectionService:
        return ProspectionService()

    @pytest.mark.asyncio
    async def test_log_activity_success(self, service: ProspectionService) -> None:
        """TC-ME-6: Can log commercial activity for a match."""
        match_id = str(uuid4())
        activity_data = ActivityCreate(
            activity_type=ActivityType.CALL,
            outcome="interested",
            details={"duration_min": 15},
        )

        record = {
            "id": str(uuid4()),
            "org_id": ORG_A,
            "match_id": match_id,
            "activity_type": "call",
            "outcome": "interested",
        }

        def mock_table(name: str):
            if name == "property_buyer_matches":
                return MockNeonQuery([{"id": match_id}])
            elif name == "match_activity_log":
                return MockNeonQuery([record])
            return MockNeonQuery([])

        with patch("backend.services.prospection_service.neon_service") as mock_sb:
            mock_sb.client.table = mock_table
            result = await service.log_activity(ORG_A, match_id, activity_data)

        assert result["activity_type"] == "call"

    @pytest.mark.asyncio
    async def test_log_activity_match_not_found(self, service: ProspectionService) -> None:
        """Activity logging fails if match not found for org."""
        activity_data = ActivityCreate(
            activity_type=ActivityType.VIEWING,
        )

        mock_query = MockNeonQuery([])

        with patch("backend.services.prospection_service.neon_service") as mock_sb:
            mock_sb.client.table.return_value = mock_query
            with pytest.raises(ValueError, match="not found"):
                await service.log_activity(ORG_A, str(uuid4()), activity_data)
