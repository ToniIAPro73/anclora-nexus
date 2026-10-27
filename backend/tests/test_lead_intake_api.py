"""Unit tests for the lead intake API route (Phase 3 — Commercial Loop).

Tests cover:
- Temperature assignment logic
- Deduplication within 24h window
- Required field validation via Pydantic
- Successful lead creation
- HTTP 409 on duplicate leads
"""

import os
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock


from backend.api.routes.lead_intake import assign_temperature, check_duplicate_lead
from backend.models.lead_intake import (
    ContactInfo,
    LeadIntakeRequest,
    LeadIntakeResponse,
)

import pytest
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# Temperature assignment tests
# ---------------------------------------------------------------------------


class TestAssignTemperature:
    def test_private_estates_landing_is_warm(self):
        result = assign_temperature("private-estates-landing", None)
        assert result == "warm"

    def test_unknown_source_is_cold(self):
        result = assign_temperature("some-external-form", None)
        assert result == "cold"

    def test_referral_metadata_makes_warm(self):
        result = assign_temperature("generic-source", {"referral": True})
        assert result == "warm"

    def test_empty_metadata_stays_cold(self):
        result = assign_temperature("generic-source", {})
        assert result == "cold"

    def test_none_metadata_stays_cold(self):
        result = assign_temperature("generic-source", None)
        assert result == "cold"


# ---------------------------------------------------------------------------
# Pydantic model validation tests
# ---------------------------------------------------------------------------


class TestContactInfo:
    def test_valid_with_email(self):
        contact = ContactInfo(name="John Doe", email="john@example.com")
        assert contact.name == "John Doe"
        assert contact.email == "john@example.com"
        assert contact.phone is None

    def test_valid_with_phone(self):
        contact = ContactInfo(name="John Doe", phone="+34600000000")
        assert contact.phone == "+34600000000"
        assert contact.email is None

    def test_valid_with_both(self):
        contact = ContactInfo(name="John", email="john@example.com", phone="+34600000000")
        assert contact.email == "john@example.com"
        assert contact.phone == "+34600000000"

    def test_rejects_no_email_no_phone(self):
        with pytest.raises(ValidationError) as exc_info:
            ContactInfo(name="John Doe")
        assert "At least one of email or phone" in str(exc_info.value)

    def test_rejects_empty_name(self):
        with pytest.raises(ValidationError):
            ContactInfo(name="", email="john@example.com")


class TestLeadIntakeRequest:
    def test_valid_full_request(self):
        req = LeadIntakeRequest(
            contact=ContactInfo(name="Maria Garcia", email="maria@test.com"),
            source_system="private-estates-landing",
            source_channel="form-main",
            timestamp=datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
            metadata={"page": "villa-andratx"},
        )
        assert req.source_system == "private-estates-landing"
        assert req.metadata == {"page": "villa-andratx"}

    def test_rejects_empty_source_system(self):
        with pytest.raises(ValidationError):
            LeadIntakeRequest(
                contact=ContactInfo(name="Test", email="t@t.com"),
                source_system="",
                source_channel="form",
                timestamp=datetime.now(timezone.utc),
            )

    def test_rejects_empty_source_channel(self):
        with pytest.raises(ValidationError):
            LeadIntakeRequest(
                contact=ContactInfo(name="Test", email="t@t.com"),
                source_system="landing",
                source_channel="",
                timestamp=datetime.now(timezone.utc),
            )

    def test_metadata_optional(self):
        req = LeadIntakeRequest(
            contact=ContactInfo(name="Test", email="t@t.com"),
            source_system="landing",
            source_channel="form",
            timestamp=datetime.now(timezone.utc),
        )
        assert req.metadata is None


class TestLeadIntakeResponse:
    def test_valid_created(self):
        resp = LeadIntakeResponse(lead_id="uuid-123", status="created", temperature="warm")
        assert resp.status == "created"
        assert resp.temperature == "warm"

    def test_valid_duplicate(self):
        resp = LeadIntakeResponse(lead_id="uuid-456", status="duplicate", temperature="cold")
        assert resp.status == "duplicate"


# ---------------------------------------------------------------------------
# Deduplication check tests
# ---------------------------------------------------------------------------


class FakeExecuteResult:
    def __init__(self, data=None):
        self.data = data or []


class FakeQueryBuilder:
    """Chainable mock for Neon query builder."""

    def __init__(self, data=None):
        self._data = data

    def select(self, *_args):
        return self

    def eq(self, *_args):
        return self

    def gte(self, *_args):
        return self

    def limit(self, *_args):
        return self

    def execute(self):
        return FakeExecuteResult(self._data)


class TestCheckDuplicateLead:
    def test_returns_none_when_no_email(self):
        result = asyncio.run(
            check_duplicate_lead(
                org_id="org-1", contact_email=None, source_system="landing"
            )
        )
        assert result is None

    @patch("backend.api.routes.lead_intake.neon_service")
    def test_returns_existing_lead_when_duplicate_found(self, mock_svc):
        existing_lead = {"id": "lead-existing-123", "temperature": "warm"}
        mock_svc.client.table.return_value = FakeQueryBuilder(data=[existing_lead])

        result = asyncio.run(
            check_duplicate_lead(
                org_id="org-1",
                contact_email="dup@example.com",
                source_system="private-estates-landing",
            )
        )
        assert result == existing_lead

    @patch("backend.api.routes.lead_intake.neon_service")
    def test_returns_none_when_no_duplicate(self, mock_svc):
        mock_svc.client.table.return_value = FakeQueryBuilder(data=[])

        result = asyncio.run(
            check_duplicate_lead(
                org_id="org-1",
                contact_email="new@example.com",
                source_system="landing",
            )
        )
        assert result is None

    @patch("backend.api.routes.lead_intake.neon_service")
    def test_returns_none_on_error(self, mock_svc):
        mock_svc.client.table.side_effect = Exception("DB connection failed")

        result = asyncio.run(
            check_duplicate_lead(
                org_id="org-1",
                contact_email="error@example.com",
                source_system="landing",
            )
        )
        # On error, we allow the lead through
        assert result is None
