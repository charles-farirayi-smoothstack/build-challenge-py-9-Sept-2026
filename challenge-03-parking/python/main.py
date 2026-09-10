"""Demonstration: 5 vehicles, 4 permits across both types, and 10 citations covering
every violation code, both appeal outcomes, one partial payment and one escalated
citation."""

from datetime import date, datetime
from decimal import Decimal

from parking import (
    AppealOutcome,
    ParkingAuthority,
    ParkingObservation,
    PermitType,
    ZoneType,
)


def print_result(label: str, result):
    if result.legal:
        print(f"{label}: LEGAL")
    else:
        citation = result.citation
        print(f"{label}: {result.violation_code.name} -> {citation.citation_id} (${citation.base_fine})")
    return result


def main() -> None:
    authority = ParkingAuthority()

    print("=== Registering vehicles ===")
    authority.register_vehicle("AAA111", "CA", "Alice Anders")
    authority.register_vehicle("BBB222", "CA", "Bob Brown")
    authority.register_vehicle("CCC333", "NV", "Carol Chen")
    authority.register_vehicle("DDD444", "CA", "Dan Diaz")
    authority.register_vehicle("EEE555", "OR", "Eve Estrada")
    for plate in ("AAA111", "BBB222", "CCC333", "DDD444", "EEE555"):
        print(f"  {authority.get_vehicle(plate)}")

    print("\n=== Issuing permits ===")
    p1 = authority.issue_permit("AAA111", PermitType.RESIDENT, "Elm Street", date(2026, 1, 10))
    p2 = authority.issue_permit("BBB222", PermitType.ACCESSIBLE, None, date(2026, 1, 15))
    p3 = authority.issue_permit("CCC333", PermitType.RESIDENT, "Oak Avenue", date(2024, 2, 29))
    p4 = authority.issue_permit("DDD444", PermitType.ACCESSIBLE, None, date(2026, 2, 1))
    for p in (p1, p2, p3, p4):
        print(f"  {p}")
    print(f"  (Note: permit {p3.permit_id} issued 2024-02-29 expires {p3.expires_on}"
          " - last day of Feb in a non-leap year.)")

    print("\n=== A few legal observations (no citation) ===")
    print_result(
        "Residential, valid resident permit",
        authority.evaluate_observation(
            ParkingObservation("AAA111", "Elm Street", ZoneType.RESIDENTIAL,
                                datetime(2026, 3, 1, 21, 0), None, False)
        ),
    )
    print_result(
        "Metered, accessible permit exempts payment",
        authority.evaluate_observation(
            ParkingObservation("BBB222", "Main St Meters", ZoneType.METERED,
                                datetime(2026, 3, 2, 11, 0), None, False)
        ),
    )
    print_result(
        "Metered, Sunday (free hours)",
        authority.evaluate_observation(
            ParkingObservation("CCC333", "Main St Meters", ZoneType.METERED,
                                datetime(2026, 3, 1, 12, 0), None, False)  # 2026-03-01 is a Sunday
        ),
    )

    print("\n=== Evaluating observations that issue citations (10 total) ===")
    results = []

    results.append(print_result(
        "1. Hydrant block (AAA111)",
        authority.evaluate_observation(
            ParkingObservation("AAA111", "Elm Street", ZoneType.RESIDENTIAL,
                                datetime(2026, 3, 1, 10, 0), None, True)
        ),
    ))

    results.append(print_result(
        "2. Hydrant block despite accessible permit (DDD444)",
        authority.evaluate_observation(
            ParkingObservation("DDD444", "Main St Meters", ZoneType.METERED,
                                datetime(2026, 3, 1, 11, 0), None, True)
        ),
    ))

    results.append(print_result(
        "3. Residential, no permit at all (EEE555)",
        authority.evaluate_observation(
            ParkingObservation("EEE555", "Elm Street", ZoneType.RESIDENTIAL,
                                datetime(2026, 3, 1, 20, 0), None, False)
        ),
    ))

    results.append(print_result(
        "4. Residential, permit held for a different zone (AAA111)",
        authority.evaluate_observation(
            ParkingObservation("AAA111", "Oak Avenue", ZoneType.RESIDENTIAL,
                                datetime(2026, 3, 1, 22, 0), None, False)
        ),
    ))

    results.append(print_result(
        "5. Residential, expired resident permit (CCC333)",
        authority.evaluate_observation(
            ParkingObservation("CCC333", "Oak Avenue", ZoneType.RESIDENTIAL,
                                datetime(2026, 3, 1, 19, 0), None, False)  # permit p3 expired 2025-02-28
        ),
    ))

    results.append(print_result(
        "6. Residential, overnight window wraps past midnight (EEE555)",
        authority.evaluate_observation(
            ParkingObservation("EEE555", "Elm Street", ZoneType.RESIDENTIAL,
                                datetime(2026, 3, 2, 3, 0), None, False)
        ),
    ))

    results.append(print_result(
        "7. Metered, no payment recorded (CCC333)",
        authority.evaluate_observation(
            ParkingObservation("CCC333", "Main St Meters", ZoneType.METERED,
                                datetime(2026, 3, 2, 9, 0), None, False)
        ),
    ))

    results.append(print_result(
        "8. Metered, meter paid until an earlier time (EEE555)",
        authority.evaluate_observation(
            ParkingObservation("EEE555", "Main St Meters", ZoneType.METERED,
                                datetime(2026, 3, 2, 14, 0), datetime(2026, 3, 2, 13, 30), False)
        ),
    ))

    results.append(print_result(
        "9. Metered, no payment recorded (AAA111)",
        authority.evaluate_observation(
            ParkingObservation("AAA111", "Main St Meters", ZoneType.METERED,
                                datetime(2026, 3, 3, 9, 30), None, False)
        ),
    ))

    results.append(print_result(
        "10. Residential, resident permit doesn't cover this zone (AAA111 at Birch Lane)",
        authority.evaluate_observation(
            ParkingObservation("AAA111", "Birch Lane", ZoneType.RESIDENTIAL,
                                datetime(2026, 3, 3, 21, 0), None, False)
        ),
    ))

    citations = authority.get_all_citations()
    print(f"\nTotal citations issued: {len(citations)}")

    print("\n=== Appeals ===")
    to_appeal_uphold = results[2].citation  # #3
    appeal1 = authority.file_appeal(to_appeal_uphold.citation_id, date(2026, 3, 5))
    print(f"Appeal on {to_appeal_uphold.citation_id} (within window): accepted={appeal1.accepted}")
    authority.resolve_appeal(to_appeal_uphold.citation_id, AppealOutcome.UPHELD, date(2026, 3, 12))
    print(f"  Resolved UPHELD -> {authority.get_citation(to_appeal_uphold.citation_id)}")

    to_appeal_dismiss = results[6].citation  # #7
    appeal2 = authority.file_appeal(to_appeal_dismiss.citation_id, date(2026, 3, 8))
    print(f"Appeal on {to_appeal_dismiss.citation_id} (within window): accepted={appeal2.accepted}")
    authority.resolve_appeal(to_appeal_dismiss.citation_id, AppealOutcome.DISMISSED, date(2026, 3, 15))
    print(f"  Resolved DISMISSED -> {authority.get_citation(to_appeal_dismiss.citation_id)}")

    # Edge case: appeal filed on day 15 - rejected.
    late_citation = results[4].citation  # #5
    from datetime import timedelta
    late_appeal = authority.file_appeal(late_citation.citation_id, late_citation.issued_on + timedelta(days=15))
    print(f"Appeal on day 15 for {late_citation.citation_id}: accepted={late_appeal.accepted}"
          f" reason={late_appeal.reason}")

    print("\n=== Payments ===")
    to_pay = results[0].citation  # #1, BLOCKING_HYDRANT, $150.00
    partial = authority.pay_citation(to_pay.citation_id, Decimal("50.00"))
    print(f"Partial payment of $50.00 on {to_pay.citation_id}: accepted={partial.accepted}"
          f" remainingBalance={partial.remaining_balance}")

    # Edge case: payment larger than balance - rejected.
    too_much = authority.pay_citation(to_pay.citation_id, Decimal("1000.00"))
    print(f"Overpayment of $1000.00 on {to_pay.citation_id}: accepted={too_much.accepted}"
          f" reason={too_much.reason}")

    print("\n=== Escalation ===")
    to_escalate = results[8].citation  # #9, issued 2026-03-03
    escalation_date = to_escalate.issued_on + timedelta(days=21)  # 2026-03-24
    first_run = authority.run_escalation(escalation_date)
    print(f"run_escalation({escalation_date}) escalated: {[c.citation_id for c in first_run]}")
    print(f"  {authority.get_citation(to_escalate.citation_id)}")

    # Edge case: running escalation twice for the same date must not double-apply.
    second_run = authority.run_escalation(escalation_date)
    print(f"run_escalation({escalation_date}) again escalated: {[c.citation_id for c in second_run]}"
          " (must be empty - idempotent)")
    print(f"  {authority.get_citation(to_escalate.citation_id)}")

    print("\n=== Final citation ledger ===")
    for c in authority.get_all_citations():
        print(f"  {c}")


if __name__ == "__main__":
    main()
