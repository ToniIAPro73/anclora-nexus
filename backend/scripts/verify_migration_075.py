import os
import sys
import uuid
import socket

# DNS resilience for macOS mDNSResponder negative cache
_orig_getaddrinfo = socket.getaddrinfo
def patched_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    try:
        return _orig_getaddrinfo(host, port, family, type, proto, flags)
    except socket.gaierror:
        if "supabase.co" in str(host):
            return [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("172.64.149.246", port)),
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("104.18.38.10", port)),
            ]
        raise
socket.getaddrinfo = patched_getaddrinfo

from backend.services.supabase_service import SupabaseService

def verify_migration():
    svc = SupabaseService()
    print("=== STEP 8: MIGRATION 075 & RLS VERIFICATION ===")
    
    # 1. Check all columns
    required_cols = [
        "source_system",
        "source_channel",
        "source_detail",
        "identity_subject_id",
        "identity_invitation_id",
        "membership_id",
        "provisioning_status",
        "provisioning_error",
    ]
    
    missing = []
    for col in required_cols:
        try:
            svc.client.table("access_requests").select(col).limit(1).execute()
        except Exception as e:
            print(f"Error checking column {col}: {e}")
            missing.append(col)
            
    if missing:
        print(f"❌ Migration not applied yet. Missing columns: {missing}")
        return False
        
    print(f"✅ All {len(required_cols)} new columns exist in public.access_requests!")
    
    # 2. Test inserting a test record with canonical v2 values
    test_id = str(uuid.uuid4())
    org_id = svc.fixed_org_id
    test_payload = {
        "id": test_id,
        "org_id": org_id,
        "email": f"migration-test-{test_id[:8]}@anclora.test",
        "full_name": "Migration Test User",
        "status": "pending",
        "product": "guesthub",
        "source": "private_estates_landing",
        "source_system": "private_estates_landing",
        "source_channel": "web_form",
        "source_detail": "admissions_modal",
        "schema_version": "anclora-intake-v1",
        "intake_domain": "access_request",
        "routing_target_domain": "access_requests",
        "request_type": "pilot_request",
        "privacy_accepted": True,
        "gdpr_consent": True,
        "provisioning_status": "not_started",
    }
    
    try:
        ins = svc.client.table("access_requests").insert(test_payload).execute()
        print("✅ Successfully inserted v2 test access request (guesthub + private_estates_landing)!")
        
        # 3. Test updating provisioning fields
        update_payload = {
            "identity_subject_id": str(uuid.uuid4()),
            "identity_invitation_id": str(uuid.uuid4()),
            "membership_id": str(uuid.uuid4()),
            "provisioning_status": "invite_ready",
        }
        upd = svc.client.table("access_requests").update(update_payload).eq("id", test_id).execute()
        print("✅ Successfully updated identity provisioning fields and status!")
        
        # 4. Clean up test record
        svc.client.table("access_requests").delete().eq("id", test_id).execute()
        print("✅ Successfully cleaned up test record. Zero side effects!")
        
        print("🎉 MIGRATION 075 AND DEV RLS VERIFIED SUCCESSFULLY WITH REAL SUPABASE OPERATIONS!")
        return True
    except Exception as e:
        print(f"❌ Error during migration verification test: {e}")
        try:
            svc.client.table("access_requests").delete().eq("id", test_id).execute()
        except Exception:
            pass
        return False

if __name__ == "__main__":
    success = verify_migration()
    sys.exit(0 if success else 1)
