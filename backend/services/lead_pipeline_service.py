"""Lead pipeline reporting and staleness detection service.

Provides pipeline metrics (by temperature, owner, conversion funnel),
staleness detection (48h with no next_action_due), and Command Center
event emission on temperature/owner changes.

Requirements: 14.1, 14.2, 14.3, 14.4
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from backend.models.lead_pipeline import (
    FunnelStage,
    LeadPipelineEvent,
    OwnerMetrics,
    PipelineMetricsResponse,
    StaleLeadInfo,
    TemperatureMetrics,
)
from backend.services.neon_service import neon_service

logger = logging.getLogger(__name__)

# Staleness threshold: leads older than 48h with no next_action_due
STALENESS_HOURS = 48

# Conversion funnel stage ordering
FUNNEL_STAGES = ["new", "contacted", "qualified", "converted", "lost"]


class LeadPipelineService:
    """Service for lead pipeline metrics and staleness detection."""

    def __init__(self) -> None:
        self.client = neon_service.client

    async def get_pipeline_metrics(self, org_id: str) -> PipelineMetricsResponse:
        """Return pipeline metrics: leads by temperature, owner, funnel, and stale leads.

        All queries scoped by org_id.
        """
        leads = self._fetch_all_active_leads(org_id)

        by_temperature = self._compute_temperature_metrics(leads)
        by_owner = self._compute_owner_metrics(leads)
        conversion_funnel = self._compute_funnel_metrics(leads)
        stale_leads = self._detect_stale_leads(leads)

        return PipelineMetricsResponse(
            total_leads=len(leads),
            by_temperature=by_temperature,
            by_owner=by_owner,
            conversion_funnel=conversion_funnel,
            stale_leads=stale_leads,
            stale_count=len(stale_leads),
        )

    async def detect_and_flag_stale_leads(self, org_id: str) -> list[StaleLeadInfo]:
        """Detect stale leads and flag them with status 'stale'.

        A lead is stale if:
        - next_action_due is NULL
        - created_at is older than 48 hours
        - status is not already 'converted', 'lost', or 'stale'

        Returns the list of newly flagged stale leads.
        """
        leads = self._fetch_all_active_leads(org_id)
        stale_leads = self._detect_stale_leads(leads)

        flagged: list[StaleLeadInfo] = []
        for stale in stale_leads:
            try:
                self.client.table("leads_pipeline").update(
                    {"status": "stale", "updated_at": datetime.now(timezone.utc).isoformat()}
                ).eq("id", stale.lead_id).eq("org_id", org_id).execute()
                flagged.append(stale)

                # Emit staleness alert to Command Center
                self._emit_staleness_alert(org_id, stale)
            except Exception as exc:
                logger.error("Failed to flag stale lead %s: %s", stale.lead_id, exc)

        return flagged

    async def emit_temperature_change_event(
        self,
        org_id: str,
        lead_id: str,
        old_temperature: str,
        new_temperature: str,
    ) -> None:
        """Emit an event to Command Center when a lead's temperature changes."""
        event = LeadPipelineEvent(
            event_type="temperature_change",
            lead_id=lead_id,
            org_id=org_id,
            old_value=old_temperature,
            new_value=new_temperature,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self._emit_command_center_event(event)

    async def emit_owner_change_event(
        self,
        org_id: str,
        lead_id: str,
        old_owner: str | None,
        new_owner: str | None,
    ) -> None:
        """Emit an event to Command Center when a lead's owner changes."""
        event = LeadPipelineEvent(
            event_type="owner_change",
            lead_id=lead_id,
            org_id=org_id,
            old_value=old_owner,
            new_value=new_owner,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        self._emit_command_center_event(event)

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _fetch_all_active_leads(self, org_id: str) -> list[dict[str, Any]]:
        """Fetch all leads for the org that are not converted or lost."""
        try:
            response = (
                self.client.table("leads_pipeline")
                .select("*")
                .eq("org_id", org_id)
                .execute()
            )
            return response.data or []
        except Exception as exc:
            logger.error("Failed to fetch leads for org %s: %s", org_id, exc)
            return []

    def _compute_temperature_metrics(self, leads: list[dict[str, Any]]) -> TemperatureMetrics:
        """Count leads by temperature."""
        cold = sum(1 for l in leads if l.get("temperature") == "cold")
        warm = sum(1 for l in leads if l.get("temperature") == "warm")
        hot = sum(1 for l in leads if l.get("temperature") == "hot")
        return TemperatureMetrics(cold=cold, warm=warm, hot=hot)

    def _compute_owner_metrics(self, leads: list[dict[str, Any]]) -> list[OwnerMetrics]:
        """Group leads by assigned_owner."""
        owner_counts: dict[str | None, int] = {}
        for lead in leads:
            owner = lead.get("assigned_owner")
            owner_key = str(owner) if owner else None
            owner_counts[owner_key] = owner_counts.get(owner_key, 0) + 1

        return [
            OwnerMetrics(owner_id=owner_id, count=count)
            for owner_id, count in sorted(owner_counts.items(), key=lambda x: x[1], reverse=True)
        ]

    def _compute_funnel_metrics(self, leads: list[dict[str, Any]]) -> list[FunnelStage]:
        """Count leads per conversion funnel stage."""
        stage_counts: dict[str, int] = {stage: 0 for stage in FUNNEL_STAGES}
        for lead in leads:
            status = lead.get("status", "new")
            if status in stage_counts:
                stage_counts[status] += 1
            elif status == "stale":
                # Stale leads are counted in their original funnel position (new)
                stage_counts["new"] = stage_counts.get("new", 0) + 1

        return [FunnelStage(stage=stage, count=count) for stage, count in stage_counts.items()]

    def _detect_stale_leads(self, leads: list[dict[str, Any]]) -> list[StaleLeadInfo]:
        """Identify leads with no next_action_due and created_at > 48h.

        Excludes leads already in terminal states (converted, lost, stale).
        """
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=STALENESS_HOURS)
        stale: list[StaleLeadInfo] = []

        for lead in leads:
            # Skip terminal states
            status = lead.get("status", "")
            if status in ("converted", "lost", "stale"):
                continue

            # Check no next_action_due
            if lead.get("next_action_due") is not None:
                continue

            # Check created_at > 48h
            created_at_raw = lead.get("created_at")
            if not created_at_raw:
                continue

            created_at = self._parse_timestamp(created_at_raw)
            if created_at is None:
                continue

            if created_at < cutoff:
                days_since = (now - created_at).total_seconds() / 86400
                stale.append(
                    StaleLeadInfo(
                        lead_id=lead["id"],
                        contact_name=lead.get("contact_name", "Unknown"),
                        assigned_owner=str(lead["assigned_owner"]) if lead.get("assigned_owner") else None,
                        temperature=lead.get("temperature", "cold"),
                        created_at=created_at_raw if isinstance(created_at_raw, str) else created_at_raw.isoformat(),
                        days_since_creation=round(days_since, 1),
                    )
                )

        return stale

    def _parse_timestamp(self, value: Any) -> datetime | None:
        """Parse a timestamp string into a timezone-aware datetime."""
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value

        if not isinstance(value, str):
            return None

        # Handle ISO format with or without timezone
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, TypeError):
            return None

    def _emit_command_center_event(self, event: LeadPipelineEvent) -> None:
        """Insert an alert into automation_alerts for Command Center consumption."""
        try:
            row = {
                "org_id": event.org_id,
                "rule_id": None,
                "alert_type": event.event_type,
                "alert_scope": "lead_pipeline",
                "severity": "warning",
                "message": self._format_event_message(event),
                "is_active": True,
                "metadata_json": {
                    "lead_id": event.lead_id,
                    "old_value": event.old_value,
                    "new_value": event.new_value,
                    "event_type": event.event_type,
                },
                "dedupe_key": f"lead_pipeline_{event.event_type}_{event.lead_id}",
            }
            self.client.table("automation_alerts").insert(row).execute()
            logger.info(
                "Command Center event emitted: %s for lead %s",
                event.event_type,
                event.lead_id,
            )
        except Exception as exc:
            logger.error(
                "Failed to emit Command Center event for lead %s: %s",
                event.lead_id,
                exc,
            )

    def _emit_staleness_alert(self, org_id: str, stale: StaleLeadInfo) -> None:
        """Emit a staleness alert to Command Center for the assigned owner."""
        try:
            row = {
                "org_id": org_id,
                "rule_id": None,
                "alert_type": "lead_stale",
                "alert_scope": "lead_pipeline",
                "severity": "warning",
                "message": (
                    f"Lead '{stale.contact_name}' has been idle for "
                    f"{stale.days_since_creation} days with no scheduled action."
                ),
                "is_active": True,
                "metadata_json": {
                    "lead_id": stale.lead_id,
                    "assigned_owner": stale.assigned_owner,
                    "temperature": stale.temperature,
                    "days_since_creation": stale.days_since_creation,
                },
                "dedupe_key": f"lead_stale_{stale.lead_id}",
            }
            self.client.table("automation_alerts").insert(row).execute()
        except Exception as exc:
            logger.error("Failed to emit staleness alert for lead %s: %s", stale.lead_id, exc)

    def _format_event_message(self, event: LeadPipelineEvent) -> str:
        """Format a human-readable message for Command Center alerts."""
        if event.event_type == "temperature_change":
            return (
                f"Lead {event.lead_id} temperature changed "
                f"from '{event.old_value}' to '{event.new_value}'"
            )
        if event.event_type == "owner_change":
            return (
                f"Lead {event.lead_id} ownership changed "
                f"from '{event.old_value or 'unassigned'}' to '{event.new_value or 'unassigned'}'"
            )
        return f"Lead pipeline event: {event.event_type} for lead {event.lead_id}"


lead_pipeline_service = LeadPipelineService()
