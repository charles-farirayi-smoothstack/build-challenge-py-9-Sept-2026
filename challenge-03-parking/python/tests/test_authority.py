from datetime import date, datetime
from decimal import Decimal

import pytest

from parking import (
    AppealOutcome,
    CitationStatus,
    ParkingAuthority,
    ParkingObservation,
    PermitType,
    ViolationCode,
    ZoneType,
)


@pytest.fixture
def authority():
    a = ParkingAuthority()
    a.register_vehicle("AAA111", "CA", "Alice Anders")
    a.register_vehicle("BBB222", "CA", "Bob Brown")
    return a


def issue_no_permit_citation(authority, plate, issued_on):
    result = authority.evaluate_observation(
        ParkingObservation(plate, "Elm St", ZoneType.RESIDENTIAL,
                            datetime.combine(issued_on, datetime.min.time().replace(hour=20)),
                            None, False)
    )
    assert not result.legal
    assert result.violation_code is ViolationCode.NO_PERMIT
    return result.citation


# ----------------------------------------------------------------------
# Zone / permit legality
# ----------------------------------------------------------------------

def test_metered_zone_is_free_outside_paid_hours(authority):
    result = authority.evaluate_observation(
        ParkingObservation("AAA111", "Main St", ZoneType.METERED,
                            datetime(2026, 3, 2, 7, 59), None, False)  # Monday, before 08:00
    )
    assert result.legal


def test_metered_zone_is_free_on_sunday(authority):
    result = authority.evaluate_observation(
        ParkingObservation("AAA111", "Main St", ZoneType.METERED,
                            datetime(2026, 3, 1, 12, 0), None, False)  # Sunday
    )
    assert result.legal


def test_metered_zone_requires_payment_during_paid_hours(authority):
    result = authority.evaluate_observation(
        ParkingObservation("AAA111", "Main St", ZoneType.METERED,
                            datetime(2026, 3, 2, 8, 0), None, False)  # Monday 08:00, no payment
    )
    assert not result.legal
    assert result.violation_code is ViolationCode.EXPIRED_METER
    assert result.citation.base_fine == Decimal("35.00")


def test_metered_zone_end_of_paid_window_is_free(authority):
    # 18:00 is up to but not including - so 18:00 itself is free.
    result = authority.evaluate_observation(
        ParkingObservation("AAA111", "Main St", ZoneType.METERED,
                            datetime(2026, 3, 2, 18, 0), None, False)
    )
    assert result.legal


def test_metered_zone_legal_when_paid_through_observation_time(authority):
    result = authority.evaluate_observation(
        ParkingObservation("AAA111", "Main St", ZoneType.METERED,
                            datetime(2026, 3, 2, 10, 0), datetime(2026, 3, 2, 10, 0), False)
    )
    assert result.legal


def test_residential_zone_requires_permit_overnight_wrapping_midnight(authority):
    night = authority.evaluate_observation(
        ParkingObservation("AAA111", "Elm St", ZoneType.RESIDENTIAL,
                            datetime(2026, 3, 2, 23, 0), None, False)
    )
    assert not night.legal
    assert night.violation_code is ViolationCode.NO_PERMIT

    early_morning = authority.evaluate_observation(
        ParkingObservation("AAA111", "Elm St", ZoneType.RESIDENTIAL,
                            datetime(2026, 3, 3, 3, 0), None, False)
    )
    assert not early_morning.legal
    assert early_morning.violation_code is ViolationCode.NO_PERMIT


def test_residential_zone_is_free_during_the_day(authority):
    result = authority.evaluate_observation(
        ParkingObservation("AAA111", "Elm St", ZoneType.RESIDENTIAL,
                            datetime(2026, 3, 2, 12, 0), None, False)
    )
    assert result.legal


def test_resident_permit_only_valid_in_its_named_zone(authority):
    authority.issue_permit("AAA111", PermitType.RESIDENT, "Elm St", date(2026, 1, 1))

    same_zone = authority.evaluate_observation(
        ParkingObservation("AAA111", "Elm St", ZoneType.RESIDENTIAL,
                            datetime(2026, 3, 2, 20, 0), None, False)
    )
    assert same_zone.legal

    other_zone = authority.evaluate_observation(
        ParkingObservation("AAA111", "Oak Ave", ZoneType.RESIDENTIAL,
                            datetime(2026, 3, 2, 20, 0), None, False)
    )
    assert not other_zone.legal
    assert other_zone.violation_code is ViolationCode.NO_PERMIT


def test_accessible_permit_valid_in_residential_zone_and_exempts_meter_payment(authority):
    authority.issue_permit("BBB222", PermitType.ACCESSIBLE, None, date(2026, 1, 1))

    residential = authority.evaluate_observation(
        ParkingObservation("BBB222", "Any Residential Zone", ZoneType.RESIDENTIAL,
                            datetime(2026, 3, 2, 20, 0), None, False)
    )
    assert residential.legal

    metered = authority.evaluate_observation(
        ParkingObservation("BBB222", "Main St", ZoneType.METERED,
                            datetime(2026, 3, 2, 10, 0), None, False)
    )
    assert metered.legal


def test_hydrant_blocking_takes_priority_over_everything_else_at_any_hour(authority):
    # Free hour (Sunday, metered) but blocking a hydrant -> still cited.
    result = authority.evaluate_observation(
        ParkingObservation("AAA111", "Main St", ZoneType.METERED,
                            datetime(2026, 3, 1, 3, 0), None, True)
    )
    assert not result.legal
    assert result.violation_code is ViolationCode.BLOCKING_HYDRANT
    assert result.citation.base_fine == Decimal("150.00")


def test_permit_expiry_honours_feb29_rollover(authority):
    permit = authority.issue_permit("AAA111", PermitType.RESIDENT, "Elm St", date(2024, 2, 29))
    assert permit.expires_on == date(2025, 2, 28)

    permit2 = authority.issue_permit("AAA111", PermitType.RESIDENT, "Elm St", date(2026, 1, 10))
    assert permit2.expires_on == date(2027, 1, 10)


def test_permit_is_invalid_on_or_after_expiry_date(authority):
    authority.issue_permit("AAA111", PermitType.RESIDENT, "Elm St", date(2026, 1, 10))

    on_expiry = authority.evaluate_observation(
        ParkingObservation("AAA111", "Elm St", ZoneType.RESIDENTIAL,
                            datetime(2027, 1, 10, 20, 0), None, False)
    )
    assert not on_expiry.legal

    before_expiry = authority.evaluate_observation(
        ParkingObservation("AAA111", "Elm St", ZoneType.RESIDENTIAL,
                            datetime(2027, 1, 9, 20, 0), None, False)
    )
    assert before_expiry.legal


# ----------------------------------------------------------------------
# Appeals
# ----------------------------------------------------------------------

def test_appeal_filed_on_day_14_is_accepted_and_day_15_is_rejected(authority):
    c1 = issue_no_permit_citation(authority, "AAA111", date(2026, 3, 1))
    on_time = authority.file_appeal(c1.citation_id, date(2026, 3, 15))  # day 14
    assert on_time.accepted

    c2 = issue_no_permit_citation(authority, "AAA111", date(2026, 3, 1))
    too_late = authority.file_appeal(c2.citation_id, date(2026, 3, 16))  # day 15
    assert not too_late.accepted
    assert c2.status is CitationStatus.ISSUED


def test_dismissed_appeal_zeroes_balance(authority):
    citation = issue_no_permit_citation(authority, "AAA111", date(2026, 3, 1))
    authority.file_appeal(citation.citation_id, date(2026, 3, 5))
    authority.resolve_appeal(citation.citation_id, AppealOutcome.DISMISSED, date(2026, 3, 10))

    assert citation.status is CitationStatus.DISMISSED
    assert citation.balance == Decimal("0.00")


def test_upheld_appeal_keeps_balance_owed_and_resumes_escalation_clock(authority):
    citation = issue_no_permit_citation(authority, "AAA111", date(2026, 3, 1))
    authority.file_appeal(citation.citation_id, date(2026, 3, 5))
    authority.resolve_appeal(citation.citation_id, AppealOutcome.UPHELD, date(2026, 3, 12))

    assert citation.status is CitationStatus.UPHELD
    assert citation.balance == Decimal("60.00")


# ----------------------------------------------------------------------
# Worked example: appeal-pause escalation day counting.
# ----------------------------------------------------------------------

def test_worked_example_escalation_penalty_lands_on_april_11_not_march_22(authority):
    citation = issue_no_permit_citation(authority, "AAA111", date(2026, 3, 1))

    appeal = authority.file_appeal(citation.citation_id, date(2026, 3, 10))
    assert appeal.accepted
    authority.resolve_appeal(citation.citation_id, AppealOutcome.UPHELD, date(2026, 3, 30))

    # 9 days accrued before the appeal (Mar 1 -> Mar 10), clock paused until resolution.
    run_on_march_22 = authority.run_escalation(date(2026, 3, 22))
    assert run_on_march_22 == []
    assert not citation.penalty_applied

    # 9 days before + 11 days after resolution (Mar30 -> Apr10) = 20 days: still no penalty.
    run_on_april_10 = authority.run_escalation(date(2026, 4, 10))
    assert run_on_april_10 == []
    assert not citation.penalty_applied

    # 9 days before + 12 days after resolution (Mar30 -> Apr11) = 21 days: penalty applies.
    run_on_april_11 = authority.run_escalation(date(2026, 4, 11))
    assert len(run_on_april_11) == 1
    assert run_on_april_11[0].citation_id == citation.citation_id
    assert citation.penalty_applied
    assert citation.penalty_amount == Decimal("30.00")  # 50% of $60.00
    assert citation.total_owed == Decimal("90.00")

    # Idempotency: running again on the same, or a later, date must not double the penalty.
    run_again_same_date = authority.run_escalation(date(2026, 4, 11))
    assert run_again_same_date == []
    run_later = authority.run_escalation(date(2026, 5, 1))
    assert run_later == []
    assert citation.total_owed == Decimal("90.00")


# ----------------------------------------------------------------------
# Escalation idempotency (unappealed citation)
# ----------------------------------------------------------------------

def test_run_escalation_applies_penalty_once_after_21_days(authority):
    citation = issue_no_permit_citation(authority, "AAA111", date(2026, 1, 1))

    too_early = authority.run_escalation(date(2026, 1, 21))  # 20 days
    assert too_early == []

    on_time = authority.run_escalation(date(2026, 1, 22))  # 21 days
    assert len(on_time) == 1
    assert citation.total_owed == Decimal("90.00")  # 60 + 30

    second_run_same_date = authority.run_escalation(date(2026, 1, 22))
    assert second_run_same_date == []

    third_run_later_date = authority.run_escalation(date(2026, 6, 1))
    assert third_run_later_date == []
    assert citation.total_owed == Decimal("90.00")


def test_escalation_skips_citations_currently_under_appeal(authority):
    citation = issue_no_permit_citation(authority, "AAA111", date(2026, 1, 1))
    authority.file_appeal(citation.citation_id, date(2026, 1, 5))

    run = authority.run_escalation(date(2026, 2, 1))  # well past 21 days
    assert run == []
    assert not citation.penalty_applied


# ----------------------------------------------------------------------
# Payments
# ----------------------------------------------------------------------

def test_partial_payment_applies_and_citation_remains_unpaid_until_balance_is_zero(authority):
    citation = issue_no_permit_citation(authority, "AAA111", date(2026, 3, 1))  # $60.00

    first = authority.pay_citation(citation.citation_id, Decimal("20.00"))
    assert first.accepted
    assert first.remaining_balance == Decimal("40.00")
    assert citation.status is CitationStatus.ISSUED

    second = authority.pay_citation(citation.citation_id, Decimal("40.00"))
    assert second.accepted
    assert second.remaining_balance == Decimal("0.00")
    assert citation.status is CitationStatus.PAID


def test_payment_exceeding_balance_is_rejected(authority):
    citation = issue_no_permit_citation(authority, "AAA111", date(2026, 3, 1))  # $60.00

    result = authority.pay_citation(citation.citation_id, Decimal("100.00"))
    assert not result.accepted
    assert citation.amount_paid == Decimal("0.00")
    assert citation.status is CitationStatus.ISSUED


def test_paid_citation_never_escalates_again(authority):
    citation = issue_no_permit_citation(authority, "AAA111", date(2026, 1, 1))
    authority.pay_citation(citation.citation_id, Decimal("60.00"))
    assert citation.status is CitationStatus.PAID

    run = authority.run_escalation(date(2026, 6, 1))
    assert run == []
    assert not citation.penalty_applied


def test_payment_applies_to_penalty_before_base_fine(authority):
    citation = issue_no_permit_citation(authority, "AAA111", date(2026, 1, 1))  # $60.00 base
    authority.run_escalation(date(2026, 1, 22))  # now $90.00 total (60 base + 30 penalty)

    result = authority.pay_citation(citation.citation_id, Decimal("30.00"))
    assert result.accepted
    assert result.remaining_balance == Decimal("60.00")
