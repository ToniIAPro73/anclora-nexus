import os
import sys

# Inject environment variables before any backend imports to satisfy Pydantic Settings
os.environ.setdefault("AI_RUNTIME_PROFILE", "groq-cloudflare")
os.environ.setdefault("GROQ_API_KEY", "groq-test")
os.environ.setdefault("CLOUDFLARE_ACCOUNT_ID", "cf-account-test")
os.environ.setdefault("CLOUDFLARE_API_TOKEN", "cf-token-test")
os.environ.setdefault("INTERNAL_AUDIT_SECRET", "test-secret")

import pytest
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime, timezone
import uuid
import json

from backend.intelligence.intelligence_types import (
    QueryPlan, GovernorDecision, RiskProfile, RiskItem, 
    Recommendation, RiskLevel, Confidence, DomainKey, QueryMode,
    SynthesizerOutput, Meta, PlanView, Trace, EvidenceView, EvidenceStatus, MetaVersion, RiskSummary
)

# --- Service Mocks ---

@pytest.fixture
def mock_llm_service():
    """Mock for backend.services.llm_service.LLMService"""
    mock = MagicMock()
    mock.summarize = AsyncMock(return_value="Mock summary")
    mock.generate_copy = AsyncMock(return_value="Mock luxury copy")
    mock.analyze = AsyncMock(return_value=json.dumps({
        "summary": "Mock analysis summary",
        "priority": 3,
        "score": 0.7
    }))
    return mock

@pytest.fixture
def mock_neon_service():
    """Mock for backend.services.neon_service.NeonService"""
    mock = MagicMock()
    mock.insert_lead = AsyncMock(return_value={"id": "lead-123"})
    mock.get_active_leads = AsyncMock(return_value=[
        {"id": "lead-1", "name": "Test Lead", "property_interest": "Villa", "budget_range": "1M"}
    ])
    mock.get_available_properties = AsyncMock(return_value=[
        {"id": "prop-1", "address": "Andratx 1", "price": 1500000, "property_type": "villa"}
    ])
    mock.insert_agent_execution = AsyncMock(return_value={"id": "exec-123"})
    mock.insert_audit_log = AsyncMock(return_value={"id": "audit-123"})
    mock.get_recent_leads = AsyncMock(return_value=[])
    mock.get_recent_executions = AsyncMock(return_value=[])
    mock.get_recent_properties_updates = AsyncMock(return_value=[])
    return mock

@pytest.fixture
def mock_db_service():
    """Mock for backend.intelligence.database.DatabaseService"""
    mock = MagicMock()
    mock.save_audit_log = MagicMock(return_value=(True, "Audit log saved: audit-123"))
    return mock

# --- Data Fixtures ---

@pytest.fixture
def sample_query_plan():
    """Standard QueryPlan fixture."""
    return QueryPlan(
        query_plan_id=str(uuid.uuid4()),
        mode=QueryMode.FAST,
        domains_selected=[DomainKey.MARKET.value],
        agents_selected=["market_agent"],
        rationale="Testing plan",
        confidence=Confidence.HIGH
    )

@pytest.fixture
def sample_governor_decision():
    """Standard GovernorDecision fixture."""
    return GovernorDecision(
        decision_id=str(uuid.uuid4()),
        diagnosis="Everything looks good in Mallorca SW.",
        recommendation=Recommendation.EXECUTE,
        risks=RiskProfile(
            labor=RiskItem(level=RiskLevel.LOW, rationale="No labor impact"),
            tax=RiskItem(level=RiskLevel.LOW, rationale="No tax impact"),
            brand=RiskItem(level=RiskLevel.LOW, rationale="No brand impact"),
            focus=RiskItem(level=RiskLevel.LOW, rationale="No focus impact")
        ),
        next_steps=("Step 1", "Step 2", "Step 3"),
        dont_do=["Don't panic", "Don't overspend"],
        flags=["safe"],
        confidence=Confidence.HIGH,
        strategic_mode_version="1.0-test",
        domains_used=[DomainKey.MARKET.value]
    )

@pytest.fixture
def sample_synthesizer_output():
    """Standard SynthesizerOutput fixture."""
    return SynthesizerOutput(
        output_id=str(uuid.uuid4()),
        answer="I have analyzed the market for you.",
        meta=Meta(
            mode=QueryMode.FAST,
            domain_hint="market",
            confidence=Confidence.HIGH,
            flags=["test"],
            recommendation=Recommendation.EXECUTE,
            risk_summary=RiskSummary(
                labor=RiskLevel.LOW,
                tax=RiskLevel.LOW,
                brand=RiskLevel.LOW,
                focus=RiskLevel.LOW
            ),
            version=MetaVersion(
                schema_version="1.0",
                strategic_mode_id="v1",
                domain_pack_id="v1"
            )
        ),
        plan=PlanView(
            domains_selected=["market"],
            rationale="Test rationale",
            lab_policy={"status": "denied", "rationale": "Test policy"}
        ),
        trace=Trace(
            query_plan_id="qp-123",
            governor_decision_id="gd-123",
            created_at=datetime.now(timezone.utc).isoformat()
        ),
        evidence=EvidenceView(status=EvidenceStatus.NOT_AVAILABLE, items=[])
    )
