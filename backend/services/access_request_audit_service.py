from __future__ import annotations

from typing import Any, Dict, Optional

from backend.services.neon_service import neon_service


class AccessRequestAuditService:
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

        return await neon_service.insert_audit_log(
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


access_request_audit_service = AccessRequestAuditService()
