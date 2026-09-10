"""Data models for the marina berth reservation and billing system."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional


class BerthType(Enum):
    """The type of berth. Each type has a base dollars-per-foot-per-night rate."""

    SLIP = "SLIP"
    END_TIE = "END_TIE"
    MOORING = "MOORING"


BASE_RATE_PER_FOOT_PER_NIGHT = {
    BerthType.SLIP: Decimal("2.40"),
    BerthType.END_TIE: Decimal("2.10"),
    BerthType.MOORING: Decimal("1.10"),
}


class PowerService(Enum):
    """The power service offered by a berth, or requested by a vessel."""

    NONE = "NONE"
    AMP_30 = "AMP_30"
    AMP_50 = "AMP_50"


POWER_SURCHARGE_PER_NIGHT = {
    PowerService.NONE: Decimal("0.00"),
    PowerService.AMP_30: Decimal("12.00"),
    PowerService.AMP_50: Decimal("20.00"),
}


def power_satisfies(offered: PowerService, requested: PowerService) -> bool:
    """Whether a berth offering `offered` power satisfies a vessel requesting `requested`."""
    if requested == PowerService.NONE:
        return True
    if requested == PowerService.AMP_30:
        return offered in (PowerService.AMP_30, PowerService.AMP_50)
    # requested == AMP_50
    return offered == PowerService.AMP_50


class ReservationStatus(Enum):
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


@dataclass
class Berth:
    berth_id: str
    dock_name: str
    berth_type: BerthType
    length_ft: float
    beam_ft: float
    depth_ft: float
    power_service: PowerService


@dataclass
class Vessel:
    name: str
    registration: str
    length_ft: float
    beam_ft: float
    draft_ft: float
    power_requirement: PowerService
    owner_name: str
    vessel_id: Optional[str] = field(default=None)


@dataclass
class Reservation:
    reservation_id: str
    berth_id: str
    vessel_id: str
    arrival_date: date
    departure_date: date
    status: ReservationStatus = ReservationStatus.CONFIRMED

    def overlaps(self, other_arrival: date, other_departure: date) -> bool:
        """Half-open overlap check: [arrival, departure) vs [other_arrival, other_departure)."""
        return self.arrival_date < other_departure and other_arrival < self.departure_date


@dataclass
class InvoiceLine:
    line_type: str  # "BASE_RATE", "POWER_SURCHARGE", or "OVERSTAY"
    line_date: date
    description: str
    amount: Decimal


@dataclass
class Invoice:
    reservation_id: str
    lines: list
    total: Decimal

    def __str__(self) -> str:
        lines_str = "\n".join(
            f"  {line.line_date} | {line.line_type} | {line.description} | ${line.amount}"
            for line in self.lines
        )
        return f"Invoice for reservation {self.reservation_id}:\n{lines_str}\n  TOTAL: ${self.total}"


@dataclass
class ReservationResult:
    reservation: Optional[Reservation] = None
    refusal_reason: Optional[str] = None

    @property
    def is_success(self) -> bool:
        return self.reservation is not None

    @staticmethod
    def success(reservation: Reservation) -> "ReservationResult":
        return ReservationResult(reservation=reservation)

    @staticmethod
    def refusal(reason: str) -> "ReservationResult":
        return ReservationResult(refusal_reason=reason)
