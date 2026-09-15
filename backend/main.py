from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from backend.services.supabase_service import supabase_service
from backend.api.routes import router as api_router
from backend.api.routes.memberships import router as memberships_router
from backend.api.routes.prospection import router as prospection_router
from backend.api.routes.finops import router as finops_router
from backend.api.routes.ingestion import router as ingestion_router
from backend.api.routes.dq import router as dq_router
from backend.api.routes.feeds import router as feeds_router
from backend.api.routes.editability import router as editability_router
from backend.api.routes.automation import router as automation_router
from backend.api.routes.command_center import router as command_center_router
from backend.api.routes.deal_margin import router as deal_margin_router
from backend.api.routes.source_observatory import router as source_observatory_router
from backend.api.routes.sellers import router as sellers_router
from backend.api.routes.access_requests import router as access_requests_router
from backend.api.routes.dms import router as dms_router
from backend.api.routes.dms_templates import router as dms_templates_router
from backend.api.routes.dms_generated import router as dms_generated_router
from backend.api.routes.dms_legal_review import router as dms_legal_review_router
from backend.api.routes.dms_versions import router as dms_versions_router
from backend.api.routes.dms_retention import router as dms_retention_router
from backend.api.internal_webhooks import router as internal_webhooks_router
from backend.api.routes.syncxml_pilot import router as syncxml_pilot_router

app = FastAPI(title="Anclora Nexus API", version="0.1.0")

import os as _os

_CORS_ORIGINS = [
    o.strip()
    for o in _os.environ.get(
        "CORS_ALLOWED_ORIGINS",
        "https://nexus.anclora.com,https://private-estates-landing.anclora.com,https://private-estates.anclora.com,https://anclora-nexus-frontend.vercel.app,http://localhost:3000",
    ).split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type", "X-Org-Id"],
)

# Register Routes
app.include_router(api_router, prefix="/api", tags=["Nexus API"])
app.include_router(memberships_router, prefix="/api", tags=["Memberships"])
app.include_router(prospection_router, prefix="/api/prospection", tags=["Prospection"])
app.include_router(finops_router, prefix="/api/finops", tags=["FinOps"])
app.include_router(ingestion_router, prefix="/api", tags=["Ingestion"])
app.include_router(dq_router, prefix="/api/dq", tags=["Data Quality"])
app.include_router(feeds_router, prefix="/api/feeds", tags=["Feeds"])
app.include_router(editability_router, prefix="/api", tags=["Editability"])
app.include_router(automation_router, prefix="/api/automation", tags=["Automation"])
app.include_router(command_center_router, prefix="/api/command-center", tags=["Command Center"])
app.include_router(deal_margin_router, prefix="/api/deal-margin", tags=["Deal Margin"])
app.include_router(source_observatory_router, prefix="/api/source-observatory", tags=["Source Observatory"])
app.include_router(sellers_router, prefix="/api/sellers", tags=["Sellers"])
app.include_router(access_requests_router, prefix="/api/access-requests", tags=["Access Requests"])
app.include_router(dms_router, prefix="/api/dms", tags=["DMS"])
app.include_router(dms_templates_router, prefix="/api/dms/templates", tags=["DMS Templates"])
app.include_router(dms_generated_router, prefix="/api/dms", tags=["DMS Generated"])
app.include_router(dms_legal_review_router, prefix="/api/dms", tags=["DMS Legal Review"])
app.include_router(dms_versions_router, prefix="/api/dms", tags=["DMS Versions"])
app.include_router(dms_retention_router, prefix="/api/dms/retention", tags=["DMS Retention"])
app.include_router(internal_webhooks_router)
# GuestHub pilot manual decision routes (legacy path prefix kept after the
# SyncXML → GuestHub rename, 2026-08 — consumed by the Nexus frontend).
app.include_router(syncxml_pilot_router, prefix="/api/syncxml-pilot", tags=["GuestHub Pilot"])
from backend.api.routes.public import router as public_router
app.include_router(public_router, prefix="/api/public", tags=["Public"])

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "0.1.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
