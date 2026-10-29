import hashlib
import hmac
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from postgrest import SyncPostgrestClient
from backend.config import settings
from backend.services.neon_tokens import create_neon_jwt
from backend.services.origin_editability_policy import sanitize_payload

class _RefreshableQuery:
    """Proxy a PostgREST builder and refresh its bearer token before execution."""

    def __init__(self, query: Any, refresh_token: Any):
        self._query = query
        self._refresh_token = refresh_token

    def execute(self, *args: Any, **kwargs: Any) -> Any:
        self._refresh_token()
        return self._query.execute(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        attribute = getattr(self._query, name)
        if not callable(attribute):
            return attribute

        def call(*args: Any, **kwargs: Any) -> Any:
            result = attribute(*args, **kwargs)
            if callable(getattr(result, "execute", None)):
                return _RefreshableQuery(result, self._refresh_token)
            return result

        return call


class _NeonPostgrestFacade:
    def __init__(self, client: SyncPostgrestClient, refresh_token: Any):
        self._client = client
        self._refresh_token = refresh_token

    def table(self, name: str) -> Any:
        return _RefreshableQuery(self._client.table(name), self._refresh_token)

    def from_(self, name: str) -> Any:
        return self.table(name)

    def rpc(self, function_name: str, params: Optional[Dict[str, Any]] = None) -> Any:
        return _RefreshableQuery(self._client.rpc(function_name, params or {}), self._refresh_token)


class NeonService:
    """Neon Data API access with short-lived service-role JWTs."""

    def __init__(self):
        if not settings.NEON_DATA_API_URL:
            raise RuntimeError("NEON_DATA_API_URL is required")
        if not settings.NEON_JWT_PRIVATE_KEY or not settings.NEON_JWT_KEY_ID:
            raise RuntimeError("NEON_JWT_PRIVATE_KEY and NEON_JWT_KEY_ID are required")
        database_client = SyncPostgrestClient(settings.NEON_DATA_API_URL.rstrip("/"))
        self._refresh_token = lambda: database_client.auth(self._service_token())
        self._refresh_token()
        self.client = _NeonPostgrestFacade(database_client, self._refresh_token)
        self.audit_secret = settings.INTERNAL_AUDIT_SECRET or ""
        self.fixed_org_id = (
            settings.LEGACY_SINGLE_TENANT_ORG_ID
            or settings.PUBLIC_CTA_ORG_ID
            or "00000000-0000-0000-0000-000000000000"
        )

    def _service_token(self) -> str:
        return create_neon_jwt(
            role="service_role",
            subject="nexus-backend-service",
            private_key=settings.NEON_JWT_PRIVATE_KEY or "",
            key_id=settings.NEON_JWT_KEY_ID or "",
            issuer=settings.NEON_JWT_ISSUER,
            audience=settings.NEON_JWT_AUDIENCE,
            ttl_seconds=settings.NEON_SERVICE_JWT_TTL_SECONDS,
        )

    def _generate_signature(self, data: Dict[str, Any]) -> str:
        """Generates HMAC-SHA256 signature for audit log integrity."""
        message = json.dumps(data, sort_keys=True)
        return hmac.new(
            self.audit_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()

    def prepare_access_request_audit_event(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Build a signed event for the scoped access-request database functions."""
        event = {
            "org_id": str(data.get("org_id") or self.fixed_org_id),
            "actor_type": str(data.get("actor_type") or "system"),
            "actor_id": str(data.get("actor_id") or "system"),
            "action": str(data.get("action") or ""),
            "resource_type": "access_request",
            "resource_id": str(data.get("resource_id") or ""),
            "details": data.get("details") or {},
        }
        return {
            **event,
            "signature": self._generate_signature(event),
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def insert_lead(self, data: Dict[str, Any]) -> Dict[str, Any]:
        response = self.client.table("leads").insert(data).execute()
        return response.data[0]

    async def update_lead(self, lead_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        existing = self.client.table("leads").select("id,source_system").eq("id", lead_id).limit(1).execute()
        existing_row = existing.data[0] if existing.data else {}
        source_system = str(existing_row.get("source_system") or "manual")
        sanitized = sanitize_payload(data, "lead", source_system)
        if not sanitized:
            fallback = self.client.table("leads").select("*").eq("id", lead_id).limit(1).execute()
            return fallback.data[0] if fallback.data else {}
        response = self.client.table("leads").update(sanitized).eq("id", lead_id).execute()
        if response.data:
            return response.data[0]
        fallback = self.client.table("leads").select("*").eq("id", lead_id).limit(1).execute()
        return fallback.data[0] if fallback.data else {}

    async def update_lead_scoped(self, org_id: str, lead_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        existing = (
            self.client.table("leads")
            .select("id,org_id,source_system")
            .eq("id", lead_id)
            .eq("org_id", org_id)
            .limit(1)
            .execute()
        )
        row = existing.data[0] if existing.data else None
        if not row:
            return None
        source_system = str(row.get("source_system") or "manual")
        sanitized = sanitize_payload(data, "lead", source_system)
        if not sanitized:
            fallback = (
                self.client.table("leads")
                .select("*")
                .eq("id", lead_id)
                .eq("org_id", org_id)
                .limit(1)
                .execute()
            )
            return fallback.data[0] if fallback.data else None
        response = (
            self.client.table("leads")
            .update(sanitized)
            .eq("id", lead_id)
            .eq("org_id", org_id)
            .execute()
        )
        return response.data[0] if response.data else None

    async def get_lead_scoped(self, org_id: str, lead_id: str) -> Optional[Dict[str, Any]]:
        response = (
            self.client.table("leads")
            .select("*")
            .eq("id", lead_id)
            .eq("org_id", org_id)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None

    async def insert_task(self, data: Dict[str, Any]) -> Dict[str, Any]:
        response = self.client.table("tasks").insert(data).execute()
        return response.data[0]

    async def insert_agent_log(self, data: Dict[str, Any]) -> Dict[str, Any]:
        response = self.client.table("agent_logs").insert(data).execute()
        return response.data[0]

    async def insert_audit_log(self, data: Dict[str, Any]) -> Dict[str, Any]:
        # Ensure org_id is present
        if "org_id" not in data:
            data["org_id"] = self.fixed_org_id

        # Generate signature before insert
        signature = self._generate_signature(data)
        audit_data = {**data, "signature": signature, "timestamp": datetime.utcnow().isoformat()}
        response = self.client.table("audit_log").insert(audit_data).execute()
        return response.data[0]

    async def get_constitutional_limits(self, org_id: str) -> Dict[str, Any]:
        response = self.client.table("constitutional_limits").select("*").eq("org_id", org_id).execute()
        return {item["limit_type"]: float(item["limit_value"]) for item in response.data}

    async def count_daily_leads(self, org_id: str) -> int:
        today = datetime.utcnow().date().isoformat()
        response = self.client.table("leads").select("id", count="exact").eq("org_id", org_id).gte("created_at", today).execute()
        return response.count or 0

    async def get_daily_token_usage(self, org_id: str) -> int:
        today = datetime.utcnow().date().isoformat()
        response = self.client.table("agent_logs").select("tokens_used").eq("org_id", org_id).gte("timestamp", today).execute()
        return sum(item.get("tokens_used", 0) for item in response.data if item.get("tokens_used"))

    async def get_active_leads(self, org_id: str, priority_min: int = 3) -> List[Dict[str, Any]]:
        response = (
            self.client.table("leads")
            .select("*")
            .eq("org_id", org_id)
            .eq("status", "new")
            .gte("ai_priority", priority_min)
            .execute()
        )
        return response.data

    async def get_available_properties(self, org_id: str) -> List[Dict[str, Any]]:
        response = (
            self.client.table("properties")
            .select("*")
            .eq("org_id", org_id)
            .eq("status", "prospect")
            .execute()
        )
        return response.data

    async def update_property_matching(self, property_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        response = self.client.table("properties").update(data).eq("id", property_id).execute()
        return response.data[0]

    async def insert_agent_execution(self, data: Dict[str, Any]) -> Dict[str, Any]:
        response = self.client.table("agent_executions").insert(data).execute()
        return response.data[0]

    async def insert_weekly_recap(self, data: Dict[str, Any]) -> Dict[str, Any]:
        response = self.client.table("weekly_recaps").insert(data).execute()
        return response.data[0]

    async def get_recent_leads(self, days: int = 7, org_id: Optional[str] = None) -> List[Dict[str, Any]]:
        threshold = (datetime.utcnow() - timedelta(days=days)).isoformat()
        query = self.client.table("leads").select("*").gte("created_at", threshold)
        if org_id:
            query = query.eq("org_id", org_id)
        response = query.execute()
        return response.data

    async def get_recent_executions(self, days: int = 7) -> List[Dict[str, Any]]:
        threshold = (datetime.utcnow() - timedelta(days=days)).isoformat()
        response = self.client.table("agent_executions").select("*").gte("created_at", threshold).execute()
        return response.data

    async def get_recent_properties_updates(self, days: int = 7) -> List[Dict[str, Any]]:
        threshold = (datetime.utcnow() - timedelta(days=days)).isoformat()
        response = self.client.table("properties").select("*").gte("created_at", threshold).execute()
        return response.data

    async def get_active_members(self, org_id: str) -> List[Dict[str, Any]]:
        response = (
            self.client.table("organization_members")
            .select("id,user_id,role,status")
            .eq("org_id", org_id)
            .eq("status", "active")
            .execute()
        )
        return response.data or []

    async def get_owner_user_id(self, org_id: str) -> Optional[str]:
        org_response = (
            self.client.table("organizations")
            .select("owner_id")
            .eq("id", org_id)
            .limit(1)
            .execute()
        )
        if org_response.data and org_response.data[0].get("owner_id"):
            return str(org_response.data[0]["owner_id"])

        members = await self.get_active_members(org_id)
        for member in members:
            if str(member.get("role", "")).lower() == "owner":
                return str(member.get("user_id"))
        return None

    async def get_open_lead_workload_by_user(self, org_id: str, user_ids: List[str]) -> Dict[str, int]:
        if not user_ids:
            return {}

        response = (
            self.client.table("leads")
            .select("status,assigned_user_id,notes")
            .eq("org_id", org_id)
            .in_("status", ["new", "contacted", "qualified", "negotiating"])
            .execute()
        )
        leads = response.data or []
        counters = {uid: 0 for uid in user_ids}

        for lead in leads:
            assigned_user_id = lead.get("assigned_user_id")
            if assigned_user_id in counters:
                counters[str(assigned_user_id)] += 1
                continue

            # Legacy fallback while old rows are being migrated.
            notes = lead.get("notes")
            if not isinstance(notes, dict):
                continue
            routing = notes.get("routing")
            if not isinstance(routing, dict):
                continue
            legacy_assigned_user_id = routing.get("assigned_user_id")
            if legacy_assigned_user_id in counters:
                counters[str(legacy_assigned_user_id)] += 1

        return counters

    async def pick_lead_assignee(self, org_id: str) -> Dict[str, Optional[str]]:
        members = await self.get_active_members(org_id)
        owner_user_id = await self.get_owner_user_id(org_id)
        active_agents = [m for m in members if str(m.get("role", "")).lower() == "agent"]

        if active_agents:
            agent_ids = [str(m["user_id"]) for m in active_agents if m.get("user_id")]
            workload = await self.get_open_lead_workload_by_user(org_id, agent_ids)
            min_load = min((workload.get(uid, 0) for uid in agent_ids), default=0)
            least_busy_agents = [uid for uid in agent_ids if workload.get(uid, 0) == min_load]

            if len(least_busy_agents) == 1:
                return {
                    "user_id": least_busy_agents[0],
                    "role": "agent",
                    "reason": "least_busy_agent",
                }

            if owner_user_id:
                return {
                    "user_id": owner_user_id,
                    "role": "owner",
                    "reason": "tie_break_owner",
                }

            if least_busy_agents:
                return {
                    "user_id": least_busy_agents[0],
                    "role": "agent",
                    "reason": "least_busy_fallback",
                }

        if owner_user_id:
            return {
                "user_id": owner_user_id,
                "role": "owner",
                "reason": "no_active_agents_owner_fallback",
            }

        if members:
            fallback_user_id = str(members[0].get("user_id")) if members[0].get("user_id") else None
            fallback_role = str(members[0].get("role")) if members[0].get("role") else None
            return {
                "user_id": fallback_user_id,
                "role": fallback_role,
                "reason": "first_active_member_fallback",
            }

        return {"user_id": None, "role": None, "reason": "no_active_members"}

neon_service = NeonService()
