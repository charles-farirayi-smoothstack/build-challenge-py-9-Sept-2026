"""Marina: fits vessels to berths, prevents overlapping reservations, and invoices stays."""

from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional

from marina.models import (
    BASE_RATE_PER_FOOT_PER_NIGHT,
    POWER_SURCHARGE_PER_NIGHT,
    Berth,
    Invoice,
    InvoiceLine,
    PowerService,
    Reservation,
    ReservationResult,
    ReservationStatus,
    Vessel,
    power_satisfies,
)

PEAK_SEASON_MULTIPLIER = Decimal("1.5")
LENGTH_CLEARANCE_FT = 2.0
BEAM_CLEARANCE_FT = 1.5
DEPTH_CLEARANCE_FT = 1.5
OVERSTAY_MULTIPLIER = Decimal("2")

TWO_PLACES = Decimal("0.01")


def _round(amount: Decimal) -> Decimal:
    return amount.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _is_peak_season(day: date) -> bool:
    """Peak season runs 1 June to 31 August inclusive."""
    return day.month in (6, 7, 8)


class Marina:
    def __init__(self) -> None:
        self._berths: Dict[str, Berth] = {}
        self._vessels: Dict[str, Vessel] = {}
        self._reservations: Dict[str, Reservation] = {}
        self._vessel_sequence = 1
        self._reservation_sequence = 1

    # -------------------- public API --------------------

    def add_berth(self, berth: Berth) -> None:
        self._berths[berth.berth_id] = berth

    def register_vessel(self, vessel: Vessel) -> str:
        vessel_id = f"V{self._vessel_sequence}"
        self._vessel_sequence += 1
        vessel.vessel_id = vessel_id
        self._vessels[vessel_id] = vessel
        return vessel_id

    def find_available_berths(
        self, vessel: Vessel, arrival_date: date, departure_date: date
    ) -> List[Berth]:
        available = []
        for berth in self._berths.values():
            if self._fits(berth, vessel) and self._is_free(berth.berth_id, arrival_date, departure_date):
                available.append(berth)
        return available

    def reserve(
        self, vessel_id: str, berth_id: str, arrival_date: date, departure_date: date
    ) -> ReservationResult:
        vessel = self._vessels.get(vessel_id)
        if vessel is None:
            return ReservationResult.refusal(f"No such vessel: {vessel_id}")

        berth = self._berths.get(berth_id)
        if berth is None:
            return ReservationResult.refusal(f"No such berth: {berth_id}")

        if not arrival_date < departure_date:
            return ReservationResult.refusal("Arrival date must be before departure date")

        if not self._fits(berth, vessel):
            return ReservationResult.refusal(
                f"Vessel does not fit berth {berth_id} (dimensions or power service incompatible)"
            )

        if not self._is_free(berth_id, arrival_date, departure_date):
            return ReservationResult.refusal(
                f"Berth {berth_id} is not available for the requested date range"
            )

        reservation_id = f"R{self._reservation_sequence}"
        self._reservation_sequence += 1
        reservation = Reservation(
            reservation_id=reservation_id,
            berth_id=berth_id,
            vessel_id=vessel_id,
            arrival_date=arrival_date,
            departure_date=departure_date,
            status=ReservationStatus.CONFIRMED,
        )
        self._reservations[reservation_id] = reservation
        return ReservationResult.success(reservation)

    def generate_invoice(self, reservation_id: str, actual_departure: date) -> Invoice:
        reservation = self._reservations.get(reservation_id)
        if reservation is None:
            raise ValueError(f"No such reservation: {reservation_id}")

        if actual_departure < reservation.arrival_date:
            raise ValueError(
                "Actual departure cannot be earlier than the arrival date; no invoice produced"
            )

        vessel = self._vessels[reservation.vessel_id]
        berth = self._berths[reservation.berth_id]

        lines: List[InvoiceLine] = []
        total = Decimal("0.00")

        reserved_end = reservation.departure_date

        # Reserved nights: [arrival_date, departure_date) - charged in full regardless of
        # early or on-time departure.
        night = reservation.arrival_date
        while night < reserved_end:
            base_amount = _round(self._night_base_rate(berth, vessel, night))
            lines.append(
                InvoiceLine("BASE_RATE", night, f"Base rate for {night}", base_amount)
            )
            total += base_amount

            if vessel.power_requirement != PowerService.NONE:
                power_amount = _round(POWER_SURCHARGE_PER_NIGHT[vessel.power_requirement])
                lines.append(
                    InvoiceLine(
                        "POWER_SURCHARGE", night, f"Power surcharge for {night}", power_amount
                    )
                )
                total += power_amount

            night += timedelta(days=1)

        # Overstay nights: [departure_date, actual_departure) - only when actual departure
        # is strictly after the reserved departure. Early/on-time departure charges the
        # reserved nights in full with no reduction and no overstay lines.
        if actual_departure > reserved_end:
            night = reserved_end
            while night < actual_departure:
                overstay_amount = _round(
                    self._night_base_rate(berth, vessel, night) * OVERSTAY_MULTIPLIER
                )
                lines.append(
                    InvoiceLine(
                        "OVERSTAY",
                        night,
                        f"Overstay charge (2x base rate) for {night}",
                        overstay_amount,
                    )
                )
                total += overstay_amount

                if vessel.power_requirement != PowerService.NONE:
                    power_amount = _round(POWER_SURCHARGE_PER_NIGHT[vessel.power_requirement])
                    lines.append(
                        InvoiceLine(
                            "POWER_SURCHARGE",
                            night,
                            f"Power surcharge for {night} (overstay)",
                            power_amount,
                        )
                    )
                    total += power_amount

                night += timedelta(days=1)

        return Invoice(reservation_id=reservation_id, lines=lines, total=total)

    # -------------------- helpers --------------------

    def _fits(self, berth: Berth, vessel: Vessel) -> bool:
        dimensions_fit = (
            berth.length_ft >= vessel.length_ft + LENGTH_CLEARANCE_FT
            and berth.beam_ft >= vessel.beam_ft + BEAM_CLEARANCE_FT
            and berth.depth_ft >= vessel.draft_ft + DEPTH_CLEARANCE_FT
        )
        power_fits = power_satisfies(berth.power_service, vessel.power_requirement)
        return dimensions_fit and power_fits

    def _is_free(self, berth_id: str, arrival_date: date, departure_date: date) -> bool:
        for reservation in self._reservations.values():
            if reservation.berth_id != berth_id:
                continue
            if reservation.status != ReservationStatus.CONFIRMED:
                continue
            if reservation.overlaps(arrival_date, departure_date):
                return False
        return True

    def _night_base_rate(self, berth: Berth, vessel: Vessel, night: date) -> Decimal:
        rate = BASE_RATE_PER_FOOT_PER_NIGHT[berth.berth_type] * Decimal(str(vessel.length_ft))
        if _is_peak_season(night):
            rate *= PEAK_SEASON_MULTIPLIER
        return rate

    # -------------------- lookups --------------------

    def find_reservation(self, reservation_id: str) -> Optional[Reservation]:
        return self._reservations.get(reservation_id)

    def find_vessel(self, vessel_id: str) -> Optional[Vessel]:
        return self._vessels.get(vessel_id)

    def find_berth(self, berth_id: str) -> Optional[Berth]:
        return self._berths.get(berth_id)

    def all_berths(self) -> List[Berth]:
        return list(self._berths.values())
