import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from backend.models.feed_orchestrator import (
    FeedChannelSummary,
    FeedPublishResponse,
    FeedRunItem,
    FeedValidationIssue,
    FeedValidationResponse,
    FeedWorkspaceResponse,
)
from backend.services.neon_service import neon_service


class FeedOrchestratorService:
    CHANNELS: Dict[str, Dict[str, Any]] = {
        "idealista": {"format": "xml", "required_fields": ["title", "price", "zone", "property_type"]},
        "fotocasa": {"format": "xml", "required_fields": ["title", "price", "zone", "property_type"]},
        "rightmove": {"format": "json", "required_fields": ["title", "price", "city", "property_type"]},
        "kyero": {"format": "json", "required_fields": ["title", "price", "zone", "property_type"]},
    }

    def _table_exists(self, table: str) -> bool:
        try:
            neon_service.client.table(table).select("id").limit(1).execute()
            return True
        except Exception:
            return False

    def _property_tables(self) -> List[str]:
        tables: List[str] = []
        for table in ("properties", "prospected_properties"):
            if self._table_exists(table):
                tables.append(table)
        return tables

    def _row_price(self, row: Dict[str, Any]) -> Optional[float]:
        raw = row.get("price")
        if raw is None:
            raw = row.get("price_eur")
        if raw is None:
            return None
        try:
            return float(raw)
        except Exception:
            return None

    def _normalize_property(self, row: Dict[str, Any], table: str) -> Dict[str, Any]:
        return {
            "id": str(row.get("id")),
            "org_id": row.get("org_id"),
            "title": row.get("title") or row.get("address"),
            "zone": row.get("zone"),
            "city": row.get("city"),
            "property_type": row.get("property_type"),
            "price": self._row_price(row),
            "status": (row.get("status") or "new").lower(),
            "source_url": row.get("source_url"),
            "source_portal": row.get("source_portal"),
            "_table": table,
            "_raw": row,
        }

    async def _list_properties(self, org_id: str, limit: int = 500) -> List[Dict[str, Any]]:
        merged: Dict[str, Dict[str, Any]] = {}
        for table in self._property_tables():
            try:
                rows = (
                    neon_service.client.table(table)
                    .select("*")
                    .eq("org_id", org_id)
                    .order("created_at", desc=True)
                    .limit(limit)
                    .execute()
                ).data or []
                for row in rows:
                    row_id = str(row.get("id"))
                    if row_id and row_id not in merged:
                        merged[row_id] = self._normalize_property(row, table)
            except Exception:
                continue
        return list(merged.values())

    async def _channel_configs(self, org_id: str) -> Dict[str, Dict[str, Any]]:
        if not self._table_exists("feed_channel_configs"):
            return {
                ch: {
                    **cfg,
                    "is_enabled": True,
                    "max_items_per_run": 100,
                    "rules_json": {},
                }
                for ch, cfg in self.CHANNELS.items()
            }
        try:
            rows = (
                neon_service.client.table("feed_channel_configs")
                .select("channel, format, is_enabled, max_items_per_run, rules_json")
                .eq("org_id", org_id)
                .execute()
            ).data or []
        except Exception:
            return {
                ch: {
                    **cfg,
                    "is_enabled": True,
                    "max_items_per_run": 100,
                    "rules_json": {},
                }
                for ch, cfg in self.CHANNELS.items()
            }

        if not rows:
            return {
                ch: {
                    **cfg,
                    "is_enabled": True,
                    "max_items_per_run": 100,
                    "rules_json": {},
                }
                for ch, cfg in self.CHANNELS.items()
            }

        configs: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            ch = str(row.get("channel") or "").lower().strip()
            if ch not in self.CHANNELS:
                continue
            cfg = dict(self.CHANNELS[ch])
            fmt = row.get("format")
            if fmt in ("xml", "json"):
                cfg["format"] = fmt
            cfg["max_items_per_run"] = int(row.get("max_items_per_run") or 100)
            cfg["is_enabled"] = bool(row.get("is_enabled", True))
            cfg["rules_json"] = row.get("rules_json") or {}
            configs[ch] = cfg
        if not configs:
            return {
                ch: {
                    **cfg,
                    "is_enabled": True,
                    "max_items_per_run": 100,
                    "rules_json": {},
                }
                for ch, cfg in self.CHANNELS.items()
            }
        return configs

    async def get_channel_config(self, org_id: str, channel: str) -> Dict[str, Any]:
        configs = await self._channel_configs(org_id)
        cfg = configs.get(channel, None)
        if cfg is None:
            cfg = {
                **self.CHANNELS[channel],
                "is_enabled": True,
                "max_items_per_run": 100,
                "rules_json": {},
            }
        return {
            "channel": channel,
            "format": cfg["format"],
            "is_enabled": bool(cfg.get("is_enabled", True)),
            "max_items_per_run": int(cfg.get("max_items_per_run", 100)),
            "rules_json": cfg.get("rules_json", {}),
        }

    async def update_channel_config(
        self,
        org_id: str,
        channel: str,
        is_enabled: Optional[bool] = None,
        max_items_per_run: Optional[int] = None,
        rules_json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        current = await self.get_channel_config(org_id, channel)
        payload = {
            "org_id": org_id,
            "channel": channel,
            "format": current["format"],
            "is_enabled": current["is_enabled"] if is_enabled is None else bool(is_enabled),
            "max_items_per_run": current["max_items_per_run"] if max_items_per_run is None else int(max_items_per_run),
            "rules_json": current["rules_json"] if rules_json is None else rules_json,
        }

        if self._table_exists("feed_channel_configs"):
            try:
                neon_service.client.table("feed_channel_configs").upsert(
                    payload,
                    on_conflict="org_id,channel",
                ).execute()
            except Exception:
                pass
        return payload

    def _validate_record(self, record: Dict[str, Any], required_fields: List[str]) -> List[FeedValidationIssue]:
        issues: List[FeedValidationIssue] = []
        for field in required_fields:
            value = record.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                issues.append(
                    FeedValidationIssue(
                        property_id=record["id"],
                        field=field,
                        severity="error",
                        message=f"Campo requerido ausente: {field}",
                    )
                )
        if record.get("price") is not None and float(record["price"]) <= 0:
            issues.append(
                FeedValidationIssue(
                    property_id=record["id"],
                    field="price",
                    severity="error",
                    message="El precio debe ser mayor que 0.",
                )
            )
        if record.get("source_url") in (None, ""):
            issues.append(
                FeedValidationIssue(
                    property_id=record["id"],
                    field="source_url",
                    severity="warning",
                    message="Sin URL de origen; recomendable para trazabilidad.",
                )
            )
        return issues

    async def _latest_runs_map(self, org_id: str) -> Dict[str, datetime]:
        latest: Dict[str, datetime] = {}

        if self._table_exists("feed_runs"):
            try:
                rows = (
                    neon_service.client.table("feed_runs")
                    .select("channel, created_at")
                    .eq("org_id", org_id)
                    .order("created_at", desc=True)
                    .limit(200)
                    .execute()
                ).data or []
                for row in rows:
                    channel = str(row.get("channel") or "")
                    if channel in latest:
                        continue
                    created_at = row.get("created_at")
                    if created_at:
                        try:
                            latest[channel] = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
                        except Exception:
                            continue
                return latest
            except Exception:
                pass

        # Legacy fallback
        if self._table_exists("ingestion_events"):
            try:
                rows = (
                    neon_service.client.table("ingestion_events")
                    .select("connector_name, processed_at")
                    .eq("org_id", org_id)
                    .ilike("connector_name", "feed:%")
                    .order("processed_at", desc=True)
                    .limit(200)
                    .execute()
                ).data or []
            except Exception:
                return latest

            for row in rows:
                connector = str(row.get("connector_name") or "")
                channel = connector.replace("feed:", "", 1)
                if channel in latest:
                    continue
                processed_at = row.get("processed_at")
                if processed_at:
                    try:
                        latest[channel] = datetime.fromisoformat(str(processed_at).replace("Z", "+00:00"))
                    except Exception:
                        continue
        return latest

    async def get_workspace(self, org_id: str) -> FeedWorkspaceResponse:
        properties = await self._list_properties(org_id)
        latest_runs = await self._latest_runs_map(org_id)
        configs = await self._channel_configs(org_id)
        channel_summaries: List[FeedChannelSummary] = []

        scoped = [p for p in properties if p.get("status") in {"new", "contacted", "negotiating", "listed"}]
        for channel, cfg in configs.items():
            if not bool(cfg.get("is_enabled", True)):
                channel_summaries.append(
                    FeedChannelSummary(
                        channel=channel,  # type: ignore[arg-type]
                        format=cfg["format"],
                        is_enabled=False,
                        status="blocked",
                        total_candidates=0,
                        ready_to_publish=0,
                        warnings=0,
                        errors=0,
                        latest_run_at=latest_runs.get(channel),
                    )
                )
                continue
            issues: List[FeedValidationIssue] = []
            ready = 0
            for record in scoped:
                rec_issues = self._validate_record(record, cfg["required_fields"])
                errors = [i for i in rec_issues if i.severity == "error"]
                if not errors:
                    ready += 1
                issues.extend(rec_issues)
            error_count = len([i for i in issues if i.severity == "error"])
            warning_count = len([i for i in issues if i.severity == "warning"])
            status = "healthy" if error_count == 0 else ("warning" if ready > 0 else "blocked")
            channel_summaries.append(
                FeedChannelSummary(
                    channel=channel,  # type: ignore[arg-type]
                    format=cfg["format"],
                    is_enabled=True,
                    status=status,  # type: ignore[arg-type]
                    total_candidates=len(scoped),
                    ready_to_publish=ready,
                    warnings=warning_count,
                    errors=error_count,
                    latest_run_at=latest_runs.get(channel),
                )
            )

        totals = {
            "channels": len(channel_summaries),
            "candidates": sum(c.total_candidates for c in channel_summaries),
            "ready": sum(c.ready_to_publish for c in channel_summaries),
            "errors": sum(c.errors for c in channel_summaries),
            "warnings": sum(c.warnings for c in channel_summaries),
        }
        return FeedWorkspaceResponse(
            generated_at=datetime.now(timezone.utc),
            channels=channel_summaries,
            totals=totals,
        )

    async def validate_channel(self, org_id: str, channel: str, limit_issues: int = 50) -> FeedValidationResponse:
        configs = await self._channel_configs(org_id)
        cfg = configs.get(channel, self.CHANNELS[channel])
        if not bool(cfg.get("is_enabled", True)):
            return FeedValidationResponse(
                channel=channel,  # type: ignore[arg-type]
                generated_at=datetime.now(timezone.utc),
                total_candidates=0,
                ready_to_publish=0,
                warnings=0,
                errors=1,
                issues=[
                    FeedValidationIssue(
                        property_id="00000000-0000-0000-0000-000000000000",
                        field="channel",
                        severity="error",
                        message="Canal desactivado en configuracion.",
                    )
                ],
            )
        properties = await self._list_properties(org_id)
        scoped = [p for p in properties if p.get("status") in {"new", "contacted", "negotiating", "listed"}]

        issues: List[FeedValidationIssue] = []
        ready = 0
        for record in scoped:
            rec_issues = self._validate_record(record, cfg["required_fields"])
            if not [i for i in rec_issues if i.severity == "error"]:
                ready += 1
            issues.extend(rec_issues)

        warnings = len([i for i in issues if i.severity == "warning"])
        errors = len([i for i in issues if i.severity == "error"])
        return FeedValidationResponse(
            channel=channel,  # type: ignore[arg-type]
            generated_at=datetime.now(timezone.utc),
            total_candidates=len(scoped),
            ready_to_publish=ready,
            warnings=warnings,
            errors=errors,
            issues=issues[:limit_issues],
        )

    async def _persist_run(
        self,
        org_id: str,
        channel: str,
        fmt: str,
        dry_run: bool,
        status: str,
        validation: FeedValidationResponse,
        published_count: int,
        rejected_count: int,
        sample_payload: Dict[str, Any],
    ) -> str:
        run_id = str(uuid.uuid4())

        if self._table_exists("feed_runs"):
            try:
                run_row = (
                    neon_service.client.table("feed_runs")
                    .insert(
                        {
                            "org_id": org_id,
                            "channel": channel,
                            "format": fmt,
                            "run_mode": "dry_run" if dry_run else "publish",
                            "status": status,
                            "total_candidates": validation.total_candidates,
                            "ready_to_publish": validation.ready_to_publish,
                            "published_count": published_count,
                            "rejected_count": rejected_count,
                            "warning_count": validation.warnings,
                            "error_count": validation.errors,
                            "sample_payload": sample_payload,
                            "notes": "Run generated from feed orchestrator API",
                        }
                    )
                    .execute()
                ).data or []
                if run_row and run_row[0].get("id"):
                    run_id = str(run_row[0]["id"])
            except Exception:
                pass

        if self._table_exists("feed_validation_issues") and validation.issues:
            try:
                payload = []
                for issue in validation.issues:
                    entity_uuid: Optional[str] = None
                    try:
                        entity_uuid = str(uuid.UUID(issue.property_id))
                    except Exception:
                        entity_uuid = None
                    payload.append(
                        {
                            "org_id": org_id,
                            "run_id": run_id,
                            "channel": channel,
                            "entity_type": "property",
                            "entity_id": entity_uuid,
                            "field_name": issue.field,
                            "severity": issue.severity,
                            "message": issue.message,
                            "metadata_json": {},
                        }
                    )
                if payload:
                    neon_service.client.table("feed_validation_issues").insert(payload).execute()
            except Exception:
                pass

        # Legacy fallback logging
        if self._table_exists("ingestion_events"):
            try:
                neon_service.client.table("ingestion_events").insert(
                    {
                        "org_id": org_id,
                        "entity_type": "property",
                        "external_id": run_id,
                        "connector_name": f"feed:{channel}",
                        "status": "success" if status != "failed" else "error",
                        "message": f"Feed run {status}",
                        "payload": {
                            "run_id": run_id,
                            "channel": channel,
                            "dry_run": dry_run,
                            "published_count": published_count,
                            "rejected_count": rejected_count,
                            "error_count": validation.errors,
                            "warning_count": validation.warnings,
                        },
                        "dedupe_key": f"feed:{channel}:{run_id}",
                        "processed_at": datetime.now(timezone.utc).isoformat(),
                    }
                ).execute()
            except Exception:
                pass
        return run_id

    async def publish_channel(
        self,
        org_id: str,
        channel: str,
        dry_run: bool,
        max_items: int,
    ) -> FeedPublishResponse:
        configs = await self._channel_configs(org_id)
        cfg = configs.get(channel, self.CHANNELS[channel])
        channel_limit = int(cfg.get("max_items_per_run", 100))
        effective_limit = min(max_items, channel_limit)

        validation = await self.validate_channel(org_id, channel, limit_issues=200)
        if not bool(cfg.get("is_enabled", True)):
            raise ValueError("Canal desactivado en configuracion. Activalo antes de publicar.")
        publishable = max(0, min(validation.ready_to_publish, effective_limit))
        rejected = max(0, min(validation.total_candidates, effective_limit) - publishable)
        status = "success" if validation.errors == 0 else ("partial" if publishable > 0 else "failed")
        published_count = 0 if dry_run else publishable

        sample_payload = {
            "channel": channel,
            "format": cfg["format"],
            "properties_exported": published_count,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "max_items_per_run": channel_limit,
            "effective_limit": effective_limit,
        }

        run_id = await self._persist_run(
            org_id=org_id,
            channel=channel,
            fmt=cfg["format"],
            dry_run=dry_run,
            status=status,
            validation=validation,
            published_count=published_count,
            rejected_count=rejected,
            sample_payload=sample_payload,
        )

        return FeedPublishResponse(
            run_id=run_id,
            channel=channel,  # type: ignore[arg-type]
            dry_run=dry_run,
            status=status,  # type: ignore[arg-type]
            published_count=published_count,
            rejected_count=rejected,
            error_count=validation.errors,
            generated_at=datetime.now(timezone.utc),
            sample_payload=sample_payload,
            issues=validation.issues[:30],
        )

    async def list_runs(self, org_id: str, limit: int = 20, channel: Optional[str] = None) -> Tuple[List[FeedRunItem], int]:
        # Preferred persistence table
        if self._table_exists("feed_runs"):
            query = (
                neon_service.client.table("feed_runs")
                .select("id, channel, status, run_mode, published_count, rejected_count, created_at", count="exact")
                .eq("org_id", org_id)
                .order("created_at", desc=True)
                .limit(limit)
            )
            if channel:
                query = query.eq("channel", channel)
            try:
                resp = query.execute()
                rows = resp.data or []
                items: List[FeedRunItem] = []
                for row in rows:
                    created = row.get("created_at")
                    try:
                        generated = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
                    except Exception:
                        generated = datetime.now(timezone.utc)
                    items.append(
                        FeedRunItem(
                            run_id=str(row.get("id")),
                            channel=str(row.get("channel")),  # type: ignore[arg-type]
                            status=str(row.get("status") or "unknown"),
                            dry_run=str(row.get("run_mode") or "") == "dry_run",
                            published_count=int(row.get("published_count") or 0),
                            rejected_count=int(row.get("rejected_count") or 0),
                            generated_at=generated,
                        )
                    )
                return items, int(resp.count or len(items))
            except Exception:
                pass

        # Legacy fallback
        if not self._table_exists("ingestion_events"):
            return [], 0
        query = (
            neon_service.client.table("ingestion_events")
            .select("external_id, connector_name, status, payload, processed_at", count="exact")
            .eq("org_id", org_id)
            .ilike("connector_name", "feed:%")
            .order("processed_at", desc=True)
            .limit(limit)
        )
        if channel:
            query = query.eq("connector_name", f"feed:{channel}")
        try:
            resp = query.execute()
            rows = resp.data or []
        except Exception:
            return [], 0

        items: List[FeedRunItem] = []
        for row in rows:
            payload = row.get("payload") or {}
            connector = str(row.get("connector_name") or "")
            ch = connector.replace("feed:", "", 1)
            processed_raw = row.get("processed_at")
            try:
                generated = datetime.fromisoformat(str(processed_raw).replace("Z", "+00:00"))
            except Exception:
                generated = datetime.now(timezone.utc)
            items.append(
                FeedRunItem(
                    run_id=str(row.get("external_id") or uuid.uuid4()),
                    channel=ch,  # type: ignore[arg-type]
                    status=str(row.get("status") or "unknown"),
                    dry_run=bool(payload.get("dry_run", False)),
                    published_count=int(payload.get("published_count", 0)),
                    rejected_count=int(payload.get("rejected_count", 0)),
                    generated_at=generated,
                )
            )
        return items, int(resp.count or len(items))


feed_orchestrator_service = FeedOrchestratorService()
