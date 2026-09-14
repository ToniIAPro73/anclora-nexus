"""Anclora Intake Contract v1 — canonical types and validation."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Literal, Optional
from pydantic import BaseModel, Field, model_validator


class IntakeSource(str, Enum):
    PRIVATE_ESTATES_LANDING = "private_estates_landing"
    PRIVATE_ESTATES_WEB = "private_estates_web"
    SYNERGI_APP = "synergi_app"
    DATA_LAB_APP = "data_lab_app"
    SYNCXML_LANDING = "syncxml_landing"
    GUESTHUB_APP = "guesthub_app"
    NEXUS_MANUAL = "nexus_manual"
    EXTERNAL_API = "external_api"


class IntakeDomain(str, Enum):
    ACCESS_REQUEST = "access_request"
    COMMERCIAL_LEAD = "commercial_lead"


class IntakeRequestType(str, Enum):
    # Access request domain
    PILOT_REQUEST = "pilot_request"
    ACCESS_REQUEST = "access_request"
    PARTNER_ADMISSION = "partner_admission"
    WORKSPACE_ACCESS_REQUEST = "workspace_access_request"
    # Commercial lead domain
    SELLER_VALUATION_REQUEST = "seller_valuation_request"
    SELLER_LEAD = "seller_lead"
    BUYER_LEAD = "buyer_lead"
    PROPERTY_INQUIRY = "property_inquiry"
    GENERAL_COMMERCIAL_INQUIRY = "general_commercial_inquiry"
    VACATION_RENTAL_MANAGEMENT_INTEREST = "vacation_rental_management_interest"


ACCESS_REQUEST_TYPES = {
    IntakeRequestType.PILOT_REQUEST,
    IntakeRequestType.ACCESS_REQUEST,
    IntakeRequestType.PARTNER_ADMISSION,
    IntakeRequestType.WORKSPACE_ACCESS_REQUEST,
}

COMMERCIAL_LEAD_TYPES = {
    IntakeRequestType.SELLER_VALUATION_REQUEST,
    IntakeRequestType.SELLER_LEAD,
    IntakeRequestType.BUYER_LEAD,
    IntakeRequestType.PROPERTY_INQUIRY,
    IntakeRequestType.GENERAL_COMMERCIAL_INQUIRY,
    IntakeRequestType.VACATION_RENTAL_MANAGEMENT_INTEREST,
}


class TargetProduct(str, Enum):
    GUESTHUB = "guesthub"
    SYNERGI = "synergi"
    DATA_LAB = "data_lab"
    # Legacy compatibility alias - normalized immediately to GUESTHUB
    SYNCXML = "syncxml"


class ServiceInterest(str, Enum):
    PROPERTY_SALE = "property_sale"
    PROPERTY_PURCHASE = "property_purchase"
    PROPERTY_VALUATION = "property_valuation"
    VACATION_RENTAL_MANAGEMENT = "vacation_rental_management"
    DOCUMENT_MANAGEMENT = "document_management"
    ENERGY_ASSESSMENT = "energy_assessment"
    OTHER = "other"


class RoutingTargetDomain(str, Enum):
    ACCESS_REQUESTS = "access_requests"
    LEADS = "leads"
    VALUATIONS = "valuations"
    BUYERS = "buyers"


# Source → required product mapping for access requests
_SOURCE_PRODUCT_MAP: dict[IntakeSource, TargetProduct] = {
    IntakeSource.SYNCXML_LANDING: TargetProduct.GUESTHUB,
    IntakeSource.GUESTHUB_APP: TargetProduct.GUESTHUB,
    IntakeSource.DATA_LAB_APP: TargetProduct.DATA_LAB,
    IntakeSource.SYNERGI_APP: TargetProduct.SYNERGI,
}

# Sources that must never create access_requests (none currently blocked, landing sources are allowed)
_COMMERCIAL_ONLY_SOURCES: set[IntakeSource] = set()


class IntakeApplicant(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    organization_name: Optional[str] = None
    preferred_language: Optional[str] = None


class IntakeContext(BaseModel):
    message: Optional[str] = None
    property_reference: Optional[str] = None
    property_interest: Optional[str] = None
    location: Optional[str] = None
    request_metadata: Optional[Dict[str, Any]] = None


class IntakeConsent(BaseModel):
    privacy_accepted: Optional[bool] = None
    consent_timestamp: Optional[str] = None
    consent_version: Optional[str] = None
    marketing_opt_in: Optional[bool] = None


class IntakeRouting(BaseModel):
    target_domain: RoutingTargetDomain
    assigned_owner_id: Optional[str] = None
    classification_reason: Optional[str] = None


class AncloraIntakeV1(BaseModel):
    """Canonical intake entry for all Anclora products.

    Validates cross-field constraints defined in ANCLORA_INTAKE_CONTRACT_V1.md.
    """

    schema_version: Literal["anclora-intake-v1"] = "anclora-intake-v1"

    intake_domain: IntakeDomain
    request_type: IntakeRequestType

    source: IntakeSource
    source_url: Optional[str] = None
    source_referrer: Optional[str] = None
    source_submission_id: Optional[str] = None

    target_product: Optional[TargetProduct] = None
    service_interest: Optional[ServiceInterest] = None

    applicant: IntakeApplicant = Field(default_factory=IntakeApplicant)
    context: IntakeContext = Field(default_factory=IntakeContext)
    consent: IntakeConsent = Field(default_factory=IntakeConsent)
    routing: Optional[IntakeRouting] = None

    idempotency_key: str

    @model_validator(mode="after")
    def validate_contract_rules(self) -> "AncloraIntakeV1":
        # Normalization: syncxml is legacy compatibility alias for guesthub
        if self.target_product == TargetProduct.SYNCXML:
            self.target_product = TargetProduct.GUESTHUB

        # Rule 1: access_request domain requires target_product
        if self.intake_domain == IntakeDomain.ACCESS_REQUEST and self.target_product is None:
            raise ValueError(
                "target_product is required when intake_domain is 'access_request'"
            )

        # Rule 2: commercial_lead must have null target_product
        if self.intake_domain == IntakeDomain.COMMERCIAL_LEAD and self.target_product is not None:
            raise ValueError(
                "target_product must be null for commercial_lead entries"
            )

        # Rule 3: source-product coherence for access requests
        if self.intake_domain == IntakeDomain.ACCESS_REQUEST and self.source in _SOURCE_PRODUCT_MAP:
            expected = _SOURCE_PRODUCT_MAP[self.source]
            if self.target_product != expected:
                raise ValueError(
                    f"source '{self.source}' requires target_product '{expected}', "
                    f"got '{self.target_product}'"
                )

        # Rule 6: commercial-only sources cannot create access requests
        if self.source in _COMMERCIAL_ONLY_SOURCES and self.intake_domain == IntakeDomain.ACCESS_REQUEST:
            raise ValueError(
                f"source '{self.source}' cannot create an access_request. "
                "Use intake_domain='commercial_lead' for this source."
            )

        # Rule: request_type must match intake_domain
        if self.intake_domain == IntakeDomain.ACCESS_REQUEST and self.request_type not in ACCESS_REQUEST_TYPES:
            raise ValueError(
                f"request_type '{self.request_type}' is not valid for intake_domain 'access_request'"
            )
        if self.intake_domain == IntakeDomain.COMMERCIAL_LEAD and self.request_type not in COMMERCIAL_LEAD_TYPES:
            raise ValueError(
                f"request_type '{self.request_type}' is not valid for intake_domain 'commercial_lead'"
            )

        return self


def resolve_routing(domain: IntakeDomain, request_type: IntakeRequestType) -> RoutingTargetDomain:
    """Deterministic routing table: intake_domain + request_type → Nexus operational domain."""
    if domain == IntakeDomain.ACCESS_REQUEST:
        return RoutingTargetDomain.ACCESS_REQUESTS

    # commercial_lead routing by request_type
    if request_type == IntakeRequestType.SELLER_VALUATION_REQUEST:
        return RoutingTargetDomain.VALUATIONS
    if request_type == IntakeRequestType.BUYER_LEAD:
        return RoutingTargetDomain.BUYERS
    # seller_lead, property_inquiry, general_commercial_inquiry, vacation_rental_management_interest → leads
    return RoutingTargetDomain.LEADS
