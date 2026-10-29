from __future__ import annotations

from typing import Any, Dict, Optional

from backend.services.neon_service import neon_service


class AccessRequestAuditService:
    def prepare_event(
        self,
        *,
        org_id: str,
        access_request_id: str,
        event_type: str,
        actor_id: Optional[str] = None,
        actor_type: str = "system",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        normalized_event_type = str(event_type or "").strip()
        if not normalized_event_type.startswith("access_request."):
            raise ValueError("event_type must use the access_request namespace")
        return neon_service.prepare_access_request_audit_event(
            {
                "org_id": org_id,
                "actor_type": actor_type,
                "actor_id": actor_id or "system",
                "action": normalized_event_type,
                "resource_type": "access_request",
                "resource_id": access_request_id,
                "details": metadata or {},
            }
        )

    async def log_event(
        self,
        *,
        org_id: str,
        access_request_id: str,
        event_type: str,
        actor_id: Optional[str] = None,
        actor_type: str = "system",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        normalized_event_type = str(event_type or "").strip()
        if not normalized_event_type:
            raise ValueError("event_type is required")

        event = self.prepare_event(
            org_id=org_id,
            access_request_id=access_request_id,
            event_type=normalized_event_type,
            actor_id=actor_id,
            actor_type=actor_type,
            metadata=metadata,
        )
        result = neon_service.client.rpc(
            "nexus_log_access_request_audit_event",
            {
                "p_org_id": org_id,
                "p_request_id": access_request_id,
                "p_audit_event": event,
            },
        ).execute()
        if not result.data:
            raise RuntimeError("Access request audit event could not be persisted")
        return result.data[0] if isinstance(result.data, list) else result.data


access_request_audit_service = AccessRequestAuditService()
