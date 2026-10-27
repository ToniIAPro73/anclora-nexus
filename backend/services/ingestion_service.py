import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from backend.models.ingestion import (
    EntityType,
    IngestionStatus,
    LeadIngestionPayload,
    PropertyIngestionPayload,
    SellerSignalIngestionPayload,
)
from backend.models.finops import UsageEventSchema
from backend.services.finops import finops_service
from backend.services.hnwi_scoring_service import hnwi_scoring_service
from backend.services.neon_service import neon_service
from backend.skills.seller_signal_ingest import run_seller_signal_ingest


class IngestionService:
    def __init__(self) -> None:
        self.client = neon_service.client

    def _serialize_payload(self, payload: Any) -> Dict[str, Any]:
        if hasattr(payload, "model_dump"):
            return payload.model_dump(mode="json")
        if hasattr(payload, "dict"):
            return payload.dict()
        return dict(payload)

    def _default_connector_name(self, payload: Any, entity_type: EntityType) -> str:
        if entity_type == EntityType.LEAD:
            return f"{payload.source_system.value}:{payload.source_channel.value}"
        if entity_type == EntityType.PROPERTY:
            return f"{payload.source_system.value}:{payload.source_portal.value}"
        return str(payload.connector_name)

    def _generate_dedupe_key(
        self,
        org_id: str,
        connector_name: str,
        entity_type: EntityType,
        external_id: str,
    ) -> str:
        base = f"{org_id}:{connector_name}:{entity_type.value}:{external_id}"
        return hashlib.sha256(base.encode("utf-8")).hexdigest()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _is_hnwi_lead(self, payload: LeadIngestionPayload, connector_name: str) -> bool:
        return any(
            [
                connector_name.startswith("hnwi-prospection"),
                payload.nationality,
                payload.zone_interest,
                payload.hnwi_intent_signal,
                payload.hnwi_source_channel is not None,
                payload.email_verified,
            ]
        )

    def _stringify_budget(self, budget: Optional[float]) -> Optional[str]:
        if budget is None:
            return None
        if float(budget).is_integer():
            return str(int(budget))
        return str(budget)

    def _normalize_notes(self, notes: Optional[str]) -> Dict[str, Any]:
        if not notes:
            return {}
        return {"ingestion_notes": notes}

    def _hnwi_channel_value(self, payload: LeadIngestionPayload) -> Optional[str]:
        if payload.hnwi_source_channel:
            return payload.hnwi_source_channel.value
        if payload.source_channel.value != "other":
            return payload.source_channel.value
        return None

    def _log_hnwi_event(
        self,
        *,
        org_id: str,
        lead_id: Optional[str],
        connector_name: str,
        trace_id: str,
        event_type: str,
        payload: LeadIngestionPayload,
        score: int,
        tier: str,
        metadata: Dict[str, Any],
    ) -> None:
        self.client.table("hnwi_prospection_events").insert(
            {
                "org_id": org_id,
                "lead_id": lead_id,
                "connector_name": connector_name,
                "trace_id": trace_id,
                "event_type": event_type,
                "channel": self._hnwi_channel_value(payload),
                "nationality": payload.nationality,
                "qualification_tier": tier,
                "score": score,
                "metadata": metadata,
            }
        ).execute()

    async def _log_hnwi_finops(
        self,
        *,
        org_id: str,
        trace_id: str,
        connector_name: str,
        payload: LeadIngestionPayload,
        score: int,
        tier: str,
        outreach_ready: bool,
    ) -> None:
        await finops_service.log_usage_event(
            org_id,
            UsageEventSchema(
                capability_code="hnwi_prospection",
                provider=connector_name.split(":")[0] if ":" in connector_name else connector_name,
                units=1,
                cost_eur=0,
                trace_id=trace_id,
                metadata={
                    "channel": self._hnwi_channel_value(payload),
                    "nationality": payload.nationality,
                    "score": score,
                    "tier": tier,
                    "email_verified": bool(payload.email_verified),
                    "outreach_ready": outreach_ready,
                },
            ),
        )

    def _get_existing_event(self, org_id: str, dedupe_key: str) -> Optional[Dict[str, Any]]:
        response = (
            self.client.table("ingestion_events")
            .select("*")
            .eq("org_id", org_id)
            .eq("dedupe_key", dedupe_key)
            .limit(1)
            .execute()
        )
        data = response.data or []
        return data[0] if data else None

    def _get_connector(self, org_id: str, connector_name: str, entity_type: EntityType) -> Optional[Dict[str, Any]]:
        response = (
            self.client.table("ingestion_connectors")
            .select("*")
            .eq("org_id", org_id)
            .eq("connector_name", connector_name)
            .eq("entity_type", entity_type.value)
            .limit(1)
            .execute()
        )
        data = response.data or []
        return data[0] if data else None

    def _create_event(
        self,
        *,
        org_id: str,
        connector_name: str,
        entity_type: EntityType,
        external_id: str,
        dedupe_key: str,
        payload: Dict[str, Any],
        trace_id: str,
        status: IngestionStatus = IngestionStatus.RECEIVED,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        processed_entity_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        row = {
            "org_id": org_id,
            "connector_name": connector_name,
            "entity_type": entity_type.value,
            "external_id": external_id,
            "dedupe_key": dedupe_key,
            "status": status.value,
            "payload": payload,
            "trace_id": trace_id,
            "error_code": error_code,
            "error_message": error_message,
            "processed_entity_id": processed_entity_id,
            "processed_at": self._now() if status in {
                IngestionStatus.PROCESSED,
                IngestionStatus.REJECTED,
                IngestionStatus.FAILED,
            } else None,
        }
        result = self.client.table("ingestion_events").insert(row).execute()
        return result.data[0] if result.data else row

    def _update_event(
        self,
        event_id: str,
        *,
        status: IngestionStatus,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        processed_entity_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        row = {
            "status": status.value,
            "error_code": error_code,
            "error_message": error_message,
            "processed_entity_id": processed_entity_id,
        }
        if status in {IngestionStatus.PROCESSED, IngestionStatus.REJECTED, IngestionStatus.FAILED}:
            row["processed_at"] = self._now()
        result = (
            self.client.table("ingestion_events")
            .update(row)
            .eq("id", event_id)
            .execute()
        )
        return result.data[0] if result.data else row

    def _register_received(
        self,
        *,
        org_id: str,
        connector_name: str,
        entity_type: EntityType,
        external_id: str,
        dedupe_key: str,
        payload: Dict[str, Any],
        trace_id: str,
    ) -> Dict[str, Any]:
        return self._create_event(
            org_id=org_id,
            connector_name=connector_name,
            entity_type=entity_type,
            external_id=external_id,
            dedupe_key=dedupe_key,
            payload=payload,
            trace_id=trace_id,
            status=IngestionStatus.RECEIVED,
        )

    def _ensure_connector_enabled(self, org_id: str, connector_name: str, entity_type: EntityType) -> None:
        connector = self._get_connector(org_id, connector_name, entity_type)
        if connector and connector.get("is_enabled") is False:
            raise ValueError(f"Connector disabled: {connector_name}")

    def _requires_gdpr_consent(self, payload: LeadIngestionPayload) -> bool:
        return payload.source_system.value == "cta_web" or payload.source_channel.value == "website"

    def _ensure_gdpr_consent(self, payload: LeadIngestionPayload) -> None:
        if self._requires_gdpr_consent(payload) and not payload.gdpr_consent:
            raise ValueError("gdpr_consent is required for web lead ingestion")

    async def ingest_lead(self, payload: LeadIngestionPayload) -> Dict[str, Any]:
        connector_name = payload.connector_name or self._default_connector_name(payload, EntityType.LEAD)
        trace_id = payload.trace_id or str(uuid4())
        dedupe_key = self._generate_dedupe_key(payload.org_id, connector_name, EntityType.LEAD, payload.external_id)
        existing = self._get_existing_event(payload.org_id, dedupe_key)
        if existing:
            return {"status": "duplicate", "dedupe_key": dedupe_key, "event_id": existing.get("id"), "trace_id": existing.get("trace_id")}

        raw_payload = self._serialize_payload(payload)
        event = self._register_received(
            org_id=payload.org_id,
            connector_name=connector_name,
            entity_type=EntityType.LEAD,
            external_id=payload.external_id,
            dedupe_key=dedupe_key,
            payload=raw_payload,
            trace_id=trace_id,
        )

        try:
            self._ensure_gdpr_consent(payload)
            self._ensure_connector_enabled(payload.org_id, connector_name, EntityType.LEAD)
            self._update_event(event["id"], status=IngestionStatus.VALIDATED)
            hnwi_score = hnwi_scoring_service.score_lead(payload) if self._is_hnwi_lead(payload, connector_name) else None

            source_metadata = {
                **payload.metadata,
                "connector_name": connector_name,
                "trace_id": trace_id,
            }
            notes_json = self._normalize_notes(payload.notes)
            if hnwi_score:
                source_metadata["hnwi"] = {
                    "nationality": payload.nationality,
                    "zone_interest": payload.zone_interest,
                    "source_channel": self._hnwi_channel_value(payload),
                    "email_verification_source": payload.email_verification_source,
                    "outreach_ready": hnwi_score.outreach_ready,
                    "explanation": hnwi_score.explanation,
                }
                if hnwi_score.intent_signal:
                    notes_json["hnwi_intent_signal"] = hnwi_score.intent_signal
                self._log_hnwi_event(
                    org_id=payload.org_id,
                    lead_id=None,
                    connector_name=connector_name,
                    trace_id=trace_id,
                    event_type="scored",
                    payload=payload,
                    score=hnwi_score.score,
                    tier=hnwi_score.tier,
                    metadata={
                        "explanation": hnwi_score.explanation,
                        "outreach_ready": hnwi_score.outreach_ready,
                    },
                )

            lead_data = {
                "org_id": payload.org_id,
                "name": payload.name,
                "email": str(payload.email) if payload.email else None,
                "phone": payload.phone,
                "budget_range": self._stringify_budget(payload.budget),
                "property_interest": payload.property_interest,
                "notes": notes_json,
                "source": connector_name,
                "source_channel": payload.source_channel.value,
                "source_system": payload.source_system.value,
                "source_detail": payload.source_detail,
                "source_url": payload.source_url,
                "source_referrer": payload.source_referrer,
                "source_event_id": event["id"],
                "captured_at": payload.captured_at.isoformat(),
                "source_metadata": source_metadata,
                "gdpr_consent": payload.gdpr_consent,
                "gdpr_consent_at": payload.gdpr_consent_at.isoformat() if payload.gdpr_consent_at else None,
                "gdpr_consent_text_version": payload.gdpr_consent_text_version,
                "status": "new",
            }
            if hnwi_score:
                lead_data.update(
                    {
                        "nationality": payload.nationality,
                        "zone_interest": payload.zone_interest,
                        "qualification_score": hnwi_score.score,
                        "qualification_tier": hnwi_score.tier,
                        "hnwi_intent_signal": hnwi_score.intent_signal,
                        "email_verified": hnwi_score.email_verified,
                        "email_verification_source": payload.email_verification_source,
                        "hnwi_source_channel": self._hnwi_channel_value(payload),
                    }
                )
            lead_result = self.client.table("leads").insert(lead_data).execute()
            lead_row = (lead_result.data or [{}])[0]
            if hnwi_score:
                lead_id = str(lead_row.get("id")) if lead_row.get("id") else None
                self._log_hnwi_event(
                    org_id=payload.org_id,
                    lead_id=lead_id,
                    connector_name=connector_name,
                    trace_id=trace_id,
                    event_type="ingested",
                    payload=payload,
                    score=hnwi_score.score,
                    tier=hnwi_score.tier,
                    metadata={"event_id": event["id"]},
                )
                try:
                    await self._log_hnwi_finops(
                        org_id=payload.org_id,
                        trace_id=trace_id,
                        connector_name=connector_name,
                        payload=payload,
                        score=hnwi_score.score,
                        tier=hnwi_score.tier,
                        outreach_ready=hnwi_score.outreach_ready,
                    )
                except Exception:
                    pass
            lead_id = str(lead_row.get("id")) if lead_row.get("id") else None
            self._update_event(
                event["id"],
                status=IngestionStatus.PROCESSED,
                processed_entity_id=lead_id,
            )
            result = {
                "id": lead_id or event["id"],
                "status": "processed",
                "message": "Lead ingested successfully",
                "dedupe_key": dedupe_key,
                "trace_id": trace_id,
                "event_id": event["id"],
                "lead_id": lead_id,
            }
            if hnwi_score:
                result.update(
                    {
                        "qualification_score": hnwi_score.score,
                        "qualification_tier": hnwi_score.tier,
                        "outreach_ready": hnwi_score.outreach_ready,
                        "email_verified": hnwi_score.email_verified,
                    }
                )
            return result
        except ValueError as exc:
            error_code = "gdpr_consent_required" if "gdpr_consent" in str(exc) else "connector_disabled"
            self._update_event(event["id"], status=IngestionStatus.REJECTED, error_code=error_code, error_message=str(exc))
            raise
        except Exception as exc:
            self._update_event(event["id"], status=IngestionStatus.FAILED, error_code="lead_ingestion_failed", error_message=str(exc))
            raise

    async def ingest_property(self, payload: PropertyIngestionPayload) -> Dict[str, Any]:
        connector_name = payload.connector_name or self._default_connector_name(payload, EntityType.PROPERTY)
        trace_id = payload.trace_id or str(uuid4())
        dedupe_key = self._generate_dedupe_key(payload.org_id, connector_name, EntityType.PROPERTY, payload.external_id)
        existing = self._get_existing_event(payload.org_id, dedupe_key)
        if existing:
            return {"status": "duplicate", "dedupe_key": dedupe_key, "event_id": existing.get("id"), "trace_id": existing.get("trace_id")}

        raw_payload = self._serialize_payload(payload)
        event = self._register_received(
            org_id=payload.org_id,
            connector_name=connector_name,
            entity_type=EntityType.PROPERTY,
            external_id=payload.external_id,
            dedupe_key=dedupe_key,
            payload=raw_payload,
            trace_id=trace_id,
        )

        try:
            self._ensure_connector_enabled(payload.org_id, connector_name, EntityType.PROPERTY)
            self._update_event(event["id"], status=IngestionStatus.VALIDATED)

            property_data = {
                "org_id": payload.org_id,
                "title": payload.title,
                "address": payload.address,
                "price_eur": payload.price_eur,
                "zone": payload.zone,
                "built_area_m2": payload.built_area_m2,
                "useful_area_m2": payload.useful_area_m2,
                "plot_area_m2": payload.plot_area_m2,
                "bedrooms": payload.bedrooms,
                "bathrooms": payload.bathrooms,
                "description": payload.description,
                "status": "prospect",
                "source": payload.source_system.value,
                "source_portal": payload.source_portal.value,
                "captured_at": payload.captured_at.isoformat(),
                "metadata_json": {
                    **payload.metadata,
                    "connector_name": connector_name,
                    "trace_id": trace_id,
                },
            }
            property_result = self.client.table("properties").insert(property_data).execute()
            property_row = (property_result.data or [{}])[0]
            self._update_event(
                event["id"],
                status=IngestionStatus.PROCESSED,
                processed_entity_id=str(property_row.get("id")) if property_row.get("id") else None,
            )
            return {"status": "processed", "dedupe_key": dedupe_key, "trace_id": trace_id, "event_id": event["id"]}
        except ValueError as exc:
            self._update_event(event["id"], status=IngestionStatus.REJECTED, error_code="connector_disabled", error_message=str(exc))
            return {"status": "rejected", "dedupe_key": dedupe_key, "trace_id": trace_id, "event_id": event["id"]}
        except Exception as exc:
            self._update_event(event["id"], status=IngestionStatus.FAILED, error_code="property_ingestion_failed", error_message=str(exc))
            raise

    def _seller_external_id(self, item: Dict[str, Any], index: int, snapshot_id: Optional[str]) -> str:
        return str(
            item.get("external_id")
            or item.get("anuncio_url")
            or item.get("website_url")
            or item.get("direccion")
            or f"{snapshot_id or 'seller-signal'}:{index}"
        )

    async def ingest_seller_signals(self, payload: SellerSignalIngestionPayload) -> Dict[str, Any]:
        trace_id = payload.trace_id or str(uuid4())
        created = 0
        duplicates = 0
        rejected = 0
        failed = 0
        event_ids: List[str] = []

        for index, item in enumerate(payload.signals):
            raw_item = self._serialize_payload(item)
            external_id = self._seller_external_id(raw_item, index, payload.snapshot_id)
            dedupe_key = self._generate_dedupe_key(payload.org_id, payload.connector_name, EntityType.SELLER_SIGNAL, external_id)
            existing = self._get_existing_event(payload.org_id, dedupe_key)
            if existing:
                duplicates += 1
                continue

            event = self._register_received(
                org_id=payload.org_id,
                connector_name=payload.connector_name,
                entity_type=EntityType.SELLER_SIGNAL,
                external_id=external_id,
                dedupe_key=dedupe_key,
                payload={
                    **raw_item,
                    "snapshot_id": payload.snapshot_id,
                    "captured_at": payload.captured_at.isoformat(),
                },
                trace_id=trace_id,
            )
            event_ids.append(str(event.get("id")))

            try:
                self._ensure_connector_enabled(payload.org_id, payload.connector_name, EntityType.SELLER_SIGNAL)
                if not (raw_item.get("anuncio_url") or raw_item.get("website_url") or raw_item.get("direccion")):
                    raise ValueError("seller signal requires anuncio_url, website_url or direccion")

                self._update_event(event["id"], status=IngestionStatus.VALIDATED)
                result = await run_seller_signal_ingest(
                    data={
                        "org_id": payload.org_id,
                        "snapshot_id": payload.snapshot_id or payload.connector_name,
                        "signals": [raw_item],
                    },
                    llm=None,  # unused by the skill
                    db=neon_service,
                )
                created_ids = result.get("created_ids") or []
                processed_entity_id = str(created_ids[0]) if created_ids else None
                self._update_event(
                    event["id"],
                    status=IngestionStatus.PROCESSED,
                    processed_entity_id=processed_entity_id,
                )
                if processed_entity_id:
                    created += 1
                else:
                    duplicates += 1
            except ValueError as exc:
                rejected += 1
                self._update_event(event["id"], status=IngestionStatus.REJECTED, error_code="seller_signal_rejected", error_message=str(exc))
            except Exception as exc:
                failed += 1
                self._update_event(event["id"], status=IngestionStatus.FAILED, error_code="seller_signal_failed", error_message=str(exc))

        return {
            "status": "processed",
            "trace_id": trace_id,
            "snapshot_id": payload.snapshot_id,
            "received": len(payload.signals),
            "created": created,
            "duplicates": duplicates,
            "rejected": rejected,
            "failed": failed,
            "event_ids": event_ids,
        }

    async def get_events(
        self,
        org_id: str,
        *,
        limit: int = 50,
        status: Optional[str] = None,
        entity_type: Optional[str] = None,
        connector_name: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        query = (
            self.client.table("ingestion_events")
            .select("*")
            .eq("org_id", org_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        if status:
            query = query.eq("status", status)
        if entity_type:
            query = query.eq("entity_type", entity_type)
        if connector_name:
            query = query.eq("connector_name", connector_name)
        if trace_id:
            query = query.eq("trace_id", trace_id)
        response = query.execute()
        return response.data or []

    async def get_event_by_id(self, event_id: str) -> Optional[Dict[str, Any]]:
        response = (
            self.client.table("ingestion_events")
            .select("*")
            .eq("id", event_id)
            .limit(1)
            .execute()
        )
        return response.data[0] if response.data else None


ingestion_service = IngestionService()
