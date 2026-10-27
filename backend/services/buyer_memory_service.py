from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import math
import re
from typing import Any, Dict, List, Tuple

from backend.models.buyer_memory import (
    BuyerMemoryMatch,
    BuyerMemoryMatchReason,
    BuyerMemoryRebuildResponse,
    BuyerMemoryRecord,
    BuyerMemoryResponse,
)
from backend.services.embedding_service import embedding_service
from backend.services.neon_service import NeonService


DEFAULT_QUERY = "buyer referral prioridad presupuesto zona visita siguiente paso"
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?:(?:\+|00)\d{1,3}[\s-]?)?(?:\d[\s-]?){7,14}\d")
WORD_RE = re.compile(r"[a-zA-Z0-9áéíóúñü]+", re.IGNORECASE)
STOPWORDS = {
    "de", "la", "el", "y", "en", "que", "para", "por", "con", "sin", "del", "los", "las",
    "una", "uno", "sobre", "desde", "este", "esta", "pero", "como", "mas", "más", "the",
    "and", "for", "with", "from", "was", "are", "muy", "todo", "toda", "buyer", "buyers",
}


class BuyerMemoryService:
    def __init__(self) -> None:
        self.client = NeonService().client

    def _table_exists(self, table: str) -> bool:
        try:
            self.client.table(table).select("id").limit(1).execute()
            return True
        except Exception:
            return False

    @staticmethod
    def _redact_pii(text: str) -> str:
        redacted = EMAIL_RE.sub("[redacted-email]", text or "")
        redacted = PHONE_RE.sub("[redacted-phone]", redacted)
        return redacted.strip()

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        tokens = [token.lower() for token in WORD_RE.findall(text or "")]
        return [token for token in tokens if len(token) > 2 and token not in STOPWORDS]

    def _build_keywords(self, *values: str) -> List[str]:
        counter: Counter[str] = Counter()
        for value in values:
            counter.update(self._tokenize(value))
        return [token for token, _count in counter.most_common(8)]

    def _profile_record(self, org_id: str, buyer: Dict[str, Any]) -> Dict[str, Any]:
        preferred_zones = ", ".join(buyer.get("preferred_zones") or [])
        partner_name = str(buyer.get("referral_partner_name") or "")
        source_type = str(buyer.get("source_type") or "manual")
        horizon = str(buyer.get("purchase_horizon") or "")
        notes = str(buyer.get("notes") or "")
        budget_bits = []
        if buyer.get("budget_min") is not None:
            budget_bits.append(f"min {buyer.get('budget_min')}")
        if buyer.get("budget_max") is not None:
            budget_bits.append(f"max {buyer.get('budget_max')}")
        summary = " · ".join(
            bit for bit in [
                str(buyer.get("full_name") or "buyer profile"),
                source_type.replace("_", " "),
                partner_name or None,
                preferred_zones or None,
                horizon or None,
            ] if bit
        )
        redacted = self._redact_pii(
            " ".join(
                part for part in [
                    str(buyer.get("full_name") or ""),
                    str(buyer.get("email") or ""),
                    str(buyer.get("phone") or ""),
                    preferred_zones,
                    " ".join(budget_bits),
                    notes,
                ] if part
            )
        )
        return {
            "org_id": org_id,
            "buyer_id": buyer.get("id"),
            "source_ref": f"profile:{buyer.get('id')}",
            "memory_kind": "profile",
            "source_type": source_type,
            "source_artifact": "buyer_profile",
            "summary": summary or "buyer profile",
            "redacted_content": redacted or summary or "buyer profile",
            "semantic_payload": {
                "source_platform": buyer.get("source_platform"),
                "buyer_intro_status": buyer.get("buyer_intro_status"),
                "preferred_zones": buyer.get("preferred_zones") or [],
                "intent_score": buyer.get("intent_score"),
                "trust_score": buyer.get("trust_score"),
                "capacity_score": buyer.get("capacity_score"),
            },
            "keywords": self._build_keywords(summary, redacted, preferred_zones, notes),
            "salience_score": 76 if source_type == "partner_referral" else 62,
            "embedding": None,
            "embedding_dimensions": None,
            "embedding_provider": None,
            "embedding_model": None,
            "embedding_status": "pending",
            "embedding_generated_at": None,
            "source_created_at": buyer.get("updated_at") or buyer.get("created_at") or datetime.now(timezone.utc).isoformat(),
        }

    def _match_record(self, org_id: str, buyer_id: str, match: Dict[str, Any], property_title: str | None) -> Dict[str, Any]:
        summary = " · ".join(
            part for part in [
                "match",
                property_title,
                str(match.get("match_status") or "candidate"),
                f"score {match.get('match_score')}" if match.get("match_score") is not None else None,
            ] if part
        )
        notes = str(match.get("notes") or "")
        return {
            "org_id": org_id,
            "buyer_id": buyer_id,
            "source_ref": f"match:{match.get('id')}",
            "memory_kind": "match",
            "source_type": "match",
            "source_artifact": property_title or "property_match",
            "summary": summary or "property match",
            "redacted_content": self._redact_pii(f"{summary} {notes}") or summary or "property match",
            "semantic_payload": {
                "property_id": match.get("property_id"),
                "property_title": property_title,
                "match_status": match.get("match_status"),
                "match_score": match.get("match_score"),
                "commission_estimate": match.get("commission_estimate"),
            },
            "keywords": self._build_keywords(summary, notes, property_title or ""),
            "salience_score": 58,
            "embedding": None,
            "embedding_dimensions": None,
            "embedding_provider": None,
            "embedding_model": None,
            "embedding_status": "pending",
            "embedding_generated_at": None,
            "source_created_at": match.get("updated_at") or match.get("created_at") or datetime.now(timezone.utc).isoformat(),
        }

    def _activity_record(self, org_id: str, buyer_id: str, activity: Dict[str, Any], property_title: str | None) -> Dict[str, Any]:
        details = activity.get("details") or {}
        detail_text = " ".join(f"{key}:{value}" for key, value in details.items())
        summary = " · ".join(
            part for part in [
                str(activity.get("activity_type") or "activity"),
                property_title,
                str(activity.get("outcome") or ""),
            ] if part
        )
        return {
            "org_id": org_id,
            "buyer_id": buyer_id,
            "source_ref": f"activity:{activity.get('id')}",
            "memory_kind": "activity",
            "source_type": str(activity.get("activity_type") or "activity"),
            "source_artifact": property_title or "match_activity",
            "summary": summary or "buyer activity",
            "redacted_content": self._redact_pii(f"{summary} {detail_text}") or summary or "buyer activity",
            "semantic_payload": {
                "match_id": activity.get("match_id"),
                "outcome": activity.get("outcome"),
                "details": details,
            },
            "keywords": self._build_keywords(summary, detail_text, property_title or ""),
            "salience_score": 70,
            "embedding": None,
            "embedding_dimensions": None,
            "embedding_provider": None,
            "embedding_model": None,
            "embedding_status": "pending",
            "embedding_generated_at": None,
            "source_created_at": activity.get("created_at") or datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _embedding_source_text(record: Dict[str, Any]) -> str:
        return f"{record.get('summary') or ''}\n{record.get('redacted_content') or ''}".strip()

    async def _vectorize_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        if not embedding_service.is_ready():
            record["embedding_status"] = "provider_unavailable"
            return record
        try:
            vector = await embedding_service.embed_text(self._embedding_source_text(record))
            record["embedding"] = vector
            record["embedding_dimensions"] = len(vector)
            record["embedding_provider"] = "cloudflare"
            record["embedding_model"] = embedding_service.summary().get("model")
            record["embedding_status"] = "ready"
            record["embedding_generated_at"] = datetime.now(timezone.utc).isoformat()
        except Exception:
            record["embedding_status"] = "error"
        return record

    @staticmethod
    def _cosine_similarity(left: List[float], right: List[float]) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0
        dot = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(a * a for a in left))
        right_norm = math.sqrt(sum(b * b for b in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return dot / (left_norm * right_norm)

    async def rebuild_for_buyer(self, *, db: NeonService, org_id: str, buyer_id: str) -> BuyerMemoryRebuildResponse:
        if not self._table_exists("buyer_memory_records"):
            return BuyerMemoryRebuildResponse(buyer_id=buyer_id, status="migration_missing", indexed_records=0, created_records=0)

        buyer_rows = (
            db.client.table("buyer_profiles")
            .select("*")
            .eq("org_id", str(org_id))
            .eq("id", str(buyer_id))
            .limit(1)
            .execute()
            .data
            or []
        )
        if not buyer_rows:
            return BuyerMemoryRebuildResponse(buyer_id=buyer_id, status="buyer_missing", indexed_records=0, created_records=0)
        buyer = buyer_rows[0]

        matches = (
            db.client.table("property_buyer_matches")
            .select("*")
            .eq("org_id", str(org_id))
            .eq("buyer_id", str(buyer_id))
            .execute()
            .data
            or []
        )
        property_ids = list({row.get("property_id") for row in matches if row.get("property_id")})
        property_titles: Dict[str, str] = {}
        for table in ("properties", "prospected_properties"):
            try:
                if not property_ids:
                    break
                rows = (
                    db.client.table(table)
                    .select("id,title,zone,address")
                    .in_("id", property_ids)
                    .execute()
                    .data
                    or []
                )
                for row in rows:
                    property_titles[str(row.get("id"))] = str(row.get("title") or row.get("zone") or row.get("address") or "property")
            except Exception:
                continue

        match_ids = list({row.get("id") for row in matches if row.get("id")})
        activities = []
        if match_ids:
            try:
                activities = (
                    db.client.table("match_activity_log")
                    .select("*")
                    .eq("org_id", str(org_id))
                    .in_("match_id", match_ids)
                    .execute()
                    .data
                    or []
                )
            except Exception:
                activities = []

        current = (
            db.client.table("buyer_memory_records")
            .select("source_ref,id,embedding_status,summary,redacted_content,embedding")
            .eq("org_id", str(org_id))
            .eq("buyer_id", str(buyer_id))
            .execute()
            .data
            or []
        )
        existing_refs = {str(row.get("source_ref")) for row in current if row.get("source_ref")}

        candidate_rows = [self._profile_record(org_id, buyer)]
        candidate_rows.extend(
            self._match_record(org_id, buyer_id, match, property_titles.get(str(match.get("property_id"))))
            for match in matches
        )
        match_lookup = {str(match.get("id")): match for match in matches if match.get("id")}
        candidate_rows.extend(
            self._activity_record(
                org_id,
                buyer_id,
                activity,
                property_titles.get(str(match_lookup.get(str(activity.get("match_id")), {}).get("property_id"))),
            )
            for activity in activities
        )

        new_rows = [row for row in candidate_rows if str(row.get("source_ref")) not in existing_refs]
        vectorized_records = 0
        for row in new_rows:
            await self._vectorize_record(row)
            if row.get("embedding_status") == "ready":
                vectorized_records += 1
        if new_rows:
            db.client.table("buyer_memory_records").insert(new_rows).execute()

        existing_pending = [row for row in current if str(row.get("embedding_status") or "pending") != "ready"]
        for row in existing_pending:
            update_payload = {
                "summary": row.get("summary") or "",
                "redacted_content": row.get("redacted_content") or "",
                "embedding_status": row.get("embedding_status") or "pending",
            }
            await self._vectorize_record(update_payload)
            if update_payload.get("embedding_status") == "ready":
                vectorized_records += 1
            db.client.table("buyer_memory_records").update({
                "embedding": update_payload.get("embedding"),
                "embedding_dimensions": update_payload.get("embedding_dimensions"),
                "embedding_provider": update_payload.get("embedding_provider"),
                "embedding_model": update_payload.get("embedding_model"),
                "embedding_status": update_payload.get("embedding_status"),
                "embedding_generated_at": update_payload.get("embedding_generated_at"),
            }).eq("id", row.get("id")).execute()

        total = len(existing_refs) + len(new_rows)
        return BuyerMemoryRebuildResponse(
            buyer_id=buyer_id,
            status="ready",
            indexed_records=total,
            created_records=len(new_rows),
            vectorized_records=vectorized_records,
        )

    def _score_record(self, record: Dict[str, Any], query_tokens: List[str]) -> Tuple[float, List[str], List[BuyerMemoryMatchReason]]:
        summary = str(record.get("summary") or "")
        redacted = str(record.get("redacted_content") or "")
        artifact = str(record.get("source_artifact") or "")
        keywords = [str(item).lower() for item in (record.get("keywords") or [])]
        searchable_tokens = set(self._tokenize(" ".join([summary, redacted, artifact, " ".join(keywords)])))
        keyword_hits = [token for token in query_tokens if token in searchable_tokens]

        score = float(record.get("salience_score") or 0) * 0.35
        reasons: List[BuyerMemoryMatchReason] = []
        if keyword_hits:
            score += len(keyword_hits) * 18
            reasons.append(BuyerMemoryMatchReason(type="keyword_hits", value=", ".join(keyword_hits[:4])))
        if artifact:
            score += 8
            reasons.append(BuyerMemoryMatchReason(type="artifact_match", value=artifact))
        return score, keyword_hits, reasons

    async def search(self, *, db: NeonService, org_id: str, buyer_id: str, query: str = DEFAULT_QUERY, limit: int = 5) -> BuyerMemoryResponse:
        if not self._table_exists("buyer_memory_records"):
            return BuyerMemoryResponse(
                buyer_id=buyer_id,
                status="migration_missing",
                query=query,
                total_records=0,
                matches=[],
                retrieval_summary="Buyer memory migration missing.",
            )

        rows = (
            db.client.table("buyer_memory_records")
            .select("*")
            .eq("org_id", str(org_id))
            .eq("buyer_id", str(buyer_id))
            .order("source_created_at", desc=True)
            .limit(100)
            .execute()
            .data
            or []
        )
        if not rows:
            return BuyerMemoryResponse(
                buyer_id=buyer_id,
                status="empty",
                query=query,
                total_records=0,
                matches=[],
                retrieval_summary="No buyer memory indexed yet.",
            )

        query_tokens = self._tokenize(query or DEFAULT_QUERY)
        vector_ready_records = len([row for row in rows if str(row.get("embedding_status")) == "ready" and row.get("embedding")])
        retrieval_mode = "lexical"
        query_vector: List[float] | None = None
        if vector_ready_records and embedding_service.is_ready():
            try:
                query_vector = await embedding_service.embed_text(query or DEFAULT_QUERY)
                retrieval_mode = "vector_hybrid"
            except Exception:
                query_vector = None
                retrieval_mode = "lexical"

        matches: List[BuyerMemoryMatch] = []
        for row in rows:
            score, keyword_hits, reasons = self._score_record(row, query_tokens)
            if query_vector and row.get("embedding"):
                similarity = self._cosine_similarity(query_vector, row.get("embedding"))
                if similarity > 0:
                    score += similarity * 28
                    reasons.append(BuyerMemoryMatchReason(type="vector_similarity", value=f"{similarity:.3f}"))
            if score <= 0:
                continue
            matches.append(
                BuyerMemoryMatch(
                    record=BuyerMemoryRecord(**row),
                    score=round(score, 2),
                    matched_keywords=keyword_hits,
                    reasons=reasons,
                )
            )

        matches.sort(key=lambda item: item.score, reverse=True)
        sliced = matches[:limit]
        retrieval_summary = (
            f"{len(sliced)} buyer memory matches from {len(rows)} indexed records"
            + (f" using {retrieval_mode}" if sliced else "")
        )
        return BuyerMemoryResponse(
            buyer_id=buyer_id,
            status="ready",
            query=query,
            total_records=len(rows),
            vector_ready_records=vector_ready_records,
            retrieval_mode=retrieval_mode,
            matches=sliced,
            retrieval_summary=retrieval_summary,
        )

    async def get_preview_map(self, *, db: NeonService, org_id: str, buyer_ids: List[str], limit_per_buyer: int = 2) -> Dict[str, Dict[str, Any]]:
        if not buyer_ids or not self._table_exists("buyer_memory_records"):
            return {}
        rows = (
            db.client.table("buyer_memory_records")
            .select("buyer_id,summary,embedding_status,source_created_at")
            .eq("org_id", str(org_id))
            .in_("buyer_id", buyer_ids)
            .order("source_created_at", desc=True)
            .limit(max(len(buyer_ids) * limit_per_buyer * 3, 20))
            .execute()
            .data
            or []
        )
        grouped: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"memory_preview": [], "memory_status": "empty"})
        for row in rows:
            buyer_id = str(row.get("buyer_id"))
            bucket = grouped[buyer_id]
            if len(bucket["memory_preview"]) < limit_per_buyer:
                bucket["memory_preview"].append(str(row.get("summary") or ""))
            if row.get("embedding_status") == "ready":
                bucket["memory_status"] = "ready"
        return grouped


buyer_memory_service = BuyerMemoryService()
