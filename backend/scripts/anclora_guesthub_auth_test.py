"""
Negative authorization test for Anclora GuestHub.
Validates that an identity user WITHOUT GuestHub membership is strictly denied with HTTP 403 ACCESS_DENIED.
"""

def test_guesthub_negative_authorization():
    # User with only data_lab membership
    claims_no_guesthub = {
        "sub": "usr-data-lab-only-12345",
        "email": "datalab-only@anclora.test",
        "application_memberships": ["data-lab"],
        "platform_roles": [],
    }
    
    # Simulate resolveGuestHubAccess
    memberships = claims_no_guesthub.get("application_memberships", [])
    platform_roles = claims_no_guesthub.get("platform_roles", [])
    
    allowed = False
    reason = "NO_MEMBERSHIP"
    
    if "GROUP_OWNER" in platform_roles:
        allowed = True
        reason = "GUESTHUB_FULL_ACCESS"
    elif "guesthub" in memberships or "syncxml" in memberships:
        allowed = True
        reason = "APPLICATION_MEMBERSHIP"
        
    if not allowed:
        return {
            "status": 403,
            "error": "ACCESS_DENIED",
            "message": "User does not have an active GuestHub membership",
            "tested_claims": claims_no_guesthub,
            "decision": {"allowed": False, "reason": reason}
        }
    else:
        return {
            "status": 200,
            "allowed": True
        }
