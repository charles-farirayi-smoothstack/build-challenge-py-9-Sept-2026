"""Loads SaleRecord objects from a CSV file.

Design decisions (mirrors the Java implementation for parity):

* A missing/unreadable file is a hard failure: :class:`SalesDataError` is raised with a clear
  message (never let a raw traceback reach the caller for that case).
* A malformed *row* (wrong column count, unparsable number/date, blank required field) never
  aborts the load. It is recorded as a :class:`MalformedRow` with a reason and skipped, and
  loading continues.
* Numbers are parsed strictly (``int()`` / ``float()``); values containing currency symbols
  (e.g. ``"$18.25"``) or non-numeric text (e.g. ``"two"``) are treated as malformed rather than
  silently cleaned.
* Dates must be strict ISO-8601 (``yyyy-mm-dd``); other formats (e.g. ``"15/04/2024"``) are
  treated as malformed for the same reason.
"""

from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional, Tuple, Union

from .exceptions import SalesDataError
from .models import MalformedRow, SaleRecord, SalesDataLoadResult

EXPECTED_COLUMN_COUNT = 8
COLUMN_NAMES = (
    "transactionId",
    "date",
    "region",
    "salesperson",
    "productCategory",
    "quantity",
    "unitPrice",
    "totalAmount",
)


class _RowParseError(Exception):
    """Internal signal used to short-circuit parsing of a single row; never escapes this module."""


class SalesDataLoader:
    """Loads and parses a sales CSV file into records + malformed-row diagnostics."""

    def load(self, csv_path: Union[str, Path]) -> SalesDataLoadResult:
        """Loads and parses the CSV file at ``csv_path``.

        Raises:
            SalesDataError: if the file does not exist or cannot be read.
        """
        path = Path(csv_path) if csv_path is not None else None
        lines = self._read_lines(path)

        if not lines:
            return SalesDataLoadResult(records=[], malformed_rows=[])

        header, *data_lines = lines

        # Functional pipeline: map each (line_number, raw_line) pair to a parse outcome,
        # skipping blank lines, then partition successes/failures with comprehensions.
        outcomes: List[Tuple[Optional[SaleRecord], Optional[MalformedRow]]] = [
            self._parse_line_safely(line_number, raw_line)
            for line_number, raw_line in enumerate(data_lines, start=2)
            if raw_line.strip() != ""
        ]

        records = [record for record, _ in outcomes if record is not None]
        malformed_rows = [malformed for _, malformed in outcomes if malformed is not None]

        return SalesDataLoadResult(records=records, malformed_rows=malformed_rows)

    def _read_lines(self, path: Optional[Path]) -> List[str]:
        if path is None:
            raise SalesDataError("Sales data path must not be None")
        if not path.exists():
            raise SalesDataError(f"Sales data file not found: {path.resolve()}")
        try:
            with path.open("r", newline="", encoding="utf-8") as f:
                return [line.rstrip("\n").rstrip("\r") for line in f]
        except OSError as exc:
            raise SalesDataError(f"Unable to read sales data file: {path.resolve()}") from exc

    def _parse_line_safely(
        self, line_number: int, raw_line: str
    ) -> Tuple[Optional[SaleRecord], Optional[MalformedRow]]:
        try:
            return self._parse_line(raw_line), None
        except _RowParseError as exc:
            return None, MalformedRow(line_number=line_number, raw_line=raw_line, reason=str(exc))

    def _parse_line(self, raw_line: str) -> SaleRecord:
        fields = next(csv.reader([raw_line]))
        if len(fields) != EXPECTED_COLUMN_COUNT:
            raise _RowParseError(
                f"Expected {EXPECTED_COLUMN_COUNT} columns but found {len(fields)}"
            )

        transaction_id = self._require_non_blank(fields[0], "transactionId")
        record_date = self._parse_date(fields[1])
        region = self._require_non_blank(fields[2], "region").upper()
        salesperson = self._require_non_blank(fields[3], "salesperson")
        product_category = self._require_non_blank(fields[4], "productCategory").upper()
        quantity = self._parse_int(fields[5], "quantity")
        unit_price = self._parse_float(fields[6], "unitPrice")
        total_amount = self._parse_float(fields[7], "totalAmount")

        return SaleRecord(
            transaction_id=transaction_id,
            date=record_date,
            region=region,
            salesperson=salesperson,
            product_category=product_category,
            quantity=quantity,
            unit_price=unit_price,
            total_amount=total_amount,
        )

    @staticmethod
    def _require_non_blank(value: Optional[str], field_name: str) -> str:
        if value is None or value.strip() == "":
            raise _RowParseError(f"Field '{field_name}' is blank")
        return value.strip()

    def _parse_date(self, value: str) -> date:
        text = self._require_non_blank(value, "date")
        try:
            return datetime.strptime(text, "%Y-%m-%d").date()
        except ValueError:
            raise _RowParseError(f"Invalid date '{value}' (expected yyyy-MM-dd)") from None

    def _parse_int(self, value: str, field_name: str) -> int:
        text = self._require_non_blank(value, field_name)
        try:
            return int(text)
        except ValueError:
            raise _RowParseError(f"Invalid integer for '{field_name}': '{value}'") from None

    def _parse_float(self, value: str, field_name: str) -> float:
        text = self._require_non_blank(value, field_name)
        try:
            return float(text)
        except ValueError:
            raise _RowParseError(f"Invalid decimal for '{field_name}': '{value}'") from None
