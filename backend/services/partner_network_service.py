from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.models.partner_network import PartnerNetworkUpdate, PartnerSharedOpportunityCreate
from backend.services.partner_workspace_service import partner_workspace_service
from backend.services.neon_service import neon_service


class PartnerNetworkService:
    def _normalize_text_list(self, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return []

    def _build_partner_aliases(self, admission: Dict[str, Any]) -> list[str]:
        aliases = []
        for value in (admission.get("full_name"), admission.get("company_name")):
            text = str(value or "").strip().lower()
            if text:
                aliases.append(text)
        return aliases

    def _matches_partner(self, buyer: Dict[str, Any], aliases: list[str]) -> bool:
        if str(buyer.get("source_type") or "") != "partner_referral":
            return False
        referral_name = str(buyer.get("referral_partner_name") or "").strip().lower()
        if not referral_name:
            return False
        return referral_name in aliases

    def _safe_float(self, value: Any, default: float = 0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _engagement_score(
        self,
        *,
        trust_score: float,
        shared_total: int,
        shared_interested: int,
        response_commitment_hours: Optional[int],
        high_intent_buyers_count: int,
    ) -> float:
        response_rate = (shared_interested / shared_total) if shared_total else 0
        commitment_bonus = 0
        if response_commitment_hours is not None:
            if response_commitment_hours <= 12:
                commitment_bonus = 10
            elif response_commitment_hours <= 24:
                commitment_bonus = 6
            elif response_commitment_hours <= 48:
                commitment_bonus = 3
        buyer_bonus = min(high_intent_buyers_count * 3, 12)
        return round(min((trust_score * 0.55) + (response_rate * 25) + commitment_bonus + buyer_bonus, 100), 1)

    def _safe_table_rows(self, table: str, org_id: str, columns: str = "*") -> list[dict[str, Any]]:
        try:
            return (
                neon_service.client.table(table)
                .select(columns)
                .eq("org_id", org_id)
                .execute()
            ).data or []
        except Exception:
            return []

    async def list_network(
        self,
        *,
        org_id: str,
        relationship_status: Optional[str] = None,
        service_category: Optional[str] = None,
        preferred_opportunity_type: Optional[str] = None,
        response_status: Optional[str] = None,
        q: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        admissions = self._safe_table_rows("partner_admissions", org_id)
        workspaces = self._safe_table_rows("synergi_partner_workspaces", org_id)
        opportunities = self._safe_table_rows("synergi_partner_opportunities", org_id)
        shared_opportunities = self._safe_table_rows("synergi_partner_shared_opportunities", org_id)
        buyers = self._safe_table_rows("buyer_profiles", org_id)

        admissions_by_id = {str(item["id"]): item for item in admissions if item.get("status") == "accepted"}
        opportunities_by_workspace: Dict[str, list[dict[str, Any]]] = {}
        for item in opportunities:
            workspace_id = str(item.get("workspace_id") or "")
            if workspace_id:
                opportunities_by_workspace.setdefault(workspace_id, []).append(item)
        shared_opportunities_by_workspace: Dict[str, list[dict[str, Any]]] = {}
        for item in shared_opportunities:
            workspace_id = str(item.get("workspace_id") or "")
            if workspace_id:
                shared_opportunities_by_workspace.setdefault(workspace_id, []).append(item)

        items: list[dict[str, Any]] = []
        for workspace in workspaces:
            admission = admissions_by_id.get(str(workspace.get("admission_id")))
            if not admission:
                continue
            aliases = self._build_partner_aliases(admission)
            matched_buyers = [buyer for buyer in buyers if self._matches_partner(buyer, aliases)]
            workspace_shared = shared_opportunities_by_workspace.get(str(workspace.get("id")), [])
            shared_interested = len([item for item in workspace_shared if str(item.get("status") or "") == "interested"])
            shared_declined = len([item for item in workspace_shared if str(item.get("status") or "") == "declined"])
            shared_pending = len(
                [item for item in workspace_shared if str(item.get("status") or "shared") == "shared"]
            )
            preferred_types = self._normalize_text_list(workspace.get("preferred_opportunity_types"))
            priority_zones = self._normalize_text_list(workspace.get("priority_zones"))
            contact_preferences = self._normalize_text_list(workspace.get("contact_preferences"))
            response_commitment_hours = workspace.get("response_commitment_hours")
            high_intent_buyers_count = len(
                [buyer for buyer in matched_buyers if self._safe_float(buyer.get("motivation_score")) >= 80]
            )
            engagement_score = self._engagement_score(
                trust_score=self._safe_float(workspace.get("trust_score"), 70),
                shared_total=len(workspace_shared),
                shared_interested=shared_interested,
                response_commitment_hours=response_commitment_hours,
                high_intent_buyers_count=high_intent_buyers_count,
            )
            item = {
                "workspace_id": workspace.get("id"),
                "admission_id": admission.get("id"),
                "partner_name": admission.get("full_name"),
                "company_name": admission.get("company_name"),
                "service_category": admission.get("service_category"),
                "sustainability_focus": bool(admission.get("sustainability_focus")),
                "partner_tier": workspace.get("partner_tier") or "approved",
                "relationship_status": workspace.get("relationship_status") or "active",
                "trust_score": float(workspace.get("trust_score") or 70),
                "preferred_for_buyers": bool(workspace.get("preferred_for_buyers")),
                "preferred_for_sellers": bool(workspace.get("preferred_for_sellers")),
                "network_tags": self._normalize_text_list(workspace.get("network_tags")),
                "strategic_notes": workspace.get("strategic_notes"),
                "coverage_areas": self._normalize_text_list(admission.get("coverage_areas")),
                "languages": self._normalize_text_list(admission.get("languages")),
                "preferred_opportunity_types": preferred_types,
                "priority_zones": priority_zones,
                "contact_preferences": contact_preferences,
                "response_commitment_hours": response_commitment_hours,
                "profile_notes": workspace.get("profile_notes"),
                "opportunities_count": len(opportunities_by_workspace.get(str(workspace.get("id")), [])),
                "shared_opportunities_count": len(workspace_shared),
                "shared_interested_count": shared_interested,
                "shared_declined_count": shared_declined,
                "shared_pending_count": shared_pending,
                "buyer_referrals_count": len(matched_buyers),
                "high_intent_buyers_count": high_intent_buyers_count,
                "engagement_score": engagement_score,
                "response_rate": round((shared_interested / len(workspace_shared) * 100), 1) if workspace_shared else 0,
                "recommended_opportunity_type": preferred_types[0] if preferred_types else None,
                "recommended_zone": priority_zones[0] if priority_zones else None,
                "last_seen_at": workspace.get("last_seen_at"),
                "last_referral_at": max(
                    [
                        str(buyer.get("last_partner_touch_at") or buyer.get("created_at") or "")
                        for buyer in matched_buyers
                        if buyer.get("last_partner_touch_at") or buyer.get("created_at")
                    ],
                    default=None,
                ),
                "last_shared_response_at": max(
                    [
                        str(item.get("updated_at") or item.get("created_at") or "")
                        for item in workspace_shared
                        if str(item.get("status") or "") in {"interested", "declined"}
                    ],
                    default=None,
                ),
                "workspace_launch_url": partner_workspace_service._build_launch_url(str(workspace.get("access_token"))),
            }
            items.append(item)

        if relationship_status:
            items = [item for item in items if item["relationship_status"] == relationship_status]
        if service_category:
            items = [item for item in items if item["service_category"] == service_category]
        if preferred_opportunity_type:
            items = [
                item for item in items
                if preferred_opportunity_type in (item.get("preferred_opportunity_types") or [])
            ]
        if response_status:
            if response_status == "responsive":
                items = [item for item in items if item["shared_interested_count"] > 0 or item["shared_declined_count"] > 0]
            elif response_status == "interested":
                items = [item for item in items if item["shared_interested_count"] > 0]
            elif response_status == "pending":
                items = [item for item in items if item["shared_pending_count"] > 0]
            elif response_status == "quiet":
                items = [item for item in items if item["shared_opportunities_count"] == 0]
        if q:
            needle = q.lower().strip()
            items = [
                item for item in items
                if needle in " ".join(
                    [
                        str(item.get("partner_name") or ""),
                        str(item.get("company_name") or ""),
                        str(item.get("service_category") or ""),
                        " ".join(item.get("network_tags") or []),
                    ]
                ).lower()
            ]

        items.sort(
            key=lambda row: (row["partner_tier"], row["engagement_score"], row["trust_score"], row["buyer_referrals_count"]),
            reverse=True,
        )
        total = len(items)
        return {
            "items": items[offset: offset + limit],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    async def get_summary(self, org_id: str) -> Dict[str, Any]:
        payload = await self.list_network(org_id=org_id, limit=500, offset=0)
        rows = payload["items"]
        return {
            "total": len(rows),
            "strategic": len([row for row in rows if row["partner_tier"] == "strategic"]),
            "preferred": len([row for row in rows if row["partner_tier"] == "preferred"]),
            "eco_focus": len([row for row in rows if row["sustainability_focus"]]),
            "buyer_referrals": sum(int(row["buyer_referrals_count"]) for row in rows),
            "shared_opportunities": sum(int(row["shared_opportunities_count"]) for row in rows),
            "responsive_partners": len([row for row in rows if row["shared_interested_count"] > 0 or row["shared_declined_count"] > 0]),
        }

    async def update_network_partner(self, org_id: str, workspace_id: str, payload: PartnerNetworkUpdate) -> Optional[Dict[str, Any]]:
        current = (
            neon_service.client.table("synergi_partner_workspaces")
            .select("*")
            .eq("org_id", org_id)
            .eq("id", workspace_id)
            .limit(1)
            .execute()
        )
        row = current.data[0] if current.data else None
        if not row:
            return None

        update_payload: Dict[str, Any] = {}
        for field in (
            "partner_tier",
            "relationship_status",
            "trust_score",
            "preferred_for_buyers",
            "preferred_for_sellers",
            "strategic_notes",
        ):
            value = getattr(payload, field)
            if value is not None:
                update_payload[field] = value.value if hasattr(value, "value") else value
        if payload.network_tags is not None:
            update_payload["network_tags"] = self._normalize_text_list(payload.network_tags)
        if not update_payload:
            return row
        updated = (
            neon_service.client.table("synergi_partner_workspaces")
            .update(update_payload)
            .eq("org_id", org_id)
            .eq("id", workspace_id)
            .execute()
        )
        return updated.data[0] if updated.data else None

    async def share_opportunity_with_partner(
        self,
        *,
        org_id: str,
        workspace_id: str,
        created_by_user_id: str,
        payload: PartnerSharedOpportunityCreate,
    ) -> Optional[Dict[str, Any]]:
        workspace = (
            neon_service.client.table("synergi_partner_workspaces")
            .select("*")
            .eq("org_id", org_id)
            .eq("id", workspace_id)
            .limit(1)
            .execute()
        ).data
        row = workspace[0] if workspace else None
        if not row:
            return None

        record = {
            "org_id": org_id,
            "workspace_id": workspace_id,
            "title": payload.title,
            "summary": payload.summary,
            "opportunity_type": payload.opportunity_type,
            "target_zone": payload.target_zone,
            "budget_context": payload.budget_context,
            "next_step": payload.next_step,
            "status": "shared",
            "created_by_user_id": created_by_user_id,
            "created_at": partner_workspace_service._now(),
            "updated_at": partner_workspace_service._now(),
        }
        created = neon_service.client.table("synergi_partner_shared_opportunities").insert(record).execute()
        item = created.data[0] if created.data else None
        if item:
            partner_workspace_service._append_activity(
                org_id=org_id,
                workspace_id=workspace_id,
                event_type="shared_opportunity_created",
                title="Opportunity shared from Anclora",
                description=payload.title,
            )
        return item


partner_network_service = PartnerNetworkService()
