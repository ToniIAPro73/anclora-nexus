import hashlib
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import httpx
from pydantic import BaseModel, EmailStr, Field, ValidationError

from backend.config import settings
from backend.services.access_request_email_service import access_request_email_service, build_access_request_fallback_admin_email
from backend.services.email_delivery_service import send_email_native
from backend.services.neon_service import neon_service

logger = logging.getLogger(__name__)

PRODUCTION_OR_REAL_DATA_PATTERN = re.compile(
    r"(datos reales|dato real|producci[oó]n|productivo|env[ií]o autom[aá]tico|ses autom[aá]tico|ministerio|ses\.hospedajes|hu[eé]spedes reales|viajeros reales)",
    re.IGNORECASE,
)
INSUFFICIENT_VALUES = {"", "no especificado", "n/a", "na", "none", "null"}
DEFAULT_TEMPORARY_PASSWORD_DAYS = 7
REAL_WRITE_BLOCK_REASON = "REAL_NEON_WRITE_BLOCKED"


class SyncXmlPilotPayload(BaseModel):
    requestId: Optional[str] = None
    idempotency_key: Optional[str] = None
    name: str = Field(min_length=1, max_length=180)
    email: EmailStr
    companyName: Optional[str] = Field(default=None, max_length=200)
    role: Optional[str] = Field(default=None, max_length=120)
    accommodationType: str = Field(min_length=1, max_length=120)
    estimatedMonthlyReservations: str = Field(min_length=1, max_length=80)
    currentWorkflow: str = Field(min_length=1, max_length=1200)
    mainPain: str = Field(min_length=1, max_length=1200)
    wantsToValidate: str = Field(default="", max_length=1200)
    acceptsSyntheticOrAnonymizedData: bool
    acceptsPilotConditions: bool
    usesRealGuestData: bool = False
    needsSesAutomaticSubmission: bool = False
    locale: str = "es"
    source: str = "syncxml_landing"
    raw: Dict[str, Any] = Field(default_factory=dict)


class SyncXmlApprovePayload(BaseModel):
    admin_notes: str = ""
    rotatePassword: bool = False
    expiresAt: Optional[str] = None


class SyncXmlRejectPayload(BaseModel):
    internal_reason: str = ""
    user_reason: str = Field(
        default=(
            "En esta fase estamos aceptando únicamente casos que encajan con una validación controlada muy concreta. "
            "Tu solicitud no encaja suficientemente con el alcance actual del piloto o requiere condiciones que todavía no ofrecemos."
        ),
        min_length=1,
        max_length=1200,
    )


class SyncXmlMoreInfoPayload(BaseModel):
    message: str = Field(
        default=(
            "Gracias por tu interés en Anclora GuestHub. Antes de confirmar el acceso al piloto necesitamos aclarar "
            "algunos detalles sobre tu caso de uso y confirmar que la prueba se realizará solo con datos sintéticos o anonimizados."
        ),
        min_length=1,
        max_length=1600,
    )


def _manual_review_result(reason: str) -> Dict[str, Any]:
    return {
        "decision": "manual_review",
        "score": 0,
        "riskFlags": [reason],
        "reasonInternal": reason,
        "emailReasonUser": "Tu solicitud requiere revisión manual antes de decidir el acceso.",
        "recommendedNextAction": "manual_review",
    }


def _is_insufficient(value: Optional[str]) -> bool:
    normalized = (value or "").strip().lower()
    return normalized in INSUFFICIENT_VALUES or len(normalized) < 4


class SyncXmlPilotService:
    def _safe_trace_context(self, payload: SyncXmlPilotPayload) -> Dict[str, Any]:
        email_hash = hashlib.sha256(str(payload.email).lower().encode("utf-8")).hexdigest()[:12]
        return {
            "requestId": payload.requestId,
            "idempotency_key": self._resolve_idempotency_key(payload),
            "email_hash": email_hash,
            "source": payload.source,
        }

    def _resolve_idempotency_key(self, payload: SyncXmlPilotPayload) -> Optional[str]:
        raw_key = payload.raw.get("idempotency_key") if payload.raw else None
        return payload.idempotency_key or raw_key or payload.requestId

    def _credentials_confirm_login_ready(self, record: Dict[str, Any], credentials: Dict[str, Any]) -> bool:
        expected_email = str(record.get("email") or "").strip().lower()
        returned_email = str(credentials.get("email") or "").strip().lower()
        return bool(
            credentials.get("ok")
            and credentials.get("loginReady") is True
            and credentials.get("temporaryPassword")
            and expected_email
            and returned_email == expected_email
            and str(credentials.get("status") or "").lower() == "active"
        )

    def _credentials_can_retry_with_rotated_password(self, record: Dict[str, Any], credentials: Dict[str, Any]) -> bool:
        expected_email = str(record.get("email") or "").strip().lower()
        returned_email = str(credentials.get("email") or "").strip().lower()
        return bool(
            credentials.get("ok")
            and credentials.get("loginReady") is True
            and not credentials.get("temporaryPassword")
            and expected_email
            and returned_email == expected_email
            and str(credentials.get("status") or "").lower() == "active"
        )

    def _is_non_production_environment(self) -> bool:
        return (settings.APP_ENV or "development").lower() != "production" or (settings.GUESTHUB_ENV or "development").lower() != "production"

    def _allow_real_neon_write(self) -> bool:
        return bool(settings.ALLOW_REAL_NEON_WRITE)

    def _is_staging_safety_mode(self) -> bool:
        return (
            self._is_non_production_environment()
            or not self._allow_real_neon_write()
            or bool(settings.USE_SYNTHETIC_DATA_ONLY)
        )

    def _block_real_write_reason(self, action: str) -> Dict[str, Any]:
        return {
            "ok": False,
            "blocked": True,
            "reason": REAL_WRITE_BLOCK_REASON,
            "action": action,
            "environment": settings.APP_ENV,
            "syncxmlEnvironment": settings.GUESTHUB_ENV,
            "allowRealNeonWrite": self._allow_real_neon_write(),
            "useSyntheticDataOnly": bool(settings.USE_SYNTHETIC_DATA_ONLY),
        }

    async def process_incoming_lead(self, data: Dict[str, Any]):
        try:
            payload = SyncXmlPilotPayload.model_validate(data)
        except ValidationError:
            logger.warning("Invalid SyncXML pilot payload: schema validation failed")
            raise

        org_id = settings.LEGACY_SINGLE_TENANT_ORG_ID or settings.PUBLIC_CTA_ORG_ID
        metadata = payload.model_dump(mode="json")
        review_result = await self._score_lead(payload)
        final_status = self._decide_status(payload, review_result)
        idempotency_key = self._resolve_idempotency_key(payload)
        trace = self._safe_trace_context(payload)

        logger.info("SyncXML pilot webhook accepted for persistence", extra=trace)

        if self._is_staging_safety_mode():
            blocked = self._block_real_write_reason("process_incoming_lead")
            blocked["decision"] = final_status
            blocked["ai_review"] = review_result
            logger.info("SyncXML pilot webhook blocked by safety mode", extra=trace)
            return blocked

        record_data = {
            "org_id": org_id,
            "product": "syncxml",
            "source": "syncxml_landing",
            "schema_version": "anclora-intake-v1",
            "intake_domain": "access_request",
            "request_type": "pilot_request",
            "routing_target_domain": "access_requests",
            "idempotency_key": idempotency_key,
            "full_name": payload.name,
            "email": str(payload.email),
            "company": payload.companyName,
            "profile_type": payload.accommodationType,
            "service_summary": payload.mainPain,
            "intended_use": payload.wantsToValidate,
            "requested_scope": "controlled_pilot",
            "message": payload.currentWorkflow,
            "privacy_accepted": payload.acceptsPilotConditions,
            "gdpr_consent": payload.acceptsPilotConditions,
            "submission_language": payload.locale,
            "status": final_status,
            "metadata": {
                **metadata,
                "request_type": "syncxml_pilot",
                "has_own_synthetic_or_anonymized_sample": payload.acceptsSyntheticOrAnonymizedData,
                "needsSyntheticSampleAttachments": payload.raw.get("needsSyntheticSampleAttachments") is True
                or payload.acceptsSyntheticOrAnonymizedData is False,
                "review_mode": "automatic" if final_status in {"approved", "rejected"} else "manual_review",
                "ai_review": review_result,
            },
        }
        if final_status == "rejected":
            record_data["rejection_reason"] = review_result.get("emailReasonUser") or "Fuera del alcance actual del piloto."

        try:
            if idempotency_key:
                existing = (
                    neon_service.client.table("access_requests")
                    .select("*")
                    .eq("idempotency_key", idempotency_key)
                    .limit(1)
                    .execute()
                )
                if existing.data:
                    existing_record = existing.data[0]
                    logger.info("SyncXML pilot webhook idempotent replay", extra=trace)
                    if existing_record.get("status") == "pending":
                        existing_review = (existing_record.get("metadata") or {}).get("ai_review") or review_result
                        await self._create_review_task(existing_record, existing_review)
                    return existing_record

            result = neon_service.client.table("access_requests").insert(record_data).execute()
            if not result.data:
                raise RuntimeError("Failed to persist SyncXML lead")
            record = result.data[0]
            logger.info(
                "SyncXML pilot access request inserted",
                extra={**trace, "access_request_id": record.get("id")},
            )

            if final_status == "pending":
                await self._create_review_task(record, review_result)
                if not payload.raw.get("adminEmailSentBySyncxml"):
                    self._send_safely(build_access_request_fallback_admin_email(record), record, "manual_review_email_failed")
            elif final_status == "approved":
                approval = await self._approve_with_credentials(
                    record,
                    SyncXmlApprovePayload(),
                    reviewer_id="system:syncxml_local_score",
                )
                return approval["record"]
            elif final_status == "rejected":
                ok = self._send_safely(access_request_email_service.build_decision_email(record), record, "decision_email_failed")
                if not ok:
                    await self._create_review_task(record, {**review_result, "riskFlags": ["decision_email_failed"]})

            return record
        except Exception as exc:
            logger.error(
                "Error processing SyncXML lead: request failed internally",
                extra={**trace, "error_type": type(exc).__name__},
            )
            raise

    async def _score_lead(self, payload: SyncXmlPilotPayload) -> Dict[str, Any]:
        if not settings.HERMES_WORKER_URL or not settings.HERMES_WORKER_API_KEY:
            logger.info("Hermes not configured for SyncXML, falling back to local scoring.")
            return self._score_locally(payload)
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    # Cross-service contract with the Hermes worker: path and type keep the
                    # legacy syncxml naming until Hermes adds a guesthub alias. Flagged for owner.
                    f"{settings.HERMES_WORKER_URL.rstrip('/')}/api/syncxml/pilot/validate",
                    json={
                        "type": "syncxml_pilot_validation",
                        "request": {
                            "name": payload.name,
                            "email": str(payload.email),
                            "company": payload.companyName,
                            "propertyCount": 1,
                            "currentWorkflow": payload.currentWorkflow,
                            "usesRealGuestData": payload.usesRealGuestData,
                            "needsSesAutomaticSubmission": payload.needsSesAutomaticSubmission,
                            "message": payload.mainPain + " " + payload.wantsToValidate,
                            "locale": payload.locale
                        }
                    },
                    headers={"Authorization": f"Bearer {settings.HERMES_WORKER_API_KEY}"},
                    timeout=15.0,
                )
            if response.is_success:
                hermes_data = response.json()
                return {
                    "decision": hermes_data.get("decision", "manual_review"),
                    "score": hermes_data.get("score", 0),
                    "riskFlags": hermes_data.get("flags", []),
                    "reasonInternal": hermes_data.get("reason", "Scored by Hermes"),
                    "emailReasonUser": "Tu solicitud ha sido revisada por nuestro asistente.",
                    "recommendedNextAction": hermes_data.get("recommendedNextAction", "manual_review"),
                }
            logger.warning("Hermes returned %s, falling back to local scoring", response.status_code)
        except Exception as exc:
            logger.warning("Hermes request failed: %s, falling back to local scoring", exc)
        return self._score_locally(payload)

    def _score_locally(self, payload: SyncXmlPilotPayload) -> Dict[str, Any]:
        if not payload.acceptsPilotConditions:
            return {
                "decision": "reject",
                "score": 10,
                "riskFlags": ["pilot_conditions_not_accepted"],
                "reasonInternal": "No acepta las condiciones mínimas del piloto.",
                "emailReasonUser": "Tu solicitud no encaja con las condiciones mínimas del piloto controlado.",
                "recommendedNextAction": "reject_pilot",
            }

        operational_text = " ".join([
            payload.currentWorkflow,
            payload.mainPain,
            payload.wantsToValidate or "",
        ])
        if PRODUCTION_OR_REAL_DATA_PATTERN.search(operational_text):
            return {
                "decision": "manual_review",
                "score": 45,
                "riskFlags": ["production_or_real_data_requested"],
                "reasonInternal": "La solicitud menciona datos reales, producción o envío automático a SES.HOSPEDAJES.",
                "emailReasonUser": "Tu solicitud requiere aclaración porque el piloto no permite datos reales ni envíos oficiales automáticos.",
                "recommendedNextAction": "manual_review",
            }

        if any(_is_insufficient(value) for value in [
            payload.accommodationType,
            payload.estimatedMonthlyReservations,
            payload.currentWorkflow,
            payload.mainPain,
        ]):
            return _manual_review_result("insufficient_operational_context")

        return {
            "decision": "approve",
            "score": 88,
            "riskFlags": [],
            "reasonInternal": "Caso compatible con validación controlada Excel/XLSX a XML.",
            "emailReasonUser": "Tu caso encaja con el alcance actual del piloto controlado.",
            "recommendedNextAction": "approve_pilot",
        }

    def _decide_status(self, payload: SyncXmlPilotPayload, ai: Dict[str, Any]) -> str:
        flags = ai.get("riskFlags") or []
        decision = ai.get("decision")
        score = int(ai.get("score") or 0)
        text = " ".join([payload.currentWorkflow, payload.mainPain, payload.wantsToValidate]).lower()
        risky_terms = ["datos reales", "producción", "produccion", "ses automático", "ses automatico", "ministerio automático"]

        if not payload.acceptsPilotConditions:
            return "rejected"
        if any(term in text for term in risky_terms):
            return "pending"
        if decision == "approve" and score >= 85 and not flags:
            if settings.GUESTHUB_PILOT_AUTO_APPROVE and not self._is_staging_safety_mode():
                return "approved"
            return "pending"
        if decision == "reject" and score <= 20 and flags:
            return "rejected"
        return "pending"

    async def _create_review_task(self, record: Dict[str, Any], ai: Dict[str, Any]) -> None:
        if self._is_staging_safety_mode():
            logger.info("Blocked SyncXML review task creation in safety mode")
            return
        request_id = str(record.get("id") or "")
        org_id = record.get("org_id") or settings.PUBLIC_CTA_ORG_ID
        payload = {
            "org_id": org_id,
            "title": f"Revisar piloto GuestHub · {record.get('email')}",
            "status": "pending",
            "task_type": "syncxml_pilot_review",
            "origin": "anclora-syncxml",
            "entity_type": "pilot_request",
            "entity_id": record.get("id"),
            "metadata": {
                "badge": "GuestHub · Piloto controlado",
                "access_request": record,
                "ai_review": ai,
            },
        }
        try:
            if request_id:
                existing = (
                    neon_service.client.table("tasks")
                    .select("id")
                    .eq("org_id", org_id)
                    .eq("task_type", "syncxml_pilot_review")
                    .eq("entity_id", request_id)
                    .limit(1)
                    .execute()
                )
                if existing.data:
                    return
            neon_service.client.table("tasks").insert(payload).execute()
        except Exception as exc:
            logger.warning("Could not create SyncXML review task: %s", exc)

    def _email_kwargs(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        payload = {
            "to_email": email_data["to"],
            "subject": email_data["subject"],
            "body": email_data["text"],
            "html": email_data["html"],
        }
        if email_data.get("attachments"):
            payload["attachments"] = email_data["attachments"]
        return payload

    def _send_safely(self, email_data: Dict[str, Any], record: Dict[str, Any], failure_code: str) -> bool:
        try:
            send_email_native(**self._email_kwargs(email_data))
            return True
        except Exception as exc:
            logger.warning("SyncXML email failed for request %s: %s", record.get("id"), exc)
            try:
                neon_service.client.table("access_requests").update({
                    "metadata": {
                        **(record.get("metadata") or {}),
                        "email_status": "failed",
                        "error_message": str(exc),
                        "failure_code": failure_code,
                    }
                }).eq("id", record["id"]).execute()
            except Exception:
                pass
            return False

    async def approve_manual(self, org_id: str, request_id: str, reviewer_id: str, payload: SyncXmlApprovePayload) -> Dict[str, Any]:
        if self._is_staging_safety_mode():
            return self._block_real_write_reason("approve_manual")
        record = await self._get_syncxml_request(org_id, request_id)
        return await self._approve_with_credentials(record, payload, reviewer_id=str(reviewer_id))

    async def _approve_with_credentials(self, record: Dict[str, Any], payload: SyncXmlApprovePayload, reviewer_id: str) -> Dict[str, Any]:
        if self._is_staging_safety_mode():
            return self._block_real_write_reason("approve_with_credentials")
        pending = self._merge_metadata(record, {
            "final_decision": "approved_pending_credentials",
            "credential_status": "pending",
            "email_status": "pending",
            "decided_by": reviewer_id,
        })
        self._update_request(record["id"], {"status": "pending", "metadata": pending, "admin_notes": payload.admin_notes})

        credentials = await self._create_syncxml_user(record, payload)
        if (
            not payload.rotatePassword
            and self._credentials_can_retry_with_rotated_password(record, credentials)
        ):
            rotated_payload = payload.model_copy(update={"rotatePassword": True})
            credentials = await self._create_syncxml_user(record, rotated_payload)

        if not self._credentials_confirm_login_ready(record, credentials):
            failed = self._merge_metadata(record, {
                "final_decision": "failed_credentials",
                "credential_status": "failed",
                "error_message": (
                    credentials.get("error")
                    or credentials.get("code")
                    or "GuestHub did not confirm login-ready pilot user provisioning"
                ),
            })
            updated = self._update_request(record["id"], {"status": "pending", "metadata": failed})
            await self._create_review_task(updated, _manual_review_result("credential_creation_failed"))
            self._send_safely(build_access_request_fallback_admin_email(updated), updated, "credential_creation_failed")
            return {"ok": False, "status": "failed_credentials", "record": updated}

        updated_record = self._update_request(record["id"], {
            "status": "approved",
            "reviewed_by": reviewer_id,
            "reviewed_at": self._now_iso(),
            "metadata": self._merge_metadata(record, {
                "final_decision": "approved",
                "credential_status": credentials.get("credentialStatus") or "created",
                "pilot_user_id": credentials.get("pilotUserId") or credentials.get("userId"),
            }),
        })
        sent = self._send_safely(
            access_request_email_service.build_syncxml_acceptance_email(updated_record, credentials),
            updated_record,
            "acceptance_email_failed",
        )
        final_metadata = self._merge_metadata(updated_record, {"email_status": "sent" if sent else "failed"})
        final_record = self._update_request(record["id"], {"metadata": final_metadata})
        if not sent:
            await self._create_review_task(final_record, _manual_review_result("acceptance_email_failed"))
        return {"ok": sent, "status": "approved" if sent else "approved_email_failed", "record": final_record}

    async def reject_manual(self, org_id: str, request_id: str, reviewer_id: str, payload: SyncXmlRejectPayload) -> Dict[str, Any]:
        if self._is_staging_safety_mode():
            return self._block_real_write_reason("reject_manual")
        record = await self._get_syncxml_request(org_id, request_id)
        updated = self._update_request(record["id"], {
            "status": "rejected",
            "reviewed_by": str(reviewer_id),
            "reviewed_at": self._now_iso(),
            "rejection_reason": payload.user_reason,
            "admin_notes": payload.internal_reason,
            "metadata": self._merge_metadata(record, {
                "final_decision": "rejected",
                "final_decision_reason": payload.internal_reason,
                "email_status": "pending",
            }),
        })
        sent = self._send_safely(access_request_email_service.build_decision_email(updated), updated, "rejection_email_failed")
        final = self._update_request(record["id"], {"metadata": self._merge_metadata(updated, {"email_status": "sent" if sent else "failed"})})
        return {"ok": sent, "status": "rejected" if sent else "rejected_email_failed", "record": final}

    async def request_more_info_manual(self, org_id: str, request_id: str, reviewer_id: str, payload: SyncXmlMoreInfoPayload) -> Dict[str, Any]:
        if self._is_staging_safety_mode():
            return self._block_real_write_reason("request_more_info_manual")
        record = await self._get_syncxml_request(org_id, request_id)
        updated = self._update_request(record["id"], {
            "status": "pending",
            "reviewed_by": str(reviewer_id),
            "reviewed_at": self._now_iso(),
            "metadata": self._merge_metadata(record, {
                "final_decision": "more_info_requested",
                "email_status": "pending",
                "more_info_message": payload.message,
            }),
        })
        sent = self._send_safely(access_request_email_service.build_syncxml_more_info_email(updated, payload.message), updated, "more_info_email_failed")
        final = self._update_request(record["id"], {"metadata": self._merge_metadata(updated, {"email_status": "sent" if sent else "failed"})})
        return {"ok": sent, "status": "more_info_requested" if sent else "more_info_email_failed", "record": final}

    async def _create_syncxml_user(self, record: Dict[str, Any], payload: SyncXmlApprovePayload) -> Dict[str, Any]:
        if self._is_staging_safety_mode():
            return self._block_real_write_reason("create_syncxml_user")
        if not settings.GUESTHUB_INTERNAL_API_SECRET:
            return {"ok": False, "error": "GUESTHUB_INTERNAL_API_SECRET is not configured"}
        expires_at = payload.expiresAt or self._default_credentials_expires_at()
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    settings.GUESTHUB_INTERNAL_API_URL,
                    json={
                        "requestId": record["id"],
                        "email": record["email"],
                        "name": record.get("full_name") or record["email"],
                        "role": "pilot_user",
                        "expiresAt": expires_at,
                        "source": "anclora-nexus",
                        "rotatePassword": payload.rotatePassword,
                    },
                    headers={"Authorization": f"Bearer {settings.GUESTHUB_INTERNAL_API_SECRET}"},
                    timeout=15.0,
                )
            if not response.is_success:
                detail = response.text[:500]
                logger.warning(
                    "GuestHub pilot user creation failed: status=%s body=%s",
                    response.status_code,
                    detail,
                )
                return {"ok": False, "error": f"GuestHub returned {response.status_code}: {detail}"}
            credentials = response.json()
            credentials.setdefault("expiresAt", expires_at)
            return credentials
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    async def _get_syncxml_request(self, org_id: str, request_id: str) -> Dict[str, Any]:
        result = (
            neon_service.client.table("access_requests")
            .select("*")
            .eq("org_id", org_id)
            .eq("id", request_id)
            .eq("product", "syncxml")
            .limit(1)
            .execute()
        )
        if not result.data:
            raise ValueError("SYNCXML_PILOT_REQUEST_NOT_FOUND")
        return result.data[0]

    def _update_request(self, request_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if self._is_staging_safety_mode():
            blocked = self._block_real_write_reason("update_access_request")
            return {**data, **blocked}
        result = neon_service.client.table("access_requests").update(data).eq("id", request_id).execute()
        return result.data[0] if result.data else data

    def _merge_metadata(self, record: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
        return {**(record.get("metadata") or {}), **updates}

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _default_credentials_expires_at(self) -> str:
        return (datetime.now(timezone.utc) + timedelta(days=DEFAULT_TEMPORARY_PASSWORD_DAYS)).isoformat().replace("+00:00", "Z")


syncxml_pilot_service = SyncXmlPilotService()
