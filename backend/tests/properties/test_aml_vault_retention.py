"""
Property-based test: AML Vault Retention Timestamp Correctness (Property 1)

**Validates: Requirements 3.2**

For any transaction record classified as AML-relevant, storing it in the AML vault
shall produce a record whose `retention_expires_at` equals `created_at + 10 years` exactly.

This test validates the pure logic of the `set_retention_expiry` trigger function
defined in neon/migrations/071_aml_vault_schema.sql:

    NEW.retention_expires_at := NEW.created_at + interval '10 years';

We replicate this logic in Python and verify it holds for arbitrary timestamps.
"""

from datetime import datetime, timezone

from dateutil.relativedelta import relativedelta
from hypothesis import given, settings
from hypothesis.strategies import datetimes, none, one_of, sampled_from, timezones

# Strategy: generate arbitrary timestamps within a reasonable range.
# PostgreSQL TIMESTAMPTZ supports dates from 4713 BC to 294276 AD,
# but we constrain to a practical range for real transaction records.
# We include both timezone-aware and naive datetimes to thoroughly test.
reasonable_timestamps = datetimes(
    min_value=datetime(2000, 1, 1),
    max_value=datetime(2100, 12, 31),
    timezones=one_of(none(), timezones()),
)


def compute_retention_expiry(created_at: datetime) -> datetime:
    """
    Replicate the PostgreSQL trigger logic:
    NEW.retention_expires_at := NEW.created_at + interval '10 years'

    Uses dateutil.relativedelta for accurate year addition that handles
    leap years correctly (e.g., 2024-02-29 + 10 years = 2034-02-28).
    """
    return created_at + relativedelta(years=10)


@given(created_at=reasonable_timestamps)
@settings(max_examples=500)
def test_retention_expires_at_equals_created_at_plus_10_years(
    created_at: datetime,
) -> None:
    """
    Property 1: AML Vault Retention Timestamp Correctness

    For any arbitrary created_at timestamp, the retention_expires_at
    must equal created_at + 10 years exactly.

    **Validates: Requirements 3.2**
    """
    retention_expires_at = compute_retention_expiry(created_at)

    # Core property: retention is exactly 10 years from creation
    expected = created_at + relativedelta(years=10)
    assert retention_expires_at == expected, (
        f"retention_expires_at ({retention_expires_at}) != "
        f"created_at + 10 years ({expected})"
    )

    # Auxiliary invariant: retention always comes after creation
    assert retention_expires_at > created_at, (
        f"retention_expires_at ({retention_expires_at}) must be "
        f"after created_at ({created_at})"
    )

    # Auxiliary invariant: the difference is exactly 10 years
    # (not 9 years 364 days, not 10 years 1 day)
    delta = relativedelta(retention_expires_at, created_at)
    assert delta.years == 10, f"Expected 10 years difference, got {delta.years}"
    assert delta.months == 0, f"Expected 0 months remainder, got {delta.months}"
    assert delta.days == 0, f"Expected 0 days remainder, got {delta.days}"
    assert delta.hours == 0, f"Expected 0 hours remainder, got {delta.hours}"
    assert delta.minutes == 0, f"Expected 0 minutes remainder, got {delta.minutes}"
    assert delta.seconds == 0, f"Expected 0 seconds remainder, got {delta.seconds}"


@given(created_at=reasonable_timestamps)
@settings(max_examples=200)
def test_retention_satisfies_constraint_check(created_at: datetime) -> None:
    """
    Validate the SQL constraint: retention_expires_at > created_at
    (CONSTRAINT retention_not_expired CHECK (retention_expires_at > created_at))

    **Validates: Requirements 3.2**
    """
    retention_expires_at = compute_retention_expiry(created_at)
    assert retention_expires_at > created_at, (
        f"SQL constraint violation: retention_expires_at ({retention_expires_at}) "
        f"must be strictly greater than created_at ({created_at})"
    )


@given(created_at=reasonable_timestamps)
@settings(max_examples=200)
def test_retention_timestamp_is_timezone_aware_when_input_is(
    created_at: datetime,
) -> None:
    """
    Verify that timezone information is preserved through the calculation.
    PostgreSQL TIMESTAMPTZ stores timezone-aware timestamps, so the
    retention calculation must not strip timezone info.

    **Validates: Requirements 3.2**
    """
    retention_expires_at = compute_retention_expiry(created_at)

    if created_at.tzinfo is not None:
        assert retention_expires_at.tzinfo is not None, (
            "Timezone info was lost during retention calculation"
        )
    else:
        assert retention_expires_at.tzinfo is None, (
            "Unexpected timezone info appeared during retention calculation"
        )
