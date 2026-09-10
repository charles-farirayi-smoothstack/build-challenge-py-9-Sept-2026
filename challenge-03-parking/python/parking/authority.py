"""ParkingAuthority: the vehicle, permit and citation stores plus the business rules
for issuing permits, judging observed vehicles, and escalating unpaid citations."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Dict, List, Optional

from .models import (
    AppealOutcome,
    AppealResult,
    Citation,
    CitationStatus,
    EvaluationResult,
    ParkingObservation,
    Permit,
    PermitStatus,
    PermitType,
    PaymentResult,
    Vehicle,
    ViolationCode,
    ZERO,
    money,
)

METERED_START = time(8, 0)
METERED_END = time(18, 0)
RESIDENTIAL_EVENING_START = time(18, 0)
RESIDENTIAL_MORNING_END = time(8, 0)
ESCALATION_DAYS = 21
APPEAL_WINDOW_DAYS = 14
SUNDAY = 6  # datetime.weekday(): Monday=0 ... Sunday=6


def add_one_year(d: date) -> date:
    """Adds one year to a date. Where the resulting date does not exist (29 February
    in a non-leap year), it falls on the last day of that month (28 February)."""
    target_year = d.year + 1
    if d.month == 2 and d.day == 29:
        try:
            return d.replace(year=target_year)
        except ValueError:
            return date(target_year, 2, 28)
    return d.replace(year=target_year)


def _is_in_metered_paid_window(observed_at: datetime) -> bool:
    monday_to_saturday = observed_at.weekday() != SUNDAY
    t = observed_at.time()
    within_hours = METERED_START <= t < METERED_END
    return monday_to_saturday and within_hours


def _is_in_residential_permit_window(observed_at: datetime) -> bool:
    # 18:00 up to but not including 08:00 the following morning: wraps past midnight.
    t = observed_at.time()
    return t >= RESIDENTIAL_EVENING_START or t < RESIDENTIAL_MORNING_END


class ParkingAuthority:
    """Holds the vehicle, permit and citation stores."""

    def __init__(self) -> None:
        self._vehicles_by_plate: Dict[str, Vehicle] = {}
        self._permits_by_plate: Dict[str, List[Permit]] = {}
        self._citations_by_id: Dict[str, Citation] = {}
        self._permit_sequence = 0
        self._citation_sequence = 0

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_vehicle(self, plate: str, registration_state: str, owner_name: str) -> Vehicle:
        vehicle = Vehicle(plate=plate, registration_state=registration_state, owner_name=owner_name)
        self._vehicles_by_plate[plate] = vehicle
        return vehicle

    def issue_permit(
        self,
        plate: str,
        permit_type: PermitType,
        zone_name: Optional[str],
        issued_on: date,
    ) -> Permit:
        self._permit_sequence += 1
        permit_id = f"P{self._permit_sequence}"
        expires_on = add_one_year(issued_on)
        effective_zone_name = zone_name if permit_type is PermitType.RESIDENT else None
        permit = Permit(
            permit_id=permit_id,
            permit_type=permit_type,
            plate=plate,
            zone_name=effective_zone_name,
            issued_on=issued_on,
            expires_on=expires_on,
            status=PermitStatus.ACTIVE,
        )
        self._permits_by_plate.setdefault(plate, []).append(permit)
        return permit

    # ------------------------------------------------------------------
    # Observation evaluation
    # ------------------------------------------------------------------

    def evaluate_observation(self, observation: ParkingObservation) -> EvaluationResult:
        if observation.is_blocking_hydrant:
            return self._issue_violation(observation, ViolationCode.BLOCKING_HYDRANT)

        observed_at = observation.observed_at

        if observation.zone_type.name == "RESIDENTIAL":
            if _is_in_residential_permit_window(observed_at):
                if self._has_valid_permit_for(observation):
                    return EvaluationResult.as_legal()
                return self._issue_violation(observation, ViolationCode.NO_PERMIT)
            return EvaluationResult.as_legal()

        # METERED
        if _is_in_metered_paid_window(observed_at):
            if self._has_valid_accessible_permit(observation):
                return EvaluationResult.as_legal()
            paid_until = observation.meter_paid_until
            paid = paid_until is not None and paid_until >= observed_at
            if paid:
                return EvaluationResult.as_legal()
            return self._issue_violation(observation, ViolationCode.EXPIRED_METER)
        return EvaluationResult.as_legal()

    def _has_valid_permit_for(self, observation: ParkingObservation) -> bool:
        for permit in self._permits_by_plate.get(observation.plate, []):
            if permit.is_valid_at(observation.observed_at) and permit.applies_to_zone(
                observation.zone_name, observation.zone_type
            ):
                return True
        return False

    def _has_valid_accessible_permit(self, observation: ParkingObservation) -> bool:
        for permit in self._permits_by_plate.get(observation.plate, []):
            if permit.permit_type is PermitType.ACCESSIBLE and permit.is_valid_at(observation.observed_at):
                return True
        return False

    def _issue_violation(self, observation: ParkingObservation, violation_code: ViolationCode) -> EvaluationResult:
        self._citation_sequence += 1
        citation_id = f"C{self._citation_sequence}"
        citation = Citation(
            citation_id=citation_id,
            plate=observation.plate,
            violation_code=violation_code,
            issued_on=observation.observed_at.date(),
            base_fine=violation_code.base_fine,
        )
        self._citations_by_id[citation_id] = citation
        return EvaluationResult.as_violation(violation_code, citation)

    # ------------------------------------------------------------------
    # Appeals
    # ------------------------------------------------------------------

    def file_appeal(self, citation_id: str, filed_on: date) -> AppealResult:
        citation = self._citations_by_id.get(citation_id)
        if citation is None:
            return AppealResult.as_refused(f"No such citation: {citation_id}")
        if citation.status != CitationStatus.ISSUED:
            return AppealResult.as_refused(f"Citation is not in an appealable state: {citation.status}")
        deadline = citation.issued_on + timedelta(days=APPEAL_WINDOW_DAYS)
        if filed_on > deadline:
            return AppealResult.as_refused(
                f"Appeal filed after the {APPEAL_WINDOW_DAYS}-day window (deadline was {deadline})"
            )
        citation.appeal_filed_on = filed_on
        citation.status = CitationStatus.APPEALED
        return AppealResult.as_accepted(citation)

    def resolve_appeal(self, citation_id: str, outcome: AppealOutcome, resolved_on: date) -> Citation:
        citation = self._citations_by_id.get(citation_id)
        if citation is None:
            raise ValueError(f"No such citation: {citation_id}")
        if citation.status != CitationStatus.APPEALED:
            raise ValueError(f"Citation is not under appeal: {citation.status}")
        citation.appeal_resolved_on = resolved_on
        if outcome is AppealOutcome.DISMISSED:
            citation.status = CitationStatus.DISMISSED
        else:
            citation.status = CitationStatus.UPHELD
        return citation

    # ------------------------------------------------------------------
    # Payment
    # ------------------------------------------------------------------

    def pay_citation(self, citation_id: str, amount: Decimal) -> PaymentResult:
        citation = self._citations_by_id.get(citation_id)
        if citation is None:
            return PaymentResult.as_rejected(f"No such citation: {citation_id}")
        if citation.status in (CitationStatus.DISMISSED, CitationStatus.PAID):
            return PaymentResult.as_rejected(f"Citation has no outstanding balance: {citation.status}")
        amount = money(amount)
        if amount <= ZERO:
            return PaymentResult.as_rejected("Payment amount must be positive")
        balance = citation.balance
        if amount > balance:
            return PaymentResult.as_rejected(f"Payment of {amount} exceeds outstanding balance of {balance}")

        # Payments apply to the penalty first, then the base fine. Both components feed
        # a single running amount_paid/balance total, so this ordering does not change
        # the arithmetic outcome, but conceptually: any payment first extinguishes the
        # outstanding penalty before anything is credited toward the base fine.
        citation.amount_paid = money(citation.amount_paid + amount)

        new_balance = money(citation.total_owed - citation.amount_paid)
        if new_balance <= ZERO:
            citation.status = CitationStatus.PAID
            new_balance = ZERO
        return PaymentResult.as_accepted(new_balance)

    # ------------------------------------------------------------------
    # Escalation
    # ------------------------------------------------------------------

    def run_escalation(self, as_of_date: date) -> List[Citation]:
        """Applies the 21-day, 50%-of-base-fine penalty to every eligible,
        un-escalated citation as of the given date, honoring the appeal pause, and
        returns the citations escalated on this run (idempotent: already-escalated
        citations are skipped)."""
        escalated: List[Citation] = []
        for citation in self._citations_by_id.values():
            if citation.penalty_applied:
                continue
            if not citation.is_escalatable:
                continue  # APPEALED (paused), DISMISSED or PAID
            elapsed_days = self._effective_elapsed_days(citation, as_of_date)
            if elapsed_days >= ESCALATION_DAYS:
                citation.penalty_applied = True
                escalated.append(citation)
        return escalated

    @staticmethod
    def _effective_elapsed_days(citation: Citation, as_of_date: date) -> int:
        if citation.appeal_filed_on is None:
            return (as_of_date - citation.issued_on).days
        days_before_appeal = (citation.appeal_filed_on - citation.issued_on).days
        if citation.appeal_resolved_on is None:
            # Still under appeal - clock paused (should not normally reach here since
            # is_escalatable excludes APPEALED status, kept as a safety net).
            return days_before_appeal
        days_after_resolution = (as_of_date - citation.appeal_resolved_on).days
        return days_before_appeal + days_after_resolution

    # ------------------------------------------------------------------
    # Accessors (for demo/tests)
    # ------------------------------------------------------------------

    def get_vehicle(self, plate: str) -> Optional[Vehicle]:
        return self._vehicles_by_plate.get(plate)

    def get_permits(self, plate: str) -> List[Permit]:
        return list(self._permits_by_plate.get(plate, []))

    def get_citation(self, citation_id: str) -> Optional[Citation]:
        return self._citations_by_id.get(citation_id)

    def get_all_citations(self) -> List[Citation]:
        return list(self._citations_by_id.values())
