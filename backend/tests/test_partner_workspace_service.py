import asyncio

from backend.models.partner_workspaces import (
    PublicPartnerOpportunityCreate,
    PublicPartnerWorkspaceProfileUpdate,
    PublicSharedOpportunityStatusUpdate,
)
from backend.services.partner_workspace_service import PartnerWorkspaceService


class _MockQuery:
    def __init__(self, table_name: str, store: dict[str, list[dict]]) -> None:
        self.table_name = table_name
        self.store = store
        self.rows = list(store.get(table_name, []))
        self.payload = None

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, key, value):
        self.rows = [row for row in self.rows if row.get(key) == value]
        return self

    def order(self, key, desc=False):
        self.rows = sorted(self.rows, key=lambda row: row.get(key) or "", reverse=desc)
        return self

    def limit(self, value):
        self.rows = self.rows[:value]
        return self

    def insert(self, payload):
        row = dict(payload)
        row.setdefault("id", f"{self.table_name}-{len(self.store.get(self.table_name, [])) + 1}")
        self.store.setdefault(self.table_name, []).append(row)
        self.rows = [row]
        return self

    def update(self, payload):
        self.payload = payload
        return self

    def execute(self):
        if self.payload is not None:
            for row in self.store.get(self.table_name, []):
                if row in self.rows:
                    row.update(self.payload)
            return type("Resp", (), {"data": self.rows, "count": len(self.rows)})()
        return type("Resp", (), {"data": self.rows, "count": len(self.rows)})()


class _MockClient:
    def __init__(self, store: dict[str, list[dict]]) -> None:
        self.store = store

    def table(self, table_name: str):
        return _MockQuery(table_name, self.store)


def test_ensure_workspace_for_accepted_admission(monkeypatch) -> None:
    service = PartnerWorkspaceService()
    store = {"partner_admissions": [], "synergi_partner_activity": []}
    monkeypatch.setattr("backend.services.partner_workspace_service.neon_service.client", _MockClient(store))
    monkeypatch.setattr("backend.services.partner_workspace_service.secrets.token_urlsafe", lambda _n: "token-123")
    monkeypatch.setattr("backend.services.partner_workspace_service.settings.APP_BASE_URL", "https://anclora.example")

    result = asyncio.run(
        service.ensure_workspace_for_accepted_admission(
            "org-1",
            {
                "id": "adm-1",
                "company_name": "Eco Partner",
                "service_category": "eco",
                "service_summary": "Servicios eco premium.",
                "coverage_areas": ["mallorca"],
            },
        )
    )

    assert result["access_token"] == "token-123"
    assert result["launch_url"] == "https://anclora.example/private-area/partner/workspace?token=token-123"
    assert store["synergi_partner_workspaces"][0]["workspace_status"] == "invited"


def test_get_workspace_by_token_returns_opportunities(monkeypatch) -> None:
    service = PartnerWorkspaceService()
    store = {
        "partner_admissions": [
            {
                "id": "adm-1",
                "org_id": "org-1",
                "full_name": "Partner Test",
                "company_name": "Partner Co",
                "service_category": "real_estate",
                "service_summary": "Referrals y coinversion.",
                "coverage_areas": ["mallorca"],
                "languages": ["es", "en"],
                "sustainability_focus": True,
                "sustainability_notes": "Domotica y eficiencia.",
            }
        ],
        "synergi_partner_workspaces": [
            {
                "id": "ws-1",
                "org_id": "org-1",
                "admission_id": "adm-1",
                "access_token": "token-123",
                "workspace_status": "invited",
                "partner_tier": "approved",
                "headline": "Partner Co · Synergi approved partner",
                "collaboration_focus": ["buyers", "co-brokerage"],
                "next_steps": ["Paso 1"],
                "resources": [{"label": "Guía", "description": "Contexto"}],
            }
        ],
        "synergi_partner_opportunities": [
            {
                "id": "opp-1",
                "workspace_id": "ws-1",
                "title": "Buyer referral prime",
                "opportunity_type": "buyer_referral",
                "summary": "Buyer high-ticket para Palma.",
                "status": "submitted",
                "created_at": "2026-03-12T00:00:00+00:00",
            }
        ],
        "synergi_partner_activity": [],
        "synergi_partner_shared_opportunities": [],
    }
    monkeypatch.setattr("backend.services.partner_workspace_service.neon_service.client", _MockClient(store))

    result = asyncio.run(service.get_workspace_by_token("token-123"))

    assert result is not None
    assert result["partner_name"] == "Partner Test"
    assert result["workspace_status"] == "active"
    assert len(result["opportunities"]) == 1
    assert len(result["anclora_priorities"]) >= 1


def test_create_opportunity_from_token(monkeypatch) -> None:
    service = PartnerWorkspaceService()
    store = {
        "synergi_partner_workspaces": [
                {
                    "id": "ws-1",
                    "org_id": "org-1",
                    "admission_id": "adm-1",
                    "access_token": "token-123456789012",
                }
            ],
        "synergi_partner_activity": [],
        "synergi_partner_shared_opportunities": [],
        }
    monkeypatch.setattr("backend.services.partner_workspace_service.neon_service.client", _MockClient(store))

    result = asyncio.run(
        service.create_opportunity_from_token(
                PublicPartnerOpportunityCreate(
                token="token-123456789012",
                title="Servicio de interiorismo",
                opportunity_type="service_offer",
                summary="Podemos apoyar reposicionamiento de villas premium con interiorismo.",
                target_zone="tramuntana",
            )
        )
    )

    assert result is not None
    assert result["workspace_id"] == "ws-1"
    assert store["synergi_partner_opportunities"][0]["opportunity_type"] == "service_offer"
    assert store["synergi_partner_activity"][0]["event_type"] == "opportunity_submitted"


def test_update_profile_from_token(monkeypatch) -> None:
    service = PartnerWorkspaceService()
    store = {
        "synergi_partner_workspaces": [
            {
                "id": "ws-1",
                "org_id": "org-1",
                "admission_id": "adm-1",
                "access_token": "token-123456789012",
            }
        ],
        "synergi_partner_activity": [],
        "synergi_partner_shared_opportunities": [],
    }
    monkeypatch.setattr("backend.services.partner_workspace_service.neon_service.client", _MockClient(store))

    result = asyncio.run(
        service.update_profile_from_token(
            PublicPartnerWorkspaceProfileUpdate(
                token="token-123456789012",
                preferred_opportunity_types=["buyer_referral", "service_offer"],
                priority_zones=["mallorca", "tramuntana"],
                contact_preferences=["email", "whatsapp"],
                response_commitment_hours=24,
                profile_notes="Priorizamos referrals de buyers internacionales.",
            )
        )
    )

    assert result is not None
    assert result["response_commitment_hours"] == 24
    assert "buyer_referral" in result["preferred_opportunity_types"]
    assert store["synergi_partner_activity"][0]["event_type"] == "profile_updated"


def test_update_shared_opportunity_status(monkeypatch) -> None:
    service = PartnerWorkspaceService()
    store = {
        "synergi_partner_workspaces": [
            {
                "id": "ws-1",
                "org_id": "org-1",
                "admission_id": "adm-1",
                "access_token": "token-123456789012",
            }
        ],
        "synergi_partner_shared_opportunities": [
            {
                "id": "shared-1",
                "workspace_id": "ws-1",
                "title": "Buyer opportunity",
                "status": "shared",
            }
        ],
        "synergi_partner_activity": [],
    }
    monkeypatch.setattr("backend.services.partner_workspace_service.neon_service.client", _MockClient(store))

    result = asyncio.run(
        service.update_shared_opportunity_status_from_token(
            "shared-1",
            PublicSharedOpportunityStatusUpdate(token="token-123456789012", status="interested"),
        )
    )

    assert result is not None
    assert result["status"] == "interested"
    assert store["synergi_partner_activity"][0]["event_type"] == "shared_opportunity_status_updated"
