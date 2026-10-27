"""Unit tests for lead pipeline reporting and staleness detection service.

Tests cover:
- Pipeline metrics computation (temperature, owner, funnel)
- Staleness detection logic (48h threshold, no next_action_due)
- Command Center event emission on temperature/owner changes
- Edge cases (empty data, missing fields, various date formats)

Requirements: 14.1, 14.2, 14.3, 14.4
"""

import os
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock


import pytest

from backend.models.lead_pipeline import (
    FunnelStage,
    LeadPipelineEvent,
    OwnerMetrics,
    PipelineMetricsResponse,
    StaleLeadInfo,
    TemperatureMetrics,
)
from backend.services.lead_pipeline_service import LeadPipelineService, STALENESS_HOURS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_lead(
    lead_id: str = "lead-001",
    temperature: str = "cold",
    status: str = "new",
    assigned_owner: str | None = None,
    next_action_due: str | None = None,
    created_at: str | None = None,
    contact_name: str = "Test User",
) -> dict:
    if created_at is None:
        created_at = datetime.now(timezone.utc).isoformat()
    return {
        "id": lead_id,
        "org_id": "org-123",
        "contact_name": contact_name,
        "contact_email": f"{lead_id}@test.com",
        "temperature": temperature,
        "status": status,
        "assigned_owner": assigned_owner,
        "next_action_due": next_action_due,
        "created_at": created_at,
    }


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

    def insert(self, _data):
        return self

    def update(self, _data):
        return self

    def execute(self):
        return FakeExecuteResult(self._data)


# ---------------------------------------------------------------------------
# Temperature metrics tests
# ---------------------------------------------------------------------------


class TestTemperatureMetrics:
    def test_counts_by_temperature(self):
        service = LeadPipelineService.__new__(LeadPipelineService)
        leads = [
            make_lead(lead_id="1", temperature="cold"),
            make_lead(lead_id="2", temperature="cold"),
            make_lead(lead_id="3", temperature="warm"),
            make_lead(lead_id="4", temperature="hot"),
            make_lead(lead_id="5", temperature="hot"),
            make_lead(lead_id="6", temperature="hot"),
        ]
        result = service._compute_temperature_metrics(leads)
        assert result.cold == 2
        assert result.warm == 1
        assert result.hot == 3

    def test_empty_leads(self):
        service = LeadPipelineService.__new__(LeadPipelineService)
        result = service._compute_temperature_metrics([])
        assert result.cold == 0
        assert result.warm == 0
        assert result.hot == 0


# ---------------------------------------------------------------------------
# Owner metrics tests
# ---------------------------------------------------------------------------


class TestOwnerMetrics:
    def test_groups_by_owner(self):
        service = LeadPipelineService.__new__(LeadPipelineService)
        leads = [
            make_lead(lead_id="1", assigned_owner="owner-a"),
            make_lead(lead_id="2", assigned_owner="owner-a"),
            make_lead(lead_id="3", assigned_owner="owner-b"),
            make_lead(lead_id="4", assigned_owner=None),
        ]
        result = service._compute_owner_metrics(leads)
        assert len(result) == 3
        # Sorted by count descending
        assert result[0].owner_id == "owner-a"
        assert result[0].count == 2
        assert result[1].owner_id == "owner-b"
        assert result[1].count == 1

    def test_unassigned_leads_grouped_under_none(self):
        service = LeadPipelineService.__new__(LeadPipelineService)
        leads = [
            make_lead(lead_id="1", assigned_owner=None),
            make_lead(lead_id="2", assigned_owner=None),
        ]
        result = service._compute_owner_metrics(leads)
        assert len(result) == 1
        assert result[0].owner_id is None
        assert result[0].count == 2


# ---------------------------------------------------------------------------
# Funnel metrics tests
# ---------------------------------------------------------------------------


class TestFunnelMetrics:
    def test_counts_per_stage(self):
        service = LeadPipelineService.__new__(LeadPipelineService)
        leads = [
            make_lead(lead_id="1", status="new"),
            make_lead(lead_id="2", status="new"),
            make_lead(lead_id="3", status="contacted"),
            make_lead(lead_id="4", status="qualified"),
            make_lead(lead_id="5", status="converted"),
        ]
        result = service._compute_funnel_metrics(leads)
        stages = {s.stage: s.count for s in result}
        assert stages["new"] == 2
        assert stages["contacted"] == 1
        assert stages["qualified"] == 1
        assert stages["converted"] == 1
        assert stages["lost"] == 0

    def test_stale_leads_counted_as_new(self):
        service = LeadPipelineService.__new__(LeadPipelineService)
        leads = [
            make_lead(lead_id="1", status="stale"),
            make_lead(lead_id="2", status="new"),
        ]
        result = service._compute_funnel_metrics(leads)
        stages = {s.stage: s.count for s in result}
        assert stages["new"] == 2


# ---------------------------------------------------------------------------
# Staleness detection tests
# ---------------------------------------------------------------------------


class TestStalenessDetection:
    def test_detects_stale_lead_no_action_older_than_48h(self):
        service = LeadPipelineService.__new__(LeadPipelineService)
        old_time = (datetime.now(timezone.utc) - timedelta(hours=72)).isoformat()
        leads = [
            make_lead(lead_id="stale-1", next_action_due=None, created_at=old_time, status="new"),
        ]
        result = service._detect_stale_leads(leads)
        assert len(result) == 1
        assert result[0].lead_id == "stale-1"
        assert result[0].days_since_creation >= 2.5

    def test_ignores_lead_with_next_action_due(self):
        service = LeadPipelineService.__new__(LeadPipelineService)
        old_time = (datetime.now(timezone.utc) - timedelta(hours=72)).isoformat()
        future_action = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        leads = [
            make_lead(lead_id="active-1", next_action_due=future_action, created_at=old_time, status="new"),
        ]
        result = service._detect_stale_leads(leads)
        assert len(result) == 0

    def test_ignores_recent_lead_without_action(self):
        service = LeadPipelineService.__new__(LeadPipelineService)
        recent = (datetime.now(timezone.utc) - timedelta(hours=12)).isoformat()
        leads = [
            make_lead(lead_id="recent-1", next_action_due=None, created_at=recent, status="new"),
        ]
        result = service._detect_stale_leads(leads)
        assert len(result) == 0

    def test_ignores_terminal_status_leads(self):
        service = LeadPipelineService.__new__(LeadPipelineService)
        old_time = (datetime.now(timezone.utc) - timedelta(hours=72)).isoformat()
        leads = [
            make_lead(lead_id="conv-1", next_action_due=None, created_at=old_time, status="converted"),
            make_lead(lead_id="lost-1", next_action_due=None, created_at=old_time, status="lost"),
            make_lead(lead_id="stale-1", next_action_due=None, created_at=old_time, status="stale"),
        ]
        result = service._detect_stale_leads(leads)
        assert len(result) == 0

    def test_handles_z_suffix_timestamps(self):
        service = LeadPipelineService.__new__(LeadPipelineService)
        old_time = (datetime.now(timezone.utc) - timedelta(hours=72)).strftime("%Y-%m-%dT%H:%M:%SZ")
        leads = [
            make_lead(lead_id="z-lead", next_action_due=None, created_at=old_time, status="contacted"),
        ]
        result = service._detect_stale_leads(leads)
        assert len(result) == 1
        assert result[0].lead_id == "z-lead"

    def test_multiple_stale_leads(self):
        service = LeadPipelineService.__new__(LeadPipelineService)
        old_time_1 = (datetime.now(timezone.utc) - timedelta(hours=60)).isoformat()
        old_time_2 = (datetime.now(timezone.utc) - timedelta(hours=96)).isoformat()
        leads = [
            make_lead(lead_id="s1", next_action_due=None, created_at=old_time_1, status="new"),
            make_lead(lead_id="s2", next_action_due=None, created_at=old_time_2, status="contacted"),
        ]
        result = service._detect_stale_leads(leads)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Command Center event emission tests
# ---------------------------------------------------------------------------


class TestCommandCenterEvents:
    @patch("backend.services.lead_pipeline_service.neon_service")
    def test_emit_temperature_change_event(self, mock_svc):
        mock_table = MagicMock()
        mock_svc.client.table.return_value = mock_table
        mock_table.insert.return_value = mock_table
        mock_table.execute.return_value = FakeExecuteResult()

        service = LeadPipelineService()

        asyncio.run(
            service.emit_temperature_change_event(
                org_id="org-123",
                lead_id="lead-001",
                old_temperature="cold",
                new_temperature="hot",
            )
        )

        mock_svc.client.table.assert_called_with("automation_alerts")
        inserted_row = mock_table.insert.call_args[0][0]
        assert inserted_row["org_id"] == "org-123"
        assert inserted_row["alert_type"] == "temperature_change"
        assert inserted_row["alert_scope"] == "lead_pipeline"
        assert inserted_row["metadata_json"]["lead_id"] == "lead-001"
        assert inserted_row["metadata_json"]["old_value"] == "cold"
        assert inserted_row["metadata_json"]["new_value"] == "hot"

    @patch("backend.services.lead_pipeline_service.neon_service")
    def test_emit_owner_change_event(self, mock_svc):
        mock_table = MagicMock()
        mock_svc.client.table.return_value = mock_table
        mock_table.insert.return_value = mock_table
        mock_table.execute.return_value = FakeExecuteResult()

        service = LeadPipelineService()

        asyncio.run(
            service.emit_owner_change_event(
                org_id="org-123",
                lead_id="lead-002",
                old_owner=None,
                new_owner="owner-xyz",
            )
        )

        mock_svc.client.table.assert_called_with("automation_alerts")
        inserted_row = mock_table.insert.call_args[0][0]
        assert inserted_row["alert_type"] == "owner_change"
        assert inserted_row["metadata_json"]["old_value"] is None
        assert inserted_row["metadata_json"]["new_value"] == "owner-xyz"

    @patch("backend.services.lead_pipeline_service.neon_service")
    def test_emit_staleness_alert(self, mock_svc):
        mock_table = MagicMock()
        mock_svc.client.table.return_value = mock_table
        mock_table.insert.return_value = mock_table
        mock_table.execute.return_value = FakeExecuteResult()

        service = LeadPipelineService()

        stale = StaleLeadInfo(
            lead_id="lead-stale-1",
            contact_name="Stale User",
            assigned_owner="owner-abc",
            temperature="cold",
            created_at="2026-01-01T00:00:00+00:00",
            days_since_creation=5.2,
        )

        service._emit_staleness_alert("org-123", stale)

        mock_svc.client.table.assert_called_with("automation_alerts")
        inserted_row = mock_table.insert.call_args[0][0]
        assert inserted_row["alert_type"] == "lead_stale"
        assert inserted_row["alert_scope"] == "lead_pipeline"
        assert "idle for 5.2 days" in inserted_row["message"]
        assert inserted_row["metadata_json"]["assigned_owner"] == "owner-abc"


# ---------------------------------------------------------------------------
# Full pipeline metrics integration
# ---------------------------------------------------------------------------


class TestGetPipelineMetrics:
    @patch("backend.services.lead_pipeline_service.neon_service")
    def test_returns_full_metrics(self, mock_svc):
        now = datetime.now(timezone.utc)
        old_time = (now - timedelta(hours=72)).isoformat()
        recent_time = (now - timedelta(hours=12)).isoformat()

        fake_leads = [
            make_lead(lead_id="1", temperature="cold", status="new", created_at=old_time),
            make_lead(lead_id="2", temperature="warm", status="contacted", assigned_owner="owner-a", next_action_due=(now + timedelta(days=1)).isoformat(), created_at=recent_time),
            make_lead(lead_id="3", temperature="hot", status="qualified", assigned_owner="owner-a", next_action_due=(now + timedelta(days=2)).isoformat(), created_at=recent_time),
            make_lead(lead_id="4", temperature="cold", status="converted", created_at=old_time),
        ]

        mock_table = MagicMock()
        mock_svc.client.table.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.execute.return_value = FakeExecuteResult(data=fake_leads)

        service = LeadPipelineService()
        result = asyncio.run(service.get_pipeline_metrics("org-123"))

        assert result.total_leads == 4
        assert result.by_temperature.cold == 2
        assert result.by_temperature.warm == 1
        assert result.by_temperature.hot == 1
        # Lead 1 is stale: old, no next_action_due, status=new
        assert result.stale_count == 1
        assert result.stale_leads[0].lead_id == "1"


# ---------------------------------------------------------------------------
# Timestamp parsing tests
# ---------------------------------------------------------------------------


class TestTimestampParsing:
    def test_parses_iso_with_timezone(self):
        service = LeadPipelineService.__new__(LeadPipelineService)
        result = service._parse_timestamp("2026-01-15T10:30:00+00:00")
        assert result is not None
        assert result.tzinfo is not None

    def test_parses_iso_with_z(self):
        service = LeadPipelineService.__new__(LeadPipelineService)
        result = service._parse_timestamp("2026-01-15T10:30:00Z")
        assert result is not None
        assert result.tzinfo is not None

    def test_parses_naive_datetime(self):
        service = LeadPipelineService.__new__(LeadPipelineService)
        result = service._parse_timestamp("2026-01-15T10:30:00")
        assert result is not None
        assert result.tzinfo == timezone.utc

    def test_returns_none_for_invalid(self):
        service = LeadPipelineService.__new__(LeadPipelineService)
        assert service._parse_timestamp("not-a-date") is None
        assert service._parse_timestamp(None) is None
        assert service._parse_timestamp(12345) is None
