from typing import List, Optional, Dict, Any
from datetime import datetime, date
from uuid import UUID

from backend.config import settings
from backend.services.neon_service import neon_service
from backend.models.finops import (
    BudgetResponse, 
    BudgetUpdate, 
    UsageEventSchema, 
    UsageEventResponse,
    AlertResponse
)

class FinOpsService:
    def __init__(self):
        self.client = neon_service.client

    async def get_budget_status(self, org_id: str) -> BudgetResponse:
        # 1. Get Policy
        policy_res = self.client.table("org_cost_policies").select("*").eq("org_id", org_id).single().execute()
        # If no policy, we should probably return a default or error, but migration backfilled it.
        # Assuming it exists or handling error could be done here.
        policy = policy_res.data
        
        # 2. Key for current month aggregation
        current_month_start = date.today().replace(day=1).isoformat()
        
        # 3. Aggregate Usage for current month
        # Since we don't have a pre-aggregated table in spec (only raw events), we sum raw events.
        # For huge scale this might be slow, but for v0 it's fine.
        # Neon API doesn't support SUM directly easily without RPC, but we can fetch and sum or use a view.
        # Given "sdd/features/cost-governance-foundation-spec-v1.md" mentions "Retorna presupuesto y consumo acumulado",
        # and we can't easily change DB schema to add views, we will query raw events.
        # NOTE: To optimize, we could fetch only 'cost_eur' column.
        
        usage_res = self.client.table("org_cost_usage_events")\
            .select("cost_eur")\
            .eq("org_id", org_id)\
            .gte("created_at", current_month_start)\
            .execute()
            
        total_usage_eur = sum(item["cost_eur"] for item in usage_res.data)
        
        monthly_budget = float(policy["monthly_budget_eur"])
        current_pct = (total_usage_eur / monthly_budget * 100) if monthly_budget > 0 else 0
        
        # Determine status
        status = "ok"
        if policy["hard_stop_enabled"] and current_pct >= float(policy["hard_stop_threshold_pct"]):
            status = "hard_stop"
        elif current_pct >= float(policy["warning_threshold_pct"]):
            status = "warning"
            
        return BudgetResponse(
            org_id=org_id,
            monthly_budget_eur=monthly_budget,
            warning_threshold_pct=float(policy["warning_threshold_pct"]),
            hard_stop_threshold_pct=float(policy["hard_stop_threshold_pct"]),
            hard_stop_enabled=policy["hard_stop_enabled"],
            current_usage_eur=total_usage_eur,
            current_usage_pct=current_pct,
            status=status
        )

    async def update_budget_policy(self, org_id: str, update_data: BudgetUpdate) -> BudgetResponse:
        data = update_data.model_dump(exclude_unset=True)
        if not data:
            return await self.get_budget_status(org_id)
            
        self.client.table("org_cost_policies").update(data).eq("org_id", org_id).execute()
        return await self.get_budget_status(org_id)

    async def log_usage_event(self, org_id: str, event: UsageEventSchema) -> UsageEventResponse:
        # 1. Insert Event
        event_dict = event.model_dump()
        event_dict["org_id"] = org_id
        # trace_id is optional, logic handles it.
        
        res = self.client.table("org_cost_usage_events").insert(event_dict).execute()
        inserted_event = res.data[0]
        
        # 2. Check Thresholds & Manage Alerts
        # We need to re-check budget status.
        status = await self.get_budget_status(org_id)
        
        month_key = date.today().strftime("%Y-%m")
        
        # Logic to Create/Resolve Alerts
        # Spec: "Si consumo >= warning threshold: alerta warning"
        # Spec: "Si consumo >= hard-stop threshold ...: bloquear" (Blocking is handled by the caller or middleware checking status, here we just alert)
        
        # Check active alerts for this month
        active_alerts_res = self.client.table("org_cost_alerts")\
            .select("*")\
            .eq("org_id", org_id)\
            .eq("month_key", month_key)\
            .eq("is_active", True)\
            .execute()
        
        active_alerts = {a["alert_type"]: a for a in active_alerts_res.data}
        
        # Hard Stop Alert
        if status.status == "hard_stop":
            if "hard_stop" not in active_alerts:
                self.client.table("org_cost_alerts").insert({
                    "org_id": org_id,
                    "alert_type": "hard_stop",
                    "month_key": month_key,
                    "threshold_pct": status.hard_stop_threshold_pct,
                    "current_pct": status.current_usage_pct,
                    "is_active": True
                }).execute()
        # Warning Alert
        elif status.status == "warning":
            if "warning" not in active_alerts and "hard_stop" not in active_alerts:
                # Only create warning if not already in hard_stop (assuming hard_stop supersedes warning or they coexist? Spec doesn't strictly say, but usually you want at least the highest severity)
                # However, spec says "Si consumo >= warning ... alerta warning". It doesn't say "unless hard stop".
                # But let's create it if missing.
                self.client.table("org_cost_alerts").insert({
                    "org_id": org_id,
                    "alert_type": "warning",
                    "month_key": month_key,
                    "threshold_pct": status.warning_threshold_pct,
                    "current_pct": status.current_usage_pct,
                    "is_active": True
                }).execute()
        
        # Note: We probably shouldn't auto-resolve alerts yet logic is complex (e.g. if budget increased).
        # Spec says "resolved_at", implies they can be resolved. 
        # For v0 simplicity: We insert new alerts if thresholds correspond. We don't implement auto-resolve logic here unless strictly required.
        # "Recovered" alert type exists in schema.
        
        return UsageEventResponse(**inserted_event)

    async def get_usage_history(
        self, 
        org_id: str, 
        capability: Optional[str] = None, 
        start_date: Optional[datetime] = None, 
        end_date: Optional[datetime] = None
    ) -> List[UsageEventResponse]:
        query = self.client.table("org_cost_usage_events").select("*").eq("org_id", org_id).order("created_at", desc=True)
        
        if capability:
            query = query.eq("capability_code", capability)
        if start_date:
            query = query.gte("created_at", start_date.isoformat())
        if end_date:
            query = query.lte("created_at", end_date.isoformat())
            
        res = query.execute()
        return [UsageEventResponse(**item) for item in res.data]

    async def get_active_alerts(self, org_id: str) -> List[AlertResponse]:
        res = self.client.table("org_cost_alerts")\
            .select("*")\
            .eq("org_id", org_id)\
            .eq("is_active", True)\
            .order("created_at", desc=True)\
            .execute()
        return [AlertResponse(**item) for item in res.data]

finops_service = FinOpsService()
