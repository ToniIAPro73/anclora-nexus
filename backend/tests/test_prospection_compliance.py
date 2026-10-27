"""
Compliance & Security tests for ANCLORA-PBM-001.
Validates: org isolation, source traceability, no irreversible automation.
"""
import pytest
from pathlib import Path
from backend.models.prospection import ALLOWED_SOURCES, PropertyCreate
from backend.services.scoring_service import ScoringService
from pydantic import ValidationError

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class TestSourceCompliance:
    """TC-CS-1/2: Source traceability and blocking."""

    def test_all_allowed_sources_defined(self) -> None:
        assert len(ALLOWED_SOURCES) >= 10, "At least 10 authorized sources expected"

    def test_no_scraper_sources(self) -> None:
        forbidden = {"scraper", "bot", "crawler", "automated"}
        assert ALLOWED_SOURCES.isdisjoint(forbidden)

    @pytest.mark.parametrize("bad", ["scraper_bot", "web_crawler", "auto_harvest", "dark_web", ""])
    def test_unauthorized_source_blocked(self, bad: str) -> None:
        with pytest.raises(ValidationError):
            PropertyCreate(source=bad)

    def test_source_url_is_optional(self) -> None:
        prop = PropertyCreate(source="direct")
        assert prop.source_url is None

    def test_source_url_preserved(self) -> None:
        prop = PropertyCreate(source="idealista", source_url="https://idealista.com/123")
        assert prop.source_url == "https://idealista.com/123"


class TestOrgIsolation:
    """TC-PP-6, TC-BP-5, TC-CS-5: Org isolation patterns."""

    def test_service_methods_require_org_id(self) -> None:
        """All public service methods take org_id as first param."""
        from backend.services.prospection_service import ProspectionService
        import inspect
        svc = ProspectionService()
        public = [m for m in dir(svc) if not m.startswith("_") and callable(getattr(svc, m))]
        for name in public:
            sig = inspect.signature(getattr(svc, name))
            params = list(sig.parameters.keys())
            assert params[0] == "self" or params[0] == "org_id" or (len(params) > 1 and params[1] == "org_id"), \
                f"Method {name} missing org_id parameter"

    def test_deps_get_org_id_exists(self) -> None:
        """Auth dependency function is defined."""
        from backend.api.deps import get_org_id
        assert callable(get_org_id)


class TestNoIrreversibleAutomation:
    """TC-CS-3: No contact automation without human step."""

    def test_no_auto_email_in_service(self) -> None:
        import inspect
        from backend.services.prospection_service import ProspectionService
        source = inspect.getsource(ProspectionService)
        assert "send_email" not in source.lower()
        assert "smtp" not in source.lower()
        assert "twilio" not in source.lower()
        assert "whatsapp_service" not in source.lower()
        assert "evolution_api" not in source.lower()

    def test_no_auto_contact_in_routes(self) -> None:
        import inspect
        from backend.api.routes import prospection
        source = inspect.getsource(prospection)
        assert "send_email" not in source.lower()
        assert "auto_contact" not in source.lower()


class TestScoreAuditability:
    """TC-CS-4: Score changes yield deterministic breakdown."""

    def test_same_input_same_score(self) -> None:
        r1 = ScoringService.compute_high_ticket_score(2000000, "Andratx", "villa", 300, 4)
        r2 = ScoringService.compute_high_ticket_score(2000000, "Andratx", "villa", 300, 4)
        assert r1.score == r2.score
        assert r1.breakdown == r2.breakdown

    def test_breakdown_always_present(self) -> None:
        result = ScoringService.compute_high_ticket_score(None, None, None)
        assert isinstance(result.breakdown, dict)
        assert len(result.breakdown) == 4


class TestDBConstraintsSpec:
    """Validates migration specs are correct."""

    MIGRATIONS_DIR = PROJECT_ROOT / "neon" / "migrations" / "archive" / "historical-migrations"

    def test_score_check_constraints_defined(self) -> None:
        import re
        sql = (self.MIGRATIONS_DIR / "018_prospection_matching_indexes.sql").read_text(encoding="utf-8")
        assert "chk_high_ticket_score_range" in sql
        assert "chk_match_score_range" in sql
        assert "chk_motivation_score_range" in sql
        assert "chk_budget_consistency" in sql

    def test_unique_constraint_defined(self) -> None:
        sql = (self.MIGRATIONS_DIR / "017_prospection_matching_tables.sql").read_text(encoding="utf-8")
        assert "UNIQUE (property_id, buyer_id)" in sql

    def test_org_id_fk_on_all_tables(self) -> None:
        sql = (self.MIGRATIONS_DIR / "017_prospection_matching_tables.sql").read_text(encoding="utf-8")
        assert sql.count("org_id") >= 4

    def test_indexes_for_org_score_ranking(self) -> None:
        sql = (self.MIGRATIONS_DIR / "018_prospection_matching_indexes.sql").read_text(encoding="utf-8")
        assert "idx_pp_org_score" in sql
        assert "idx_pbm_org_score" in sql

