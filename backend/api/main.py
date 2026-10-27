"""
Anclora Intelligence API v1
FastAPI application for Intelligence orchestrator
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone

# Create FastAPI app
app = FastAPI(
    title="Anclora Intelligence API",
    description="Strategic Intelligence orchestrator for Anclora Real Estate",
    version="1.0.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    # Dev mode: permissive CORS to avoid localhost origin drift issues.
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ═══════════════════════════════════════════════════════════════
# ROUTES - Import AFTER app is created
# ═══════════════════════════════════════════════════════════════

from .routes.automation import router as automation_router
from .routes.access_requests import router as access_requests_router
from .routes.intelligence import router as intelligence_router
from .routes.ingestion import router as ingestion_router
from .routes.leads import router as leads_router
from .routes.lead_intake import router as lead_intake_router
from .routes.lead_pipeline import router as lead_pipeline_router
from .routes.finops import router as finops_router
from .routes.partners import router as partners_router
from .routes.public import router as public_router
from .routes.prospection import router as prospection_router
from .routes.sellers import router as sellers_router
from .routes.skills import router as skills_router
from .routes.syncxml_pilot import router as syncxml_pilot_router

# Include Intelligence routes (+ NotebookLM territorial insights)
app.include_router(intelligence_router, prefix="/api/intelligence", tags=["Intelligence"])

# Include Automation rules and alerts
app.include_router(automation_router, prefix="/api/automation", tags=["Automation"])

# Include internal access request review routes
app.include_router(access_requests_router, prefix="/api/access-requests", tags=["Access Requests"])

# Include Prospection & Buyer Matching routes
app.include_router(prospection_router, prefix="/api/prospection", tags=["Prospection"])

# Include FinOps routes
app.include_router(finops_router, prefix="/api/finops", tags=["FinOps"])

# Include partner admission routes
app.include_router(partners_router, prefix="/api/partners", tags=["Partners"])

# Include Nexus Sellers — Motor de Adquisición de Vendedores
app.include_router(sellers_router, prefix="/api/sellers", tags=["Sellers"])

# Include operational skill runner routes used by frontend cron jobs
app.include_router(skills_router, prefix="/api", tags=["Skills"])

# Include unified ingestion routes
app.include_router(ingestion_router, prefix="/api", tags=["Ingestion"])

# Include lead outreach routes
app.include_router(leads_router, prefix="/api", tags=["Leads"])

# Include lead intake API (Phase 3 — Commercial Loop)
app.include_router(lead_intake_router, prefix="/api/v1", tags=["Lead Intake"])

# Include lead pipeline reporting and staleness detection (Phase 3)
app.include_router(lead_pipeline_router, prefix="/api/v1", tags=["Lead Pipeline"])

# Include public capture routes
app.include_router(public_router, prefix="/api/public", tags=["Public"])

# Include GuestHub Pilot manual decision routes (legacy path prefix kept after
# the SyncXML → GuestHub rename, 2026-08 — consumed by the Nexus frontend).
app.include_router(syncxml_pilot_router, prefix="/api/syncxml-pilot", tags=["GuestHub Pilot"])

# ═══════════════════════════════════════════════════════════════
# HEALTH CHECK
# ═══════════════════════════════════════════════════════════════

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "Anclora Intelligence API v1.0",
    }

# ═══════════════════════════════════════════════════════════════
# ROOT
# ═══════════════════════════════════════════════════════════════

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Anclora Intelligence API v2.0",
        "endpoints": {
            "health": "/health",
            "intelligence": "/api/intelligence/query",
            "territorial_insights": "/api/intelligence/territorial-insights",
            "runtime_profile": "/api/intelligence/runtime-profile",
            "skills": "/api/skills/run",
            "ingestion": "/api/ingestion/events",
            "sellers": "/api/sellers/",
            "sellers_stats": "/api/sellers/stats",
            "docs": "/docs",
            "redoc": "/redoc",
        },
    }

# ═══════════════════════════════════════════════════════════════
# STARTUP / SHUTDOWN
# ═══════════════════════════════════════════════════════════════

@app.on_event("startup")
async def startup_event():
    """Startup event."""
    print("🚀 Anclora Intelligence API starting up...")

@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event."""
    print("🛑 Anclora Intelligence API shutting down...")

# ═══════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
