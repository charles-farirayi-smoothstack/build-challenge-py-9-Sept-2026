"""Domain model for the municipal parking permits and citations system."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import Enum, auto
from typing import Optional


def money(amount) -> Decimal:
    """Normalize any numeric value to a Decimal with 2 fractional digits,
    rounding half up per the currency-handling guidance."""
    return Decimal(amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


ZERO = money("0.00")
PENALTY_RATE = Decimal("0.50")


class ZoneType(Enum):
    METERED = auto()
    RESIDENTIAL = auto()


class PermitType(Enum):
    RESIDENT = auto()
    ACCESSIBLE = auto()

    @property
    def annual_cost(self) -> Decimal:
        return money("40.00") if self is PermitType.RESIDENT else ZERO


class PermitStatus(Enum):
    ACTIVE = auto()
    REVOKED = auto()


class ViolationCode(Enum):
    BLOCKING_HYDRANT = auto()
    NO_PERMIT = auto()
    EXPIRED_METER = auto()

    @property
    def base_fine(self) -> Decimal:
        return {
            ViolationCode.BLOCKING_HYDRANT: money("150.00"),
            ViolationCode.NO_PERMIT: money("60.00"),
            ViolationCode.EXPIRED_METER: money("35.00"),
        }[self]


class CitationStatus(Enum):
    """ISSUED and UPHELD are both "active/owing" states the escalation clock runs
    against; APPEALED pauses the clock; DISMISSED and PAID are terminal states in
    which no further escalation happens."""

    ISSUED = auto()
    APPEALED = auto()
    UPHELD = auto()
    DISMISSED = auto()
    PAID = auto()


class AppealOutcome(Enum):
    UPHELD = auto()
    DISMISSED = auto()


@dataclass
class Vehicle:
    plate: str
    registration_state: str
    owner_name: str


@dataclass
class Permit:
    permit_id: str
    permit_type: PermitType
    plate: str
    zone_name: Optional[str]  # populated only for RESIDENT
    issued_on: date
    expires_on: date
    status: PermitStatus = PermitStatus.ACTIVE

    def is_valid_at(self, observed_at: datetime) -> bool:
        """A permit is valid at an observation when it is ACTIVE and the observation
        time falls on or after issuedOn and strictly before expiresOn."""
        if self.status != PermitStatus.ACTIVE:
            return False
        start = datetime.combine(self.issued_on, datetime.min.time())
        end = datetime.combine(self.expires_on, datetime.min.time())
        return start <= observed_at < end

    def applies_to_zone(self, observed_zone_name: str, observed_zone_type: ZoneType) -> bool:
        if self.permit_type is PermitType.ACCESSIBLE:
            # Valid in residential zones and in metered zones (without payment).
            return True
        # RESIDENT: valid only in the one named residential zone recorded on the permit.
        return observed_zone_type is ZoneType.RESIDENTIAL and self.zone_name == observed_zone_name


@dataclass
class Citation:
    citation_id: str
    plate: str
    violation_code: ViolationCode
    issued_on: date
    base_fine: Decimal
    penalty_applied: bool = False
    amount_paid: Decimal = field(default_factory=lambda: ZERO)
    status: CitationStatus = CitationStatus.ISSUED
    appeal_filed_on: Optional[date] = None
    appeal_resolved_on: Optional[date] = None

    @property
    def penalty_amount(self) -> Decimal:
        if not self.penalty_applied:
            return ZERO
        return money(self.base_fine * PENALTY_RATE)

    @property
    def total_owed(self) -> Decimal:
        return money(self.base_fine + self.penalty_amount)

    @property
    def balance(self) -> Decimal:
        """Remaining balance. DISMISSED citations always have a zero balance."""
        if self.status is CitationStatus.DISMISSED:
            return ZERO
        remaining = money(self.total_owed - self.amount_paid)
        return remaining if remaining > ZERO else ZERO

    @property
    def is_escalatable(self) -> bool:
        """Whether this citation is in an active/owing state against which the
        escalation clock runs (ISSUED, or UPHELD after a resolved appeal)."""
        return self.status in (CitationStatus.ISSUED, CitationStatus.UPHELD)


@dataclass
class ParkingObservation:
    plate: str
    zone_name: str
    zone_type: ZoneType
    observed_at: datetime
    meter_paid_until: Optional[datetime] = None
    is_blocking_hydrant: bool = False


@dataclass
class EvaluationResult:
    legal: bool
    violation_code: Optional[ViolationCode] = None
    citation: Optional[Citation] = None

    @staticmethod
    def as_legal() -> "EvaluationResult":
        return EvaluationResult(legal=True)

    @staticmethod
    def as_violation(violation_code: ViolationCode, citation: Citation) -> "EvaluationResult":
        return EvaluationResult(legal=False, violation_code=violation_code, citation=citation)


@dataclass
class AppealResult:
    accepted: bool
    citation: Optional[Citation] = None
    reason: Optional[str] = None

    @staticmethod
    def as_accepted(citation: Citation) -> "AppealResult":
        return AppealResult(accepted=True, citation=citation)

    @staticmethod
    def as_refused(reason: str) -> "AppealResult":
        return AppealResult(accepted=False, reason=reason)


@dataclass
class PaymentResult:
    accepted: bool
    remaining_balance: Optional[Decimal] = None
    reason: Optional[str] = None

    @staticmethod
    def as_accepted(remaining_balance: Decimal) -> "PaymentResult":
        return PaymentResult(accepted=True, remaining_balance=remaining_balance)

    @staticmethod
    def as_rejected(reason: str) -> "PaymentResult":
        return PaymentResult(accepted=False, reason=reason)
