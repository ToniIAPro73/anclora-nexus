"""
Tests for Anclora Intake Contract v1.

Covers:
  - Contract validation (valid and invalid combinations)
  - Routing table
  - Semantic rules (source-product coherence, domain constraints)
"""

import pytest

from backend.models.intake_contract import (
    AncloraIntakeV1,
    IntakeDomain,
    IntakeRequestType,
    IntakeSource,
    RoutingTargetDomain,
    TargetProduct,
    resolve_routing,
)


def _base(
    intake_domain=IntakeDomain.ACCESS_REQUEST,
    request_type=IntakeRequestType.PILOT_REQUEST,
    source=IntakeSource.SYNCXML_LANDING,
    target_product=TargetProduct.SYNCXML,
    service_interest=None,
    idempotency_key="test-key-001",
):
    return dict(
        schema_version="anclora-intake-v1",
        intake_domain=intake_domain,
        request_type=request_type,
        source=source,
        target_product=target_product,
        service_interest=service_interest,
        idempotency_key=idempotency_key,
    )


# ─── Section A: Valid contract combinations ──────────────────────────────────

def test_syncxml_pilot_valid():
    """SyncXML landing + pilot_request + syncxml → valid."""
    contract = AncloraIntakeV1(**_base())
    # Legacy SYNCXML alias is normalized to GUESTHUB.
    assert contract.target_product == TargetProduct.GUESTHUB
    assert contract.intake_domain == IntakeDomain.ACCESS_REQUEST


def test_data_lab_access_valid():
    """Data Lab app + access_request + data_lab → valid."""
    data = _base(
        intake_domain=IntakeDomain.ACCESS_REQUEST,
        request_type=IntakeRequestType.ACCESS_REQUEST,
        source=IntakeSource.DATA_LAB_APP,
        target_product=TargetProduct.DATA_LAB,
    )
    contract = AncloraIntakeV1(**data)
    assert contract.target_product == TargetProduct.DATA_LAB


def test_synergi_admission_valid():
    """Synergi app + partner_admission + synergi → valid."""
    data = _base(
        intake_domain=IntakeDomain.ACCESS_REQUEST,
        request_type=IntakeRequestType.PARTNER_ADMISSION,
        source=IntakeSource.SYNERGI_APP,
        target_product=TargetProduct.SYNERGI,
    )
    contract = AncloraIntakeV1(**data)
    assert contract.target_product == TargetProduct.SYNERGI


def test_pe_landing_seller_valuation_valid():
    """PE Landing + seller_valuation_request + null → valid commercial lead."""
    data = _base(
        intake_domain=IntakeDomain.COMMERCIAL_LEAD,
        request_type=IntakeRequestType.SELLER_VALUATION_REQUEST,
        source=IntakeSource.PRIVATE_ESTATES_LANDING,
        target_product=None,
        service_interest="property_valuation",
    )
    contract = AncloraIntakeV1(**data)
    assert contract.target_product is None
    assert contract.intake_domain == IntakeDomain.COMMERCIAL_LEAD


def test_pe_web_buyer_lead_valid():
    """PE web + buyer_lead + null → valid commercial lead."""
    data = _base(
        intake_domain=IntakeDomain.COMMERCIAL_LEAD,
        request_type=IntakeRequestType.BUYER_LEAD,
        source=IntakeSource.PRIVATE_ESTATES_WEB,
        target_product=None,
        service_interest="property_purchase",
    )
    contract = AncloraIntakeV1(**data)
    assert contract.target_product is None


def test_pe_web_vacation_rental_interest_valid():
    """PE web + vacation_rental_management_interest + null → valid commercial lead."""
    data = _base(
        intake_domain=IntakeDomain.COMMERCIAL_LEAD,
        request_type=IntakeRequestType.VACATION_RENTAL_MANAGEMENT_INTEREST,
        source=IntakeSource.PRIVATE_ESTATES_WEB,
        target_product=None,
        service_interest="vacation_rental_management",
    )
    contract = AncloraIntakeV1(**data)
    assert contract.request_type == IntakeRequestType.VACATION_RENTAL_MANAGEMENT_INTEREST


# ─── Section B: Invalid combinations that must be rejected ───────────────────

def test_syncxml_landing_with_synergi_product_rejected():
    """SyncXML landing + target_product=synergi → INVALID (rule 3)."""
    data = _base(
        source=IntakeSource.SYNCXML_LANDING,
        target_product=TargetProduct.SYNERGI,
    )
    with pytest.raises(ValueError, match="target_product"):
        AncloraIntakeV1(**data)


def test_syncxml_landing_with_null_product_rejected():
    """SyncXML landing + target_product=null → INVALID (rule 1 + 3)."""
    data = _base(
        source=IntakeSource.SYNCXML_LANDING,
        target_product=None,
    )
    with pytest.raises(ValueError):
        AncloraIntakeV1(**data)


def test_commercial_lead_with_target_product_rejected():
    """Commercial lead + target_product=syncxml → INVALID (rule 2)."""
    data = _base(
        intake_domain=IntakeDomain.COMMERCIAL_LEAD,
        request_type=IntakeRequestType.SELLER_LEAD,
        source=IntakeSource.PRIVATE_ESTATES_LANDING,
        target_product=TargetProduct.SYNCXML,
    )
    with pytest.raises(ValueError, match="null for commercial_lead"):
        AncloraIntakeV1(**data)


def test_pe_landing_can_create_access_request():
    """PE Landing source + access_request domain → VALID (landing sources may create access requests)."""
    data = _base(
        intake_domain=IntakeDomain.ACCESS_REQUEST,
        request_type=IntakeRequestType.PILOT_REQUEST,
        source=IntakeSource.PRIVATE_ESTATES_LANDING,
        target_product=TargetProduct.SYNCXML,
    )
    contract = AncloraIntakeV1(**data)
    assert contract.intake_domain == IntakeDomain.ACCESS_REQUEST


def test_pe_web_can_create_access_request():
    """PE web source + access_request domain → VALID (no source is commercial-only today)."""
    data = _base(
        intake_domain=IntakeDomain.ACCESS_REQUEST,
        request_type=IntakeRequestType.PILOT_REQUEST,
        source=IntakeSource.PRIVATE_ESTATES_WEB,
        target_product=TargetProduct.SYNCXML,
    )
    contract = AncloraIntakeV1(**data)
    assert contract.intake_domain == IntakeDomain.ACCESS_REQUEST


def test_wrong_request_type_for_access_domain_rejected():
    """Access request domain + seller_lead request_type → INVALID."""
    data = _base(
        intake_domain=IntakeDomain.ACCESS_REQUEST,
        request_type=IntakeRequestType.SELLER_LEAD,
        source=IntakeSource.SYNCXML_LANDING,
        target_product=TargetProduct.SYNCXML,
    )
    with pytest.raises(ValueError, match="not valid for intake_domain"):
        AncloraIntakeV1(**data)


def test_wrong_request_type_for_commercial_domain_rejected():
    """Commercial lead domain + pilot_request request_type → INVALID."""
    data = _base(
        intake_domain=IntakeDomain.COMMERCIAL_LEAD,
        request_type=IntakeRequestType.PILOT_REQUEST,
        source=IntakeSource.PRIVATE_ESTATES_LANDING,
        target_product=None,
    )
    with pytest.raises(ValueError, match="not valid for intake_domain"):
        AncloraIntakeV1(**data)


def test_access_request_requires_target_product():
    """Access request without target_product → INVALID (rule 1)."""
    data = _base(
        source=IntakeSource.NEXUS_MANUAL,
        target_product=None,
    )
    with pytest.raises(ValueError, match="target_product is required"):
        AncloraIntakeV1(**data)


# ─── Section C: Routing table ─────────────────────────────────────────────────

def test_routing_access_request_goes_to_access_requests():
    assert resolve_routing(IntakeDomain.ACCESS_REQUEST, IntakeRequestType.PILOT_REQUEST) == RoutingTargetDomain.ACCESS_REQUESTS
    assert resolve_routing(IntakeDomain.ACCESS_REQUEST, IntakeRequestType.PARTNER_ADMISSION) == RoutingTargetDomain.ACCESS_REQUESTS
    assert resolve_routing(IntakeDomain.ACCESS_REQUEST, IntakeRequestType.ACCESS_REQUEST) == RoutingTargetDomain.ACCESS_REQUESTS


def test_routing_seller_valuation_goes_to_valuations():
    assert resolve_routing(IntakeDomain.COMMERCIAL_LEAD, IntakeRequestType.SELLER_VALUATION_REQUEST) == RoutingTargetDomain.VALUATIONS


def test_routing_buyer_lead_goes_to_buyers():
    assert resolve_routing(IntakeDomain.COMMERCIAL_LEAD, IntakeRequestType.BUYER_LEAD) == RoutingTargetDomain.BUYERS


def test_routing_seller_lead_goes_to_leads():
    assert resolve_routing(IntakeDomain.COMMERCIAL_LEAD, IntakeRequestType.SELLER_LEAD) == RoutingTargetDomain.LEADS


def test_routing_vacation_rental_goes_to_leads():
    assert resolve_routing(IntakeDomain.COMMERCIAL_LEAD, IntakeRequestType.VACATION_RENTAL_MANAGEMENT_INTEREST) == RoutingTargetDomain.LEADS


def test_routing_property_inquiry_goes_to_leads():
    assert resolve_routing(IntakeDomain.COMMERCIAL_LEAD, IntakeRequestType.PROPERTY_INQUIRY) == RoutingTargetDomain.LEADS


def test_routing_pe_landing_seller_never_goes_to_access_requests():
    """PE Landing seller → leads or valuations, never access_requests."""
    result = resolve_routing(IntakeDomain.COMMERCIAL_LEAD, IntakeRequestType.SELLER_LEAD)
    assert result != RoutingTargetDomain.ACCESS_REQUESTS


def test_routing_pe_web_buyer_never_goes_to_access_requests():
    result = resolve_routing(IntakeDomain.COMMERCIAL_LEAD, IntakeRequestType.BUYER_LEAD)
    assert result != RoutingTargetDomain.ACCESS_REQUESTS


def test_routing_vacation_rental_interest_never_goes_to_access_requests():
    result = resolve_routing(IntakeDomain.COMMERCIAL_LEAD, IntakeRequestType.VACATION_RENTAL_MANAGEMENT_INTEREST)
    assert result != RoutingTargetDomain.ACCESS_REQUESTS
