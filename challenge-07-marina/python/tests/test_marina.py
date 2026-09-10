"""pytest tests for the marina berth reservation and billing system."""

from datetime import date
from decimal import Decimal

import pytest

from marina import Berth, BerthType, Marina, PowerService, Vessel


@pytest.fixture
def m() -> Marina:
    return Marina()


def test_worked_example_peak_boundary_stay_charges_three_nights_at_seasonal_rates(m):
    m.add_berth(Berth("B1", "Dock A", BerthType.SLIP, 45, 16, 8, PowerService.NONE))
    vessel = Vessel("Sea Breeze", "REG-001", 40, 14, 6, PowerService.NONE, "Alice")
    vessel_id = m.register_vessel(vessel)

    result = m.reserve(vessel_id, "B1", date(2024, 5, 30), date(2024, 6, 2))
    assert result.is_success

    invoice = m.generate_invoice(result.reservation.reservation_id, date(2024, 6, 2))

    # 30 May and 31 May at base rate ($2.40 * 40 = $96.00 each), 1 June at 1.5x ($144.00)
    assert invoice.total == Decimal("336.00")

    base_lines = [line for line in invoice.lines if line.line_type == "BASE_RATE"]
    assert len(base_lines) == 3
    by_date = {line.line_date: line.amount for line in base_lines}
    assert by_date[date(2024, 5, 30)] == Decimal("96.00")
    assert by_date[date(2024, 5, 31)] == Decimal("96.00")
    assert by_date[date(2024, 6, 1)] == Decimal("144.00")


def test_vessel_that_fits_no_berth_returns_empty_availability_and_refuses_reservation(m):
    m.add_berth(Berth("B1", "Dock A", BerthType.SLIP, 20, 8, 4, PowerService.NONE))
    huge_vessel = Vessel("Leviathan", "REG-999", 80, 22, 12, PowerService.AMP_50, "Dave")
    vessel_id = m.register_vessel(huge_vessel)

    available = m.find_available_berths(huge_vessel, date(2024, 7, 1), date(2024, 7, 5))
    assert available == []

    result = m.reserve(vessel_id, "B1", date(2024, 7, 1), date(2024, 7, 5))
    assert not result.is_success
    assert result.refusal_reason


def test_arrival_equals_departure_is_rejected(m):
    m.add_berth(Berth("B1", "Dock A", BerthType.SLIP, 45, 16, 8, PowerService.NONE))
    vessel = Vessel("Sea Breeze", "REG-001", 40, 14, 6, PowerService.NONE, "Alice")
    vessel_id = m.register_vessel(vessel)

    same_day = date(2024, 7, 10)
    result = m.reserve(vessel_id, "B1", same_day, same_day)
    assert not result.is_success


def test_overlapping_reservation_by_single_night_is_rejected(m):
    m.add_berth(Berth("B1", "Dock A", BerthType.SLIP, 45, 16, 8, PowerService.NONE))
    vessel1 = Vessel("Sea Breeze", "REG-001", 40, 14, 6, PowerService.NONE, "Alice")
    vessel2 = Vessel("Blue Horizon", "REG-002", 30, 11, 4, PowerService.NONE, "Bob")
    vessel1_id = m.register_vessel(vessel1)
    vessel2_id = m.register_vessel(vessel2)

    first = m.reserve(vessel1_id, "B1", date(2024, 7, 1), date(2024, 7, 5))
    assert first.is_success

    # Overlaps by exactly one night: 4 July.
    second = m.reserve(vessel2_id, "B1", date(2024, 7, 4), date(2024, 7, 8))
    assert not second.is_success


def test_departure_equal_to_arrival_of_next_reservation_does_not_conflict(m):
    m.add_berth(Berth("B1", "Dock A", BerthType.SLIP, 45, 16, 8, PowerService.NONE))
    vessel1 = Vessel("Sea Breeze", "REG-001", 40, 14, 6, PowerService.NONE, "Alice")
    vessel2 = Vessel("Blue Horizon", "REG-002", 30, 11, 4, PowerService.NONE, "Bob")
    vessel1_id = m.register_vessel(vessel1)
    vessel2_id = m.register_vessel(vessel2)

    first = m.reserve(vessel1_id, "B1", date(2024, 7, 1), date(2024, 7, 5))
    assert first.is_success

    # Arrival on the departure date of the first reservation: half-open, no conflict.
    second = m.reserve(vessel2_id, "B1", date(2024, 7, 5), date(2024, 7, 8))
    assert second.is_success


def test_overstay_adds_double_base_rate_and_normal_power_surcharge_per_overstayed_night(m):
    m.add_berth(Berth("B1", "Dock A", BerthType.SLIP, 45, 16, 8, PowerService.AMP_30))
    vessel = Vessel("Blue Horizon", "REG-002", 30, 11, 4, PowerService.AMP_30, "Bob")
    vessel_id = m.register_vessel(vessel)

    # 1 Mar - 4 Mar: 3 reserved nights, non-peak, $2.40 * 30 = $72.00 per night base.
    result = m.reserve(vessel_id, "B1", date(2024, 3, 1), date(2024, 3, 4))
    assert result.is_success
    reservation_id = result.reservation.reservation_id

    # Overstay two nights: actual departure 6 March.
    invoice = m.generate_invoice(reservation_id, date(2024, 3, 6))

    expected_base = Decimal("72.00") * 3  # 216.00
    expected_power_reserved = Decimal("12.00") * 3  # 36.00
    expected_overstay = Decimal("144.00") * 2  # 288.00
    expected_power_overstay = Decimal("12.00") * 2  # 24.00
    expected_total = expected_base + expected_power_reserved + expected_overstay + expected_power_overstay

    assert invoice.total == expected_total

    overstay_lines = [line for line in invoice.lines if line.line_type == "OVERSTAY"]
    assert len(overstay_lines) == 2

    # Early departure does not reduce the bill: reserved nights charged in full.
    early_invoice = m.generate_invoice(reservation_id, date(2024, 3, 2))
    expected_early_total = expected_base + expected_power_reserved
    assert early_invoice.total == expected_early_total
    assert not [line for line in early_invoice.lines if line.line_type == "OVERSTAY"]


def test_actual_departure_before_arrival_date_raises_and_produces_no_invoice(m):
    m.add_berth(Berth("B1", "Dock A", BerthType.SLIP, 45, 16, 8, PowerService.NONE))
    vessel = Vessel("Sea Breeze", "REG-001", 40, 14, 6, PowerService.NONE, "Alice")
    vessel_id = m.register_vessel(vessel)

    result = m.reserve(vessel_id, "B1", date(2024, 7, 1), date(2024, 7, 5))
    assert result.is_success
    reservation_id = result.reservation.reservation_id

    with pytest.raises(ValueError):
        m.generate_invoice(reservation_id, date(2024, 6, 30))


def test_power_requirement_50_amp_vessel_requires_amp_50_berth(m):
    m.add_berth(Berth("B1", "Dock A", BerthType.SLIP, 45, 16, 8, PowerService.AMP_30))
    m.add_berth(Berth("B2", "Dock A", BerthType.SLIP, 45, 16, 8, PowerService.AMP_50))
    vessel = Vessel("Wind Dancer", "REG-003", 40, 14, 6, PowerService.AMP_50, "Carol")
    m.register_vessel(vessel)

    available = m.find_available_berths(vessel, date(2024, 7, 1), date(2024, 7, 5))
    assert len(available) == 1
    assert available[0].berth_id == "B2"


def test_power_requirement_30_amp_vessel_accepts_amp_30_or_amp_50(m):
    m.add_berth(Berth("B1", "Dock A", BerthType.SLIP, 45, 16, 8, PowerService.AMP_30))
    m.add_berth(Berth("B2", "Dock A", BerthType.SLIP, 45, 16, 8, PowerService.AMP_50))
    m.add_berth(Berth("B3", "Dock A", BerthType.SLIP, 45, 16, 8, PowerService.NONE))
    vessel = Vessel("Blue Horizon", "REG-002", 30, 11, 4, PowerService.AMP_30, "Bob")

    available = m.find_available_berths(vessel, date(2024, 7, 1), date(2024, 7, 5))
    assert len(available) == 2


def test_no_power_requirement_accepts_any_berth(m):
    m.add_berth(Berth("B1", "Dock A", BerthType.SLIP, 45, 16, 8, PowerService.AMP_30))
    m.add_berth(Berth("B2", "Dock A", BerthType.SLIP, 45, 16, 8, PowerService.AMP_50))
    m.add_berth(Berth("B3", "Dock A", BerthType.SLIP, 45, 16, 8, PowerService.NONE))
    vessel = Vessel("Sea Breeze", "REG-001", 40, 14, 6, PowerService.NONE, "Alice")

    available = m.find_available_berths(vessel, date(2024, 7, 1), date(2024, 7, 5))
    assert len(available) == 3


def test_dimension_fit_requires_clearance_margins(m):
    exact = Berth("B1", "Dock A", BerthType.SLIP, 42, 15.5, 7.5, PowerService.NONE)
    m.add_berth(exact)
    vessel = Vessel("Sea Breeze", "REG-001", 40, 14, 6, PowerService.NONE, "Alice")

    available = m.find_available_berths(vessel, date(2024, 7, 1), date(2024, 7, 5))
    assert len(available) == 1

    m2 = Marina()
    too_small = Berth("B2", "Dock A", BerthType.SLIP, 41.9, 15.5, 7.5, PowerService.NONE)
    m2.add_berth(too_small)
    available2 = m2.find_available_berths(vessel, date(2024, 7, 1), date(2024, 7, 5))
    assert available2 == []


def test_base_rates_per_berth_type_are_correct(m):
    m.add_berth(Berth("SLIP1", "Dock A", BerthType.SLIP, 45, 16, 8, PowerService.NONE))
    m.add_berth(Berth("TIE1", "Dock A", BerthType.END_TIE, 45, 16, 8, PowerService.NONE))
    m.add_berth(Berth("MOOR1", "Dock A", BerthType.MOORING, 45, 16, 8, PowerService.NONE))

    arrival = date(2024, 1, 10)
    departure = date(2024, 1, 11)

    vessel1 = Vessel("V1", "REG-1", 10, 5, 3, PowerService.NONE, "Alice")
    vessel1_id = m.register_vessel(vessel1)
    slip_res = m.reserve(vessel1_id, "SLIP1", arrival, departure)
    slip_invoice = m.generate_invoice(slip_res.reservation.reservation_id, departure)
    assert slip_invoice.total == Decimal("24.00")

    vessel2 = Vessel("V2", "REG-2", 10, 5, 3, PowerService.NONE, "Bob")
    vessel2_id = m.register_vessel(vessel2)
    tie_res = m.reserve(vessel2_id, "TIE1", arrival, departure)
    tie_invoice = m.generate_invoice(tie_res.reservation.reservation_id, departure)
    assert tie_invoice.total == Decimal("21.00")

    vessel3 = Vessel("V3", "REG-3", 10, 5, 3, PowerService.NONE, "Carol")
    vessel3_id = m.register_vessel(vessel3)
    moor_res = m.reserve(vessel3_id, "MOOR1", arrival, departure)
    moor_invoice = m.generate_invoice(moor_res.reservation.reservation_id, departure)
    assert moor_invoice.total == Decimal("11.00")
