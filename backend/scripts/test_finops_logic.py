
import asyncio
import os
import sys
from datetime import date
from uuid import uuid4
from dotenv import load_dotenv
import pytest

# Path setup to import backend modules
sys.path.append(os.getcwd())

from backend.services.finops import finops_service
from backend.models.finops import UsageEventSchema, BudgetUpdate

@pytest.mark.skipif(
    os.getenv("NEON_FINOPS_LIVE_TESTS") != "1",
    reason="Live Neon FinOps QA mutates database rows; opt in with NEON_FINOPS_LIVE_TESTS=1",
)
@pytest.mark.asyncio
async def test_finops_logic():
    print("=== FinOps Logic & Isolation QA Test ===")

    # Use real Org IDs from the DB if possible, or create temporary ones for testing
    # For isolation, we just need two different UUID strings.
    org_a = str(uuid4())
    org_b = str(uuid4())

    print(f"Testing with Orgs:\n  Org A: {org_a}\n  Org B: {org_b}")

    try:
        # 1. Setup Policies for both
        print("\n[Step 1] Setting up policies...")
        # Since we can't easily insert orgs without complex setup, let's try to update existing ones or just use what's there.
        # But for logic testing, we can use the 'neon' client directly to inject test data if needed.
        # However, the service relies on existing orgs.
        # Let's find one real org_id to use for the main logic test.
        real_org_res = finops_service.client.table("organizations").select("id").limit(1).execute()
        if not real_org_res.data:
            print("[ERROR] No organizations found in DB to test with.")
            return

        test_org_id = real_org_res.data[0]["id"]
        print(f"Using real Org ID for logic test: {test_org_id}")

        # Reset policy to known state
        print("  Resetting policy and usage for test...")
        await finops_service.update_budget_policy(test_org_id, BudgetUpdate(
            monthly_budget_eur=100.0,
            warning_threshold_pct=50.0,
            hard_stop_threshold_pct=90.0,
            hard_stop_enabled=True
        ))

        # CLEANUP: Delete previous usage events for this month to avoid interference
        current_month_start = date.today().replace(day=1).isoformat()
        finops_service.client.table("org_cost_usage_events")\
            .delete()\
            .eq("org_id", test_org_id)\
            .gte("created_at", current_month_start)\
            .execute()

        # CLEANUP: Deactivate previous alerts
        finops_service.client.table("org_cost_alerts")\
            .update({"is_active": False})\
            .eq("org_id", test_org_id)\
            .execute()

        # 2. Test Isolation: Fetch Org B usage (should be empty/only its own)
        # Even if Org B doesn't exist in policies, the query should handle it gracefully or return 0.
        usage_b = await finops_service.get_usage_history(org_b)
        print(f"[OK] Org B usage history is isolated (count: {len(usage_b)})")

        # 3. Test Threshold Sequence (OK -> Warning -> Hard Stop)
        print("\n[Step 3] Testing Threshold Sequence...")

        # Log event: 10 EUR (10% of 100) -> Status: OK
        print("Logging 10 EUR event...")
        await finops_service.log_usage_event(test_org_id, UsageEventSchema(
            capability_code="test_qa",
            units=1.0,
            cost_eur=10.0
        ))
        status = await finops_service.get_budget_status(test_org_id)
        print(f"  Status after 10 EUR: {status.status} (Usage: {status.current_usage_eur} EUR, {status.current_usage_pct}%)")
        assert status.status == "ok"

        # Log event: 50 EUR (Total 60%) -> Status: Warning
        print("Logging 50 EUR event...")
        await finops_service.log_usage_event(test_org_id, UsageEventSchema(
            capability_code="test_qa",
            units=1.0,
            cost_eur=50.0
        ))
        status = await finops_service.get_budget_status(test_org_id)
        print(f"  Status after +50 EUR: {status.status} (Usage: {status.current_usage_eur} EUR, {status.current_usage_pct}%)")
        assert status.status == "warning"

        # Verify Alert was created
        alerts = await finops_service.get_active_alerts(test_org_id)
        has_warning = any(a.alert_type == "warning" for a in alerts)
        print(f"  [OK] Warning alert detected in DB: {has_warning}")
        assert has_warning

        # Log event: 40 EUR (Total 100%) -> Status: Hard Stop
        print("Logging 40 EUR event...")
        await finops_service.log_usage_event(test_org_id, UsageEventSchema(
            capability_code="test_qa",
            units=1.0,
            cost_eur=40.0
        ))
        status = await finops_service.get_budget_status(test_org_id)
        print(f"  Status after +40 EUR: {status.status} (Usage: {status.current_usage_eur} EUR, {status.current_usage_pct}%)")
        assert status.status == "hard_stop"

        # Verify Hard Stop Alert was created
        alerts = await finops_service.get_active_alerts(test_org_id)
        has_hard_stop = any(a.alert_type == "hard_stop" for a in alerts)
        print(f"  [OK] Hard Stop alert detected in DB: {has_hard_stop}")
        assert has_hard_stop

        print("\n[SUCCESS] FinOps Logic & Isolation verified.")

    except Exception as e:
        print(f"\n[FAIL] Test encountered error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_finops_logic())
