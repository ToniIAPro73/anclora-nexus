from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from backend.models.membership import UserRole
from backend.models.source_observatory import (
    ObservatoryOverviewResponse,
    ObservatoryRankingResponse,
    ObservatorySummary,
    ObservatoryTrendsResponse,
    RankingItem,
    ScopeMetadata,
    SourceScorecard,
    TrendPoint,
)
from backend.services.cloud_ops_service import get_cloud_ops_summary
from backend.services.neon_service import neon_service


class SourceObservatoryService:
    def __init__(self) -> None:
        self.client = neon_service.client

    def _table_exists(self, table: str) -> bool:
        try:
            self.client.table(table).select("id").limit(1).execute()
            return True
        except Exception:
            return False

    async def _get_role(self, org_id: str, user_id: str) -> str:
        try:
            result = (
                self.client.table("organization_members")
                .select("role,status")
                .eq("org_id", org_id)
                .eq("user_id", user_id)
                .eq("status", "active")
                .limit(1)
                .execute()
            )
            if result.data:
                return str(result.data[0].get("role") or UserRole.AGENT.value)
        except Exception:
            pass
        return UserRole.OWNER.value

    def _source_key_from_event(self, connector_name: Optional[str]) -> str:
        value = str(connector_name or "").strip().lower()
        return value or "unknown"

    def _safe_select(self, table: str, fields: str, org_id: str) -> List[dict]:
        if not self._table_exists(table):
            return []
        try:
            return (
                self.client.table(table)
                .select(fields)
                .eq("org_id", org_id)
                .execute()
                .data
                or []
            )
        except Exception:
            return []

    async def _load_source_data(self, org_id: str) -> Tuple[List[dict], List[dict], List[dict], List[dict]]:
        events = self._safe_select(
            "ingestion_events",
            "connector_name,status,processed_at,created_at,entity_type,processed_entity_id,dedupe_key",
            org_id,
        )
        leads = self._safe_select("leads", "source_system,source_channel", org_id)
        properties = self._safe_select("properties", "source", org_id)
        sellers = self._safe_select("nexus_sellers", "fuente", org_id)
        return events, leads, properties, sellers

    def _event_bucket(self, status: Optional[str]) -> str:
        value = str(status or "").strip().lower()
        if value in {"processed", "success"}:
            return "processed"
        if value in {"rejected"}:
            return "rejected"
        if value in {"failed", "error"}:
            return "failed"
        if value in {"validated"}:
            return "validated"
        if value in {"received"}:
            return "received"
        return "other"

    def _parse_timestamp(self, raw: Optional[str]) -> Optional[datetime]:
        if not raw:
            return None
        try:
            return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except Exception:
            return None

    def _freshness_hours(self, latest_event_at: Optional[datetime]) -> Optional[float]:
        if latest_event_at is None:
            return None
        delta = datetime.now(timezone.utc) - latest_event_at.astimezone(timezone.utc)
        return round(delta.total_seconds() / 3600, 2)

    def _operational_status(
        self,
        *,
        total_events: int,
        failed_events: int,
        rejected_events: int,
        latest_event_at: Optional[datetime],
        processed_events: int,
    ) -> str:
        freshness_hours = self._freshness_hours(latest_event_at)
        terminal_total = processed_events + failed_events + rejected_events
        failure_rate = ((failed_events + rejected_events) / terminal_total) if terminal_total > 0 else 0.0

        if total_events == 0 or processed_events == 0:
            return "warning"
        if failure_rate >= 0.35:
            return "critical"
        if freshness_hours is not None and freshness_hours >= 168:
            return "critical"
        if failure_rate > 0 or (freshness_hours is not None and freshness_hours >= 72):
            return "warning"
        return "healthy"

    def _blank_counter(self) -> Dict[str, object]:
        return {
            "total": 0,
            "processed": 0,
            "validated": 0,
            "received": 0,
            "rejected": 0,
            "failed": 0,
            "duplicates": 0,
            "created_entities": 0,
            "lead_count": 0,
            "property_count": 0,
            "seller_count": 0,
            "latest_event_at": None,
            "entity_types": set(),
        }

    def _ensure_counter(self, counters: Dict[str, Dict[str, object]], key: str) -> Dict[str, object]:
        if key not in counters:
            counters[key] = self._blank_counter()
        return counters[key]

    async def get_overview(self, org_id: str, user_id: str) -> ObservatoryOverviewResponse:
        role = await self._get_role(org_id, user_id)
        events, leads, properties, sellers = await self._load_source_data(org_id)

        counters: Dict[str, Dict[str, object]] = {}

        for event in events:
            key = self._source_key_from_event(event.get("connector_name"))
            counter = self._ensure_counter(counters, key)
            counter["total"] = int(counter["total"]) + 1
            bucket = self._event_bucket(event.get("status"))
            counter[bucket] = int(counter.get(bucket, 0)) + 1

            entity_type = str(event.get("entity_type") or "").strip().lower()
            if entity_type:
                entity_types = counter["entity_types"]
                if isinstance(entity_types, set):
                    entity_types.add(entity_type)

            if (
                bucket == "processed"
                and event.get("processed_entity_id") is None
                and not key.startswith("feed:")
                and entity_type in {"lead", "property", "seller_signal"}
            ):
                counter["duplicates"] = int(counter["duplicates"]) + 1
            if event.get("processed_entity_id"):
                counter["created_entities"] = int(counter["created_entities"]) + 1

            latest = self._parse_timestamp(event.get("processed_at")) or self._parse_timestamp(event.get("created_at"))
            current_latest = counter["latest_event_at"]
            if latest and (current_latest is None or latest > current_latest):
                counter["latest_event_at"] = latest

        for lead in leads:
            source_system = str(lead.get("source_system") or "unknown").lower()
            source_channel = str(lead.get("source_channel") or "unknown").lower()
            key = f"{source_system}:{source_channel}"
            counter = self._ensure_counter(counters, key)
            counter["lead_count"] = int(counter["lead_count"]) + 1

        for property_row in properties:
            source = str(property_row.get("source") or "unknown").lower()
            key = f"{source}:properties"
            counter = self._ensure_counter(counters, key)
            counter["property_count"] = int(counter["property_count"]) + 1

        for seller_row in sellers:
            fuente = str(seller_row.get("fuente") or "unknown").lower()
            key = f"{fuente}:sellers"
            counter = self._ensure_counter(counters, key)
            counter["seller_count"] = int(counter["seller_count"]) + 1

        items: List[SourceScorecard] = []
        for key, counter in counters.items():
            total = int(counter["total"])
            processed = int(counter["processed"])
            rejected = int(counter["rejected"])
            failed = int(counter["failed"])
            latest_event_at = counter["latest_event_at"] if isinstance(counter["latest_event_at"], datetime) else None
            terminal_total = processed + rejected + failed
            success_rate = (processed / terminal_total * 100) if terminal_total > 0 else 0.0

            items.append(
                SourceScorecard(
                    source_key=key,
                    total_events=total,
                    success_events=processed,
                    duplicate_events=int(counter["duplicates"]),
                    error_events=rejected + failed,
                    success_rate_pct=round(success_rate, 2),
                    lead_count=int(counter["lead_count"]),
                    property_count=int(counter["property_count"]),
                    seller_count=int(counter["seller_count"]),
                    processed_events=processed,
                    rejected_events=rejected,
                    failed_events=failed,
                    created_entities=int(counter["created_entities"]),
                    freshness_hours=self._freshness_hours(latest_event_at),
                    latest_event_at=latest_event_at.isoformat() if latest_event_at else None,
                    operational_status=self._operational_status(
                        total_events=total,
                        failed_events=failed,
                        rejected_events=rejected,
                        latest_event_at=latest_event_at,
                        processed_events=processed,
                    ),
                    entity_types=sorted(list(counter["entity_types"])) if isinstance(counter["entity_types"], set) else [],
                )
            )

        cloud_ops = get_cloud_ops_summary()
        for check in cloud_ops["checks"]:
            items.append(
                SourceScorecard(
                    source_key=str(check["check_key"]),
                    total_events=0,
                    success_events=0,
                    duplicate_events=0,
                    error_events=0,
                    success_rate_pct=100.0 if check["status"] == "healthy" else 0.0,
                    lead_count=0,
                    property_count=0,
                    seller_count=0,
                    processed_events=0,
                    rejected_events=0,
                    failed_events=0,
                    created_entities=0,
                    freshness_hours=check["heartbeat_age_hours"],
                    latest_event_at=check["heartbeat_at"],
                    operational_status=str(check["status"]),
                    entity_types=["ops"],
                    heartbeat_age_hours=check["heartbeat_age_hours"],
                    latency_ms=check["latency_ms"],
                    retry_count=int(check["retry_count"]),
                    ops_message=str(check["message"]),
                )
            )

        items.sort(
            key=lambda item: (
                {"critical": 2, "warning": 1, "healthy": 0}.get(item.operational_status, 0),
                item.success_rate_pct * -1,
                item.total_events * -1,
            )
        )

        summary = ObservatorySummary(
            total_sources=len(items),
            healthy_sources=sum(1 for item in items if item.operational_status == "healthy"),
            warning_sources=sum(1 for item in items if item.operational_status == "warning"),
            critical_sources=sum(1 for item in items if item.operational_status == "critical"),
            stale_sources=sum(1 for item in items if item.freshness_hours is not None and item.freshness_hours >= 72),
            total_events=sum(item.total_events for item in items),
            total_created_entities=sum(item.created_entities for item in items),
            total_failures=sum(item.error_events for item in items),
            cloud_checks_total=int(cloud_ops["total_checks"]),
            cloud_checks_healthy=int(cloud_ops["healthy_checks"]),
            cloud_checks_warning=int(cloud_ops["warning_checks"]),
            cloud_checks_critical=int(cloud_ops["critical_checks"]),
        )
        return ObservatoryOverviewResponse(
            scope=ScopeMetadata(org_id=org_id, role=role),
            summary=summary,
            items=items,
            total=len(items),
        )

    async def get_ranking(self, org_id: str, user_id: str) -> ObservatoryRankingResponse:
        overview = await self.get_overview(org_id, user_id)
        ranking: List[RankingItem] = []
        for item in overview.items:
            volume_factor = min(item.total_events / 20.0, 1.0) * 8
            created_factor = min(item.created_entities / 20.0, 1.0) * 12
            coverage_factor = min((item.lead_count + item.property_count + item.seller_count) / 40.0, 1.0) * 10
            freshness_penalty = 0.0
            if item.freshness_hours is not None and item.freshness_hours >= 72:
                freshness_penalty = 12.0 if item.freshness_hours >= 168 else 6.0
            status_penalty = 18.0 if item.operational_status == "critical" else (8.0 if item.operational_status == "warning" else 0.0)
            score = round((item.success_rate_pct * 0.75) + volume_factor + created_factor + coverage_factor - freshness_penalty - status_penalty, 2)
            ranking.append(
                RankingItem(
                    source_key=item.source_key,
                    score=score,
                    success_rate_pct=item.success_rate_pct,
                    lead_count=item.lead_count,
                    created_entities=item.created_entities,
                    freshness_hours=item.freshness_hours,
                    operational_status=item.operational_status,
                )
            )
        ranking.sort(key=lambda row: row.score, reverse=True)
        return ObservatoryRankingResponse(scope=overview.scope, items=ranking, total=len(ranking))

    def _month_keys(self, months: int) -> List[str]:
        now = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return [(now - timedelta(days=index * 31)).strftime("%Y-%m") for index in range(months - 1, -1, -1)]

    async def get_trends(self, org_id: str, user_id: str, months: int = 6) -> ObservatoryTrendsResponse:
        role = await self._get_role(org_id, user_id)
        month_keys = self._month_keys(months)
        min_date = f"{month_keys[0]}-01T00:00:00+00:00"

        events: List[dict] = []
        if self._table_exists("ingestion_events"):
            try:
                events = (
                    self.client.table("ingestion_events")
                    .select("connector_name,status,processed_at,created_at,processed_entity_id")
                    .eq("org_id", org_id)
                    .gte("created_at", min_date)
                    .execute()
                    .data
                    or []
                )
            except Exception:
                events = []

        bucket: Dict[Tuple[str, str], Dict[str, int]] = defaultdict(
            lambda: {"total": 0, "processed": 0, "failed": 0, "rejected": 0, "created_entities": 0}
        )
        for event in events:
            timestamp = self._parse_timestamp(event.get("processed_at")) or self._parse_timestamp(event.get("created_at"))
            if not timestamp:
                continue
            period = timestamp.astimezone(timezone.utc).strftime("%Y-%m")
            source_key = self._source_key_from_event(event.get("connector_name"))
            key = (period, source_key)
            bucket[key]["total"] += 1
            event_bucket = self._event_bucket(event.get("status"))
            if event_bucket == "processed":
                bucket[key]["processed"] += 1
            elif event_bucket == "failed":
                bucket[key]["failed"] += 1
            elif event_bucket == "rejected":
                bucket[key]["rejected"] += 1
            if event.get("processed_entity_id"):
                bucket[key]["created_entities"] += 1

        points: List[TrendPoint] = []
        for (period, source_key), counter in bucket.items():
            terminal_total = counter["processed"] + counter["failed"] + counter["rejected"]
            success_rate = (counter["processed"] / terminal_total * 100) if terminal_total > 0 else 0.0
            points.append(
                TrendPoint(
                    period=period,
                    source_key=source_key,
                    events=counter["total"],
                    success_rate_pct=round(success_rate, 2),
                    processed_events=counter["processed"],
                    failed_events=counter["failed"] + counter["rejected"],
                    created_entities=counter["created_entities"],
                )
            )
        points.sort(key=lambda item: (item.period, item.source_key))
        return ObservatoryTrendsResponse(scope=ScopeMetadata(org_id=org_id, role=role), months=months, points=points)


source_observatory_service = SourceObservatoryService()
