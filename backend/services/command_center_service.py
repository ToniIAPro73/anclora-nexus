from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List

from fastapi import HTTPException, status

from backend.models.command_center import (
    CommandCenterSnapshotResponse,
    CommandCenterTrendsResponse,
    KPIValue,
    OperationalAlertPreview,
    OperationalOverview,
    PipelineOverview,
    ScopeMetadata,
    TrendPoint,
)
from backend.models.membership import UserRole
from backend.services.automation_service import automation_service
from backend.services.cloud_ops_service import get_cloud_ops_summary
from backend.services.finops import finops_service
from backend.services.source_observatory_service import source_observatory_service
from backend.services.neon_service import neon_service
from backend.services.territorial_sync_service import (
    get_territorial_pipeline_status,
    get_territorial_sync_status,
)


class CommandCenterService:
    def __init__(self) -> None:
        self.client = neon_service.client

    def _table_exists(self, table: str) -> bool:
        try:
            self.client.table(table).select("id").limit(1).execute()
            return True
        except Exception:
            return False

    async def _get_role(self, org_id: str, user_id: str) -> str:
        result = (
            self.client.table("organization_members")
            .select("role,status")
            .eq("org_id", org_id)
            .eq("user_id", user_id)
            .eq("status", "active")
            .limit(1)
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="FORBIDDEN_ORG_SCOPE")
        return str(result.data[0].get("role") or UserRole.AGENT.value)

    def _is_agent(self, role: str) -> bool:
        return role == UserRole.AGENT.value

    async def _count_entities(self, table: str, org_id: str, role: str, user_id: str, status_filter: List[str] | None = None) -> int:
        query = self.client.table(table).select("id", count="exact").eq("org_id", org_id)
        if self._is_agent(role):
            query = query.eq("assigned_user_id", user_id)
        if status_filter:
            query = query.in_("status", status_filter)
        result = query.execute()
        return result.count or 0

    async def _build_operational_overview(self, org_id: str, user_id: str) -> OperationalOverview:
        alerts = await automation_service.list_alerts(org_id=org_id, user_id=user_id)
        observatory = await source_observatory_service.get_overview(org_id=org_id, user_id=user_id)
        sync_status = get_territorial_sync_status()
        pipeline_status = get_territorial_pipeline_status()
        cloud_ops = get_cloud_ops_summary()
        cloud_checks = {item["check_key"]: item for item in cloud_ops["checks"]}

        return OperationalOverview(
            active_alerts=alerts.total,
            critical_alerts=sum(1 for item in alerts.items if item.severity == "critical"),
            degraded_sources=observatory.summary.warning_sources + observatory.summary.critical_sources,
            stale_sources=observatory.summary.stale_sources,
            cloud_warning_checks=int(cloud_ops["warning_checks"]),
            cloud_critical_checks=int(cloud_ops["critical_checks"]),
            territorial_sync_status=str(sync_status.get("status") or "unknown"),
            territorial_pipeline_status=str(pipeline_status.get("status") or "unknown"),
            seller_signal_source_status=str((cloud_checks.get("cloud:seller-signal-source") or {}).get("status") or "unknown"),
            ai_runtime_status=str((cloud_checks.get("cloud:ai-runtime") or {}).get("status") or "unknown"),
            top_alerts=[
                OperationalAlertPreview(
                    id=item.id,
                    alert_scope=item.alert_scope,
                    severity=item.severity,
                    alert_type=item.alert_type,
                    message=item.message,
                    created_at=item.created_at.isoformat() if hasattr(item.created_at, "isoformat") else str(item.created_at),
                    metadata_json=item.metadata_json,
                )
                for item in alerts.items[:5]
            ],
        )

    def _build_pipeline_overview(self, org_id: str) -> PipelineOverview:
        seller_signals_processed = 0
        if self._table_exists("ingestion_events"):
            try:
                events = (
                    self.client.table("ingestion_events")
                    .select("status,entity_type")
                    .eq("org_id", org_id)
                    .eq("entity_type", "seller_signal")
                    .execute()
                    .data
                    or []
                )
                seller_signals_processed = sum(1 for item in events if str(item.get("status") or "") == "processed")
            except Exception:
                seller_signals_processed = 0

        sellers_total = 0
        sellers_high_priority = 0
        sellers_converted = 0
        if self._table_exists("nexus_sellers"):
            try:
                sellers = (
                    self.client.table("nexus_sellers")
                    .select("prioridad,estado_contacto")
                    .eq("org_id", org_id)
                    .execute()
                    .data
                    or []
                )
                sellers_total = len(sellers)
                sellers_high_priority = sum(1 for item in sellers if int(item.get("prioridad") or 0) >= 4)
                sellers_converted = sum(
                    1 for item in sellers
                    if str(item.get("estado_contacto") or "") == "mandato_exclusivo"
                )
            except Exception:
                sellers_total = 0

        supervised_sends_confirmed = 0
        active_workbench_ready = 0
        if self._table_exists("seller_interactions"):
            try:
                interactions = (
                    self.client.table("seller_interactions")
                    .select("seller_id,resultado,metadata")
                    .eq("org_id", org_id)
                    .execute()
                    .data
                    or []
                )
                supervised_sends_confirmed = sum(
                    1
                    for item in interactions
                    if str(item.get("resultado") or "") in {"sent_confirmed_human", "sent_native_supervised"}
                )
                ready_sellers = {
                    str(item.get("seller_id"))
                    for item in interactions
                    if str(((item.get("metadata") or {}).get("artifact") or "")) in {
                        "email_draft",
                        "whatsapp_draft",
                        "call_brief",
                        "context_brief",
                        "captation_dossier",
                    }
                }
                active_workbench_ready = len(ready_sellers)
            except Exception:
                supervised_sends_confirmed = 0

        seller_conversion_rate = round((sellers_converted / sellers_total * 100) if sellers_total > 0 else 0.0, 1)

        return PipelineOverview(
            seller_signals_processed=seller_signals_processed,
            sellers_total=sellers_total,
            sellers_high_priority=sellers_high_priority,
            sellers_converted=sellers_converted,
            seller_conversion_rate=seller_conversion_rate,
            supervised_sends_confirmed=supervised_sends_confirmed,
            active_workbench_ready=active_workbench_ready,
        )

    async def get_snapshot(self, org_id: str, user_id: str) -> CommandCenterSnapshotResponse:
        role = await self._get_role(org_id, user_id)
        leads_total = await self._count_entities("leads", org_id, role, user_id)
        leads_qualified = await self._count_entities("leads", org_id, role, user_id, ["qualified", "negotiating", "closed"])
        properties_total = await self._count_entities("properties", org_id, role, user_id)
        properties_sold = await self._count_entities("properties", org_id, role, user_id, ["sold", "listed"])
        tasks_total = await self._count_entities("tasks", org_id, role, user_id)
        tasks_completed = await self._count_entities("tasks", org_id, role, user_id, ["completed"])

        lead_conversion = (leads_qualified / leads_total * 100) if leads_total > 0 else 0
        property_close_rate = (properties_sold / properties_total * 100) if properties_total > 0 else 0
        task_completion_rate = (tasks_completed / tasks_total * 100) if tasks_total > 0 else 0

        budget = await finops_service.get_budget_status(org_id)
        has_full_cost_visibility = not self._is_agent(role)
        operational_overview = await self._build_operational_overview(org_id=org_id, user_id=user_id)
        pipeline_overview = self._build_pipeline_overview(org_id=org_id)

        return CommandCenterSnapshotResponse(
            scope=ScopeMetadata(org_id=org_id, role=role),
            commercial_kpis=[
                KPIValue(label="leads_total", value=float(leads_total), unit="count"),
                KPIValue(label="lead_conversion_rate", value=lead_conversion, unit="percent"),
                KPIValue(label="property_close_rate", value=property_close_rate, unit="percent"),
            ],
            productivity_kpis=[
                KPIValue(label="tasks_total", value=float(tasks_total), unit="count"),
                KPIValue(label="tasks_completed", value=float(tasks_completed), unit="count"),
                KPIValue(label="task_completion_rate", value=task_completion_rate, unit="percent"),
            ],
            budget_status=budget.status,
            burn_pct=budget.current_usage_pct if has_full_cost_visibility else None,
            monthly_budget_eur=budget.monthly_budget_eur if has_full_cost_visibility else None,
            current_usage_eur=budget.current_usage_eur if has_full_cost_visibility else None,
            cost_visibility="full" if has_full_cost_visibility else "limited",
            operational_overview=operational_overview,
            pipeline_overview=pipeline_overview,
        )

    def _month_keys(self, months: int) -> List[str]:
        now = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        keys: List[str] = []
        for i in range(months - 1, -1, -1):
            d = now - timedelta(days=i * 31)
            keys.append(d.strftime("%Y-%m"))
        return keys

    async def get_trends(self, org_id: str, user_id: str, months: int = 6) -> CommandCenterTrendsResponse:
        role = await self._get_role(org_id, user_id)
        month_keys = self._month_keys(months)
        min_date = f"{month_keys[0]}-01T00:00:00+00:00"

        lead_q = self.client.table("leads").select("created_at,assigned_user_id").eq("org_id", org_id).gte("created_at", min_date)
        task_q = (
            self.client.table("tasks")
            .select("created_at,status,assigned_user_id")
            .eq("org_id", org_id)
            .gte("created_at", min_date)
        )
        cost_q = (
            self.client.table("org_cost_usage_events")
            .select("created_at,cost_eur")
            .eq("org_id", org_id)
            .gte("created_at", min_date)
        )
        if self._is_agent(role):
            lead_q = lead_q.eq("assigned_user_id", user_id)
            task_q = task_q.eq("assigned_user_id", user_id)

        leads = lead_q.execute().data or []
        tasks = task_q.execute().data or []
        costs = cost_q.execute().data or []

        lead_map: Dict[str, int] = defaultdict(int)
        task_map: Dict[str, int] = defaultdict(int)
        cost_map: Dict[str, float] = defaultdict(float)
        alert_map: Dict[str, int] = defaultdict(int)
        critical_alert_map: Dict[str, int] = defaultdict(int)
        seller_signal_map: Dict[str, int] = defaultdict(int)
        sellers_created_map: Dict[str, int] = defaultdict(int)
        supervised_send_map: Dict[str, int] = defaultdict(int)

        for item in leads:
            created_at = str(item.get("created_at") or "")
            if len(created_at) >= 7:
                lead_map[created_at[:7]] += 1

        for item in tasks:
            if str(item.get("status")) != "completed":
                continue
            created_at = str(item.get("created_at") or "")
            if len(created_at) >= 7:
                task_map[created_at[:7]] += 1

        if not self._is_agent(role):
            for item in costs:
                created_at = str(item.get("created_at") or "")
                if len(created_at) >= 7:
                    cost_map[created_at[:7]] += float(item.get("cost_eur") or 0)

        if self._table_exists("automation_alerts"):
            try:
                alerts = (
                    self.client.table("automation_alerts")
                    .select("created_at,severity")
                    .eq("org_id", org_id)
                    .gte("created_at", min_date)
                    .execute()
                    .data
                    or []
                )
                for item in alerts:
                    created_at = str(item.get("created_at") or "")
                    if len(created_at) < 7:
                        continue
                    key = created_at[:7]
                    alert_map[key] += 1
                    if str(item.get("severity") or "") == "critical":
                        critical_alert_map[key] += 1
            except Exception:
                pass

        if self._table_exists("ingestion_events"):
            try:
                ingestion_events = (
                    self.client.table("ingestion_events")
                    .select("created_at,status,entity_type")
                    .eq("org_id", org_id)
                    .eq("entity_type", "seller_signal")
                    .gte("created_at", min_date)
                    .execute()
                    .data
                    or []
                )
                for item in ingestion_events:
                    if str(item.get("status") or "") != "processed":
                        continue
                    created_at = str(item.get("created_at") or "")
                    if len(created_at) >= 7:
                        seller_signal_map[created_at[:7]] += 1
            except Exception:
                pass

        if self._table_exists("nexus_sellers"):
            try:
                sellers = (
                    self.client.table("nexus_sellers")
                    .select("created_at")
                    .eq("org_id", org_id)
                    .gte("created_at", min_date)
                    .execute()
                    .data
                    or []
                )
                for item in sellers:
                    created_at = str(item.get("created_at") or "")
                    if len(created_at) >= 7:
                        sellers_created_map[created_at[:7]] += 1
            except Exception:
                pass

        if self._table_exists("seller_interactions"):
            try:
                sends = (
                    self.client.table("seller_interactions")
                    .select("created_at,resultado")
                    .eq("org_id", org_id)
                    .gte("created_at", min_date)
                    .execute()
                    .data
                    or []
                )
                for item in sends:
                    if str(item.get("resultado") or "") not in {"sent_confirmed_human", "sent_native_supervised"}:
                        continue
                    created_at = str(item.get("created_at") or "")
                    if len(created_at) >= 7:
                        supervised_send_map[created_at[:7]] += 1
            except Exception:
                pass

        points = [
            TrendPoint(
                period=key,
                leads_created=lead_map.get(key, 0),
                tasks_completed=task_map.get(key, 0),
                cost_eur=round(cost_map.get(key, 0), 2),
                active_alerts=alert_map.get(key, 0),
                critical_alerts=critical_alert_map.get(key, 0),
                seller_signals_processed=seller_signal_map.get(key, 0),
                sellers_created=sellers_created_map.get(key, 0),
                supervised_sends_confirmed=supervised_send_map.get(key, 0),
            )
            for key in month_keys
        ]

        return CommandCenterTrendsResponse(
            scope=ScopeMetadata(org_id=org_id, role=role),
            months=months,
            points=points,
        )


command_center_service = CommandCenterService()
