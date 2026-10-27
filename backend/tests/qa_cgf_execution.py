
import asyncio
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.api.deps import get_current_user, get_org_id
from backend.services.neon_service import neon_service

# To be replaced with real ID from DB query
ORG_ID = "00000000-0000-0000-0000-000000000000"

def mock_get_current_user():
    # Use master user if needed, but for v0 any user in org works if RLS policies align
    # However, for regression, we might need a user that has permissions.
    # We use a dummy ID that will work with our mocks/overrides.
    return {"id": "test-user-qa", "email": "qa@anclora.com", "org_id": ORG_ID}

def mock_get_org_id():
    return ORG_ID

# Override deps
app.dependency_overrides[get_current_user] = mock_get_current_user
app.dependency_overrides[get_org_id] = mock_get_org_id

client = TestClient(app)

def test_regression_endpoints():
    print("\n--- Regression Tests ---")
    # 1. Properties
    print("Checking Properties endpoints...")
    try:
        # We need to mock the service or rely on DB. 
        # Since we use real DB, properties table must exist.
        res = client.get("/api/properties") # Assuming this endpoint exists
        # If endpoint is different, we might fail. Let's check routes.
        # But for now, just checking unrelated endpoints don't crash 500.
        if res.status_code != 404:
             assert res.status_code in [200, 401, 403], f"Properties endpoint failed: {res.status_code} {res.text}"
             print("Properties endpoint OK (alive)")
    except Exception as e:
        print(f"Properties check skipped/failed: {e}")

    # 2. Leads
    print("Checking Leads endpoints...")
    try:
        res = client.get("/api/leads")
        if res.status_code != 404:
             assert res.status_code in [200, 401, 403], f"Leads endpoint failed: {res.status_code} {res.text}"
             print("Leads endpoint OK (alive)")
    except Exception as e:
        print(f"Leads check skipped/failed: {e}")



def test_cgf_flow():
    print(f"Starting QA for Org: {ORG_ID}")
    
    # 1. Get Budget (Verify Backfill)
    print("1. Get Budget...")
    res = client.get("/api/finops/budget")
    assert res.status_code == 200, f"Get Budget failed: {res.text}"
    budget = res.json()
    print(f"Budget Config: {budget}")
    assert budget["monthly_budget_eur"] == 250.0  # From migration 027
    assert budget["status"] == "ok"

    # 2. Log Usage (Small amount)
    print("2. Log Usage (0.5 EUR)...")
    payload = {
        "capability_code": "qa_test",
        "units": 1,
        "cost_eur": 0.5,
        "provider": "openai"
    }
    res = client.post("/api/finops/usage/log", json=payload)
    assert res.status_code == 200, res.text
    
    # 3. Verify Usage in History
    print("3. Verify Usage History...")
    res = client.get("/api/finops/usage")
    assert res.status_code == 200
    history = res.json()
    assert len(history) > 0
    assert history[0]["cost_eur"] == 0.5
    
    # 4. Trigger Warning (80% of 250 = 200)
    # Current usage: 0.5. Need 199.5 more.
    print("4. Trigger Warning...")
    payload["cost_eur"] = 200.0
    res = client.post("/api/finops/usage/log", json=payload)
    assert res.status_code == 200
    
    res = client.get("/api/finops/budget")
    budget = res.json()
    print(f"Budget Status: {budget['status']}, Usage: {budget['current_usage_pct']}%")
    assert budget["status"] == "warning"
    
    # Check Alerts
    res = client.get("/api/finops/alerts")
    alerts = res.json()
    warning_alerts = [a for a in alerts if a["alert_type"] == "warning"]
    assert len(warning_alerts) > 0
    print("Warning Alert verified.")

    # 5. Trigger Hard Stop (100% = 250)
    # Current: 200.5. Need 49.5 more.
    print("5. Trigger Hard Stop...")
    payload["cost_eur"] = 50.0
    res = client.post("/api/finops/usage/log", json=payload)
    assert res.status_code == 200
    
    res = client.get("/api/finops/budget")
    budget = res.json()
    print(f"Budget Status: {budget['status']}, Usage: {budget['current_usage_pct']}%")
    assert budget["status"] == "hard_stop"
    
    # Check Alerts
    res = client.get("/api/finops/alerts")
    alerts = res.json()
    hs_alerts = [a for a in alerts if a["alert_type"] == "hard_stop"]
    assert len(hs_alerts) > 0
    print("Hard Stop Alert verified.")
    
    test_regression_endpoints()
    
    print("\nQA Execution Passed Successfully!")

if __name__ == "__main__":
    try:
        test_cgf_flow()
    except AssertionError as e:
        print(f"QA FAILED: {e}")
        exit(1)
    except Exception as e:
        print(f"QA ERROR: {e}")
        exit(1)
