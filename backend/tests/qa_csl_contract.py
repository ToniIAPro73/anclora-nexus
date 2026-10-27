import asyncio
import os
import sys
from decimal import Decimal
from uuid import uuid4

# Add root to sys.path
sys.path.append(os.getcwd())

from backend.models.prospection import PropertyCreate, PropertyUpdate
from backend.services.prospection_service import prospection_service

async def run_qa():
    print("--- Starting API CSL QA ---")
    # org_id = str(uuid4())
    org_id = "9d6cb56d-3f21-4f7b-80ea-797a7c2c62cf"
    print(f"Using test Org ID: {org_id}")

    # 1. Create Property with surface fields
    print("\n1. Testing Property Creation...")
    prop_data = PropertyCreate(
        source="direct",
        title="QA Villa Test",
        city="Andratx",
        price=Decimal("1500000"),
        useful_area_m2=Decimal("200.50"),
        built_area_m2=Decimal("250.00"),
        plot_area_m2=Decimal("1000.00")
    )
    
    created = await prospection_service.create_property(org_id, prop_data)
    prop_id = created["id"]
    print(f"Created Property ID: {prop_id}")
    assert created["useful_area_m2"] == 200.5
    assert created["built_area_m2"] == 250.0
    assert created["plot_area_m2"] == 1000.0
    print("SUCCESS: Creation fields verified.")

    # 2. Update Property (Manual origin allows changes)
    print("\n2. Testing Manual Update...")
    update_data = PropertyUpdate(
        useful_area_m2=Decimal("210.00")
    )
    updated = await prospection_service.update_property(org_id, prop_id, update_data)
    assert updated["useful_area_m2"] == 210.0
    print("SUCCESS: Manual update verified.")

    # 3. Test Validation (useful > built)
    print("\n3. Testing Logical Validation (useful > built)...")
    try:
        PropertyUpdate(useful_area_m2=Decimal("300"), built_area_m2=Decimal("250"))
        print("FAILURE: Validation useful > built DID NOT RAISE EXCEPTION")
        sys.exit(1)
    except Exception as e:
        print(f"SUCCESS: Caught expected validation error: {e}")

    # 4. Cleanup test data
    print("\n4. Cleaning up...")
    from backend.services.neon_service import neon_service
    neon_service.client.table("properties").delete().eq("id", prop_id).execute()
    print("SUCCESS: Cleanup done.")
    
    print("\n--- API CSL QA COMPLETED SUCCESSFULLY ---")

if __name__ == "__main__":
    asyncio.run(run_qa())
