import os
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from route_helpers import flatten_routes

os.environ.setdefault("AI_RUNTIME_PROFILE", "groq-cloudflare")
os.environ.setdefault("GROQ_API_KEY", "groq-test")
os.environ.setdefault("CLOUDFLARE_ACCOUNT_ID", "cf-account-test")
os.environ.setdefault("CLOUDFLARE_API_TOKEN", "cf-token-test")
os.environ.setdefault("INTERNAL_AUDIT_SECRET", "test-secret")

from backend.api.routes.sellers import router
from backend.api.deps import check_budget_hard_stop, get_org_id


ORG_ID = "org-test-1"


async def mock_check_budget_hard_stop():
    class BudgetStatus:
        status = "ok"
    return BudgetStatus()


app = FastAPI()
app.include_router(router, prefix="/api/sellers")
app.dependency_overrides[check_budget_hard_stop] = mock_check_budget_hard_stop
app.dependency_overrides[get_org_id] = lambda: ORG_ID
client = TestClient(app)


class TestSellersRouteRegistration:
    def test_workbench_endpoint_exists(self) -> None:
        routes = flatten_routes(app.routes)
        matching = [
            r for r in routes
            if hasattr(r, "path") and r.path == "/api/sellers/{seller_id}/workbench" and "GET" in r.methods
        ]
        assert len(matching) == 1

    def test_dossier_export_endpoint_exists(self) -> None:
        routes = flatten_routes(app.routes)
        matching = [
            r for r in routes
            if hasattr(r, "path") and r.path == "/api/sellers/{seller_id}/dossier-export" and "GET" in r.methods
        ]
        assert len(matching) == 1

    def test_supervised_send_endpoint_exists(self) -> None:
        routes = flatten_routes(app.routes)
        matching = [
            r for r in routes
            if hasattr(r, "path") and r.path == "/api/sellers/{seller_id}/send-supervised/{channel}" and "POST" in r.methods
        ]
        assert len(matching) == 1

    def test_memory_routes_exist(self) -> None:
        routes = flatten_routes(app.routes)
        get_matches = [
            r for r in routes
            if hasattr(r, "path") and r.path == "/api/sellers/{seller_id}/memory" and "GET" in r.methods
        ]
        post_matches = [
            r for r in routes
            if hasattr(r, "path") and r.path == "/api/sellers/{seller_id}/memory/rebuild" and "POST" in r.methods
        ]
        assert len(get_matches) == 1
        assert len(post_matches) == 1


class TestSellersRouteContracts:
    @patch("backend.api.routes.sellers.sellers_service")
    def test_patch_seller_updates_contact_channels(self, mock_service: MagicMock) -> None:
        seller_id = str(uuid4())
        mock_service.update_seller = AsyncMock(return_value={
            "id": seller_id,
            "email_contacto": "owner@example.com",
            "telefono_contacto": "+34600111222",
            "whatsapp_contacto": "+34600111222",
        })

        response = client.patch(
            f"/api/sellers/{seller_id}",
            json={
                "email_contacto": "owner@example.com",
                "telefono_contacto": "+34600111222",
                "whatsapp_contacto": "+34600111222",
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["email_contacto"] == "owner@example.com"
        assert mock_service.update_seller.await_args.kwargs["org_id"] == ORG_ID

    @patch("backend.api.routes.sellers.sellers_service")
    def test_workbench_returns_payload(self, mock_service: MagicMock) -> None:
        seller_id = str(uuid4())
        mock_service.get_seller_workbench = AsyncMock(return_value={
            "seller": {"id": seller_id, "nombre_propietario": "Toni", "prioridad": 5},
            "interactions": [],
            "latest_artifacts": {
                "dossier": None,
                "email_draft": None,
                "whatsapp_draft": None,
                "call_brief": None,
                "context_brief": None,
            },
            "snapshot": {
                "has_argumentario": False,
                "has_email_draft": False,
                "has_whatsapp_draft": False,
                "has_call_brief": False,
                "has_context_brief": False,
                "interactions_count": 0,
                "semantic_memory_count": 1,
                "semantic_memory_ready": True,
                "recommended_channel": "whatsapp",
                "readiness": "ready_to_send",
            },
            "memory": {
                "version": "ANCLORA-SMSR-001.v1_1",
                "seller_id": seller_id,
                "status": "ready",
                "query": "seguimiento",
                "total_records": 1,
                "matches": [],
                "retrieval_summary": "nota",
            },
            "console": {
                "readiness": "ready_to_send",
                "recommended_channel": "whatsapp",
                "next_action": "Open the first WhatsApp touchpoint",
                "reasons": ["Seller is still cold."],
                "last_touch_at": None,
                "memory_focus_terms": ["seguimiento"],
                "memory_highlights": [{"summary": "nota", "score": 82}],
            },
        })

        response = client.get(f"/api/sellers/{seller_id}/workbench")

        assert response.status_code == 200
        body = response.json()
        assert body["seller"]["id"] == seller_id
        assert body["snapshot"]["interactions_count"] == 0
        assert body["snapshot"]["semantic_memory_ready"] is True
        assert body["console"]["recommended_channel"] == "whatsapp"
        assert mock_service.get_seller_workbench.await_args.kwargs["org_id"] == ORG_ID

    @patch("backend.api.routes.sellers.run_whale_dossier", new_callable=AsyncMock)
    def test_generate_dossier_returns_multichannel_artifacts(self, mock_skill: AsyncMock) -> None:
        seller_id = str(uuid4())
        mock_skill.return_value = {
            "seller_id": seller_id,
            "argumentario": "Dossier text",
            "email_subject": "Subject",
            "email_body": "Email body",
            "whatsapp_body": "WhatsApp body",
            "call_brief": "Call brief body",
            "context_brief": "Context brief body",
            "zona_insight_used": True,
            "processed_at": "2026-03-09T00:00:00+00:00",
        }

        response = client.post(f"/api/sellers/{seller_id}/generate-dossier")

        assert response.status_code == 200
        body = response.json()
        assert body["whatsapp_body"] == "WhatsApp body"
        assert body["call_brief"] == "Call brief body"
        assert body["context_brief"] == "Context brief body"

    @patch("backend.api.routes.sellers.sellers_service")
    def test_dossier_export_returns_payload(self, mock_service: MagicMock) -> None:
        seller_id = str(uuid4())
        mock_service.build_seller_dossier_export = AsyncMock(return_value={
            "seller": {"id": seller_id, "nombre_propietario": "Toni"},
            "generated_at": "2026-03-09T00:00:00+00:00",
            "file_name": "dossier-toni.pdf",
            "sections": {
                "context_brief": "Context",
                "call_brief": "Call",
                "dossier": "Dossier",
                "email_subject": "Subject",
                "email_body": "Body",
                "whatsapp_body": "WhatsApp",
            },
            "share_summary": "share text",
        })

        response = client.get(f"/api/sellers/{seller_id}/dossier-export")

        assert response.status_code == 200
        body = response.json()
        assert body["file_name"] == "dossier-toni.pdf"
        assert body["sections"]["dossier"] == "Dossier"

    @patch("backend.api.routes.sellers.sellers_service")
    def test_supervised_send_returns_launch_payload(self, mock_service: MagicMock) -> None:
        seller_id = str(uuid4())
        mock_service.build_supervised_send_payload = AsyncMock(return_value={
            "channel": "email",
            "seller_id": seller_id,
            "interaction_id": str(uuid4()),
            "target": "owner@example.com",
            "subject": "Subject",
            "body": "Body",
            "launch_url": "mailto:owner@example.com?subject=Subject&body=Body",
            "status": "ready_for_human_send",
        })

        response = client.post(f"/api/sellers/{seller_id}/send-supervised/email")

        assert response.status_code == 200
        body = response.json()
        assert body["channel"] == "email"
        assert body["target"] == "owner@example.com"

    @patch("backend.api.routes.sellers.sellers_service")
    def test_supervised_send_supports_native_email_transport(self, mock_service: MagicMock) -> None:
        seller_id = str(uuid4())
        mock_service.build_supervised_send_payload = AsyncMock(return_value={
            "channel": "email",
            "seller_id": seller_id,
            "interaction_id": str(uuid4()),
            "target": "owner@example.com",
            "subject": "Subject",
            "body": "Body",
            "launch_url": None,
            "status": "sent_natively",
            "transport": "native_email",
            "delivery": {"provider": "smtp", "message_id": "<id@test>"},
        })

        response = client.post(
            f"/api/sellers/{seller_id}/send-supervised/email",
            json={"transport": "native_email"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "sent_natively"
        assert body["transport"] == "native_email"

    @patch("backend.api.routes.sellers.sellers_service")
    def test_confirm_supervised_send_returns_updated_interaction(self, mock_service: MagicMock) -> None:
        seller_id = str(uuid4())
        interaction_id = str(uuid4())
        mock_service.confirm_supervised_send = AsyncMock(return_value={
            "id": interaction_id,
            "seller_id": seller_id,
            "estado": "realizado",
            "resultado": "sent_confirmed_human",
            "metadata": {"confirmed_at": "2026-03-10T00:00:00Z"},
        })

        response = client.post(f"/api/sellers/{seller_id}/interactions/{interaction_id}/confirm-send")

        assert response.status_code == 200
        body = response.json()
        assert body["estado"] == "realizado"
        assert body["resultado"] == "sent_confirmed_human"

    @patch("backend.api.routes.sellers.seller_memory_service")
    def test_get_memory_returns_semantic_matches(self, mock_memory: MagicMock) -> None:
        seller_id = str(uuid4())
        mock_memory.search = AsyncMock(return_value=type("MemoryResponse", (), {
            "model_dump": lambda self: {
                "version": "ANCLORA-SMSR-001.v1_1",
                "seller_id": seller_id,
                "status": "ready",
                "query": "objeciones",
                "total_records": 2,
                "matches": [],
                "retrieval_summary": "followup",
            }
        })())

        response = client.get(f"/api/sellers/{seller_id}/memory?query=objeciones")

        assert response.status_code == 200
        assert response.json()["status"] == "ready"

    @patch("backend.api.routes.sellers.seller_memory_service")
    def test_rebuild_memory_returns_sync_counts(self, mock_memory: MagicMock) -> None:
        seller_id = str(uuid4())
        mock_memory.rebuild_for_seller = AsyncMock(return_value=type("RebuildResponse", (), {
            "model_dump": lambda self: {
                "version": "ANCLORA-SMSR-001.v1_1",
                "seller_id": seller_id,
                "status": "ready",
                "indexed_records": 4,
                "created_records": 2,
            }
        })())

        response = client.post(f"/api/sellers/{seller_id}/memory/rebuild")

        assert response.status_code == 200
        assert response.json()["created_records"] == 2
