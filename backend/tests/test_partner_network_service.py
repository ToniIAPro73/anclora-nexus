import asyncio

from backend.models.partner_network import PartnerNetworkUpdate, PartnerSharedOpportunityCreate
from backend.services.partner_network_service import PartnerNetworkService


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


def test_list_partner_network_aggregates_buyers(monkeypatch) -> None:
    service = PartnerNetworkService()
    store = {
        "partner_admissions": [
            {
                "id": "adm-1",
                "org_id": "org-1",
                "status": "accepted",
                "full_name": "Agent eXp Mallorca",
                "company_name": "Agent eXp Mallorca",
                "service_category": "real_estate",
                "coverage_areas": ["mallorca"],
                "languages": ["es", "en"],
                "sustainability_focus": True,
            }
        ],
        "synergi_partner_workspaces": [
            {
                "id": "ws-1",
                "org_id": "org-1",
                "admission_id": "adm-1",
                "access_token": "token-1",
                "partner_tier": "preferred",
                "relationship_status": "active",
                "trust_score": 88,
                "network_tags": ["exp", "buyers"],
                "preferred_for_buyers": True,
            }
        ],
        "synergi_partner_opportunities": [
            {"id": "opp-1", "org_id": "org-1", "workspace_id": "ws-1"},
        ],
        "synergi_partner_shared_opportunities": [
            {"id": "shared-1", "org_id": "org-1", "workspace_id": "ws-1"},
        ],
        "buyer_profiles": [
            {
                "id": "b-1",
                "org_id": "org-1",
                "source_type": "partner_referral",
                "referral_partner_name": "Agent eXp Mallorca",
                "motivation_score": 91,
                "created_at": "2026-03-12T10:00:00+00:00",
            }
        ],
    }
    monkeypatch.setattr("backend.services.partner_network_service.neon_service.client", _MockClient(store))
    monkeypatch.setattr(
        "backend.services.partner_network_service.partner_workspace_service._build_launch_url",
        lambda token: f"https://anclora.local/private-area/partner/workspace?token={token}",
    )

    result = asyncio.run(service.list_network(org_id="org-1"))

    assert result["total"] == 1
    assert result["items"][0]["buyer_referrals_count"] == 1
    assert result["items"][0]["high_intent_buyers_count"] == 1
    assert result["items"][0]["workspace_launch_url"].endswith("token-1")
    assert result["items"][0]["shared_opportunities_count"] == 1
    assert result["items"][0]["preferred_opportunity_types"] == []
    assert result["items"][0]["shared_pending_count"] == 1
    assert result["items"][0]["engagement_score"] > 0


def test_update_partner_network(monkeypatch) -> None:
    service = PartnerNetworkService()
    store = {
        "synergi_partner_workspaces": [
            {"id": "ws-1", "org_id": "org-1", "partner_tier": "approved", "relationship_status": "active", "trust_score": 70}
        ]
    }
    monkeypatch.setattr("backend.services.partner_network_service.neon_service.client", _MockClient(store))

    result = asyncio.run(
        service.update_network_partner(
            "org-1",
            "ws-1",
            PartnerNetworkUpdate(
                partner_tier="strategic",
                relationship_status="watchlist",
                trust_score=92,
                network_tags=["eco", "exp"],
            ),
        )
    )

    assert result is not None
    assert result["partner_tier"] == "strategic"
    assert result["relationship_status"] == "watchlist"
    assert result["trust_score"] == 92


def test_share_opportunity_with_partner(monkeypatch) -> None:
    service = PartnerNetworkService()
    store = {
        "synergi_partner_workspaces": [
            {"id": "ws-1", "org_id": "org-1", "partner_tier": "approved"}
        ],
        "synergi_partner_shared_opportunities": [],
        "synergi_partner_activity": [],
    }
    monkeypatch.setattr("backend.services.partner_network_service.neon_service.client", _MockClient(store))

    result = asyncio.run(
        service.share_opportunity_with_partner(
            org_id="org-1",
            workspace_id="ws-1",
            created_by_user_id="user-1",
            payload=PartnerSharedOpportunityCreate(
                title="Buyer opportunity",
                summary="Buyer internacional interesado en villa prime en la costa sudoeste.",
                opportunity_type="buyer_opportunity",
                target_zone="andratx",
            ),
        )
    )

    assert result is not None
    assert result["status"] == "shared"
    assert store["synergi_partner_activity"][0]["event_type"] == "shared_opportunity_created"


def test_list_partner_network_filters_by_preference_and_response(monkeypatch) -> None:
    service = PartnerNetworkService()
    store = {
        "partner_admissions": [
            {
                "id": "adm-1",
                "org_id": "org-1",
                "status": "accepted",
                "full_name": "Eco Partner",
                "company_name": "Eco Partner",
                "service_category": "eco",
                "coverage_areas": ["tramuntana"],
                "languages": ["es"],
            }
        ],
        "synergi_partner_workspaces": [
            {
                "id": "ws-1",
                "org_id": "org-1",
                "admission_id": "adm-1",
                "access_token": "token-1",
                "partner_tier": "preferred",
                "relationship_status": "active",
                "trust_score": 80,
                "preferred_opportunity_types": ["service_request"],
                "priority_zones": ["tramuntana"],
                "contact_preferences": ["email", "whatsapp"],
                "response_commitment_hours": 24,
            }
        ],
        "synergi_partner_opportunities": [],
        "synergi_partner_shared_opportunities": [
            {"id": "shared-1", "org_id": "org-1", "workspace_id": "ws-1", "status": "interested", "updated_at": "2026-03-12T10:00:00+00:00"},
        ],
        "buyer_profiles": [],
    }
    monkeypatch.setattr("backend.services.partner_network_service.neon_service.client", _MockClient(store))
    monkeypatch.setattr(
        "backend.services.partner_network_service.partner_workspace_service._build_launch_url",
        lambda token: f"https://anclora.local/private-area/partner/workspace?token={token}",
    )

    result = asyncio.run(
        service.list_network(
            org_id="org-1",
            preferred_opportunity_type="service_request",
            response_status="interested",
        )
    )

    assert result["total"] == 1
    assert result["items"][0]["recommended_opportunity_type"] == "service_request"
    assert result["items"][0]["recommended_zone"] == "tramuntana"
    assert result["items"][0]["shared_interested_count"] == 1
    assert result["items"][0]["response_rate"] == 100.0
