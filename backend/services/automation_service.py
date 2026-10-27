from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import HTTPException, status

from backend.models.automation import (
    AlertItem,
    AlertListResponse,
    AutomationExecutionStatus,
    AutomationRuleStatus,
    DryRunRequest,
    DryRunResponse,
    ExecuteRequest,
    ExecuteResponse,
    ExecutionLogResponse,
    RuleCreateRequest,
    RuleListResponse,
    RuleResponse,
    RuleUpdateRequest,
    ScopeMetadata,
)
from backend.models.membership import UserRole
from backend.models.source_observatory import SourceScorecard
from backend.services.cloud_ops_service import get_cloud_ops_checks
from backend.services.finops import finops_service
from backend.services.source_observatory_service import source_observatory_service
from backend.services.neon_service import neon_service
from backend.services.territorial_sync_service import (
    get_territorial_pipeline_status,
    get_territorial_sync_status,
)


class AutomationService:
    def __init__(self) -> None:
        self.client = neon_service.client

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _table_exists(self, table: str) -> bool:
        try:
            self.client.table(table).select("id").limit(1).execute()
            return True
        except Exception:
            return False

    def _parse_timestamp(self, raw: Optional[str]) -> Optional[datetime]:
        if not raw:
            return None
        try:
            return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except Exception:
            return None

    async def _get_role(self, org_id: str, user_id: str) -> str:
        try:
            result = (
                self.client.table("organization_members")
                .select("role,status")
                .eq("org_id", org_id)
                .eq("user_id", user_id)
                .eq("status", "active")
                .limit(1)
                .execute()
            )
            if result.data:
                return str(result.data[0].get("role") or UserRole.AGENT.value)
        except Exception:
            pass
        return UserRole.OWNER.value

    def _assert_can_write(self, role: str) -> None:
        if role not in {UserRole.OWNER.value, UserRole.MANAGER.value}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="FORBIDDEN_ROLE_SCOPE")

    async def _get_rule(self, org_id: str, rule_id: str) -> Optional[Dict[str, Any]]:
        result = (
            self.client.table("automation_rules")
            .select("*")
            .eq("org_id", org_id)
            .eq("id", rule_id)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None

    async def list_rules(self, org_id: str, user_id: str) -> RuleListResponse:
        role = await self._get_role(org_id, user_id)
        if not self._table_exists("automation_rules"):
            return RuleListResponse(scope=ScopeMetadata(org_id=org_id, role=role), items=[], total=0)
        result = (
            self.client.table("automation_rules")
            .select("*", count="exact")
            .eq("org_id", org_id)
            .order("updated_at", desc=True)
            .execute()
        )
        items = [RuleResponse(**item) for item in (result.data or [])]
        return RuleListResponse(scope=ScopeMetadata(org_id=org_id, role=role), items=items, total=result.count or len(items))

    async def create_rule(self, org_id: str, user_id: str, payload: RuleCreateRequest) -> RuleResponse:
        role = await self._get_role(org_id, user_id)
        self._assert_can_write(role)
        if not self._table_exists("automation_rules"):
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AUTOMATION_SCHEMA_NOT_READY")
        now = self._now()
        data = {
            "org_id": org_id,
            "name": payload.name,
            "status": AutomationRuleStatus.ACTIVE.value,
            "event_type": payload.event_type,
            "channel": payload.channel,
            "action_type": payload.action_type,
            "schedule_cron": payload.schedule_cron,
            "max_cost_eur_per_run": payload.max_cost_eur_per_run,
            "requires_human_checkpoint": payload.requires_human_checkpoint,
            "conditions": payload.conditions,
            "created_at": now,
            "updated_at": now,
        }
        result = self.client.table("automation_rules").insert(data).execute()
        created = result.data[0]
        try:
            await neon_service.insert_audit_log(
                {
                    "org_id": org_id,
                    "entity_type": "automation_rule",
                    "entity_id": created["id"],
                    "action": "create",
                    "actor_user_id": user_id,
                    "details": {"name": payload.name, "channel": payload.channel},
                }
            )
        except Exception:
            pass
        return RuleResponse(**created)

    async def update_rule(self, org_id: str, user_id: str, rule_id: str, payload: RuleUpdateRequest) -> Optional[RuleResponse]:
        role = await self._get_role(org_id, user_id)
        self._assert_can_write(role)
        if not self._table_exists("automation_rules"):
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AUTOMATION_SCHEMA_NOT_READY")
        existing = await self._get_rule(org_id, rule_id)
        if not existing:
            return None
        data = payload.model_dump(exclude_unset=True)
        if not data:
            return RuleResponse(**existing)
        data["updated_at"] = self._now()
        result = (
            self.client.table("automation_rules")
            .update(data)
            .eq("org_id", org_id)
            .eq("id", rule_id)
            .execute()
        )
        updated = result.data[0]
        try:
            await neon_service.insert_audit_log(
                {
                    "org_id": org_id,
                    "entity_type": "automation_rule",
                    "entity_id": rule_id,
                    "action": "update",
                    "actor_user_id": user_id,
                    "details": data,
                }
            )
        except Exception:
            pass
        return RuleResponse(**updated)

    async def _evaluate_guardrails(
        self,
        org_id: str,
        rule: Dict[str, Any],
        cost_estimate_eur: float,
        confirm_human_checkpoint: bool,
        for_execute: bool,
    ) -> Dict[str, Any]:
        reasons: list[str] = []

        if str(rule.get("status")) != AutomationRuleStatus.ACTIVE.value:
            reasons.append("RULE_NOT_ACTIVE")

        max_cost = float(rule.get("max_cost_eur_per_run") or 0)
        if max_cost > 0 and cost_estimate_eur > max_cost:
            reasons.append("COST_LIMIT_EXCEEDED")

        if bool(rule.get("requires_human_checkpoint")) and for_execute and not confirm_human_checkpoint:
            reasons.append("HUMAN_CHECKPOINT_REQUIRED")

        budget = await finops_service.get_budget_status(org_id)
        if budget.status == "hard_stop":
            reasons.append("FINOPS_HARD_STOP_ACTIVE")

        blocked = len(reasons) > 0
        return {
            "decision": "blocked" if blocked else "allow",
            "reasons": reasons,
            "guardrails": {
                "max_cost_eur_per_run": max_cost,
                "cost_estimate_eur": cost_estimate_eur,
                "requires_human_checkpoint": bool(rule.get("requires_human_checkpoint")),
                "human_checkpoint_confirmed": bool(confirm_human_checkpoint),
                "finops_status": budget.status,
            },
        }

    async def dry_run(self, org_id: str, user_id: str, rule_id: str, payload: DryRunRequest) -> Optional[DryRunResponse]:
        role = await self._get_role(org_id, user_id)
        if not self._table_exists("automation_rules"):
            return None
        rule = await self._get_rule(org_id, rule_id)
        if not rule:
            return None
        evaluation = await self._evaluate_guardrails(
            org_id=org_id,
            rule=rule,
            cost_estimate_eur=payload.cost_estimate_eur,
            confirm_human_checkpoint=False,
            for_execute=False,
        )
        return DryRunResponse(
            scope=ScopeMetadata(org_id=org_id, role=role),
            rule_id=rule_id,
            decision=evaluation["decision"],
            reasons=evaluation["reasons"],
            guardrails=evaluation["guardrails"],
        )

    def _build_guardrail_alert_payload(self, org_id: str, rule_id: str, reasons: List[str]) -> Dict[str, Any]:
        now = self._now()
        dedupe_reasons = "-".join(sorted(reasons)) if reasons else "blocked"
        return {
            "org_id": org_id,
            "rule_id": rule_id,
            "alert_scope": "rule",
            "severity": "warning",
            "alert_type": "guardrail_block",
            "message": ",".join(reasons) if reasons else "blocked",
            "dedupe_key": f"guardrail-block:{rule_id}:{dedupe_reasons}",
            "metadata_json": {"reasons": reasons},
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }

    async def execute(self, org_id: str, user_id: str, rule_id: str, payload: ExecuteRequest) -> Optional[ExecuteResponse]:
        role = await self._get_role(org_id, user_id)
        self._assert_can_write(role)
        if not self._table_exists("automation_rules") or not self._table_exists("automation_executions"):
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AUTOMATION_SCHEMA_NOT_READY")
        rule = await self._get_rule(org_id, rule_id)
        if not rule:
            return None

        evaluation = await self._evaluate_guardrails(
            org_id=org_id,
            rule=rule,
            cost_estimate_eur=payload.cost_estimate_eur,
            confirm_human_checkpoint=payload.confirm_human_checkpoint,
            for_execute=True,
        )
        trace_id = str(uuid4())
        execution_status = (
            AutomationExecutionStatus.BLOCKED.value
            if evaluation["decision"] == "blocked"
            else AutomationExecutionStatus.EXECUTED.value
        )
        execution_data = {
            "org_id": org_id,
            "rule_id": rule_id,
            "status": execution_status,
            "decision": evaluation["decision"],
            "reasons": evaluation["reasons"],
            "cost_estimate_eur": payload.cost_estimate_eur,
            "event_payload": payload.event_payload,
            "trace_id": trace_id,
            "created_at": self._now(),
        }
        execution = self.client.table("automation_executions").insert(execution_data).execute().data[0]

        if evaluation["decision"] == "blocked" and self._table_exists("automation_alerts"):
            self.client.table("automation_alerts").insert(
                self._build_guardrail_alert_payload(org_id=org_id, rule_id=rule_id, reasons=evaluation["reasons"])
            ).execute()

        try:
            await neon_service.insert_audit_log(
                {
                    "org_id": org_id,
                    "entity_type": "automation_execution",
                    "entity_id": execution["id"],
                    "action": "execute",
                    "actor_user_id": user_id,
                    "details": {
                        "rule_id": rule_id,
                        "decision": evaluation["decision"],
                        "reasons": evaluation["reasons"],
                        "trace_id": trace_id,
                    },
                }
            )
        except Exception:
            pass

        return ExecuteResponse(
            scope=ScopeMetadata(org_id=org_id, role=role),
            rule_id=rule_id,
            execution_id=execution["id"],
            status=AutomationExecutionStatus(execution_status),
            decision=evaluation["decision"],
            reasons=evaluation["reasons"],
            trace_id=trace_id,
        )

    async def list_executions(
        self,
        org_id: str,
        user_id: str,
        execution_status: Optional[str] = None,
        rule_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> ExecutionLogResponse:
        role = await self._get_role(org_id, user_id)
        if not self._table_exists("automation_executions"):
            return ExecutionLogResponse(scope=ScopeMetadata(org_id=org_id, role=role), items=[], total=0)
        query = self.client.table("automation_executions").select("*", count="exact").eq("org_id", org_id).order("created_at", desc=True)
        if execution_status:
            query = query.eq("status", execution_status)
        if rule_id:
            query = query.eq("rule_id", rule_id)
        query = query.range(offset, offset + limit - 1)
        result = query.execute()
        return ExecutionLogResponse(
            scope=ScopeMetadata(org_id=org_id, role=role),
            items=result.data or [],
            total=result.count or len(result.data or []),
        )

    def _build_operational_alert_candidates(
        self,
        *,
        sync_status: Dict[str, Any],
        pipeline_status: Dict[str, Any],
        observatory_items: List[SourceScorecard],
        cloud_checks: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = []

        sync_state = str(sync_status.get("status") or "").lower()
        if sync_state in {"warning", "error"}:
            candidates.append(
                {
                    "alert_scope": "territorial_sync",
                    "severity": "critical" if sync_state == "error" else "warning",
                    "alert_type": "territorial_sync_degraded",
                    "message": "NotebookLM territorial sync pack degraded.",
                    "dedupe_key": f"territorial-sync:{sync_state}",
                    "metadata_json": {
                        "status": sync_state,
                        "generated_at": sync_status.get("generated_at"),
                        "warnings": sync_status.get("warnings") or [],
                        "errors": sync_status.get("errors") or [],
                    },
                }
            )

        pipeline_state = str(pipeline_status.get("status") or "").lower()
        last_success_at = self._parse_timestamp(pipeline_status.get("last_success_at"))
        freshness_hours = None
        if last_success_at is not None:
            freshness_hours = round((datetime.now(timezone.utc) - last_success_at).total_seconds() / 3600, 2)

        if pipeline_state in {"error", "failed"}:
            candidates.append(
                {
                    "alert_scope": "territorial_pipeline",
                    "severity": "critical",
                    "alert_type": "territorial_pipeline_failed",
                    "message": "Territorial pipeline failed on latest run.",
                    "dedupe_key": f"territorial-pipeline:{pipeline_state}",
                    "metadata_json": {
                        "status": pipeline_state,
                        "last_error_at": pipeline_status.get("last_error_at"),
                        "message": pipeline_status.get("message"),
                    },
                }
            )
        elif pipeline_state == "idle" and not pipeline_status.get("last_success_at"):
            candidates.append(
                {
                    "alert_scope": "territorial_pipeline",
                    "severity": "warning",
                    "alert_type": "territorial_pipeline_missing",
                    "message": "Territorial pipeline has not recorded any successful run yet.",
                    "dedupe_key": "territorial-pipeline:missing-success",
                    "metadata_json": {"status": pipeline_state},
                }
            )
        elif freshness_hours is not None and freshness_hours >= 72:
            candidates.append(
                {
                    "alert_scope": "territorial_pipeline",
                    "severity": "critical" if freshness_hours >= 168 else "warning",
                    "alert_type": "territorial_pipeline_stale",
                    "message": "Territorial pipeline heartbeat is stale.",
                    "dedupe_key": f"territorial-pipeline:stale:{'critical' if freshness_hours >= 168 else 'warning'}",
                    "metadata_json": {
                        "freshness_hours": freshness_hours,
                        "last_success_at": pipeline_status.get("last_success_at"),
                    },
                }
            )

        for item in observatory_items:
            if item.source_key.startswith("cloud:"):
                continue
            if item.operational_status not in {"warning", "critical"}:
                continue
            candidates.append(
                {
                    "alert_scope": "source_connector",
                    "severity": "critical" if item.operational_status == "critical" else "warning",
                    "alert_type": "source_connector_degraded",
                    "message": f"Source connector {item.source_key} is {item.operational_status}.",
                    "dedupe_key": f"source-connector:{item.source_key}:{item.operational_status}",
                    "metadata_json": {
                        "source_key": item.source_key,
                        "success_rate_pct": item.success_rate_pct,
                        "freshness_hours": item.freshness_hours,
                        "created_entities": item.created_entities,
                        "failed_events": item.failed_events,
                        "rejected_events": item.rejected_events,
                    },
                }
            )

        for check in cloud_checks:
            check_key = str(check.get("check_key") or "")
            check_status = str(check.get("status") or "")
            if check_status not in {"warning", "critical"}:
                continue
            if check_key == "cloud:ai-runtime":
                candidates.append(
                    {
                        "alert_scope": "ai_runtime",
                        "severity": "critical" if check_status == "critical" else "warning",
                        "alert_type": "ai_runtime_degraded",
                        "message": "AI runtime is degraded and may affect seller memory and outreach quality.",
                        "dedupe_key": f"ai-runtime:{check_status}",
                        "metadata_json": check.get("metadata") or {},
                    }
                )
            if check_key == "cloud:seller-signal-source":
                candidates.append(
                    {
                        "alert_scope": "seller_signal_source",
                        "severity": "critical" if check_status == "critical" else "warning",
                        "alert_type": "seller_signal_source_degraded",
                        "message": "Seller signal live source is degraded or stale.",
                        "dedupe_key": f"seller-signal-source:{check_status}",
                        "metadata_json": {
                            **(check.get("metadata") or {}),
                            "heartbeat_age_hours": check.get("heartbeat_age_hours"),
                            "retry_count": check.get("retry_count"),
                        },
                    }
                )

        return candidates

    def _list_active_alerts_by_scope(self, org_id: str, scopes: List[str]) -> List[Dict[str, Any]]:
        if not self._table_exists("automation_alerts") or not scopes:
            return []
        try:
            return (
                self.client.table("automation_alerts")
                .select("*")
                .eq("org_id", org_id)
                .eq("is_active", True)
                .in_("alert_scope", scopes)
                .execute()
                .data
                or []
            )
        except Exception:
            return []

    def _resolve_alert(self, org_id: str, alert_id: str) -> None:
        try:
            (
                self.client.table("automation_alerts")
                .update({"is_active": False, "resolved_at": self._now(), "updated_at": self._now()})
                .eq("org_id", org_id)
                .eq("id", alert_id)
                .execute()
            )
        except Exception:
            pass

    def _activate_or_refresh_alert(self, org_id: str, payload: Dict[str, Any], existing_by_dedupe: Dict[str, Dict[str, Any]]) -> None:
        dedupe_key = payload.get("dedupe_key")
        now = self._now()
        if dedupe_key and dedupe_key in existing_by_dedupe:
            existing = existing_by_dedupe[dedupe_key]
            try:
                (
                    self.client.table("automation_alerts")
                    .update(
                        {
                            "message": payload["message"],
                            "severity": payload["severity"],
                            "metadata_json": payload.get("metadata_json") or {},
                            "updated_at": now,
                            "is_active": True,
                            "resolved_at": None,
                        }
                    )
                    .eq("org_id", org_id)
                    .eq("id", existing["id"])
                    .execute()
                )
            except Exception:
                pass
            return

        row = {
            "org_id": org_id,
            "rule_id": payload.get("rule_id"),
            "alert_scope": payload["alert_scope"],
            "severity": payload["severity"],
            "alert_type": payload["alert_type"],
            "message": payload["message"],
            "dedupe_key": dedupe_key,
            "metadata_json": payload.get("metadata_json") or {},
            "is_active": True,
            "created_at": now,
            "updated_at": now,
            "resolved_at": None,
        }
        try:
            self.client.table("automation_alerts").insert(row).execute()
        except Exception:
            pass

    async def reconcile_operational_alerts(self, org_id: str, user_id: str) -> None:
        if not self._table_exists("automation_alerts"):
            return
        sync_status = get_territorial_sync_status()
        pipeline_status = get_territorial_pipeline_status()
        observatory = await source_observatory_service.get_overview(org_id=org_id, user_id=user_id)
        cloud_checks = get_cloud_ops_checks()
        candidates = self._build_operational_alert_candidates(
            sync_status=sync_status,
            pipeline_status=pipeline_status,
            observatory_items=observatory.items,
            cloud_checks=[item.to_dict() for item in cloud_checks],
        )
        active_operational = self._list_active_alerts_by_scope(
            org_id,
            scopes=["territorial_sync", "territorial_pipeline", "source_connector", "seller_signal_source", "ai_runtime"],
        )
        existing_by_dedupe = {
            str(item.get("dedupe_key")): item for item in active_operational if item.get("dedupe_key")
        }
        candidate_dedupes = {
            str(item["dedupe_key"]) for item in candidates if item.get("dedupe_key")
        }

        for alert in active_operational:
            dedupe_key = alert.get("dedupe_key")
            if dedupe_key and dedupe_key not in candidate_dedupes:
                self._resolve_alert(org_id, str(alert["id"]))

        for candidate in candidates:
            self._activate_or_refresh_alert(org_id, candidate, existing_by_dedupe)

    async def list_alerts(self, org_id: str, user_id: str) -> AlertListResponse:
        role = await self._get_role(org_id, user_id)
        if not self._table_exists("automation_alerts"):
            return AlertListResponse(scope=ScopeMetadata(org_id=org_id, role=role), items=[], total=0)
        await self.reconcile_operational_alerts(org_id=org_id, user_id=user_id)
        result = (
            self.client.table("automation_alerts")
            .select("*", count="exact")
            .eq("org_id", org_id)
            .eq("is_active", True)
            .order("created_at", desc=True)
            .execute()
        )
        items = [AlertItem(**item) for item in (result.data or [])]
        return AlertListResponse(
            scope=ScopeMetadata(org_id=org_id, role=role),
            items=items,
            total=result.count or len(items),
        )

    async def acknowledge_alert(self, org_id: str, user_id: str, alert_id: str) -> bool:
        role = await self._get_role(org_id, user_id)
        self._assert_can_write(role)
        if not self._table_exists("automation_alerts"):
            return False
        result = (
            self.client.table("automation_alerts")
            .update({"is_active": False, "resolved_at": self._now(), "updated_at": self._now()})
            .eq("org_id", org_id)
            .eq("id", alert_id)
            .execute()
        )
        if not result.data:
            return False
        try:
            await neon_service.insert_audit_log(
                {
                    "org_id": org_id,
                    "entity_type": "automation_alert",
                    "entity_id": alert_id,
                    "action": "acknowledge",
                    "actor_user_id": user_id,
                    "details": {"status": "resolved"},
                }
            )
        except Exception:
            pass
        return True


automation_service = AutomationService()
