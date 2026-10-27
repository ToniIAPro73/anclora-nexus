import asyncio

from backend.models.prospection import BuyerCreate
from backend.services.prospection_service import ProspectionService


class _MockQuery:
    def __init__(self, table_name: str, store: dict[str, list[dict]]) -> None:
        self.table_name = table_name
        self.store = store
        self.rows = list(store.get(table_name, []))

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, key, value):
        self.rows = [row for row in self.rows if row.get(key) == value]
        return self

    def in_(self, key, values):
        value_set = {str(value) for value in values}
        self.rows = [row for row in self.rows if str(row.get(key)) in value_set]
        return self

    def order(self, key, desc=False):
        self.rows = sorted(self.rows, key=lambda row: row.get(key) or "", reverse=desc)
        return self

    def range(self, start, end):
        self.rows = self.rows[start:end + 1]
        return self

    def limit(self, value):
        self.rows = self.rows[:value]
        return self

    def insert(self, payload):
        rows = payload if isinstance(payload, list) else [payload]
        self.store.setdefault(self.table_name, []).extend(rows)
        self.rows = rows
        return self

    def execute(self):
        return type("Resp", (), {"data": self.rows, "count": len(self.rows)})()


class _MockClient:
    def __init__(self, store: dict[str, list[dict]]) -> None:
        self.store = store

    def table(self, table_name: str):
        return _MockQuery(table_name, self.store)


def test_create_buyer_computes_referral_scores(monkeypatch) -> None:
    service = ProspectionService()
    store = {"buyer_profiles": []}
    mock_client = _MockClient(store)
    monkeypatch.setattr("backend.services.prospection_service.neon_service.client", mock_client)

    buyer = asyncio.run(
        service.create_buyer(
            "org-1",
            BuyerCreate(
                full_name="Buyer Referral",
                budget_min=1500000,
                budget_max=3500000,
                preferred_zones=["andratx", "deia"],
                purchase_horizon="0_3m",
                source_type="partner_referral",
                source_platform="exp_agent",
                referral_partner_name="Agent eXp Mallorca",
            ),
        )
    )

    assert buyer["source_type"] == "partner_referral"
    assert float(buyer["trust_score"]) >= 90
    assert float(buyer["intent_score"]) >= 80
    assert float(buyer["motivation_score"]) >= 80


def test_workspace_returns_buyer_source_summary(monkeypatch) -> None:
    service = ProspectionService()
    store = {
        "properties": [],
        "buyer_profiles": [
            {"id": "b1", "org_id": "org-1", "status": "active", "source_type": "partner_referral", "source_platform": "exp_agent", "motivation_score": 91},
            {"id": "b2", "org_id": "org-1", "status": "active", "source_type": "crm_reactivation", "source_platform": "crm", "motivation_score": 65},
            {"id": "b3", "org_id": "org-1", "status": "active", "source_type": "web_inbound", "source_platform": "web", "motivation_score": 72},
        ],
        "property_buyer_matches": [],
    }
    mock_client = _MockClient(store)
    monkeypatch.setattr("backend.services.prospection_service.neon_service.client", mock_client)

    workspace = asyncio.run(service.get_workspace(org_id="org-1", role="owner", user_id=None))

    assert workspace["buyer_source_summary"]["partner_referrals"] == 1
    assert workspace["buyer_source_summary"]["crm_reactivation"] == 1
    assert workspace["buyer_source_summary"]["web_inbound"] == 1
