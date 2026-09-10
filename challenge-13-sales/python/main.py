"""Demonstrates SalesDataLoader and SalesAnalyzer against the real fixture at
data/v5/challenge-4/sales.csv.

The fixture path is resolved robustly: a path given as the first CLI argument, then the
SALES_CSV_PATH environment variable, then a handful of relative candidates that work whether
this is run from the python/ project directory or from the repository root.
"""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path
from typing import List

from sales import SalesAnalyzer, SalesDataError, SalesDataLoader

DEFAULT_CANDIDATES = [
    "../../data/v5/challenge-4/sales.csv",
    "data/v5/challenge-4/sales.csv",
]


def resolve_csv_path(argv: List[str]) -> Path:
    if len(argv) > 1:
        return Path(argv[1])
    env_path = os.environ.get("SALES_CSV_PATH")
    if env_path:
        return Path(env_path)
    for candidate in DEFAULT_CANDIDATES:
        path = Path(candidate)
        if path.exists():
            return path
    # Fall back to the first candidate; SalesDataLoader will raise a clear "not found" error.
    return Path(DEFAULT_CANDIDATES[0])


def main(argv: List[str]) -> int:
    csv_path = resolve_csv_path(argv)
    print(f"Loading sales data from: {csv_path.resolve()}")
    print()

    loader = SalesDataLoader()
    try:
        result = loader.load(csv_path)
    except SalesDataError as exc:
        # Clean, actionable error -- no raw traceback.
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Loaded {result.valid_count} valid records, {result.malformed_count} malformed rows skipped.")
    if result.malformed_rows:
        print("\nMalformed rows:")
        for m in result.malformed_rows:
            print(f"  line {m.line_number}: {m.reason} -- raw: {m.raw_line}")
    print()

    analyzer = SalesAnalyzer(result.records)

    print(analyzer.generate_summary_report())

    print("-- Total Sales by Region --")
    for region, total in analyzer.get_total_sales_by_region().items():
        print(f"  {region:<10} {total:10.2f}")

    print("\n-- Average Sale by Category --")
    for category, avg in analyzer.get_average_sale_by_category().items():
        print(f"  {category:<12} {avg:10.2f}")

    print("\n-- Total Sales by Region and Category --")
    for region, by_category in analyzer.get_total_sales_by_region_and_category().items():
        print(f"  {region}:")
        for category, total in by_category.items():
            print(f"    {category:<12} {total:10.2f}")

    print("\n-- Monthly Sales Trend --")
    for month, total in analyzer.get_monthly_sales_trend().items():
        print(f"  {month:<8} {total:10.2f}")

    print("\n-- Top 5 Salespersons --")
    for sp in analyzer.get_top_salespersons(5):
        print(f"  {sp.salesperson:<18} total={sp.total_sales:10.2f} transactions={sp.transaction_count}")

    from_date, to_date = date(2024, 3, 1), date(2024, 3, 31)
    march = analyzer.get_sales_by_date_range(from_date, to_date)
    print(f"\n-- Sales Between {from_date} and {to_date} (inclusive) --")
    total_march = sum(r.total_amount for r in march)
    print(f"  {len(march)} transactions, total={total_march:.2f}")

    print("\n-- Sales in region EAST --")
    east = analyzer.get_sales_by_region("EAST")
    print(f"  {len(east)} transactions")

    print("\n-- Sales in category ELECTRONICS --")
    electronics = analyzer.get_sales_by_category("ELECTRONICS")
    print(f"  {len(electronics)} transactions")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
