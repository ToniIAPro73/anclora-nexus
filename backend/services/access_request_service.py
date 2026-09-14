import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from backend.config import settings
from backend.models.access_requests import (
    AccessRequestAnalyticsSummary,
    AccessRequestAttentionItem,
    AccessRequestEmailStatus,
    AccessRequestLifecycleResponse,
    AccessRequestProduct,
    AccessRequestProvisioningStatus,
    AccessRequestRejectDecision,
    AccessRequestReviewDecision,
    AccessRequestSlaItem,
    AccessRequestSlaReason,
    AccessRequestSlaScanResponse,
    AccessRequestSlaSeverity,
    AccessRequestSource,
    AccessRequestStatus,
    PublicAccessRequestCreate,
)
from backend.services.access_request_audit_service import access_request_audit_service
from backend.services.access_request_email_service import access_request_email_service
from backend.services.captcha_verification_service import captcha_verification_service, CaptchaVerificationError
from backend.services.identity_provisioning_service import identity_provisioning_service
from backend.services.supabase_service import supabase_service

logger = logging.getLogger(__name__)

TERMINAL_ACCESS_REQUEST_STATUSES = {
    AccessRequestStatus.APPROVED.value,
    AccessRequestStatus.REJECTED.value,
    AccessRequestStatus.CANCELLED.value,
}
DECISION_EMAIL_AUDIT_ACTIONS = {
    "access_request.email_sent",
    "access_request.email_skipped",
    "access_request.email_send_failed",
    "access_request.decision_email_retry_succeeded",
    "access_request.decision_email_retry_failed",
}
SLA_AUDIT_ACTIONS = {
    "access_request.sla_warning",
    "access_request.sla_critical",
}

class AccessRequestNotFoundError(Exception):
    pass

class AccessRequestInvalidTransitionError(Exception):
    pass

class AccessRequestService:
    async def create_public_request(self, data: PublicAccessRequestCreate, remote_ip: Optional[str] = None) -> Dict[str, Any]:
        # 1. Verify Captcha
        captcha_result = captcha_verification_service.verify(
            provider=data.captcha_provider,
            token=data.captcha_token,
            remote_ip=remote_ip
        )
        
        # Enforce verification if provider is specified and required
        if captcha_result.get("required") and not captcha_result.get("verified"):
            logger.warning(f"Captcha verification failed for {data.email}")
            raise CaptchaVerificationError(f"{data.captcha_provider} verification failed")
        
        # 2. Prepare data for persistence
        # org_id is strictly controlled by backend
        org_id = settings.LEGACY_SINGLE_TENANT_ORG_ID or settings.PUBLIC_CTA_ORG_ID
        
        persistence_data = data.model_dump(exclude={"captcha_token", "lead_type"})
        persistence_data["org_id"] = org_id
        persistence_data["captcha_verified"] = captcha_result.get("verified", False)
        persistence_data["captcha_hostname"] = captcha_result.get("hostname")
        persistence_data["status"] = "pending"

        # Anclora Intake Contract v1: set domain and routing fields from product
        persistence_data["schema_version"] = "anclora-intake-v1"
        persistence_data["intake_domain"] = "access_request"
        persistence_data["routing_target_domain"] = "access_requests"
        if not persistence_data.get("request_type"):
            _product = str(data.product.value) if hasattr(data.product, "value") else str(data.product)
            persistence_data["request_type"] = {
                "syncxml": "pilot_request",
                "guesthub": "pilot_request",
                "synergi": "partner_admission",
                "data_lab": "access_request",
            }.get(_product)
        
        # 3. Persist to Supabase
        result = supabase_service.client.table("access_requests").insert(persistence_data).execute()
        
        if not result.data:
            logger.error(f"Failed to persist access request: {result}")
            raise RuntimeError("Failed to persist access request")
            
        record = result.data[0]
        await self._log_audit_event(
            org_id=str(record.get("org_id") or org_id),
            access_request_id=str(record["id"]),
            event_type="access_request.created",
            metadata={
                "product": record.get("product") or persistence_data.get("product"),
                "source": record.get("source") or persistence_data.get("source"),
                "email": record.get("email"),
            },
        )
        
        # 4. TODO: Internal notification
        logger.info(f"Access request created: {record['id']} for {record['email']}")
        
        return {
            "id": record["id"],
            "status": record["status"],
            "product": record["product"],
            "email": record["email"]
        }

    async def list_requests(
        self,
        org_id: str,
        status: Optional[AccessRequestStatus] = None,
        product: Optional[AccessRequestProduct] = None,
        source: Optional[AccessRequestSource] = None,
        request_type: Optional[str] = None,
        intake_domain: Optional[str] = None,
        email: Optional[str] = None,
        created_from: Optional[str] = None,
        created_to: Optional[str] = None,
        limit: int = 50,
    ) -> list[Dict[str, Any]]:
        query = supabase_service.client.table("access_requests").select("*").eq("org_id", org_id)
        if status:
            query = query.eq("status", status.value)
        if product:
            query = query.eq("product", product.value)
        if source:
            query = query.eq("source", source.value)
        if request_type:
            query = query.eq("request_type", request_type)
        # Always filter to access_request domain — commercial leads never appear in this view
        if not intake_domain:
            intake_domain = "access_request"
        query = query.eq("intake_domain", intake_domain)
        if email and email.strip():
            query = query.ilike("email", f"%{email.strip()}%")
        if created_from:
            query = query.gte("created_at", created_from)
        if created_to:
            query = query.lte("created_at", created_to)

        result = query.order("created_at", desc=True).limit(limit).execute()
        return result.data or []

    async def get_request(self, org_id: str, request_id: str) -> Dict[str, Any]:
        result = (
            supabase_service.client.table("access_requests")
            .select("*")
            .eq("org_id", org_id)
            .eq("id", request_id)
            .limit(1)
            .execute()
        )
        if not result.data:
            raise AccessRequestNotFoundError(f"Access request {request_id} not found")
        return result.data[0]

    async def get_analytics_summary(
        self,
        org_id: str,
        limit: int = 500,
    ) -> AccessRequestAnalyticsSummary:
        sample_limit = max(1, min(limit, 1000))
        request_result = (
            supabase_service.client.table("access_requests")
            .select("*")
            .eq("org_id", org_id)
            .order("created_at", desc=True)
            .limit(sample_limit)
            .execute()
        )
        rows = request_result.data or []
        audit_result = (
            supabase_service.client.table("audit_log")
            .select("timestamp,action,resource_id,details")
            .eq("org_id", org_id)
            .eq("resource_type", "access_request")
            .order("timestamp", desc=True)
            .limit(min(sample_limit * 4, 2000))
            .execute()
        )
        audit_events_by_request = self._group_audit_events(audit_result.data or [])

        now = datetime.now(timezone.utc)
        requests_by_product = {product.value: 0 for product in AccessRequestProduct}
        requests_by_source = {source.value: 0 for source in AccessRequestSource}
        status_counts = {status.value: 0 for status in AccessRequestStatus}
        pending_older_than_24h = 0
        pending_older_than_72h = 0
        decision_email_failed_count = 0
        decision_email_unknown_count = 0
        retry_available_count = 0
        provisioning_attention_count = 0
        review_durations: list[float] = []
        attention_items: list[AccessRequestAttentionItem] = []

        for row in rows:
            status_value = str(row.get("status") or "")
            product_value = str(row.get("product") or "")
            source_value = str(row.get("source") or "")
            if status_value in status_counts:
                status_counts[status_value] += 1
            if product_value in requests_by_product:
                requests_by_product[product_value] += 1
            if source_value in requests_by_source:
                requests_by_source[source_value] += 1

            created_at = self._parse_datetime(row.get("created_at"))
            reviewed_at = self._parse_datetime(row.get("reviewed_at"))
            age_hours = self._hours_between(created_at, now) if created_at else None
            if created_at and reviewed_at:
                review_durations.append(self._hours_between(created_at, reviewed_at))

            events = audit_events_by_request.get(str(row.get("id")), [])
            lifecycle = self._build_lifecycle(row, events)

            if status_value == AccessRequestStatus.PENDING.value:
                if age_hours is not None and age_hours >= 24:
                    pending_older_than_24h += 1
                    if age_hours >= 72:
                        pending_older_than_72h += 1
                        attention_items.append(self._attention_item(row, "pending_older_than_72h", "critical", age_hours))
                    else:
                        attention_items.append(self._attention_item(row, "pending_older_than_24h", "warning", age_hours))

            if status_value in TERMINAL_ACCESS_REQUEST_STATUSES:
                if lifecycle.email_status == AccessRequestEmailStatus.FAILED:
                    decision_email_failed_count += 1
                    attention_items.append(self._attention_item(row, "decision_email_failed", "critical", age_hours))
                if lifecycle.email_status == AccessRequestEmailStatus.UNKNOWN:
                    decision_email_unknown_count += 1
                    attention_items.append(self._attention_item(row, "decision_email_unknown", "warning", age_hours))
                if lifecycle.retry_available:
                    retry_available_count += 1
                    attention_items.append(self._attention_item(row, "retry_available", "warning", age_hours))

            if (
                status_value == AccessRequestStatus.APPROVED.value
                and lifecycle.provisioning_status != AccessRequestProvisioningStatus.INVITE_READY
            ):
                provisioning_attention_count += 1
                attention_items.append(self._attention_item(row, "provisioning_attention", "warning", age_hours))

        attention_items = sorted(
            attention_items,
            key=lambda item: (
                0 if item.severity == "critical" else 1,
                -(item.age_hours or 0),
            ),
        )[:25]

        average_review_time_hours = (
            round(sum(review_durations) / len(review_durations), 2)
            if review_durations
            else None
        )
        return AccessRequestAnalyticsSummary(
            total_requests=len(rows),
            pending_count=status_counts[AccessRequestStatus.PENDING.value],
            approved_count=status_counts[AccessRequestStatus.APPROVED.value],
            rejected_count=status_counts[AccessRequestStatus.REJECTED.value],
            cancelled_count=status_counts[AccessRequestStatus.CANCELLED.value],
            requests_by_product=requests_by_product,
            requests_by_source=requests_by_source,
            pending_older_than_24h=pending_older_than_24h,
            pending_older_than_72h=pending_older_than_72h,
            average_review_time_hours=average_review_time_hours,
            decision_email_failed_count=decision_email_failed_count,
            decision_email_unknown_count=decision_email_unknown_count,
            retry_available_count=retry_available_count,
            provisioning_attention_count=provisioning_attention_count,
            generated_at=self._now(),
            sample_size=len(rows),
            sample_limit=sample_limit,
            is_sampled=len(rows) >= sample_limit,
            attention_items=attention_items,
        )

    async def run_sla_scan(
        self,
        org_id: str,
        reviewer_id: str,
        dedupe_window_hours: int = 24,
        limit: int = 500,
    ) -> AccessRequestSlaScanResponse:
        reviewer_id = reviewer_id.strip()
        if not reviewer_id:
            raise ValueError("reviewer_id is required")

        scan_limit = max(1, min(limit, 1000))
        dedupe_hours = max(1, min(dedupe_window_hours, 168))
        now = datetime.now(timezone.utc)
        scan_id = str(uuid.uuid4())

        # 1. Fetch requests
        request_result = (
            supabase_service.client.table("access_requests")
            .select("*")
            .eq("org_id", org_id)
            .order("created_at", desc=True)
            .limit(scan_limit)
            .execute()
        )
        rows = request_result.data or []

        # 2. Fetch recent SLA audit events for deduplication
        # We look back dedupe_hours + some buffer to be safe
        lookback_time = (now - timedelta(hours=dedupe_hours + 1)).isoformat()
        audit_result = (
            supabase_service.client.table("audit_log")
            .select("timestamp,action,resource_id,details")
            .eq("org_id", org_id)
            .eq("resource_type", "access_request")
            .in_("action", list(SLA_AUDIT_ACTIONS))
            .gte("timestamp", lookback_time)
            .execute()
        )
        recent_sla_events = audit_result.data or []
        audit_events_by_request = self._group_audit_events(recent_sla_events)

        # 3. Process requests and identify SLA alerts
        items: list[AccessRequestSlaItem] = []
        alerts_created = 0
        alerts_suppressed = 0
        warning_count = 0
        critical_count = 0

        for row in rows:
            request_id = str(row["id"])
            status_value = str(row.get("status") or AccessRequestStatus.PENDING.value)
            
            # Build lifecycle to get email/provisioning status
            # For heavy scans, we might want to optimize this, but for now we follow analytics pattern
            # Fetching individual audit events per request would be slow, but we only need recent SLA events for dedupe
            # and maybe some others for email status.
            # However, analytics_summary fetches MANY audit events.
            # Let's assume we need to evaluate the same logic as analytics_summary attention items.
            
            created_at = self._parse_datetime(row.get("created_at"))
            age_hours = self._hours_between(created_at, now) if created_at else None
            
            # For email/provisioning status, we need full audit history of the request
            # OR we can rely on the fact that lifecycle logic is already in _build_lifecycle
            # To avoid N+1 queries, we could have fetched all relevant audit events for these rows upfront.
            # But analytics summary does a limit 2000.
            
            # Let's try to identify reasons
            potential_alerts: list[Tuple[AccessRequestSlaReason, AccessRequestSlaSeverity]] = []

            if status_value == AccessRequestStatus.PENDING.value:
                if age_hours is not None:
                    if age_hours >= 72:
                        potential_alerts.append((AccessRequestSlaReason.PENDING_OLDER_THAN_72H, AccessRequestSlaSeverity.CRITICAL))
                    elif age_hours >= 24:
                        potential_alerts.append((AccessRequestSlaReason.PENDING_OLDER_THAN_24H, AccessRequestSlaSeverity.WARNING))

            # For terminal statuses, we need lifecycle to check email/provisioning
            # This is slow if we do it for every row. 
            # In a real system, we'd fetch all audit events for these rows in one query.
            # For now, let's only do it if it's in a terminal status or we need attention.
            
            if status_value in TERMINAL_ACCESS_REQUEST_STATUSES or (status_value == AccessRequestStatus.APPROVED.value):
                # We need more info for these. Let's fetch audit events for THIS request.
                # Optimization: in a real scan we'd batch this.
                request_audit = (
                    supabase_service.client.table("audit_log")
                    .select("timestamp,action,resource_id,details")
                    .eq("org_id", org_id)
                    .eq("resource_type", "access_request")
                    .eq("resource_id", request_id)
                    .order("timestamp", desc=True)
                    .execute()
                )
                lifecycle = self._build_lifecycle(row, request_audit.data or [])
                
                if status_value in TERMINAL_ACCESS_REQUEST_STATUSES:
                    if lifecycle.email_status == AccessRequestEmailStatus.FAILED:
                        potential_alerts.append((AccessRequestSlaReason.DECISION_EMAIL_FAILED, AccessRequestSlaSeverity.CRITICAL))
                    if lifecycle.email_status == AccessRequestEmailStatus.UNKNOWN:
                        potential_alerts.append((AccessRequestSlaReason.DECISION_EMAIL_UNKNOWN, AccessRequestSlaSeverity.WARNING))
                    if lifecycle.retry_available:
                        potential_alerts.append((AccessRequestSlaReason.RETRY_AVAILABLE, AccessRequestSlaSeverity.WARNING))

                if status_value == AccessRequestStatus.APPROVED.value and lifecycle.provisioning_status != AccessRequestProvisioningStatus.INVITE_READY:
                    potential_alerts.append((AccessRequestSlaReason.PROVISIONING_ATTENTION, AccessRequestSlaSeverity.WARNING))

            # 4. Filter through dedupe and log
            for reason, severity in potential_alerts:
                # Check dedupe
                is_suppressed = False
                last_alert_at = None
                
                request_recent_events = audit_events_by_request.get(request_id, [])
                for event in request_recent_events:
                    details = event.get("details") or {}
                    if (
                        details.get("reason") == reason.value and 
                        details.get("severity") == severity.value
                    ):
                        event_time = self._parse_datetime(event.get("timestamp"))
                        if event_time and (now - event_time).total_seconds() < dedupe_hours * 3600:
                            is_suppressed = True
                            last_alert_at = event_time
                            break
                
                audit_event_created = False
                if not is_suppressed:
                    event_type = "access_request.sla_critical" if severity == AccessRequestSlaSeverity.CRITICAL else "access_request.sla_warning"
                    await self._log_audit_event(
                        org_id=org_id,
                        access_request_id=request_id,
                        event_type=event_type,
                        actor_id=reviewer_id,
                        actor_type="user",
                        metadata={
                            "reason": reason.value,
                            "severity": severity.value,
                            "age_hours": age_hours,
                            "scan_id": scan_id,
                        }
                    )
                    audit_event_created = True
                    alerts_created += 1
                    if severity == AccessRequestSlaSeverity.CRITICAL:
                        critical_count += 1
                    else:
                        warning_count += 1
                else:
                    alerts_suppressed += 1

                items.append(AccessRequestSlaItem(
                    request_id=request_id,
                    reason=reason,
                    severity=severity,
                    status=status_value,
                    product=str(row.get("product") or ""),
                    source=str(row.get("source") or ""),
                    email=str(row.get("email") or ""),
                    age_hours=age_hours,
                    audit_event_created=audit_event_created,
                    suppressed_by_dedupe=is_suppressed,
                    last_alert_at=last_alert_at
                ))

        return AccessRequestSlaScanResponse(
            scan_id=scan_id,
            generated_at=now,
            scanned_count=len(rows),
            alerts_created=alerts_created,
            alerts_suppressed=alerts_suppressed,
            warning_count=warning_count,
            critical_count=critical_count,
            notification_status="audit_only",
            dedupe_window_hours=dedupe_hours,
            items=items
        )

    async def approve_request(
        self,
        org_id: str,
        request_id: str,
        decision: AccessRequestReviewDecision,
        reviewer_id: str,
    ) -> Dict[str, Any]:
        reviewer_id = reviewer_id.strip()
        if not reviewer_id:
            raise ValueError("reviewer_id is required")

        pending_record = await self._ensure_pending(org_id, request_id)

        # Execute canonical provisioning via Anclora Identity
        prov_result = await identity_provisioning_service.provision_approved_request(
            request=pending_record,
            reviewer_id=reviewer_id,
        )

        invite_token = prov_result.get("invite_token") or pending_record.get("invite_token") or self._generate_invite_token()
        invite_expires_at = prov_result.get("invite_expires_at") or pending_record.get("invite_expires_at") or self._invite_expires_at()
        invite_created = not pending_record.get("invite_token")
        now = self._now()
        update_payload: Dict[str, Any] = {
            "status": AccessRequestStatus.APPROVED.value,
            "reviewed_at": now,
            "reviewed_by": reviewer_id,
            "admin_notes": decision.admin_notes,
            "invite_token": invite_token,
            "invite_expires_at": invite_expires_at,
            "provisioning_status": prov_result.get("provisioning_status", AccessRequestProvisioningStatus.INVITE_READY.value),
            "updated_at": now,
        }
        if prov_result.get("identity_subject_id"):
            update_payload["identity_subject_id"] = prov_result["identity_subject_id"]
        if prov_result.get("identity_invitation_id"):
            update_payload["identity_invitation_id"] = prov_result["identity_invitation_id"]
        if prov_result.get("membership_id"):
            update_payload["membership_id"] = prov_result["membership_id"]
        if prov_result.get("provisioning_error"):
            update_payload["provisioning_error"] = prov_result["provisioning_error"]

        record = await self._update_pending_request(org_id, request_id, update_payload)
        await self._log_audit_event(
            org_id=org_id,
            access_request_id=request_id,
            event_type="access_request.approved",
            actor_id=reviewer_id,
            actor_type="user",
            metadata={"admin_notes": decision.admin_notes},
        )
        await self._log_audit_event(
            org_id=org_id,
            access_request_id=request_id,
            event_type="access_request.provisioning_intent_prepared",
            actor_id=reviewer_id,
            actor_type="user",
            metadata={
                "product": record.get("product"),
                "invite_created": invite_created,
                "invite_expires_at": invite_expires_at,
                "provisioning_status": update_payload["provisioning_status"],
                "provisioning_case": prov_result.get("provisioning_case"),
                "identity_subject_id": prov_result.get("identity_subject_id"),
                "identity_invitation_id": prov_result.get("identity_invitation_id"),
                "membership_id": prov_result.get("membership_id"),
            },
        )
        record["decision_email"] = await self._send_decision_email(record)
        record["lifecycle"] = self._build_lifecycle(record, [], record["decision_email"]).model_dump(mode="json")
        return record

    async def reject_request(
        self,
        org_id: str,
        request_id: str,
        decision: AccessRequestRejectDecision,
        reviewer_id: str,
    ) -> Dict[str, Any]:
        reviewer_id = reviewer_id.strip()
        if not reviewer_id:
            raise ValueError("reviewer_id is required")

        await self._ensure_pending(org_id, request_id)
        now = self._now()
        update_payload = {
            "status": AccessRequestStatus.REJECTED.value,
            "reviewed_at": now,
            "reviewed_by": reviewer_id,
            "admin_notes": decision.admin_notes,
            "rejection_reason": decision.rejection_reason,
            "updated_at": now,
        }
        record = await self._update_pending_request(org_id, request_id, update_payload)
        await self._log_audit_event(
            org_id=org_id,
            access_request_id=request_id,
            event_type="access_request.rejected",
            actor_id=reviewer_id,
            actor_type="user",
            metadata={
                "admin_notes": decision.admin_notes,
                "rejection_reason": decision.rejection_reason,
            },
        )
        record["decision_email"] = await self._send_decision_email(record)
        record["lifecycle"] = self._build_lifecycle(record, [], record["decision_email"]).model_dump(mode="json")
        return record

    async def get_lifecycle(
        self,
        org_id: str,
        request_id: str,
    ) -> AccessRequestLifecycleResponse:
        record = await self.get_request(org_id, request_id)
        audit_events = await self.list_audit_events(org_id, request_id)
        return self._build_lifecycle(record, audit_events)

    async def retry_decision_email(
        self,
        org_id: str,
        request_id: str,
        reviewer_id: str,
    ) -> Dict[str, Any]:
        reviewer_id = reviewer_id.strip()
        if not reviewer_id:
            raise ValueError("reviewer_id is required")

        record = await self.get_request(org_id, request_id)
        if record.get("status") == AccessRequestStatus.PENDING.value:
            raise AccessRequestInvalidTransitionError(
                f"Access request {request_id} is pending and has no decision email to retry"
            )
        if record.get("status") not in {
            AccessRequestStatus.APPROVED.value,
            AccessRequestStatus.REJECTED.value,
        }:
            raise AccessRequestInvalidTransitionError(
                f"Access request {request_id} cannot retry decision email from {record.get('status')}"
            )

        audit_events = await self.list_audit_events(org_id, request_id)
        lifecycle = self._build_lifecycle(record, audit_events)
        if lifecycle.email_status == AccessRequestEmailStatus.SENT or not lifecycle.retry_available:
            raise AccessRequestInvalidTransitionError(
                f"Access request {request_id} decision email retry is not available"
            )

        await self._log_audit_event(
            org_id=org_id,
            access_request_id=request_id,
            event_type="access_request.decision_email_retry_requested",
            actor_id=reviewer_id,
            actor_type="user",
            metadata={"previous_email_status": lifecycle.email_status.value},
        )
        result = await self._send_decision_email(record)
        sanitized_result = self._sanitize_decision_email_result(result)
        retry_succeeded = sanitized_result.get("status") == AccessRequestEmailStatus.SENT.value
        await self._log_audit_event(
            org_id=org_id,
            access_request_id=request_id,
            event_type="access_request.decision_email_retry_succeeded"
            if retry_succeeded
            else "access_request.decision_email_retry_failed",
            actor_id=reviewer_id,
            actor_type="user",
            metadata={
                "status": sanitized_result.get("status"),
                "transport": sanitized_result.get("transport"),
                "to": sanitized_result.get("to"),
                "subject": sanitized_result.get("subject"),
            },
        )
        record["decision_email"] = sanitized_result
        record["lifecycle"] = self._build_lifecycle(record, [], sanitized_result).model_dump(mode="json")
        return record

    async def list_audit_events(
        self,
        org_id: str,
        request_id: str,
    ) -> list[Dict[str, Any]]:
        await self.get_request(org_id, request_id)
        result = (
            supabase_service.client.table("audit_log")
            .select("id,timestamp,actor_type,actor_id,action,resource_type,resource_id,details")
            .eq("org_id", org_id)
            .eq("resource_type", "access_request")
            .eq("resource_id", request_id)
            .order("timestamp", desc=False)
            .execute()
        )
        return result.data or []

    async def _ensure_pending(self, org_id: str, request_id: str) -> Dict[str, Any]:
        record = await self.get_request(org_id, request_id)
        current_status = record.get("status")
        if current_status != AccessRequestStatus.PENDING.value:
            if current_status in TERMINAL_ACCESS_REQUEST_STATUSES:
                raise AccessRequestInvalidTransitionError(
                    f"Access request {request_id} is already {current_status}"
                )
            raise AccessRequestInvalidTransitionError(
                f"Access request {request_id} cannot transition from {current_status}"
            )
        return record

    async def _update_pending_request(
        self,
        org_id: str,
        request_id: str,
        update_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        result = (
            supabase_service.client.table("access_requests")
            .update(update_payload)
            .eq("org_id", org_id)
            .eq("id", request_id)
            .eq("status", AccessRequestStatus.PENDING.value)
            .execute()
        )
        if not result.data:
            raise AccessRequestInvalidTransitionError(
                f"Access request {request_id} is no longer pending"
            )
        return result.data[0]

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _generate_invite_token(self) -> str:
        return secrets.token_urlsafe(32)

    def _invite_expires_at(self) -> str:
        return (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()

    def _build_lifecycle(
        self,
        record: Dict[str, Any],
        audit_events: list[Dict[str, Any]],
        decision_email: Optional[Dict[str, Any]] = None,
    ) -> AccessRequestLifecycleResponse:
        status = str(record.get("status") or AccessRequestStatus.PENDING.value)
        email_status = self._derive_email_status(status, audit_events, decision_email)
        return AccessRequestLifecycleResponse(
            request_id=str(record["id"]),
            status=status,
            decision_status=status,
            provisioning_status=self._derive_provisioning_status(record),
            email_status=email_status,
            reviewed_by=record.get("reviewed_by"),
            reviewed_at=record.get("reviewed_at"),
            invite_expires_at=record.get("invite_expires_at"),
            retry_available=status in {
                AccessRequestStatus.APPROVED.value,
                AccessRequestStatus.REJECTED.value,
            }
            and email_status != AccessRequestEmailStatus.SENT,
            last_event_at=self._derive_last_event_at(record, audit_events),
        )

    def _derive_provisioning_status(self, record: Dict[str, Any]) -> AccessRequestProvisioningStatus:
        status = record.get("status")
        prov_status = record.get("provisioning_status")
        if prov_status:
            try:
                return AccessRequestProvisioningStatus(prov_status)
            except ValueError:
                pass
        if status == AccessRequestStatus.PENDING.value:
            return AccessRequestProvisioningStatus.NOT_STARTED
        if status == AccessRequestStatus.REJECTED.value or status == AccessRequestStatus.CANCELLED.value:
            return AccessRequestProvisioningStatus.NOT_APPLICABLE
        if status == AccessRequestStatus.APPROVED.value:
            if record.get("membership_id") or prov_status == "provisioned":
                return AccessRequestProvisioningStatus.PROVISIONED
            if record.get("invite_token") and record.get("invite_expires_at"):
                return AccessRequestProvisioningStatus.INVITE_READY
            return AccessRequestProvisioningStatus.PROVISIONING_PENDING
        return AccessRequestProvisioningStatus.NOT_APPLICABLE

    def _derive_email_status(
        self,
        status: str,
        audit_events: list[Dict[str, Any]],
        decision_email: Optional[Dict[str, Any]] = None,
    ) -> AccessRequestEmailStatus:
        if status == AccessRequestStatus.PENDING.value:
            return AccessRequestEmailStatus.NOT_APPLICABLE
        if decision_email and decision_email.get("status"):
            return self._normalize_email_status(str(decision_email["status"]))

        for event in reversed(audit_events):
            action = event.get("action")
            if action not in DECISION_EMAIL_AUDIT_ACTIONS:
                continue
            details = event.get("details") or {}
            if action == "access_request.email_sent":
                return AccessRequestEmailStatus.SENT
            if action == "access_request.email_skipped":
                return AccessRequestEmailStatus.SKIPPED
            if action == "access_request.email_send_failed":
                return AccessRequestEmailStatus.FAILED
            if action == "access_request.decision_email_retry_succeeded":
                return AccessRequestEmailStatus.SENT
            if action == "access_request.decision_email_retry_failed":
                return self._normalize_email_status(str(details.get("status") or "failed"))
        return AccessRequestEmailStatus.UNKNOWN

    def _normalize_email_status(self, value: str) -> AccessRequestEmailStatus:
        normalized = value.strip().lower()
        if normalized == AccessRequestEmailStatus.SENT.value:
            return AccessRequestEmailStatus.SENT
        if normalized == AccessRequestEmailStatus.FAILED.value:
            return AccessRequestEmailStatus.FAILED
        if normalized == AccessRequestEmailStatus.SKIPPED.value:
            return AccessRequestEmailStatus.SKIPPED
        if normalized == AccessRequestEmailStatus.NOT_APPLICABLE.value:
            return AccessRequestEmailStatus.NOT_APPLICABLE
        return AccessRequestEmailStatus.UNKNOWN

    def _derive_last_event_at(
        self,
        record: Dict[str, Any],
        audit_events: list[Dict[str, Any]],
    ) -> Optional[str]:
        event_timestamps = [
            str(event["timestamp"])
            for event in audit_events
            if event.get("timestamp")
        ]
        if event_timestamps:
            return max(event_timestamps)
        return record.get("updated_at") or record.get("reviewed_at") or record.get("created_at")

    def _group_audit_events(self, events: list[Dict[str, Any]]) -> Dict[str, list[Dict[str, Any]]]:
        grouped: Dict[str, list[Dict[str, Any]]] = {}
        for event in events:
            resource_id = str(event.get("resource_id") or "")
            if not resource_id:
                continue
            grouped.setdefault(resource_id, []).append(event)
        for resource_events in grouped.values():
            resource_events.sort(key=lambda event: str(event.get("timestamp") or ""))
        return grouped

    def _parse_datetime(self, value: Any) -> Optional[datetime]:
        if not value:
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

    def _hours_between(self, start: datetime, end: datetime) -> float:
        return round(max((end - start).total_seconds(), 0) / 3600, 2)

    def _attention_item(
        self,
        row: Dict[str, Any],
        reason: str,
        severity: str,
        age_hours: Optional[float],
    ) -> AccessRequestAttentionItem:
        return AccessRequestAttentionItem(
            request_id=str(row["id"]),
            reason=reason,
            severity=severity,
            status=str(row.get("status") or AccessRequestStatus.PENDING.value),
            product=str(row.get("product") or AccessRequestProduct.SYNERGI.value),
            source=str(row.get("source") or AccessRequestSource.NEXUS_MANUAL.value),
            email=str(row.get("email") or ""),
            created_at=row.get("created_at"),
            reviewed_at=row.get("reviewed_at"),
            age_hours=age_hours,
        )

    def _sanitize_decision_email_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        if result.get("status") != AccessRequestEmailStatus.FAILED.value:
            return result
        sanitized = dict(result)
        sanitized["error"] = "decision_email_send_failed"
        return sanitized

    async def _log_audit_event(
        self,
        *,
        org_id: str,
        access_request_id: str,
        event_type: str,
        actor_id: Optional[str] = None,
        actor_type: str = "system",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        try:
            await access_request_audit_service.log_event(
                org_id=org_id,
                access_request_id=access_request_id,
                event_type=event_type,
                actor_id=actor_id,
                actor_type=actor_type,
                metadata=metadata,
            )
        except Exception as e:
            logger.warning("Access request audit logging failed: %s", e)

    async def _send_decision_email(self, record: Dict[str, Any]) -> Dict[str, Any]:
        try:
            result = access_request_email_service.send_decision_email(record)
            await self._log_audit_event(
                org_id=str(record["org_id"]),
                access_request_id=str(record["id"]),
                event_type="access_request.email_sent"
                if result.get("status") == "sent"
                else "access_request.email_skipped",
                metadata={
                    "status": result.get("status"),
                    "transport": result.get("transport"),
                    "to": result.get("to"),
                    "subject": result.get("subject"),
                },
            )
            return result
        except Exception as e:
            logger.warning("Access request decision email failed: %s", e)
            await self._log_audit_event(
                org_id=str(record["org_id"]),
                access_request_id=str(record["id"]),
                event_type="access_request.email_send_failed",
                metadata={"error": str(e), "status": record.get("status")},
            )
            return {"status": "failed", "error": str(e)}

access_request_service = AccessRequestService()
