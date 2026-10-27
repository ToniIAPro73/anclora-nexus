from datetime import datetime
from enum import Enum
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field

class UserRole(str, Enum):
    OWNER = "owner"
    MANAGER = "manager"
    AGENT = "agent"

class MembershipStatus(str, Enum):
    ACTIVE = "active"
    PENDING = "pending"
    SUSPENDED = "suspended"
    REMOVED = "removed"

class MembershipBase(BaseModel):
    org_id: UUID
    role: UserRole
    status: MembershipStatus = MembershipStatus.PENDING

class MembershipCreate(BaseModel):
    email: EmailStr
    role: UserRole

class MembershipUpdate(BaseModel):
    role: Optional[UserRole] = None
    status: Optional[MembershipStatus] = None

class Membership(MembershipBase):
    id: UUID
    user_id: Optional[UUID] = None
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    joined_at: Optional[datetime] = None
    invitation_code: Optional[str] = None
    invitation_accepted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class MembershipList(BaseModel):
    members: List[Membership]
    total: int
    limit: int
    offset: int

class InvitationValidateResponse(BaseModel):
    valid: bool
    email: EmailStr
    role: UserRole
    org_name: str
    expires_at: datetime

class InvitationAcceptRequest(BaseModel):
    user_id: UUID
