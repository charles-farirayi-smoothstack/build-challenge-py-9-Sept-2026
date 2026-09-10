"""Demonstration: 6 berths across 2 docks, 4 vessels of varying dimensions, and 6
reservations including one peak-boundary stay, one overstay and one vessel that
fits nothing.
"""

from datetime import date

from marina import Berth, BerthType, Marina, PowerService, Vessel


def print_reservation_result(result) -> None:
    if result.is_success:
        print(f"  CONFIRMED: {result.reservation}")
    else:
        print(f"  REFUSED: {result.refusal_reason}")


def main() -> None:
    m = Marina()

    # ---- 6 berths across 2 docks ----
    m.add_berth(Berth("B1", "Dock A", BerthType.SLIP, 45, 16, 8, PowerService.AMP_50))
    m.add_berth(Berth("B2", "Dock A", BerthType.SLIP, 35, 13, 6, PowerService.AMP_30))
    m.add_berth(Berth("B3", "Dock A", BerthType.END_TIE, 60, 19, 10, PowerService.AMP_50))
    m.add_berth(Berth("B4", "Dock B", BerthType.MOORING, 30, 12, 5, PowerService.NONE))
    m.add_berth(Berth("B5", "Dock B", BerthType.SLIP, 25, 10, 5, PowerService.AMP_30))
    m.add_berth(Berth("B6", "Dock B", BerthType.END_TIE, 20, 9, 4, PowerService.NONE))

    print("=== Berths ===")
    for b in m.all_berths():
        print(b)

    # ---- 4 vessels of varying dimensions ----
    v1 = Vessel("Sea Breeze", "REG-001", 40, 14, 6, PowerService.NONE, "Alice")
    v2 = Vessel("Blue Horizon", "REG-002", 30, 11, 4, PowerService.AMP_30, "Bob")
    v3 = Vessel("Wind Dancer", "REG-003", 55, 17, 8, PowerService.AMP_50, "Carol")
    v4 = Vessel("Leviathan", "REG-004", 80, 22, 12, PowerService.AMP_50, "Dave")  # fits nothing

    v1_id = m.register_vessel(v1)
    v2_id = m.register_vessel(v2)
    v3_id = m.register_vessel(v3)
    v4_id = m.register_vessel(v4)

    print("\n=== Vessels ===")
    print(f"{v1} -> id {v1_id}")
    print(f"{v2} -> id {v2_id}")
    print(f"{v3} -> id {v3_id}")
    print(f"{v4} -> id {v4_id}")

    print("\n=== Reservations ===")

    # 1) Worked example: peak-boundary stay, 40ft vessel, no power, in a slip,
    # 30 May - 2 June -> 3 nights, $336.00
    print("-- Reservation 1: peak-boundary stay (Sea Breeze, B1, 30 May - 2 Jun) --")
    r1 = m.reserve(v1_id, "B1", date(2024, 5, 30), date(2024, 6, 2))
    print_reservation_result(r1)

    # 2) Normal reservation for v2 on B2
    print("-- Reservation 2: normal stay (Blue Horizon, B2, 10 Jul - 14 Jul) --")
    r2 = m.reserve(v2_id, "B2", date(2024, 7, 10), date(2024, 7, 14))
    print_reservation_result(r2)

    # 3) v3 on B3 (needs AMP_50, big vessel)
    print("-- Reservation 3: normal stay (Wind Dancer, B3, 1 Sep - 5 Sep) --")
    r3 = m.reserve(v3_id, "B3", date(2024, 9, 1), date(2024, 9, 5))
    print_reservation_result(r3)

    # 4) Overstay reservation: v2 on B1, reserved 3 nights, actually leaves 2 nights late
    print("-- Reservation 4: overstay stay (Blue Horizon, B1, 1 Mar - 4 Mar, actual departure 6 Mar) --")
    r4 = m.reserve(v2_id, "B1", date(2024, 3, 1), date(2024, 3, 4))
    print_reservation_result(r4)

    # 5) Attempt to reserve overlapping range on same berth as reservation 1 (rejected)
    print("-- Reservation 5: overlapping attempt (another vessel, B1, 1 Jun - 3 Jun) --")
    r5 = m.reserve(v2_id, "B1", date(2024, 6, 1), date(2024, 6, 3))
    print_reservation_result(r5)

    # 6) Vessel that fits nothing
    print("-- Reservation 6: vessel that fits nothing (Leviathan) --")
    available_for_v4 = m.find_available_berths(v4, date(2024, 8, 1), date(2024, 8, 5))
    print(f"Available berths for Leviathan: {available_for_v4}")
    r6 = m.reserve(v4_id, "B3", date(2024, 8, 1), date(2024, 8, 5))
    print_reservation_result(r6)

    print("\n=== Invoices ===")
    if r1.is_success:
        invoice1 = m.generate_invoice(r1.reservation.reservation_id, r1.reservation.departure_date)
        print(invoice1)
    if r2.is_success:
        invoice2 = m.generate_invoice(r2.reservation.reservation_id, r2.reservation.departure_date)
        print(invoice2)
    if r3.is_success:
        invoice3 = m.generate_invoice(r3.reservation.reservation_id, r3.reservation.departure_date)
        print(invoice3)
    if r4.is_success:
        # Overstay: reserved departure 4 Mar, actual departure 6 Mar (2 overstayed nights)
        invoice4 = m.generate_invoice(r4.reservation.reservation_id, date(2024, 3, 6))
        print(invoice4)


if __name__ == "__main__":
    main()
