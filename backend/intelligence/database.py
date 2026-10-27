"""
Anclora Intelligence v1 — Database Service
Manages connection to Neon PostgreSQL and audit log operations
"""

import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from .models import IntelligenceAuditLog, get_database_session, create_append_only_trigger


class DatabaseService:
    """Service for database operations."""
    
    def __init__(self):
        """Initialize database service."""
        try:
            self.engine, self.SessionLocal = get_database_session()
            print("✅ Database connection initialized")
            
            # Create APPEND-ONLY triggers
            try:
                create_append_only_trigger(self.engine)
                print("✅ APPEND-ONLY triggers created")
            except Exception as e:
                print(f"⚠️  Trigger creation note: {e}")
        
        except Exception as e:
            print(f"❌ Database initialization error: {e}")
            raise
    
    def save_audit_log(
        self,
        correlation_id: str,
        user_id: str,
        message: str,
        query_plan: dict,
        query_plan_id: str,
        governor_decision: dict,
        governor_decision_id: str,
        synthesizer_output: dict,
        synthesizer_output_id: str,
        status: str,
        strategic_mode_version: str,
        confidence_overall: str,
        execution_times: dict,
        error_message: Optional[str] = None,
        warnings: Optional[list] = None,
    ) -> Tuple[bool, str]:
        """
        Save an audit log entry to the database.
        
        Args:
            correlation_id: Unique request ID
            user_id: User making the request
            message: Original message from user
            query_plan: Full QueryPlan snapshot (dict)
            query_plan_id: ID of query plan
            governor_decision: Full GovernorDecision snapshot (dict)
            governor_decision_id: ID of governor decision
            synthesizer_output: Full SynthesizerOutput snapshot (dict)
            synthesizer_output_id: ID of synthesizer output
            status: success|error|partial
            strategic_mode_version: Version of strategic mode used
            confidence_overall: low|medium|high
            execution_times: Dict with timing metrics
            error_message: Optional error message
            warnings: Optional list of warnings
        
        Returns:
            (success, message)
        """
        
        session = None
        
        try:
            session = self.SessionLocal()
            
            # Calculate checksum for integrity
            checksum_data = {
                'correlation_id': correlation_id,
                'user_id': user_id,
                'message': message,
                'query_plan_id': query_plan_id,
                'governor_decision_id': governor_decision_id,
                'synthesizer_output_id': synthesizer_output_id,
                'status': status,
                'created_at': datetime.now(timezone.utc).isoformat(),
            }
            checksum = hashlib.sha256(
                json.dumps(checksum_data, sort_keys=True).encode()
            ).hexdigest()
            
            # HMAC-SHA256 Signature (Constitution Requirement)
            audit_secret = os.getenv("AUDIT_SECRET", "anclora-nexus-v1-dev-secret")
            signature = hmac.new(
                audit_secret.encode(),
                checksum.encode(),
                hashlib.sha256
            ).hexdigest()
            
            # Create audit log entry
            audit_entry = IntelligenceAuditLog(
                correlation_id=correlation_id,
                user_id=user_id,
                message=message,
                message_length=len(message),
                
                query_plan_id=query_plan_id,
                query_plan=query_plan,
                
                governor_decision_id=governor_decision_id,
                governor_decision=governor_decision,
                
                synthesizer_output_id=synthesizer_output_id,
                synthesizer_output=synthesizer_output,
                
                strategic_mode_version=strategic_mode_version,
                status=status,
                error_message=error_message,
                warnings=warnings or [],
                
                confidence_overall=confidence_overall,
                
                router_time_ms=execution_times.get('router_ms'),
                governor_time_ms=execution_times.get('governor_ms'),
                synthesizer_time_ms=execution_times.get('synthesizer_ms'),
                total_time_ms=execution_times.get('total_ms'),
                
                checksum=checksum,
                signature=signature,
                output_ai=True,
            )
            
            # Save to database
            session.add(audit_entry)
            session.commit()
            
            return True, f"Audit log saved: {audit_entry.id}"
        
        except Exception as e:
            if session:
                session.rollback()
            return False, f"Database error: {str(e)}"
        
        finally:
            if session:
                session.close()
    
    def get_audit_log(self, correlation_id: str) -> Optional[dict]:
        """
        Retrieve an audit log entry by correlation_id.
        
        Args:
            correlation_id: The correlation ID to retrieve
        
        Returns:
            Dict representation of audit log or None
        """
        
        session = None
        
        try:
            session = self.SessionLocal()
            
            entry = session.query(IntelligenceAuditLog).filter(
                IntelligenceAuditLog.correlation_id == correlation_id
            ).first()
            
            if not entry:
                return None
            
            return {
                'id': entry.id,
                'correlation_id': entry.correlation_id,
                'user_id': entry.user_id,
                'message': entry.message,
                'status': entry.status,
                'confidence': entry.confidence_overall,
                'total_time_ms': entry.total_time_ms,
                'created_at': entry.created_at.isoformat(),
                'query_plan_id': entry.query_plan_id,
                'governor_decision_id': entry.governor_decision_id,
                'synthesizer_output_id': entry.synthesizer_output_id,
            }
        
        except Exception as e:
            print(f"Error retrieving audit log: {e}")
            return None
        
        finally:
            if session:
                session.close()
    
    def get_user_history(self, user_id: str, limit: int = 10) -> list:
        """
        Get recent audit log entries for a user.
        
        Args:
            user_id: The user ID
            limit: Maximum number of entries to return
        
        Returns:
            List of audit log entries
        """
        
        session = None
        
        try:
            session = self.SessionLocal()
            
            entries = session.query(IntelligenceAuditLog).filter(
                IntelligenceAuditLog.user_id == user_id
            ).order_by(
                IntelligenceAuditLog.created_at.desc()
            ).limit(limit).all()
            
            return [
                {
                    'id': entry.id,
                    'correlation_id': entry.correlation_id,
                    'message': entry.message[:100],  # First 100 chars
                    'status': entry.status,
                    'recommendation': entry.governor_decision.get('recommendation') if entry.governor_decision else None,
                    'total_time_ms': entry.total_time_ms,
                    'created_at': entry.created_at.isoformat(),
                }
                for entry in entries
            ]
        
        except Exception as e:
            print(f"Error retrieving user history: {e}")
            return []
        
        finally:
            if session:
                session.close()


# ═══════════════════════════════════════════════════════════════
# SINGLETON INSTANCE
# ═══════════════════════════════════════════════════════════════

_db_service = None

def get_db_service() -> DatabaseService:
    """Get or create singleton database service."""
    global _db_service
    if _db_service is None:
        _db_service = DatabaseService()
    return _db_service
