"""Data classes used throughout the sales package."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import List


@dataclass(frozen=True)
class SaleRecord:
    """A single, successfully parsed sales transaction.

    Columns (CSV order): transactionId, date, region, salesperson, productCategory,
    quantity, unitPrice, totalAmount
    """

    transaction_id: str
    date: date
    region: str
    salesperson: str
    product_category: str
    quantity: int
    unit_price: float
    total_amount: float


@dataclass(frozen=True)
class MalformedRow:
    """A CSV row that could not be parsed into a :class:`SaleRecord`."""

    line_number: int
    raw_line: str
    reason: str


@dataclass(frozen=True)
class SalesDataLoadResult:
    """Outcome of loading a sales CSV file."""

    records: List[SaleRecord] = field(default_factory=list)
    malformed_rows: List[MalformedRow] = field(default_factory=list)

    @property
    def valid_count(self) -> int:
        return len(self.records)

    @property
    def malformed_count(self) -> int:
        return len(self.malformed_rows)


@dataclass(frozen=True)
class SalespersonTotal:
    """A salesperson's aggregated performance."""

    salesperson: str
    total_sales: float
    transaction_count: int
