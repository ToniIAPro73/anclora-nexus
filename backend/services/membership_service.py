import secrets
import string
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException
from backend.models.membership import (
    Membership,
    MembershipCreate,
    MembershipUpdate,
    UserRole,
    MembershipStatus
)
from backend.services.neon_service import neon_service

class MembershipService:
    """
    Service for managing organization memberships and invitations.
    """

    def _generate_invitation_code(self, length: int = 32) -> str:
        """
        Generates a secure random invitation code.
        """
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    def _get_active_owner_ids(self, org_id: UUID) -> List[str]:
        """
        Returns active owner membership ids using case-insensitive checks.
        """
        rows = neon_service.client.table("organization_members")\
            .select("id,role,status")\
            .eq("org_id", str(org_id))\
            .execute()
        owner_ids: List[str] = []
        for row in (rows.data or []):
            role = str(row.get("role") or "").strip().lower()
            status = str(row.get("status") or "").strip().lower()
            if role == UserRole.OWNER.value and status == MembershipStatus.ACTIVE.value:
                owner_ids.append(str(row["id"]))
        return owner_ids

    async def invite_member(self, org_id: UUID, payload: MembershipCreate, inviter_id: UUID) -> dict:
        """
        Invites a new member to an organization.

        Args:
            org_id: The ID of the organization.
            payload: The membership creation data (email, role).
            inviter_id: The ID of the user sending the invitation.

        Returns:
            The created membership record with invitation code.

        Raises:
            HTTPException: If member already exists or other validation fails.
        """
        # Business rules for invitations.
        if payload.role == UserRole.AGENT:
            raise HTTPException(status_code=400, detail="Invitations for role 'agent' are disabled. Invite as manager.")
        if payload.role == UserRole.OWNER:
            raise HTTPException(status_code=400, detail="Invitations for role 'owner' are not allowed.")

        invited_email = str(payload.email).strip().lower()

        # Resolve invited email to an existing user profile if available.
        profile = neon_service.client.table("user_profiles")\
            .select("id,email")\
            .ilike("email", invited_email)\
            .limit(1)\
            .execute()

        invited_user_id = str(profile.data[0]["id"]) if profile.data else None

        # Check duplicates by invited_email first (covers pre-signup invites).
        existing_by_email = neon_service.client.table("organization_members")\
            .select("*")\
            .eq("org_id", str(org_id))\
            .eq("invited_email", invited_email)\
            .limit(1)\
            .execute()
        if existing_by_email.data:
            existing_member = existing_by_email.data[0]
            if existing_member["status"] == MembershipStatus.ACTIVE:
                raise HTTPException(status_code=409, detail="User is already an active member of this organization")
            if existing_member["status"] == MembershipStatus.PENDING:
                raise HTTPException(status_code=409, detail="User already has a pending invitation")

        # If the user already exists, also check by user_id.
        existing_by_user = None
        if invited_user_id:
            existing_by_user = neon_service.client.table("organization_members")\
                .select("*")\
                .eq("org_id", str(org_id))\
                .eq("user_id", invited_user_id)\
                .limit(1)\
                .execute()
            if existing_by_user.data:
                existing_member = existing_by_user.data[0]
                if existing_member["status"] == MembershipStatus.ACTIVE:
                    raise HTTPException(status_code=409, detail="User is already an active member of this organization")
                if existing_member["status"] == MembershipStatus.PENDING:
                    raise HTTPException(status_code=409, detail="User already has a pending invitation")

        # Generate code
        invitation_code = self._generate_invitation_code()

        data = {
            "org_id": str(org_id),
            "user_id": invited_user_id,
            "invited_email": invited_email,
            "role": payload.role,
            "status": MembershipStatus.PENDING,
            "invitation_code": invitation_code,
            "invited_by": str(inviter_id),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }

        reusable = None
        if existing_by_email and existing_by_email.data:
            reusable = existing_by_email.data[0]
        elif existing_by_user and existing_by_user.data:
            reusable = existing_by_user.data[0]

        if reusable:
            # Reactivate a previously removed/suspended member as a new pending invitation.
            result = neon_service.client.table("organization_members")\
                .update({
                    "user_id": invited_user_id,
                    "invited_email": invited_email,
                    "role": payload.role,
                    "status": MembershipStatus.PENDING,
                    "invitation_code": invitation_code,
                    "invited_by": str(inviter_id),
                    "invitation_accepted_at": None,
                    "updated_at": datetime.utcnow().isoformat()
                })\
                .eq("id", str(reusable["id"]))\
                .eq("org_id", str(org_id))\
                .execute()
        else:
            result = neon_service.client.table("organization_members").insert(data).execute()
        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create invitation")
            
        member_data = result.data[0]
        member_data["email"] = invited_email
        return member_data

    async def list_members(self, org_id: UUID, role: Optional[UserRole] = None, status: Optional[MembershipStatus] = None, limit: int = 50, offset: int = 0) -> dict:
        """
        Lists members of an organization with filtering and pagination.
        """
        query = neon_service.client.table("organization_members").select("*", count="exact").eq("org_id", str(org_id))

        if role:
            query = query.eq("role", role)
        if status:
            query = query.eq("status", status)

        result = query.range(offset, offset + limit - 1).execute()

        members = result.data or []
        user_ids: List[str] = []
        for member in members:
            raw_user_id = member.get("user_id")
            if not raw_user_id:
                continue
            try:
                normalized_user_id = str(UUID(str(raw_user_id)))
                member["user_id"] = normalized_user_id
                user_ids.append(normalized_user_id)
            except (ValueError, TypeError):
                # Keep listing members even if one row has malformed user_id.
                member["user_id"] = None

        profiles_by_id = {}
        if user_ids:
            profiles = neon_service.client.table("user_profiles")\
                .select("id,email,full_name,avatar_url")\
                .in_("id", list(dict.fromkeys(user_ids)))\
                .execute()
            profiles_by_id = {p["id"]: p for p in (profiles.data or [])}

        for member in members:
            profile = profiles_by_id.get(member.get("user_id"))
            if profile:
                member["email"] = profile.get("email")
                member["full_name"] = profile.get("full_name")
                member["avatar_url"] = profile.get("avatar_url")
            else:
                member["email"] = member.get("invited_email")

            email = member.get("email")
            if email is not None:
                email = str(email).strip().lower()
                member["email"] = email if "@" in email else None

        return {
            "members": members,
            "total": int(result.count) if result.count is not None else len(members),
            "limit": limit,
            "offset": offset
        }

    async def update_membership(self, org_id: UUID, member_id: UUID, payload: MembershipUpdate) -> dict:
        """
        Updates a member's role or status.
        """
        target_role = payload.role.value if isinstance(payload.role, UserRole) else payload.role

        # Validate last owner check
        if target_role and target_role != UserRole.OWNER.value:
            # Check if this member IS an owner
            current = neon_service.client.table("organization_members")\
                .select("*")\
                .eq("id", str(member_id))\
                .eq("org_id", str(org_id))\
                .limit(1)\
                .execute()
            
            if current.data and str(current.data[0].get("role") or "").strip().lower() == UserRole.OWNER.value:
                owner_ids = self._get_active_owner_ids(org_id)
                if len(owner_ids) <= 1:
                    raise HTTPException(status_code=400, detail="Cannot change role of the last owner")
        elif target_role == UserRole.OWNER.value:
            current = neon_service.client.table("organization_members")\
                .select("*")\
                .eq("id", str(member_id))\
                .eq("org_id", str(org_id))\
                .limit(1)\
                .execute()
            if not current.data:
                raise HTTPException(status_code=404, detail="Member not found")
            current_role = str(current.data[0].get("role") or "").lower()
            if current_role != UserRole.OWNER.value:
                existing_owner_ids = set(self._get_active_owner_ids(org_id))
                if existing_owner_ids and str(member_id) not in existing_owner_ids:
                    raise HTTPException(status_code=400, detail="Organization already has an owner")

        update_data = payload.dict(exclude_unset=True)
        if "role" in update_data and isinstance(update_data["role"], UserRole):
            update_data["role"] = update_data["role"].value
        if "status" in update_data and isinstance(update_data["status"], MembershipStatus):
            update_data["status"] = update_data["status"].value
        update_data["updated_at"] = datetime.utcnow().isoformat()

        result = neon_service.client.table("organization_members")\
            .update(update_data)\
            .eq("id", str(member_id))\
            .eq("org_id", str(org_id))\
            .execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Member not found")

        updated_member = result.data[0]
        if payload.role and updated_member.get("user_id"):
            neon_service.client.table("user_profiles")\
                .update({"role": payload.role})\
                .eq("id", str(updated_member["user_id"]))\
                .execute()

        return updated_member

    async def remove_member(self, org_id: UUID, member_id: UUID):
        """
        Removes a member from an organization.
        """
        existing = neon_service.client.table("organization_members")\
            .select("id,role,status")\
            .eq("id", str(member_id))\
            .eq("org_id", str(org_id))\
            .limit(1)\
            .execute()
        if not existing.data:
            raise HTTPException(status_code=404, detail="Member not found")
        member = existing.data[0]
        if str(member.get("role") or "").strip().lower() == UserRole.OWNER.value:
            raise HTTPException(status_code=400, detail="Cannot remove owner member")

        neon_service.client.table("organization_members")\
            .delete()\
            .eq("id", str(member_id))\
            .eq("org_id", str(org_id))\
            .execute()

    async def validate_invitation(self, code: str) -> dict:
        """
        Validates an invitation code.
        """
        result = neon_service.client.table("organization_members")\
            .select("*, organizations(name)")\
            .eq("invitation_code", code)\
            .eq("status", MembershipStatus.PENDING)\
            .execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Invalid or expired invitation code")

        inv = result.data[0]
        # Check expiration (7 days)
        created_at = datetime.fromisoformat(inv["created_at"].replace("Z", "+00:00"))
        if datetime.now(created_at.tzinfo) > created_at + timedelta(days=7):
            raise HTTPException(status_code=404, detail="Invitation code expired")

        return {
            "valid": True,
            "email": inv.get("invited_email") or (
                neon_service.client.table("user_profiles")
                .select("email")
                .eq("id", inv["user_id"])
                .limit(1)
                .execute()
                .data[0]["email"]
                if inv.get("user_id")
                else ""
            ),
            "role": inv["role"],
            "org_name": inv.get("organizations", {}).get("name", "Anclora"),
            "expires_at": created_at + timedelta(days=7)
        }

    async def accept_invitation(self, code: str, user_id: UUID) -> dict:
        """
        Accepts an invitation and activates the membership.
        """
        # First validate
        _ = await self.validate_invitation(code)

        invite = neon_service.client.table("organization_members")\
            .select("*")\
            .eq("invitation_code", code)\
            .eq("status", MembershipStatus.PENDING)\
            .limit(1)\
            .execute()
        if not invite.data:
            raise HTTPException(status_code=404, detail="Invalid or expired invitation code")

        inv = invite.data[0]
        org_id = inv["org_id"]

        existing_active = neon_service.client.table("organization_members")\
            .select("id")\
            .eq("org_id", org_id)\
            .eq("user_id", str(user_id))\
            .eq("status", MembershipStatus.ACTIVE)\
            .limit(1)\
            .execute()
        if existing_active.data and str(existing_active.data[0]["id"]) != str(inv["id"]):
            raise HTTPException(status_code=409, detail="User is already an active member of this organization")

        # Update membership
        result = neon_service.client.table("organization_members")\
            .update({
                "user_id": str(user_id),
                "status": MembershipStatus.ACTIVE,
                "invitation_accepted_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            })\
            .eq("id", str(inv["id"]))\
            .execute()

        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to accept invitation")

        accepted = result.data[0]
        neon_service.client.table("user_profiles")\
            .update({
                "org_id": accepted["org_id"],
                "role": accepted["role"]
            })\
            .eq("id", str(user_id))\
            .execute()

        return accepted

membership_service = MembershipService()
