"""
Anclora Intelligence v1 — SQLAlchemy Models
Database models for Neon PostgreSQL
"""

from sqlalchemy import (
    Column, String, DateTime, JSON, Text, 
    Boolean, Float, Integer, Index, CheckConstraint,
    create_engine, event
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone
import uuid

Base = declarative_base()


from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, List, Any
from .intelligence_types import Confidence, AuditStatus

# ═══════════════════════════════════════════════════════════════
# PYDANTIC SCHEMAS (Validation)
# ═══════════════════════════════════════════════════════════════

class AuditLogBase(BaseModel):
    """Base schema for audit log entries."""
    model_config = ConfigDict(from_attributes=True)
    correlation_id: str
    user_id: str
    message: str
    status: AuditStatus
    confidence_overall: Confidence
    strategic_mode_version: str

class AuditLogCreate(AuditLogBase):
    """Schema for creating a new audit log entry."""
    query_plan_id: str
    query_plan: Dict[str, Any]
    governor_decision_id: str
    governor_decision: Dict[str, Any]
    synthesizer_output_id: str
    synthesizer_output: Dict[str, Any]
    execution_times: Dict[str, float]
    error_message: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    checksum: str
    signature: Optional[str] = None
    model_used: str = "claude-3.5-sonnet"

class AuditLogRead(AuditLogBase):
    """Schema for reading an audit log entry."""
    id: str
    message_length: int
    created_at: datetime
    stored_at: datetime
    total_time_ms: Optional[float] = None
    output_ai: bool

# ═══════════════════════════════════════════════════════════════
# SQLALCHEMY MODELS
# ═══════════════════════════════════════════════════════════════

class IntelligenceAuditLog(Base):
    """
    Audit log table for Intelligence operations.
    APPEND-ONLY: Triggers prevent UPDATE/DELETE
    """
    
    __tablename__ = "intelligence_audit_logs"
    
    # ─── PRIMARY KEY ───
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # ─── CORRELATION & TRACING ───
    correlation_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(255), nullable=False, index=True)
    
    # ─── INPUT ───
    message = Column(Text, nullable=False)
    message_length = Column(Integer, nullable=False)
    
    # ─── SNAPSHOTS (Full JSON) ───
    query_plan_id = Column(String(36), nullable=False)
    query_plan = Column(JSON, nullable=False)  # Full QueryPlan snapshot
    
    governor_decision_id = Column(String(36), nullable=False)
    governor_decision = Column(JSON, nullable=False)  # Full GovernorDecision snapshot
    
    synthesizer_output_id = Column(String(36), nullable=False)
    synthesizer_output = Column(JSON, nullable=False)  # Full SynthesizerOutput snapshot
    
    # ─── GOVERNANCE ───
    strategic_mode_version = Column(String(50), nullable=False)
    domain_pack_version = Column(String(50), nullable=False, default="real-estate-mallorca@v0.1")
    
    # ─── STATUS & OUTCOME ───
    status = Column(String(20), nullable=False)  # success|error|partial
    error_message = Column(Text, nullable=True)
    warnings = Column(JSON, nullable=True, default=list)  # List of warnings
    
    # ─── AI METADATA ───
    output_ai = Column(Boolean, nullable=False, default=True)
    model_used = Column(String(100), nullable=False, default="claude-opus-4.5")
    confidence_overall = Column(String(20), nullable=False)  # low|medium|high
    
    # ─── EXECUTION METRICS ───
    router_time_ms = Column(Float, nullable=True)
    governor_time_ms = Column(Float, nullable=True)
    synthesizer_time_ms = Column(Float, nullable=True)
    total_time_ms = Column(Float, nullable=True)
    
    # ─── TIMESTAMPS ───
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    stored_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    
    # ─── INTEGRITY ───
    checksum = Column(String(64), nullable=False)  # SHA-256 of full entry
    signature = Column(String(255), nullable=True)
    
    # ─── RETENTION ───
    retention_policy = Column(String(50), nullable=False, default="permanent")
    
    # ─── INDEXES ───
    __table_args__ = (
        Index('idx_correlation_id', 'correlation_id'),
        Index('idx_user_id', 'user_id'),
        Index('idx_created_at', 'created_at'),
        Index('idx_status', 'status'),
        Index('idx_user_date', 'user_id', 'created_at'),  # Compound
        CheckConstraint(
            "status IN ('success', 'error', 'partial')",
            name='check_status'
        ),
        CheckConstraint(
            "confidence_overall IN ('low', 'medium', 'high')",
            name='check_confidence'
        ),
    )
    
    def __repr__(self):
        return (
            f"<IntelligenceAuditLog("
            f"id={self.id}, "
            f"correlation_id={self.correlation_id}, "
            f"status={self.status}, "
            f"created_at={self.created_at}"
            f")>"
        )


# ═══════════════════════════════════════════════════════════════
# DATABASE CONFIG
# ═══════════════════════════════════════════════════════════════

class DatabaseConfig:
    """Configuration for database connections."""
    
    # Neon local connection (from docker-compose)
    SQLALCHEMY_URL = "postgresql://postgres:postgres@localhost:5432/postgres"
    
    # Production would use:
    # SQLALCHEMY_URL = os.getenv("DATABASE_URL")
    
    ECHO_SQL = False  # Set to True for debugging
    POOL_SIZE = 5
    MAX_OVERFLOW = 10


# ═══════════════════════════════════════════════════════════════
# SESSION FACTORY
# ═══════════════════════════════════════════════════════════════

def get_database_session():
    """Create database engine and session factory."""
    engine = create_engine(
        DatabaseConfig.SQLALCHEMY_URL,
        echo=DatabaseConfig.ECHO_SQL,
        pool_size=DatabaseConfig.POOL_SIZE,
        max_overflow=DatabaseConfig.MAX_OVERFLOW,
    )
    
    # Create tables
    Base.metadata.create_all(engine)
    
    # Create session factory
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    return engine, SessionLocal


# ═══════════════════════════════════════════════════════════════
# TRIGGERS (APPEND-ONLY PROTECTION)
# ═══════════════════════════════════════════════════════════════

def create_append_only_trigger(engine):
    """
    Create PostgreSQL triggers to prevent UPDATE/DELETE on audit log.
    Run this after tables are created.
    """
    
    trigger_sql = """
    -- Create function to prevent updates/deletes
    CREATE OR REPLACE FUNCTION prevent_audit_update()
    RETURNS TRIGGER AS Cyan
    BEGIN
        RAISE EXCEPTION 'Intelligence audit logs are append-only. No updates allowed.';
    END;
    Cyan LANGUAGE plpgsql;
    
    -- Create function to prevent deletes
    CREATE OR REPLACE FUNCTION prevent_audit_delete()
    RETURNS TRIGGER AS Cyan
    BEGIN
        RAISE EXCEPTION 'Intelligence audit logs are append-only. No deletes allowed.';
    END;
    Cyan LANGUAGE plpgsql;
    
    -- Attach triggers to table
    DROP TRIGGER IF EXISTS audit_prevent_update ON intelligence_audit_logs;
    CREATE TRIGGER audit_prevent_update
    BEFORE UPDATE ON intelligence_audit_logs
    FOR EACH ROW EXECUTE FUNCTION prevent_audit_update();
    
    DROP TRIGGER IF EXISTS audit_prevent_delete ON intelligence_audit_logs;
    CREATE TRIGGER audit_prevent_delete
    BEFORE DELETE ON intelligence_audit_logs
    FOR EACH ROW EXECUTE FUNCTION prevent_audit_delete();
    """
    
    with engine.connect() as conn:
        for statement in trigger_sql.split(';'):
            if statement.strip():
                try:
                    conn.execute(statement)
                    conn.commit()
                except Exception as e:
                    print(f"Note: Trigger may already exist: {e}")
