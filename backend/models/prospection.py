"""
Pydantic models for Prospection & Buyer Matching v1.
Feature: ANCLORA-PBM-001
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


# ═══════════════════════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════════════════════


class PropertyStatus(str, Enum):
    NEW = "new"
    CONTACTED = "contacted"
    NEGOTIATING = "negotiating"
    LISTED = "listed"
    DISCARDED = "discarded"


class BuyerStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    CLOSED = "closed"


class BuyerSourceType(str, Enum):
    PARTNER_REFERRAL = "partner_referral"
    CRM_REACTIVATION = "crm_reactivation"
    WEB_INBOUND = "web_inbound"
    PAID_LEAD = "paid_lead"
    MANUAL = "manual"
    PORTAL_SIGNAL = "portal_signal"


class BuyerSourcePlatform(str, Enum):
    EXP_AGENT = "exp_agent"
    EXTERNAL_AGENT = "external_agent"
    CRM = "crm"
    WEB = "web"
    META = "meta"
    GOOGLE = "google"
    WHATSAPP = "whatsapp"
    EMAIL = "email"
    IDEALISTA = "idealista"
    MANUAL = "manual"
    OTHER = "other"


class BuyerReferralPartnerType(str, Enum):
    EXP_AGENT = "exp_agent"
    EXTERNAL_AGENT = "external_agent"
    BROKER = "broker"
    PARTNER = "partner"
    FAMILY_OFFICE = "family_office"
    RELOCATION = "relocation"


class BuyerIntroStatus(str, Enum):
    NEW = "new"
    INTRODUCED = "introduced"
    QUALIFIED = "qualified"
    VIEWING = "viewing"
    CLOSED = "closed"


class MatchStatus(str, Enum):
    CANDIDATE = "candidate"
    CONTACTED = "contacted"
    VIEWING = "viewing"
    NEGOTIATING = "negotiating"
    OFFER = "offer"
    CLOSED = "closed"
    DISCARDED = "discarded"


class ActivityType(str, Enum):
    CALL = "call"
    EMAIL = "email"
    VIEWING = "viewing"
    OFFER = "offer"
    NEGOTIATION = "negotiation"
    CLOSING = "closing"
    NOTE = "note"


class PropertySourceSystem(str, Enum):
    MANUAL = "manual"
    WIDGET = "widget"
    PBM = "pbm"


class PropertySourcePortal(str, Enum):
    IDEALISTA = "idealista"
    FOTOCASA = "fotocasa"
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    RIGHTMOVE = "rightmove"
    KYERO = "kyero"
    OTHER = "other"


# Allowed sources for property prospection (compliance)
ALLOWED_SOURCES: set[str] = {
    "idealista",
    "fotocasa",
    "rightmove",
    "kyero",
    "statefox",
    "properstar",
    "inmobalia",
    "james_edition",
    "luxury_estate",
    "direct",
    "referral",
    "mls",
}


# ═══════════════════════════════════════════════════════════════════════════════
# SCORE MODELS
# ═══════════════════════════════════════════════════════════════════════════════


class ScoreBreakdown(BaseModel):
    """Individual factor contribution to a score."""

    factor: str
    weight: float = Field(ge=0, le=100)
    raw_value: float
    weighted_value: float = Field(ge=0, le=100)


class ScoreResult(BaseModel):
    """Result of a scoring computation."""

    score: float = Field(ge=0, le=100)
    breakdown: Dict[str, float]


# ═══════════════════════════════════════════════════════════════════════════════
# PROPERTY MODELS
# ═══════════════════════════════════════════════════════════════════════════════


class PropertyCreate(BaseModel):
    """Schema for creating a prospected property."""

    source: str
    source_url: Optional[str] = None
    title: Optional[str] = None
    zone: Optional[str] = None
    city: Optional[str] = None
    price: Optional[Decimal] = Field(default=None, ge=0)
    property_type: Optional[str] = None
    bedrooms: Optional[int] = Field(default=None, ge=0)
    bathrooms: Optional[int] = Field(default=None, ge=0)
    area_m2: Optional[Decimal] = Field(default=None, ge=0)
    useful_area_m2: Optional[Decimal] = Field(default=None, ge=0)
    built_area_m2: Optional[Decimal] = Field(default=None, ge=0)
    plot_area_m2: Optional[Decimal] = Field(default=None, ge=0)
    status: PropertyStatus = PropertyStatus.NEW
    source_system: PropertySourceSystem = PropertySourceSystem.MANUAL
    source_portal: Optional[PropertySourcePortal] = None
    notes: Optional[str] = None

    @model_validator(mode="after")
    def validate_surface_areas(self) -> "PropertyCreate":
        """Ensure useful_area_m2 <= built_area_m2 when both are set."""
        if (
            self.useful_area_m2 is not None
            and self.built_area_m2 is not None
            and self.useful_area_m2 > self.built_area_m2
        ):
            msg = f"useful_area_m2 ({self.useful_area_m2}) must be <= built_area_m2 ({self.built_area_m2})"
            raise ValueError(msg)
        return self

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: str) -> str:
        """Validate source is from allowed list (compliance)."""
        normalized: str = v.lower().strip()
        if normalized not in ALLOWED_SOURCES:
            msg = f"Source '{v}' is not authorized. Allowed: {sorted(ALLOWED_SOURCES)}"
            raise ValueError(msg)
        return normalized

    @field_validator("source_portal", mode="before")
    @classmethod
    def normalize_portal(cls, v: Any) -> Any:
        """Normalize source_portal string to enum value."""
        if isinstance(v, str) and v.strip():
            normalized = v.lower().strip()
            try:
                return PropertySourcePortal(normalized)
            except ValueError:
                return PropertySourcePortal.OTHER
        return v


class PropertyUpdate(BaseModel):
    """Schema for updating a prospected property."""

    source: Optional[str] = None
    source_url: Optional[str] = None
    title: Optional[str] = None
    zone: Optional[str] = None
    city: Optional[str] = None
    price: Optional[Decimal] = Field(default=None, ge=0)
    property_type: Optional[str] = None
    bedrooms: Optional[int] = Field(default=None, ge=0)
    bathrooms: Optional[int] = Field(default=None, ge=0)
    area_m2: Optional[Decimal] = Field(default=None, ge=0)
    useful_area_m2: Optional[Decimal] = Field(default=None, ge=0)
    built_area_m2: Optional[Decimal] = Field(default=None, ge=0)
    plot_area_m2: Optional[Decimal] = Field(default=None, ge=0)
    status: Optional[PropertyStatus] = None
    source_system: Optional[PropertySourceSystem] = None
    source_portal: Optional[PropertySourcePortal] = None
    notes: Optional[str] = None

    @model_validator(mode="after")
    def validate_surface_areas(self) -> "PropertyUpdate":
        """Ensure useful_area_m2 <= built_area_m2 when both are set."""
        if (
            self.useful_area_m2 is not None
            and self.built_area_m2 is not None
            and self.useful_area_m2 > self.built_area_m2
        ):
            msg = f"useful_area_m2 ({self.useful_area_m2}) must be <= built_area_m2 ({self.built_area_m2})"
            raise ValueError(msg)
        return self


class PropertyResponse(BaseModel):
    """Response schema for a prospected property."""

    id: UUID
    org_id: UUID
    source: str
    source_url: Optional[str] = None
    title: Optional[str] = None
    zone: Optional[str] = None
    city: Optional[str] = None
    price: Optional[Decimal] = None
    property_type: Optional[str] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    area_m2: Optional[Decimal] = None
    useful_area_m2: Optional[Decimal] = None
    built_area_m2: Optional[Decimal] = None
    plot_area_m2: Optional[Decimal] = None
    high_ticket_score: Optional[Decimal] = None
    score_breakdown: Dict[str, Any] = Field(default_factory=dict)
    status: str
    source_system: str
    source_portal: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PropertyList(BaseModel):
    """Paginated list of properties."""

    items: List[PropertyResponse]
    total: int
    limit: int
    offset: int


# ═══════════════════════════════════════════════════════════════════════════════
# BUYER MODELS
# ═══════════════════════════════════════════════════════════════════════════════


class BuyerCreate(BaseModel):
    """Schema for creating a buyer profile."""

    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    budget_min: Optional[Decimal] = Field(default=None, ge=0)
    budget_max: Optional[Decimal] = Field(default=None, ge=0)
    preferred_zones: List[str] = Field(default_factory=list)
    preferred_types: List[str] = Field(default_factory=list)
    required_features: Dict[str, Any] = Field(default_factory=dict)
    purchase_horizon: Optional[str] = None
    motivation_score: Optional[Decimal] = Field(default=None, ge=0, le=100)
    source_type: BuyerSourceType = BuyerSourceType.MANUAL
    source_platform: BuyerSourcePlatform = BuyerSourcePlatform.MANUAL
    referral_partner_name: Optional[str] = None
    referral_partner_contact: Optional[str] = None
    referral_partner_type: Optional[BuyerReferralPartnerType] = None
    referral_terms: Optional[str] = None
    buyer_intro_status: BuyerIntroStatus = BuyerIntroStatus.NEW
    trust_score: Optional[Decimal] = Field(default=None, ge=0, le=100)
    intent_score: Optional[Decimal] = Field(default=None, ge=0, le=100)
    capacity_score: Optional[Decimal] = Field(default=None, ge=0, le=100)
    intelligence_pack_id: Optional[UUID] = None
    source_details: Dict[str, Any] = Field(default_factory=dict)
    last_partner_touch_at: Optional[datetime] = None
    status: BuyerStatus = BuyerStatus.ACTIVE
    notes: Optional[str] = None

    @model_validator(mode="after")
    def validate_budget_range(self) -> "BuyerCreate":
        """Ensure budget_min <= budget_max when both are set."""
        if (
            self.budget_min is not None
            and self.budget_max is not None
            and self.budget_min > self.budget_max
        ):
            msg = f"budget_min ({self.budget_min}) must be <= budget_max ({self.budget_max})"
            raise ValueError(msg)
        return self


class BuyerUpdate(BaseModel):
    """Schema for updating a buyer profile."""

    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    budget_min: Optional[Decimal] = Field(default=None, ge=0)
    budget_max: Optional[Decimal] = Field(default=None, ge=0)
    preferred_zones: Optional[List[str]] = None
    preferred_types: Optional[List[str]] = None
    required_features: Optional[Dict[str, Any]] = None
    purchase_horizon: Optional[str] = None
    motivation_score: Optional[Decimal] = Field(default=None, ge=0, le=100)
    source_type: Optional[BuyerSourceType] = None
    source_platform: Optional[BuyerSourcePlatform] = None
    referral_partner_name: Optional[str] = None
    referral_partner_contact: Optional[str] = None
    referral_partner_type: Optional[BuyerReferralPartnerType] = None
    referral_terms: Optional[str] = None
    buyer_intro_status: Optional[BuyerIntroStatus] = None
    trust_score: Optional[Decimal] = Field(default=None, ge=0, le=100)
    intent_score: Optional[Decimal] = Field(default=None, ge=0, le=100)
    capacity_score: Optional[Decimal] = Field(default=None, ge=0, le=100)
    intelligence_pack_id: Optional[UUID] = None
    source_details: Optional[Dict[str, Any]] = None
    last_partner_touch_at: Optional[datetime] = None
    status: Optional[BuyerStatus] = None
    notes: Optional[str] = None


class BuyerResponse(BaseModel):
    """Response schema for a buyer profile."""

    id: UUID
    org_id: UUID
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    budget_min: Optional[Decimal] = None
    budget_max: Optional[Decimal] = None
    preferred_zones: List[str] = Field(default_factory=list)
    preferred_types: List[str] = Field(default_factory=list)
    required_features: Dict[str, Any] = Field(default_factory=dict)
    purchase_horizon: Optional[str] = None
    motivation_score: Optional[Decimal] = None
    source_type: str
    source_platform: str
    referral_partner_name: Optional[str] = None
    referral_partner_contact: Optional[str] = None
    referral_partner_type: Optional[str] = None
    referral_terms: Optional[str] = None
    buyer_intro_status: str
    trust_score: Optional[Decimal] = None
    intent_score: Optional[Decimal] = None
    capacity_score: Optional[Decimal] = None
    intelligence_pack_id: Optional[UUID] = None
    source_details: Dict[str, Any] = Field(default_factory=dict)
    last_partner_touch_at: Optional[datetime] = None
    status: str
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BuyerList(BaseModel):
    """Paginated list of buyers."""

    items: List[BuyerResponse]
    total: int
    limit: int
    offset: int


# ═══════════════════════════════════════════════════════════════════════════════
# MATCH MODELS
# ═══════════════════════════════════════════════════════════════════════════════


class MatchUpdate(BaseModel):
    """Schema for updating a match."""

    match_status: Optional[MatchStatus] = None
    commission_estimate: Optional[Decimal] = Field(default=None, ge=0)
    notes: Optional[str] = None


class MatchResponse(BaseModel):
    """Response schema for a property-buyer match."""

    id: UUID
    org_id: UUID
    property_id: UUID
    buyer_id: UUID
    match_score: Decimal
    score_breakdown: Dict[str, Any] = Field(default_factory=dict)
    match_status: str
    commission_estimate: Optional[Decimal] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    # Denormalized for frontend display
    property_title: Optional[str] = None
    buyer_name: Optional[str] = None

    class Config:
        from_attributes = True


class MatchList(BaseModel):
    """Paginated list of matches."""

    items: List[MatchResponse]
    total: int
    limit: int
    offset: int


# ═══════════════════════════════════════════════════════════════════════════════
# ACTIVITY MODELS
# ═══════════════════════════════════════════════════════════════════════════════


class ActivityCreate(BaseModel):
    """Schema for logging a match activity."""

    activity_type: ActivityType
    outcome: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class ActivityResponse(BaseModel):
    """Response schema for a match activity."""

    id: UUID
    org_id: UUID
    match_id: UUID
    activity_type: str
    outcome: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    created_by: Optional[UUID] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ActivityList(BaseModel):
    """List of activities for a match."""

    items: List[ActivityResponse]
    total: int


# ═══════════════════════════════════════════════════════════════════════════════
# RECOMPUTE REQUEST
# ═══════════════════════════════════════════════════════════════════════════════


class RecomputeRequest(BaseModel):
    """Request to recompute match scores."""

    property_ids: Optional[List[UUID]] = None
    buyer_ids: Optional[List[UUID]] = None


class RecomputeResponse(BaseModel):
    """Response from recompute operation."""

    matches_created: int
    matches_updated: int
    total_computed: int


# ═══════════════════════════════════════════════════════════════════════════════
# WORKSPACE ACTION MODELS
# ═══════════════════════════════════════════════════════════════════════════════


class WorkspaceEntityType(str, Enum):
    PROPERTY = "property"
    BUYER = "buyer"
    MATCH = "match"


class FollowupTaskActionRequest(BaseModel):
    entity_type: WorkspaceEntityType
    entity_id: UUID
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    assigned_user_id: Optional[UUID] = None


class MarkReviewedActionRequest(BaseModel):
    entity_type: WorkspaceEntityType
    entity_id: UUID
    note: Optional[str] = None


class WorkspaceActionResponse(BaseModel):
    ok: bool = True
    action: str
    entity_type: WorkspaceEntityType
    entity_id: UUID
    task_id: Optional[UUID] = None
    message: str
