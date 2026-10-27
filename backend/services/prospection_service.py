"""
Prospection Service — CRUD operations with org isolation.
Feature: ANCLORA-PBM-001

Manages prospected properties, buyer profiles, matches, and activities.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from backend.models.prospection import (
    ActivityCreate,
    BuyerCreate,
    BuyerUpdate,
    MatchUpdate,
    PropertyCreate,
    PropertyUpdate,
    RecomputeResponse,
)
from backend.services.scoring_service import scoring_service
from backend.services.origin_editability_policy import sanitize_payload
from backend.services.neon_service import neon_service
from backend.services.buyer_memory_service import buyer_memory_service


class ProspectionService:
    """
    CRUD service for Prospection & Buyer Matching.
    All queries are filtered by org_id for isolation.
    """

    def _property_table(self, org_id: Optional[str] = None) -> str:
        """
        Resolve property table for prospection flows.
        Prefer unified properties table, but if org_id is provided choose the
        table that actually has rows for that org.
        """
        existing_tables: List[str] = []

        # Prefer current unified model first.
        for table in ("properties", "prospected_properties"):
            try:
                neon_service.client.table(table).select("id").limit(1).execute()
                existing_tables.append(table)
            except Exception:
                continue

        if not existing_tables:
            return "properties"

        if org_id is not None:
            for table in existing_tables:
                try:
                    probe = (
                        neon_service.client.table(table)
                        .select("id")
                        .eq("org_id", org_id)
                        .limit(1)
                        .execute()
                    )
                    if probe.data:
                        return table
                except Exception:
                    continue

        return existing_tables[0]

    def _property_tables(self) -> List[str]:
        """Return available property tables in preferred order."""
        tables: List[str] = []
        for table in ("properties", "prospected_properties"):
            try:
                neon_service.client.table(table).select("id").limit(1).execute()
                tables.append(table)
            except Exception:
                continue
        return tables or ["properties"]

    def _table_has_column(self, table: str, column: str) -> bool:
        """Best-effort check to avoid querying non-existent columns."""
        try:
            neon_service.client.table(table).select(column).limit(1).execute()
            return True
        except Exception:
            return False

    def _table_exists(self, table: str) -> bool:
        """Best-effort table existence check."""
        try:
            neon_service.client.table(table).select("id").limit(1).execute()
            return True
        except Exception:
            return False

    def _normalize_property_record(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize heterogeneous property rows so they always satisfy
        PropertyResponse response model requirements.
        """
        now_iso = datetime.utcnow().isoformat()
        normalized = dict(row)
        normalized["source"] = normalized.get("source") or "direct"
        normalized["status"] = normalized.get("status") or "new"
        normalized["source_system"] = normalized.get("source_system") or "pbm"
        normalized["created_at"] = normalized.get("created_at") or now_iso
        normalized["updated_at"] = normalized.get("updated_at") or now_iso
        return normalized

    def _normalize_property_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [self._normalize_property_record(i) for i in items]

    def _normalize_buyer_record(self, row: Dict[str, Any]) -> Dict[str, Any]:
        now_iso = datetime.utcnow().isoformat()
        normalized = dict(row)
        normalized["preferred_zones"] = normalized.get("preferred_zones") or []
        normalized["preferred_types"] = normalized.get("preferred_types") or []
        normalized["required_features"] = normalized.get("required_features") or {}
        normalized["source_details"] = normalized.get("source_details") or {}
        normalized["source_type"] = normalized.get("source_type") or "manual"
        normalized["source_platform"] = normalized.get("source_platform") or "manual"
        normalized["buyer_intro_status"] = normalized.get("buyer_intro_status") or "new"
        normalized["status"] = normalized.get("status") or "active"
        normalized["created_at"] = normalized.get("created_at") or now_iso
        normalized["updated_at"] = normalized.get("updated_at") or now_iso
        return normalized

    def _normalize_buyer_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [self._normalize_buyer_record(i) for i in items]

    def _score_buyer_intake(self, record: Dict[str, Any]) -> Dict[str, float]:
        source_type = str(record.get("source_type") or "manual")
        source_platform = str(record.get("source_platform") or "manual")
        horizon = str(record.get("purchase_horizon") or "").lower()
        budget_max = float(record.get("budget_max") or 0)
        budget_min = float(record.get("budget_min") or 0)
        preferred_zones = record.get("preferred_zones") or []
        partner_name = str(record.get("referral_partner_name") or "").strip()

        source_intent = {
            "partner_referral": 86.0,
            "crm_reactivation": 72.0,
            "web_inbound": 68.0,
            "paid_lead": 58.0,
            "portal_signal": 48.0,
            "manual": 52.0,
        }.get(source_type, 50.0)
        platform_trust = {
            "exp_agent": 92.0,
            "external_agent": 82.0,
            "crm": 74.0,
            "web": 66.0,
            "email": 60.0,
            "whatsapp": 62.0,
            "meta": 56.0,
            "google": 58.0,
            "idealista": 45.0,
            "manual": 54.0,
            "other": 50.0,
        }.get(source_platform, 50.0)
        horizon_intent = {
            "immediate": 95.0,
            "0_3m": 84.0,
            "3_6m": 74.0,
            "6_12m": 60.0,
            "12m_plus": 42.0,
        }.get(horizon, 56.0)

        budget_anchor = max(budget_max, budget_min)
        if budget_anchor >= 4_000_000:
            capacity = 95.0
        elif budget_anchor >= 2_500_000:
            capacity = 86.0
        elif budget_anchor >= 1_500_000:
            capacity = 76.0
        elif budget_anchor >= 750_000:
            capacity = 64.0
        elif budget_anchor > 0:
            capacity = 52.0
        else:
            capacity = 40.0

        if source_type == "partner_referral":
            capacity = min(100.0, capacity + 6.0)
        if partner_name:
            platform_trust = min(100.0, platform_trust + 4.0)
        if preferred_zones:
            source_intent = min(100.0, source_intent + min(len(preferred_zones) * 2.0, 6.0))

        intent_score = round((source_intent * 0.55) + (horizon_intent * 0.45), 2)
        trust_score = round(platform_trust, 2)
        capacity_score = round(capacity, 2)
        motivation_score = round((intent_score * 0.50) + (trust_score * 0.20) + (capacity_score * 0.30), 2)
        return {
            "intent_score": intent_score,
            "trust_score": trust_score,
            "capacity_score": capacity_score,
            "motivation_score": motivation_score,
        }

    def _coerce_buyer_payload(self, record: Dict[str, Any]) -> Dict[str, Any]:
        for field in (
            "budget_min",
            "budget_max",
            "motivation_score",
            "trust_score",
            "intent_score",
            "capacity_score",
        ):
            if field in record and record[field] is not None:
                record[field] = float(record[field])

        for field in ("source_type", "source_platform", "referral_partner_type", "buyer_intro_status", "status"):
            if field in record and record[field] is not None:
                value = record[field]
                record[field] = str(value.value) if hasattr(value, "value") else str(value)
        return record

    # ─────────────────────────────────────────────────────────────────────
    # PROPERTIES
    # ─────────────────────────────────────────────────────────────────────

    async def create_property(
        self, org_id: str, data: PropertyCreate
    ) -> Dict[str, Any]:
        """Create a new prospected property and compute its score."""
        record: Dict[str, Any] = {
            "org_id": org_id,
            **data.model_dump(exclude_none=True),
        }

        # Normalize Enums to strings for Neon
        if "source_system" in record:
            record["source_system"] = str(record["source_system"].value)
        if "source_portal" in record and record["source_portal"] is not None:
            record["source_portal"] = str(record["source_portal"].value)

        # Convert Decimal to float for JSON serialization
        decimal_fields = [
            "price",
            "area_m2",
            "useful_area_m2",
            "built_area_m2",
            "plot_area_m2",
        ]
        for field in decimal_fields:
            if field in record and record[field] is not None:
                record[field] = float(record[field])

        # Compute initial high_ticket_score
        score_result = scoring_service.compute_high_ticket_score(
            price=record.get("price"),
            zone=data.zone,
            property_type=data.property_type,
            area_m2=record.get("area_m2"),
            bedrooms=data.bedrooms,
        )
        record["high_ticket_score"] = score_result.score
        record["score_breakdown"] = score_result.breakdown

        response = neon_service.client.table(self._property_table(org_id)).insert(
            record
        ).execute()
        return response.data[0]

    async def list_properties(
        self,
        org_id: str,
        zone: Optional[str] = None,
        status: Optional[str] = None,
        min_score: Optional[float] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List prospected properties with filters."""
        # First strategy: use the property IDs that are actually referenced by matches
        # for this org. This keeps prospection cards aligned with the match board.
        try:
            matches_base = (
                neon_service.client.table("property_buyer_matches")
                .select("property_id, match_score")
                .eq("org_id", org_id)
                .limit(5000)
                .execute()
            )
            match_rows = matches_base.data or []
            matched_property_ids = list(
                {m.get("property_id") for m in match_rows if m.get("property_id")}
            )
            best_match_score: Dict[str, float] = {}
            for m in match_rows:
                pid = m.get("property_id")
                score = m.get("match_score")
                if pid is None or score is None:
                    continue
                best_match_score[pid] = max(best_match_score.get(pid, 0.0), float(score))

            if matched_property_ids:
                merged: Dict[str, Dict[str, Any]] = {}
                for property_table in self._property_tables():
                    try:
                        rows = (
                            neon_service.client.table(property_table)
                            .select("*")
                            .in_("id", matched_property_ids)
                            .limit(5000)
                            .execute()
                        ).data or []
                        for row in rows:
                            merged[row["id"]] = row
                    except Exception:
                        continue

                if merged:
                    items = list(merged.values())
                    for item in items:
                        if item.get("high_ticket_score") is None:
                            item["high_ticket_score"] = best_match_score.get(item.get("id"), 0)

                    if zone:
                        items = [i for i in items if (i.get("zone") or "") == zone]
                    if status:
                        items = [i for i in items if (i.get("status") or "") == status]
                    if min_score is not None:
                        items = [i for i in items if float(i.get("high_ticket_score") or 0) >= min_score]

                    items.sort(key=lambda x: float(x.get("high_ticket_score") or 0), reverse=True)
                    total = len(items)
                    page_items = items[offset : offset + limit]
                    return {
                        "items": self._normalize_property_items(page_items),
                        "total": total,
                        "limit": limit,
                        "offset": offset,
                    }
        except Exception:
            pass

        # Robust strategy: try all available property tables and use
        # the first one that returns rows for this org+filters.
        tables = self._property_tables()
        last_response = None

        for property_table in tables:
            supports_score = self._table_has_column(property_table, "high_ticket_score")
            supports_status = self._table_has_column(property_table, "status")
            supports_zone = self._table_has_column(property_table, "zone")
            supports_source_system = self._table_has_column(property_table, "source_system")

            query = (
                neon_service.client.table(property_table)
                .select("*", count="exact")
                .eq("org_id", org_id)
            )

            # Prospection screen should show only prospecting-origin properties.
            if supports_source_system:
                query = query.in_("source_system", ["widget", "pbm"])

            if zone and supports_zone:
                query = query.eq("zone", zone)
            if status and supports_status:
                query = query.eq("status", status)
            if min_score is not None and supports_score:
                query = query.gte("high_ticket_score", min_score)

            query = query.range(offset, offset + limit - 1)

            try:
                if supports_score:
                    response = query.order("high_ticket_score", desc=True).execute()
                else:
                    response = query.order("created_at", desc=True).execute()
            except Exception:
                response = query.execute()

            last_response = response
            if response.data:
                return {
                    "items": self._normalize_property_items(response.data),
                    "total": response.count or len(response.data),
                    "limit": limit,
                    "offset": offset,
                }

        # Fallback: if properties are not found by org_id but matches exist,
        # recover property cards by property_id linked to org matches.
        try:
            matches_resp = (
                neon_service.client.table("property_buyer_matches")
                .select("property_id")
                .eq("org_id", org_id)
                .limit(5000)
                .execute()
            )
            property_ids = list({m.get("property_id") for m in (matches_resp.data or []) if m.get("property_id")})

            if property_ids:
                recovered: List[Dict[str, Any]] = []
                for property_table in tables:
                    try:
                        resp = (
                            neon_service.client.table(property_table)
                            .select("*")
                            .in_("id", property_ids)
                            .range(offset, offset + limit - 1)
                            .execute()
                        )
                        if resp.data:
                            recovered = resp.data
                            break
                    except Exception:
                        continue

                if recovered:
                    return {
                        "items": self._normalize_property_items(recovered),
                        "total": len(property_ids),
                        "limit": limit,
                        "offset": offset,
                    }
        except Exception:
            # Keep standard empty response if fallback path fails.
            pass

        # If no table has rows, return last response shape or empty.
        if last_response is not None:
            return {
                "items": self._normalize_property_items(last_response.data or []),
                "total": last_response.count or len(last_response.data or []),
                "limit": limit,
                "offset": offset,
            }
        return {"items": [], "total": 0, "limit": limit, "offset": offset}

    async def get_property(self, org_id: str, property_id: str) -> Optional[Dict[str, Any]]:
        """Get a single property by ID with org isolation."""
        property_table = self._property_table(org_id)
        response = (
            neon_service.client.table(property_table)
            .select("*")
            .eq("id", property_id)
            .eq("org_id", org_id)
            .execute()
        )
        return response.data[0] if response.data else None

    async def update_property(
        self, org_id: str, property_id: str, data: PropertyUpdate
    ) -> Optional[Dict[str, Any]]:
        """Update a prospected property with origin-based editability enforcement."""
        property_table = self._property_table(org_id)
        # 1. Fetch current record to check origin
        existing = await self.get_property(org_id, property_id)
        if not existing:
            return None

        update_data: Dict[str, Any] = data.model_dump(exclude_none=True)

        # 2. Enforce Origin-based Editability Contract server-side.
        source_system = str(existing.get("source_system", "manual"))
        update_data = sanitize_payload(update_data, "property", source_system)

        # 3. Handle Enums and Decimals
        if "source_system" in update_data:
            update_data["source_system"] = str(update_data["source_system"].value)
        if "source_portal" in update_data and update_data["source_portal"] is not None:
            update_data["source_portal"] = str(update_data["source_portal"].value)

        decimal_fields = [
            "price",
            "area_m2",
            "useful_area_m2",
            "built_area_m2",
            "plot_area_m2",
        ]
        for field in decimal_fields:
            if field in update_data and update_data[field] is not None:
                update_data[field] = float(update_data[field])

        # 4. Perform update
        response = (
            neon_service.client.table(property_table)
            .update(update_data)
            .eq("id", property_id)
            .eq("org_id", org_id)
            .execute()
        )
        return response.data[0] if response.data else None

    async def rescore_property(
        self, org_id: str, property_id: str
    ) -> Optional[Dict[str, Any]]:
        """Recalculate high_ticket_score for a property."""
        property_table = self._property_table(org_id)
        prop = await self.get_property(org_id, property_id)
        if not prop:
            return None

        score_result = scoring_service.compute_high_ticket_score(
            price=float(prop["price"]) if prop.get("price") else None,
            zone=prop.get("zone"),
            property_type=prop.get("property_type"),
            area_m2=float(prop["area_m2"]) if prop.get("area_m2") else None,
            bedrooms=prop.get("bedrooms"),
        )

        response = (
            neon_service.client.table(property_table)
            .update({
                "high_ticket_score": score_result.score,
                "score_breakdown": score_result.breakdown,
            })
            .eq("id", property_id)
            .eq("org_id", org_id)
            .execute()
        )
        return response.data[0] if response.data else None

    # ─────────────────────────────────────────────────────────────────────
    # BUYERS
    # ─────────────────────────────────────────────────────────────────────

    async def create_buyer(
        self, org_id: str, data: BuyerCreate
    ) -> Dict[str, Any]:
        """Create a new buyer profile."""
        record: Dict[str, Any] = {
            "org_id": org_id,
            **data.model_dump(exclude_none=True),
        }
        record = self._coerce_buyer_payload(record)
        computed_scores = self._score_buyer_intake(record)
        for key, value in computed_scores.items():
            if record.get(key) is None:
                record[key] = value

        response = neon_service.client.table("buyer_profiles").insert(
            record
        ).execute()
        return self._normalize_buyer_record(response.data[0])

    async def list_buyers(
        self,
        org_id: str,
        status: Optional[str] = None,
        source_type: Optional[str] = None,
        source_platform: Optional[str] = None,
        min_budget: Optional[float] = None,
        max_budget: Optional[float] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List buyer profiles with filters."""
        query = (
            neon_service.client.table("buyer_profiles")
            .select("*", count="exact")
            .eq("org_id", org_id)
            .order("motivation_score", desc=True)
        )

        if status:
            query = query.eq("status", status)
        if source_type and self._table_has_column("buyer_profiles", "source_type"):
            query = query.eq("source_type", source_type)
        if source_platform and self._table_has_column("buyer_profiles", "source_platform"):
            query = query.eq("source_platform", source_platform)
        if min_budget is not None:
            query = query.gte("budget_max", min_budget)
        if max_budget is not None:
            query = query.lte("budget_min", max_budget)

        query = query.range(offset, offset + limit - 1)
        response = query.execute()

        return {
            "items": self._normalize_buyer_items(response.data or []),
            "total": response.count or len(response.data),
            "limit": limit,
            "offset": offset,
        }

    async def get_buyer(self, org_id: str, buyer_id: str) -> Optional[Dict[str, Any]]:
        """Get a single buyer by ID with org isolation."""
        response = (
            neon_service.client.table("buyer_profiles")
            .select("*")
            .eq("id", buyer_id)
            .eq("org_id", org_id)
            .execute()
        )
        return response.data[0] if response.data else None

    async def update_buyer(
        self, org_id: str, buyer_id: str, data: BuyerUpdate
    ) -> Optional[Dict[str, Any]]:
        """Update a buyer profile."""
        update_data: Dict[str, Any] = data.model_dump(exclude_none=True)
        update_data = self._coerce_buyer_payload(update_data)

        response = (
            neon_service.client.table("buyer_profiles")
            .update(update_data)
            .eq("id", buyer_id)
            .eq("org_id", org_id)
            .execute()
        )
        return self._normalize_buyer_record(response.data[0]) if response.data else None

    # ─────────────────────────────────────────────────────────────────────
    # MATCHES
    # ─────────────────────────────────────────────────────────────────────

    async def list_matches(
        self,
        org_id: str,
        status: Optional[str] = None,
        min_score: Optional[float] = None,
        property_id: Optional[str] = None,
        buyer_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List matches with optional filters, ordered by score."""
        query = (
            neon_service.client.table("property_buyer_matches")
            .select("*", count="exact")
            .eq("org_id", org_id)
            .order("match_score", desc=True)
        )

        if status:
            query = query.eq("match_status", status)
        if min_score is not None:
            query = query.gte("match_score", min_score)
        if property_id:
            query = query.eq("property_id", property_id)
        if buyer_id:
            query = query.eq("buyer_id", buyer_id)

        query = query.range(offset, offset + limit - 1)
        response = query.execute()

        # Denormalize: fetch property titles and buyer names for display
        items = response.data
        await self._enrich_matches(org_id, items)

        return {
            "items": items,
            "total": response.count or len(items),
            "limit": limit,
            "offset": offset,
        }

    async def get_opportunity_ranking(
        self,
        org_id: str,
        limit: int = 25,
        min_opportunity_score: Optional[float] = None,
        match_status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Return explainable commercial ranking built from existing matches.
        Score components:
        - 65% match_score
        - 20% normalized commission estimate
        - 15% buyer motivation
        """
        matches_query = (
            neon_service.client.table("property_buyer_matches")
            .select("*")
            .eq("org_id", org_id)
            .order("match_score", desc=True)
            .limit(max(limit * 5, 100))
        )
        if match_status:
            matches_query = matches_query.eq("match_status", match_status)
        match_rows = matches_query.execute().data or []
        await self._enrich_matches(org_id, match_rows)

        if not match_rows:
            return {
                "items": [],
                "total": 0,
                "limit": limit,
                "scope": {"org_id": org_id},
                "totals": {"hot": 0, "warm": 0, "cold": 0},
            }

        buyer_ids = list({str(m.get("buyer_id")) for m in match_rows if m.get("buyer_id")})
        buyers = (
            neon_service.client.table("buyer_profiles")
            .select("id,motivation_score,status")
            .eq("org_id", org_id)
            .in_("id", buyer_ids)
            .execute()
        ).data or []
        buyer_map = {str(b["id"]): b for b in buyers}

        commissions = [
            float(m.get("commission_estimate"))
            for m in match_rows
            if m.get("commission_estimate") is not None
        ]
        max_commission = max(commissions) if commissions else 0.0

        ranked: List[Dict[str, Any]] = []
        for m in match_rows:
            match_score = float(m.get("match_score") or 0)
            commission = float(m.get("commission_estimate") or 0)
            commission_norm = (commission / max_commission * 100) if max_commission > 0 else 0.0

            buyer = buyer_map.get(str(m.get("buyer_id")), {})
            motivation = float(buyer.get("motivation_score") or 0)
            if motivation > 0 and motivation <= 10:
                motivation = motivation * 10.0

            opportunity_score = (match_score * 0.65) + (commission_norm * 0.20) + (motivation * 0.15)

            explanation = self._build_opportunity_explanation(m, match_score, commission_norm, motivation)
            action = self._recommend_next_action(opportunity_score, str(m.get("match_status") or "candidate"))

            record = {
                "match_id": m.get("id"),
                "property_id": m.get("property_id"),
                "buyer_id": m.get("buyer_id"),
                "property_title": m.get("property_title"),
                "buyer_name": m.get("buyer_name"),
                "match_status": m.get("match_status"),
                "match_score": round(match_score, 2),
                "commission_estimate": round(commission, 2) if commission else None,
                "opportunity_score": round(opportunity_score, 2),
                "priority_band": "hot" if opportunity_score >= 75 else "warm" if opportunity_score >= 50 else "cold",
                "next_action": action,
                "explanation": explanation,
                "updated_at": m.get("updated_at"),
            }
            if min_opportunity_score is None or record["opportunity_score"] >= min_opportunity_score:
                ranked.append(record)

        ranked.sort(key=lambda r: r["opportunity_score"], reverse=True)
        sliced = ranked[:limit]
        totals = {
            "hot": len([r for r in sliced if r["priority_band"] == "hot"]),
            "warm": len([r for r in sliced if r["priority_band"] == "warm"]),
            "cold": len([r for r in sliced if r["priority_band"] == "cold"]),
        }
        return {
            "items": sliced,
            "total": len(ranked),
            "limit": limit,
            "scope": {"org_id": org_id},
            "totals": totals,
        }

    async def update_match(
        self, org_id: str, match_id: str, data: MatchUpdate
    ) -> Optional[Dict[str, Any]]:
        """Update match status or commission estimate."""
        update_data: Dict[str, Any] = data.model_dump(exclude_none=True)

        if "commission_estimate" in update_data and update_data["commission_estimate"] is not None:
            update_data["commission_estimate"] = float(update_data["commission_estimate"])
        if "match_status" in update_data:
            update_data["match_status"] = str(update_data["match_status"])

        response = (
            neon_service.client.table("property_buyer_matches")
            .update(update_data)
            .eq("id", match_id)
            .eq("org_id", org_id)
            .execute()
        )
        return response.data[0] if response.data else None

    async def recompute_matches(
        self,
        org_id: str,
        property_ids: Optional[List[str]] = None,
        buyer_ids: Optional[List[str]] = None,
    ) -> RecomputeResponse:
        """
        Recompute match scores for all (or filtered) property-buyer pairs.
        Creates new matches and updates existing ones.
        """
        property_table = self._property_table(org_id)
        # Fetch properties
        prop_query = (
            neon_service.client.table(property_table)
            .select("*")
            .eq("org_id", org_id)
        )
        if self._table_has_column(property_table, "status"):
            prop_query = prop_query.neq("status", "discarded")
        if property_ids:
            prop_query = prop_query.in_("id", property_ids)
        properties = prop_query.execute().data

        # Fetch active buyers
        buyer_query = (
            neon_service.client.table("buyer_profiles")
            .select("*")
            .eq("org_id", org_id)
            .eq("status", "active")
        )
        if buyer_ids:
            buyer_query = buyer_query.in_("id", buyer_ids)
        buyers = buyer_query.execute().data

        # Fetch existing matches for dedup
        existing_matches_response = (
            neon_service.client.table("property_buyer_matches")
            .select("id, property_id, buyer_id")
            .eq("org_id", org_id)
            .execute()
        )
        existing_pairs: Dict[tuple[str, str], str] = {
            (m["property_id"], m["buyer_id"]): m["id"]
            for m in existing_matches_response.data
        }

        created: int = 0
        updated: int = 0

        for prop in properties:
            for buyer in buyers:
                score_result = scoring_service.compute_match_score(
                    property_data=prop,
                    buyer_data=buyer,
                )

                pair_key = (prop["id"], buyer["id"])
                match_data: Dict[str, Any] = {
                    "match_score": score_result.score,
                    "score_breakdown": score_result.breakdown,
                }

                if pair_key in existing_pairs:
                    # Update existing match
                    neon_service.client.table("property_buyer_matches").update(
                        match_data
                    ).eq("id", existing_pairs[pair_key]).execute()
                    updated += 1
                else:
                    # Create new match
                    match_data.update({
                        "org_id": org_id,
                        "property_id": prop["id"],
                        "buyer_id": buyer["id"],
                        "match_status": "candidate",
                    })
                    neon_service.client.table("property_buyer_matches").insert(
                        match_data
                    ).execute()
                    created += 1

        return RecomputeResponse(
            matches_created=created,
            matches_updated=updated,
            total_computed=created + updated,
        )

    # ─────────────────────────────────────────────────────────────────────
    # ACTIVITIES
    # ─────────────────────────────────────────────────────────────────────

    async def log_activity(
        self,
        org_id: str,
        match_id: str,
        data: ActivityCreate,
        created_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Log a commercial activity for a match."""
        # Verify match exists and belongs to org
        match_check = (
            neon_service.client.table("property_buyer_matches")
            .select("id")
            .eq("id", match_id)
            .eq("org_id", org_id)
            .execute()
        )
        if not match_check.data:
            raise ValueError(f"Match {match_id} not found for org {org_id}")

        record: Dict[str, Any] = {
            "org_id": org_id,
            "match_id": match_id,
            "activity_type": data.activity_type.value,
            "outcome": data.outcome,
            "details": data.details,
        }
        if created_by:
            record["created_by"] = created_by

        response = neon_service.client.table("match_activity_log").insert(
            record
        ).execute()
        return response.data[0]

    async def list_activities(
        self, org_id: str, match_id: str
    ) -> Dict[str, Any]:
        """List activities for a specific match."""
        response = (
            neon_service.client.table("match_activity_log")
            .select("*", count="exact")
            .eq("org_id", org_id)
            .eq("match_id", match_id)
            .order("created_at", desc=True)
            .execute()
        )
        return {
            "items": response.data,
            "total": response.count or len(response.data),
        }

    async def get_workspace(
        self,
        org_id: str,
        role: str,
        user_id: Optional[str] = None,
        source_system: Optional[str] = None,
        property_status: Optional[str] = None,
        buyer_status: Optional[str] = None,
        match_status: Optional[str] = None,
        min_property_score: Optional[float] = None,
        min_match_score: Optional[float] = None,
        limit: int = 25,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Unified workspace payload for prospection operations.
        Scope:
        - owner/manager: full org data
        - agent: assigned data only
        """
        role_norm = (role or "").strip().lower()
        is_agent = role_norm == "agent"

        property_table = self._property_table(org_id)
        prop_has_assignee = self._table_has_column(property_table, "assigned_user_id")
        matches_table_exists = self._table_exists("property_buyer_matches")
        buyers_table_exists = self._table_exists("buyer_profiles")
        match_has_assignee = matches_table_exists and self._table_has_column("property_buyer_matches", "assigned_user_id")
        match_has_status = matches_table_exists and self._table_has_column("property_buyer_matches", "match_status")
        match_has_score = matches_table_exists and self._table_has_column("property_buyer_matches", "match_score")
        buyer_has_assignee = buyers_table_exists and self._table_has_column("buyer_profiles", "assigned_user_id")
        buyer_has_motivation = buyers_table_exists and self._table_has_column("buyer_profiles", "motivation_score")

        assigned_property_ids: List[str] = []
        if is_agent and user_id and not match_has_assignee:
            assigned_property_ids = await self._list_assigned_property_ids(org_id, user_id)

        # Properties block
        prop_query = (
            neon_service.client.table(property_table)
            .select("*", count="exact")
            .eq("org_id", org_id)
        )
        if source_system and self._table_has_column(property_table, "source_system"):
            prop_query = prop_query.eq("source_system", source_system)
        if property_status and self._table_has_column(property_table, "status"):
            prop_query = prop_query.eq("status", property_status)
        if min_property_score is not None and self._table_has_column(property_table, "high_ticket_score"):
            prop_query = prop_query.gte("high_ticket_score", min_property_score)
        if is_agent and user_id and prop_has_assignee:
            prop_query = prop_query.eq("assigned_user_id", user_id)
        prop_query = prop_query.range(offset, offset + limit - 1)
        if self._table_has_column(property_table, "high_ticket_score"):
            prop_resp = prop_query.order("high_ticket_score", desc=True).execute()
        else:
            prop_resp = prop_query.order("created_at", desc=True).execute()
        prop_items = self._normalize_property_items(prop_resp.data or [])
        prop_total = prop_resp.count or len(prop_items)

        # Matches block
        match_items: List[Dict[str, Any]] = []
        match_total = 0
        if (not matches_table_exists) or (is_agent and user_id and (not match_has_assignee) and (not assigned_property_ids)):
            match_items = []
            match_total = 0
        else:
            match_query = (
                neon_service.client.table("property_buyer_matches")
                .select("*", count="exact")
                .eq("org_id", org_id)
            )
            if match_status:
                if match_has_status:
                    match_query = match_query.eq("match_status", match_status)
                elif self._table_has_column("property_buyer_matches", "status"):
                    match_query = match_query.eq("status", match_status)
            if min_match_score is not None and match_has_score:
                match_query = match_query.gte("match_score", min_match_score)
            if is_agent and user_id:
                if match_has_assignee:
                    match_query = match_query.eq("assigned_user_id", user_id)
                elif assigned_property_ids:
                    match_query = match_query.in_("property_id", assigned_property_ids)
            match_query = match_query.range(offset, offset + limit - 1)
            if match_has_score:
                match_query = match_query.order("match_score", desc=True)
            else:
                match_query = match_query.order("created_at", desc=True)
            match_resp = match_query.execute()
            match_items = match_resp.data or []
            match_total = match_resp.count or len(match_items)
            await self._enrich_matches(org_id, match_items)

        # Buyers block
        buyer_items: List[Dict[str, Any]] = []
        buyer_total = 0
        buyer_source_summary: Dict[str, Any] = {
            "by_source_type": {},
            "by_source_platform": {},
            "partner_referrals": 0,
            "crm_reactivation": 0,
            "web_inbound": 0,
        }
        if buyers_table_exists:
            buyer_query = (
                neon_service.client.table("buyer_profiles")
                .select("*", count="exact")
                .eq("org_id", org_id)
            )
            if buyer_status:
                buyer_query = buyer_query.eq("status", buyer_status)
            if is_agent and user_id:
                if buyer_has_assignee:
                    buyer_query = buyer_query.eq("assigned_user_id", user_id)
                elif matches_table_exists:
                    scoped_matches_query = (
                        neon_service.client.table("property_buyer_matches")
                        .select("buyer_id")
                        .eq("org_id", org_id)
                        .limit(5000)
                    )
                    if match_has_assignee:
                        scoped_matches_query = scoped_matches_query.eq("assigned_user_id", user_id)
                    elif assigned_property_ids:
                        scoped_matches_query = scoped_matches_query.in_("property_id", assigned_property_ids)

                    scoped_matches_resp = scoped_matches_query.execute()
                    scoped_buyer_ids = list({
                        m.get("buyer_id")
                        for m in (scoped_matches_resp.data or [])
                        if m.get("buyer_id")
                    })
                    if not scoped_buyer_ids:
                        return {
                            "scope": {
                                "org_id": org_id,
                                "role": role_norm,
                                "user_id": user_id,
                            },
                            "properties": {"items": prop_items, "total": prop_total, "limit": limit, "offset": offset},
                            "buyers": {"items": [], "total": 0, "limit": limit, "offset": offset},
                            "matches": {"items": match_items, "total": match_total, "limit": limit, "offset": offset},
                            "totals": {"properties": prop_total, "buyers": 0, "matches": match_total},
                        }
                    buyer_query = buyer_query.in_("id", scoped_buyer_ids)
            buyer_query = buyer_query.range(offset, offset + limit - 1)
            if buyer_has_motivation:
                buyer_query = buyer_query.order("motivation_score", desc=True)
            else:
                buyer_query = buyer_query.order("created_at", desc=True)
            buyer_resp = buyer_query.execute()
            buyer_items = self._normalize_buyer_items(buyer_resp.data or [])
            buyer_total = buyer_resp.count or len(buyer_items)
            summary_query = (
                neon_service.client.table("buyer_profiles")
                .select("source_type,source_platform")
                .eq("org_id", org_id)
                .limit(5000)
            )
            if buyer_status:
                summary_query = summary_query.eq("status", buyer_status)
            summary_rows = summary_query.execute().data or []
            for row in summary_rows:
                source_type = str(row.get("source_type") or "manual")
                source_platform = str(row.get("source_platform") or "manual")
                buyer_source_summary["by_source_type"][source_type] = buyer_source_summary["by_source_type"].get(source_type, 0) + 1
                buyer_source_summary["by_source_platform"][source_platform] = buyer_source_summary["by_source_platform"].get(source_platform, 0) + 1
            buyer_source_summary["partner_referrals"] = buyer_source_summary["by_source_type"].get("partner_referral", 0)
            buyer_source_summary["crm_reactivation"] = buyer_source_summary["by_source_type"].get("crm_reactivation", 0)
            buyer_source_summary["web_inbound"] = buyer_source_summary["by_source_type"].get("web_inbound", 0)
            preview_map = await buyer_memory_service.get_preview_map(
                db=neon_service,
                org_id=org_id,
                buyer_ids=[str(item.get("id")) for item in buyer_items if item.get("id")],
            )
            for item in buyer_items:
                preview = preview_map.get(str(item.get("id")), {})
                item["memory_preview"] = preview.get("memory_preview", [])
                item["memory_status"] = preview.get("memory_status", "empty")

        return {
            "scope": {
                "org_id": org_id,
                "role": role_norm,
                "user_id": user_id if is_agent else None,
            },
            "properties": {"items": prop_items, "total": prop_total, "limit": limit, "offset": offset},
            "buyers": {"items": buyer_items, "total": buyer_total, "limit": limit, "offset": offset},
            "matches": {"items": match_items, "total": match_total, "limit": limit, "offset": offset},
            "totals": {"properties": prop_total, "buyers": buyer_total, "matches": match_total},
            "buyer_source_summary": buyer_source_summary,
        }

    async def create_workspace_followup_task(
        self,
        org_id: str,
        user_id: str,
        entity_type: str,
        entity_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        due_date: Optional[str] = None,
        assigned_user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a follow-up task directly from workspace context."""
        task_payload = {
            "org_id": org_id,
            "title": title or f"Follow-up {entity_type}",
            "description": description or f"Workspace follow-up for {entity_type} {entity_id}",
            "type": "follow_up",
            "related_entity_type": entity_type,
            "related_entity_id": entity_id,
            "assigned_user_id": assigned_user_id or user_id,
            "due_date": due_date or datetime.utcnow().isoformat(),
            "ai_generated": False,
        }
        task_res = neon_service.client.table("tasks").insert(task_payload).execute()
        task_row = task_res.data[0] if task_res.data else {}

        try:
            await neon_service.insert_audit_log(
                {
                    "org_id": org_id,
                    "event_type": "workspace_followup_task_created",
                    "actor_user_id": user_id,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "details": {"task_id": task_row.get("id"), "source": "prospection_workspace"},
                }
            )
        except Exception:
            # Audit logging should not block operational task creation.
            pass

        return {"task_id": task_row.get("id")}

    async def mark_workspace_item_reviewed(
        self,
        org_id: str,
        user_id: str,
        entity_type: str,
        entity_id: str,
        note: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Persist a reviewed mark on property/buyer/match from workspace."""
        reviewed_note = (note or "reviewed_from_workspace").strip()
        stamp = datetime.utcnow().isoformat()
        entry = f"[reviewed:{stamp}] {reviewed_note}"

        if entity_type == "property":
            current = await self.get_property(org_id, entity_id)
            if not current:
                raise ValueError("property not found")
            existing_notes = str(current.get("notes") or "").strip()
            new_notes = f"{existing_notes}\n{entry}".strip() if existing_notes else entry
            updated = await self.update_property(org_id, entity_id, PropertyUpdate(notes=new_notes))
            if not updated:
                raise ValueError("property not found")
        elif entity_type == "buyer":
            current = await self.get_buyer(org_id, entity_id)
            if not current:
                raise ValueError("buyer not found")
            existing_notes = str(current.get("notes") or "").strip()
            new_notes = f"{existing_notes}\n{entry}".strip() if existing_notes else entry
            updated = await self.update_buyer(org_id, entity_id, BuyerUpdate(notes=new_notes))
            if not updated:
                raise ValueError("buyer not found")
        elif entity_type == "match":
            current = await self.get_match(org_id, entity_id)
            if not current:
                raise ValueError("match not found")
            existing_notes = str(current.get("notes") or "").strip()
            new_notes = f"{existing_notes}\n{entry}".strip() if existing_notes else entry
            updated = await self.update_match(org_id, entity_id, MatchUpdate(notes=new_notes))
            if not updated:
                raise ValueError("match not found")
        else:
            raise ValueError("unsupported entity type")

        try:
            await neon_service.insert_audit_log(
                {
                    "org_id": org_id,
                    "event_type": "workspace_item_reviewed",
                    "actor_user_id": user_id,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "details": {"note": reviewed_note, "source": "prospection_workspace"},
                }
            )
        except Exception:
            pass

        return {"entity_id": entity_id, "entity_type": entity_type}

    # ─────────────────────────────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────────────────────────────

    async def _list_assigned_property_ids(self, org_id: str, user_id: str) -> List[str]:
        """Collect assigned property ids across available property tables."""
        assigned_ids: set[str] = set()
        for property_table in self._property_tables():
            if not self._table_has_column(property_table, "assigned_user_id"):
                continue
            try:
                rows = (
                    neon_service.client.table(property_table)
                    .select("id")
                    .eq("org_id", org_id)
                    .eq("assigned_user_id", user_id)
                    .limit(5000)
                    .execute()
                ).data or []
                for row in rows:
                    row_id = row.get("id")
                    if row_id:
                        assigned_ids.add(str(row_id))
            except Exception:
                continue
        return list(assigned_ids)

    async def _enrich_matches(
        self, org_id: str, matches: List[Dict[str, Any]]
    ) -> None:
        """Add property_title and buyer_name to match records."""
        if not matches:
            return

        property_ids = list({m["property_id"] for m in matches})
        buyer_ids = list({m["buyer_id"] for m in matches})

        # Fetch property display names from all known property tables.
        prop_rows: List[Dict[str, Any]] = []
        seen_ids: set[str] = set()
        for property_table in self._property_tables():
            try:
                props = (
                    neon_service.client.table(property_table)
                    .select("*")
                    .eq("org_id", org_id)
                    .in_("id", property_ids)
                    .execute()
                )
                for row in (props.data or []):
                    if row["id"] not in seen_ids:
                        prop_rows.append(row)
                        seen_ids.add(row["id"])
            except Exception:
                continue

        # Fallback without org filter for legacy data inconsistencies.
        if len(prop_rows) < len(property_ids):
            for property_table in self._property_tables():
                try:
                    props_any_org = (
                        neon_service.client.table(property_table)
                        .select("*")
                        .in_("id", property_ids)
                        .execute()
                    )
                    for row in (props_any_org.data or []):
                        if row["id"] not in seen_ids:
                            prop_rows.append(row)
                            seen_ids.add(row["id"])
                except Exception:
                    continue

        prop_map: Dict[str, str] = {}
        for p in prop_rows:
            prop_map[p["id"]] = (
                p.get("title")
                or p.get("address")
                or p.get("zone")
                or "Sin título"
            )

        # Fetch buyer names
        buyers = (
            neon_service.client.table("buyer_profiles")
            .select("id, full_name")
            .eq("org_id", org_id)
            .in_("id", buyer_ids)
            .execute()
        )
        buyer_map: Dict[str, str] = {
            b["id"]: b.get("full_name", "Sin nombre") for b in buyers.data
        }

        for match in matches:
            match["property_title"] = prop_map.get(match["property_id"], "Sin título")
            match["buyer_name"] = buyer_map.get(match["buyer_id"], "Sin nombre")

    def _build_opportunity_explanation(
        self,
        match_row: Dict[str, Any],
        match_score: float,
        commission_norm: float,
        motivation: float,
    ) -> Dict[str, Any]:
        breakdown = match_row.get("score_breakdown") or {}
        top_factors: List[Dict[str, Any]] = []
        if isinstance(breakdown, dict):
            for key, value in sorted(breakdown.items(), key=lambda kv: float(kv[1] or 0), reverse=True)[:3]:
                top_factors.append({"factor": str(key), "value": round(float(value or 0), 2)})

        return {
            "drivers": {
                "match_score": round(match_score, 2),
                "commission_potential": round(commission_norm, 2),
                "buyer_motivation": round(motivation, 2),
            },
            "top_factors": top_factors,
            "confidence": round(min(100.0, (len(top_factors) * 25) + 25), 2),
        }

    def _recommend_next_action(self, opportunity_score: float, match_status: str) -> str:
        status = (match_status or "").lower()
        if status in {"offer", "negotiating"} and opportunity_score >= 70:
            return "prepare_offer_closure"
        if status in {"viewing", "contacted"} and opportunity_score >= 60:
            return "schedule_decision_followup"
        if opportunity_score >= 75:
            return "priority_call_24h"
        if opportunity_score >= 50:
            return "qualify_and_nurture"
        return "deprioritize_or_recycle"


# Module-level singleton
prospection_service = ProspectionService()
