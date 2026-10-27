from typing import Optional
from uuid import UUID
from fastapi import HTTPException, status
from backend.services.neon_service import neon_service
from backend.models.membership import UserRole, MembershipStatus

async def verify_org_membership(
    user_id: UUID,
    org_id: UUID,
    required_role: Optional[UserRole] = None,
    required_status: MembershipStatus = MembershipStatus.ACTIVE
):
    """
    Middleware/Dependency to verify organization membership and roles.

    Args:
        user_id: The ID of the user requesting access.
        org_id: The ID of the organization being accessed.
        required_role: Optional role required for the action.
        required_status: The required status of the membership (default: 'active').

    Returns:
        The membership record if valid.

    Raises:
        HTTPException 403: If membership is invalid or role is insufficient.
    """
    result = neon_service.client.table("organization_members")\
        .select("*")\
        .eq("user_id", str(user_id))\
        .eq("org_id", str(org_id))\
        .execute()

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not a member of this organization"
        )

    member = result.data[0]

    # Check status
    if member["status"] != required_status:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Membership status is {member['status']}, required: {required_status}"
        )

    # Check role hierarchy if required_role is set
    if required_role:
        role_hierarchy = {
            UserRole.OWNER: 3,
            UserRole.MANAGER: 2,
            UserRole.AGENT: 1
        }

        user_role_level = role_hierarchy.get(member["role"], 0)
        required_role_level = role_hierarchy.get(required_role, 0)

        if user_role_level < required_role_level:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {required_role}"
            )

    return member
