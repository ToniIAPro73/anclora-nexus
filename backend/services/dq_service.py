import re
import asyncio
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
from backend.services.neon_service import neon_service
from backend.models.dq import (
    DQQualityIssue, DQEntityCandidate, DQResolutionLog,
    EntityType, IssueType, Severity, IssueStatus, 
    CandidateStatus, ResolutionAction, DQMetricsResponse,
    DQIssuesResponse
)

class DQService:
    def __init__(self):
        self.email_regex = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

    def normalize_phone(self, phone: Optional[str]) -> Optional[str]:
        if not phone:
            return None
        # Remove all non-numeric characters
        digits = re.sub(r"\D", "", phone)
        # Handle Spanish numbers (prefix 34 if missing and looks like it)
        if len(digits) == 9 and digits.startswith(("6", "7", "8", "9")):
            digits = "34" + digits
        return digits

    def normalize_email(self, email: Optional[str]) -> Optional[str]:
        if not email:
            return None
        return email.strip().lower()

    def calculate_similarity_score(self, entity_type: EntityType, e1: Dict[str, Any], e2: Dict[str, Any]) -> float:
        score = 0.0
        signals = {}

        if entity_type == EntityType.LEAD:
            # Email match (highest priority)
            email1 = self.normalize_email(e1.get("email"))
            email2 = self.normalize_email(e2.get("email"))
            if email1 and email2 and email1 == email2:
                score += 50
                signals["email_match"] = True

            # Phone match
            phone1 = self.normalize_phone(e1.get("phone"))
            phone2 = self.normalize_phone(e2.get("phone"))
            if phone1 and phone2 and phone1 == phone2:
                score += 35
                signals["phone_match"] = True

            # Name match (simple case insensitive)
            name1 = (e1.get("name") or "").strip().lower()
            name2 = (e2.get("name") or "").strip().lower()
            if name1 and name2 and name1 == name2:
                score += 15
                signals["name_match"] = True
            elif name1 and name2 and (name1 in name2 or name2 in name1):
                score += 7
                signals["name_partial_match"] = True

        elif entity_type == EntityType.PROPERTY:
            # Catastro match
            cat1 = (e1.get("catastro_ref") or "").strip()
            cat2 = (e2.get("catastro_ref") or "").strip()
            if cat1 and cat2 and cat1 == cat2:
                score += 60
                signals["catastro_match"] = True

            # Address match
            addr1 = (e1.get("address") or "").strip().lower()
            addr2 = (e2.get("address") or "").strip().lower()
            if addr1 and addr2 and addr1 == addr2:
                score += 25
                signals["address_match"] = True

            # Price/Surface proximity
            price1 = float(e1.get("price") or 0)
            price2 = float(e2.get("price") or 0)
            if price1 > 0 and price2 > 0:
                diff = abs(price1 - price2) / max(price1, price2)
                if diff < 0.05: # 5% tolerance
                    score += 7
                    signals["price_proximity"] = True

            surf1 = float(e1.get("surface_m2") or 0)
            surf2 = float(e2.get("surface_m2") or 0)
            if surf1 > 0 and surf2 > 0:
                diff = abs(surf1 - surf2) / max(surf1, surf2)
                if diff < 0.1: # 10% tolerance
                    score += 8
                    signals["surface_proximity"] = True

        return min(100.0, score), signals

    def detect_quality_issues(self, entity_type: EntityType, e: Dict[str, Any]) -> List[Dict[str, Any]]:
        issues = []
        if entity_type == EntityType.LEAD:
            if not e.get("email") and not e.get("phone"):
                issues.append({
                    "issue_type": IssueType.MISSING_FIELD,
                    "severity": Severity.HIGH,
                    "issue_payload": {"fields": ["email", "phone"], "message": "At least one contact method required"}
                })
            elif e.get("email") and not self.email_regex.match(e.get("email")):
                issues.append({
                    "issue_type": IssueType.INVALID_FORMAT,
                    "severity": Severity.MEDIUM,
                    "issue_payload": {"field": "email", "value": e.get("email")}
                })
            
            if not e.get("name") or len(e.get("name").strip()) < 2:
                issues.append({
                    "issue_type": IssueType.MISSING_FIELD,
                    "severity": Severity.MEDIUM,
                    "issue_payload": {"field": "name", "message": "Valid name required"}
                })

        elif entity_type == EntityType.PROPERTY:
            price = float(e.get("price") or 0)
            if price <= 0:
                issues.append({
                    "issue_type": IssueType.INCONSISTENT_VALUE,
                    "severity": Severity.HIGH,
                    "issue_payload": {"field": "price", "value": price, "message": "Price must be positive"}
                })
            
            built = float(e.get("built_area_m2") or 0)
            useful = float(e.get("useful_area_m2") or 0)
            if useful > 0 and built > 0 and useful > built:
                issues.append({
                    "issue_type": IssueType.INCONSISTENT_VALUE,
                    "severity": Severity.CRITICAL,
                    "issue_payload": {"fields": ["useful_area_m2", "built_area_m2"], "message": "Useful area cannot exceed built area"}
                })
            
            if not e.get("address"):
                issues.append({
                    "issue_type": IssueType.MISSING_FIELD,
                    "severity": Severity.HIGH,
                    "issue_payload": {"field": "address", "message": "Address is required"}
                })

        return issues

    async def get_issues(self, org_id: str, entity_type: Optional[EntityType] = None, status: IssueStatus = IssueStatus.OPEN, limit: int = 50, offset: int = 0) -> DQIssuesResponse:
        query = neon_service.client.table("dq_quality_issues").select("*", count="exact").eq("org_id", org_id).eq("status", status.value)
        if entity_type:
            query = query.eq("entity_type", entity_type.value)
        
        response = query.order("severity", desc=True).order("created_at", desc=True).range(offset, offset + limit - 1).execute()
        
        return DQIssuesResponse(
            issues=[DQQualityIssue(**item) for item in response.data],
            total_count=response.count or 0
        )

    async def get_metrics(self, org_id: str) -> DQMetricsResponse:
        issues_resp = neon_service.client.table("dq_quality_issues").select("id, severity, status").eq("org_id", org_id).execute()
        candidates_resp = neon_service.client.table("dq_entity_candidates").select("id, status").eq("org_id", org_id).execute()
        
        issues = issues_resp.data or []
        candidates = candidates_resp.data or []
        
        return DQMetricsResponse(
            total_issues=len(issues),
            open_issues=len([i for i in issues if i["status"] == "open"]),
            critical_issues=len([i for i in issues if i["severity"] == "critical" and i["status"] == "open"]),
            total_candidates=len(candidates),
            suggested_merges=len([c for c in candidates if c["status"] == "suggested_merge"]),
            last_recompute_at=datetime.utcnow() # TODO: Track this in a separate table/config
        )

    async def recompute_all(self, org_id: str):
        # 1. Fetch all leads and properties
        leads_resp = neon_service.client.table("leads").select("*").eq("org_id", org_id).execute()
        props_resp = neon_service.client.table("properties").select("*").eq("org_id", org_id).execute()
        
        leads = leads_resp.data or []
        props = props_resp.data or []
        
        # 2. Re-detect quality issues
        # Simple strategy: delete current OPEN issues and re-insert
        neon_service.client.table("dq_quality_issues").delete().eq("org_id", org_id).eq("status", "open").execute()
        
        new_issues = []
        for l in leads:
            issues = self.detect_quality_issues(EntityType.LEAD, l)
            for iss in issues:
                new_issues.append({**iss, "org_id": org_id, "entity_type": EntityType.LEAD.value, "entity_id": l["id"]})
        
        for p in props:
            issues = self.detect_quality_issues(EntityType.PROPERTY, p)
            for iss in issues:
                new_issues.append({**iss, "org_id": org_id, "entity_type": EntityType.PROPERTY.value, "entity_id": p["id"]})
        
        if new_issues:
            # Batch insert (Neon limit might apply, but for v0 it should be fine)
             neon_service.client.table("dq_quality_issues").insert(new_issues).execute()
        
        # 3. Find duplicate candidates
        # Fetch EXISTING candidates to avoid unique constraint violations
        existing_candidates_resp = neon_service.client.table("dq_entity_candidates").select("left_entity_id, right_entity_id").eq("org_id", org_id).execute()
        existing_pairs = set()
        if existing_candidates_resp.data:
            for c in existing_candidates_resp.data:
                existing_pairs.add((c["left_entity_id"], c["right_entity_id"]))

        new_candidates = []
        
        # Match leads
        for i in range(len(leads)):
            for j in range(i + 1, len(leads)):
                # Check if pair already exists
                if (leads[i]["id"], leads[j]["id"]) in existing_pairs or (leads[j]["id"], leads[i]["id"]) in existing_pairs:
                    continue

                score, signals = self.calculate_similarity_score(EntityType.LEAD, leads[i], leads[j])
                if score >= 40: # Threshold for candidate
                    new_candidates.append({
                        "org_id": org_id,
                        "entity_type": EntityType.LEAD.value,
                        "left_entity_id": leads[i]["id"],
                        "right_entity_id": leads[j]["id"],
                        "similarity_score": score,
                        "signals": signals,
                        "status": "suggested_merge"
                    })
        
        # Match properties
        for i in range(len(props)):
            for j in range(i + 1, len(props)):
                # Check if pair already exists
                if (props[i]["id"], props[j]["id"]) in existing_pairs or (props[j]["id"], props[i]["id"]) in existing_pairs:
                    continue

                score, signals = self.calculate_similarity_score(EntityType.PROPERTY, props[i], props[j])
                if score >= 40:
                    new_candidates.append({
                        "org_id": org_id,
                        "entity_type": EntityType.PROPERTY.value,
                        "left_entity_id": props[i]["id"],
                        "right_entity_id": props[j]["id"],
                        "similarity_score": score,
                        "signals": signals,
                        "status": "suggested_merge"
                    })
        
        if new_candidates:
            neon_service.client.table("dq_entity_candidates").insert(new_candidates).execute()

    async def resolve_candidate(self, org_id: str, candidate_id: UUID, action: ResolutionAction, actor_user_id: Optional[UUID] = None, details: Optional[Dict[str, Any]] = None):
        # 1. Fetch candidate
        resp = neon_service.client.table("dq_entity_candidates").select("*").eq("id", str(candidate_id)).eq("org_id", org_id).single().execute()
        if not resp.data:
            raise ValueError("Candidate not found")
        
        candidate = resp.data
        
        # 2. Determine new status
        new_status = CandidateStatus.APPROVED_MERGE if action == ResolutionAction.APPROVE_MERGE else CandidateStatus.REJECTED_MERGE
        if action == ResolutionAction.MARK_DUPLICATE:
            new_status = CandidateStatus.AUTO_LINK
        
        # 3. Update candidate
        neon_service.client.table("dq_entity_candidates").update({"status": new_status.value}).eq("id", str(candidate_id)).execute()
        
        # 4. Create resolution log
        log_entry = {
            "org_id": org_id,
            "entity_type": candidate["entity_type"],
            "candidate_id": str(candidate_id),
            "action": action.value,
            "actor_user_id": str(actor_user_id) if actor_user_id else None,
            "details": details or {}
        }
        neon_service.client.table("dq_resolution_log").insert(log_entry).execute()
        
        # 5. TODO: Implement actual merge logic if approved
        # For v1, we just mark as approved. Actual merge might be a separate background task or manual.
        
        return {"status": "success", "new_status": new_status}

dq_service = DQService()
